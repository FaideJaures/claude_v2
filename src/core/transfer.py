# claude_v2/src/core/transfer.py
import os
import tempfile
import shutil
import concurrent.futures
import zipfile
import json
from pathlib import Path
import shlex
import time

from core.file_chunker import FileChunker
from utils.adb import Adb

from utils.termux import TermuxInstaller
from core.reassembly import ReassemblyManager
from core.pre_apk_manager import PreApkManager
from core.parallel_workers import (
    WorkerConfig,
    ParallelChunker,
    ParallelZipper,
    ParallelBatchPusher,
    bin_pack_files,
)
from core.device_workers import DeviceWorkerPool
from dataclasses import dataclass


@dataclass
class TransferStats:
    """Statistics for a completed transfer."""
    start_time: float = 0.0
    end_time: float = 0.0
    bytes_transferred: int = 0
    files_count: int = 0
    chunks_count: int = 0
    bundles_count: int = 0
    device_id: str = ""

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time

    @property
    def speed_mbps(self) -> float:
        if self.duration_seconds > 0:
            return (self.bytes_transferred / (1024 * 1024)) / self.duration_seconds
        return 0.0

    def format_summary(self) -> str:
        duration = self.duration_seconds
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        size_mb = self.bytes_transferred / (1024 * 1024)
        return (
            f"Durée: {minutes}m {seconds}s\n"
            f"Vitesse: {self.speed_mbps:.2f} MB/s\n"
            f"Fichiers: {self.files_count}\n"
            f"Données: {size_mb:.2f} MB"
        )


def _escape_shell_path(path: str) -> str:
    """Escape a path for use in shell single-quoted strings.
    
    When using single quotes in shell, the only way to include a literal
    single quote is to end the quote, add an escaped single quote, and
    start a new quote: ' -> '\\''
    
    Example: "Nah, I'd win." -> "Nah, I'\\''d win."
    
    Args:
        path: The path string to escape
        
    Returns:
        The escaped path safe for use in shell single-quoted strings
    """
    return path.replace("'", "'\\''") if path else path

class TransferManager:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.adb = Adb(self.logger)
        self.termux_installer = TermuxInstaller(self.logger, self.adb)
        self.files_to_chunk = []
        self.files_to_batch = []
        self.manifests = []
        self.modal_callback = None  # Will be set by UI
        self.progress_callback = None  # For progress updates: callback(percent, status)
        self.is_prepared_folder_transfer = False  # Flag to prevent cleanup of prepared folder
        self.cancelled = False
        self._worker_config = None  # Cached worker configuration

    def cancel(self):
        """Cancel transfer operations."""
        self.cancelled = True
        self.adb.terminate_all()
        self.logger.info("Transfert annulé par l'utilisateur")

    def get_worker_config(self) -> WorkerConfig:
        """Get worker configuration from config dict."""
        if self._worker_config is None:
            self._worker_config = WorkerConfig(
                chunking_workers=self.config.get("chunking_workers", 4),
                zipping_workers=self.config.get("zipping_workers", 10),
                reassembly_workers=self.config.get("reassembly_workers", 4),
                unzip_workers=self.config.get("unzip_workers", 10),
                final_move_workers=self.config.get("final_move_workers", 10),
                small_file_mode=self.config.get("small_file_mode", "zip"),
            )
        return self._worker_config

    def analyze_folder(self, source_dir: str) -> dict:
        """
        Analyze a folder without modifying internal state.
        Returns statistics about what would be transferred.
        
        Args:
            source_dir: Path to the source directory
            
        Returns:
            Dictionary with folder statistics
        """
        files_to_chunk = []
        files_to_batch = []
        total_size = 0

        small_file_threshold = self.config.get("small_file_threshold", 10 * 1024 * 1024)
        chunk_size = self.config.get("chunk_size", 100 * 1024 * 1024)
        bundle_size = self.config.get("bundle_size", 50 * 1024 * 1024)

        source_path = Path(source_dir)
        for root, dirs, files in os.walk(source_path):
            # Skip chunk folders
            dirs[:] = [d for d in dirs if not d.endswith('_chunks')]
            
            for file in files:
                file_path = Path(root) / file
                try:
                    size = file_path.stat().st_size
                    total_size += size
                    if size > small_file_threshold:
                        files_to_chunk.append((file_path, size))
                    else:
                        files_to_batch.append((file_path, size))
                except OSError:
                    pass

        # Estimate chunks (based on chunk_size)
        estimated_chunks = sum(
            (size + chunk_size - 1) // chunk_size
            for _, size in files_to_chunk
        )

        # Estimate bundles (based on bundle_size)
        small_total = sum(size for _, size in files_to_batch)
        estimated_bundles = max(1, (small_total + bundle_size - 1) // bundle_size) if files_to_batch else 0

        return {
            "total_files": len(files_to_chunk) + len(files_to_batch),
            "total_size_bytes": total_size,
            "large_files_count": len(files_to_chunk),
            "small_files_count": len(files_to_batch),
            "estimated_chunks": estimated_chunks,
            "estimated_bundles": estimated_bundles,
        }


    def start_transfer(self, source_dir, target_dir, device_id):
        total_start_time = time.time()
        self.logger.info(f"Initialisation du transfert de {source_dir} vers {target_dir} sur l'appareil {device_id}")
        self.logger.info(f"Configuration: {self.config}")

        # Note: Termux check removed - now done at startup

        with tempfile.TemporaryDirectory() as temp_dir:
            self.temp_dir = Path(temp_dir)
            self.logger.info(f"Dossier temporaire créé: {self.temp_dir}")

            # 1. Scan files
            self.logger.info("Analyse des fichiers...")
            self.scan_files(source_dir)
            self.logger.info(f"{len(self.files_to_chunk)} fichiers à fragmenter.")
            self.logger.info(f"{len(self.files_to_batch)} fichiers à traiter en lots.")

            # 2. Process files (chunking and batching)
            chunking_start_time = time.time()
            self.logger.info("Préparation des fichiers...")
            self.process_files(Path(source_dir))
            chunking_time = time.time() - chunking_start_time
            self.logger.info(f"Temps de préparation des fichiers: {chunking_time:.2f} secondes.")

            # 3. Transfer files
            transfer_start_time = time.time()
            self.logger.info("Transfert des fichiers...")
            remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")
            self.parallel_transfer(remote_temp_dir, device_id)
            transfer_time = time.time() - transfer_start_time
            self.logger.info(f"Temps de transfert des fichiers: {transfer_time:.2f} secondes.")
            
            
            # 4. Reassemble files via Termux
            reassembly_start_time = time.time()
            self.logger.info("Réassemblage des fichiers sur l'appareil...")
            reassembly_manager = ReassemblyManager(
                self.config, 
                self.logger, 
                self.adb, 
                device_id,
                modal_callback=getattr(self, 'modal_callback', None)
            )
            success = reassembly_manager.reassemble_via_termux(remote_temp_dir, target_dir)
            reassembly_time = time.time() - reassembly_start_time
            
            if not success:
                self.logger.error("Le réassemblage a échoué.")
                return False
            
            self.logger.info(f"Temps de réassemblage des fichiers: {reassembly_time:.2f} secondes.")

            # Note: Cleanup is now handled by reassembly_manager

        total_time = time.time() - total_start_time
        self.logger.success(f"Transfert terminé avec succès en {total_time:.2f} secondes !")
        return True

    def start_transfer_parallel(self, source_dir, target_dir, device_id):
        """
        Start transfer with full multi-worker parallel processing.
        
        This is the new recommended transfer method that uses:
        - Pre-APK installation and confirmation
        - Parallel chunking with ProcessPoolExecutor
        - Parallel zipping (or batch push) with ProcessPoolExecutor  
        - Parallel device-side operations with multiple ADB sessions
        
        Args:
            source_dir: Source directory path
            target_dir: Target directory path on device
            device_id: Device identifier
            
        Returns:
            True if successful, False otherwise
        """
        total_start_time = time.time()
        self.logger.info(f"=== Transfert parallèle vers {device_id} ===")
        self.logger.info(f"Source: {source_dir}")
        self.logger.info(f"Destination: {target_dir}")
        
        worker_config = self.get_worker_config()
        self.logger.info(f"Workers: chunking={worker_config.chunking_workers}, "
                        f"zipping={worker_config.zipping_workers}, "
                        f"reassembly={worker_config.reassembly_workers}")
        
        # === 0. PRE-APK FLOW ===
        if self.config.get("pre_apk_enabled", True):
            self.logger.info("Phase 0: Pré-APK...")
            pre_apk_mgr = PreApkManager(
                self.adb, 
                self.logger, 
                self.config,
                modal_callback=self.modal_callback
            )
            if not pre_apk_mgr.run_pre_transfer(device_id):
                self.logger.error("Pré-APK flow annulé ou échoué")
                return False
        
        with tempfile.TemporaryDirectory() as temp_dir:
            self.temp_dir = Path(temp_dir)
            self.logger.info(f"Dossier temporaire: {self.temp_dir}")
            
            # === 1. SCAN FILES ===
            phase_start = time.time()
            self.logger.info("Phase 1: Analyse des fichiers...")
            self.scan_files(source_dir)
            self.logger.info(f"  {len(self.files_to_chunk)} grands fichiers (chunking)")
            self.logger.info(f"  {len(self.files_to_batch)} petits fichiers (bundling)")
            self.logger.info(f"  Durée: {time.time() - phase_start:.2f}s")
            
            # === 2. PARALLEL PROCESSING (CHUNKING + ZIPPING) ===
            phase_start = time.time()
            self.logger.info("Phase 2: Traitement parallèle...")
            self.process_files_parallel(Path(source_dir), device_id=device_id)
            self.logger.info(f"  Durée: {time.time() - phase_start:.2f}s")
            
            # Check cancellation
            if self.cancelled:
                self.logger.info("Transfert annulé")
                return False
            
            # === 3. TRANSFER TO DEVICE ===  
            phase_start = time.time()
            self.logger.info("Phase 3: Transfert vers l'appareil...")
            remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")
            stats = self.parallel_transfer(remote_temp_dir, device_id)
            
            if stats is None:
                self.logger.error("Transfert échoué")
                return False
            
            self.logger.info(f"  Durée: {time.time() - phase_start:.2f}s")
            
            # === 4. PARALLEL DEVICE-SIDE OPERATIONS ===
            phase_start = time.time()
            self.logger.info("Phase 4: Réassemblage parallèle sur l'appareil...")
            
            device_pool = DeviceWorkerPool(
                self.adb,
                device_id,
                self.logger,
                self.config
            )
            
            success = device_pool.run_full_reassembly_flow(
                manifests=self.manifests,
                remote_temp_dir=remote_temp_dir,
                target_dir=target_dir
            )
            
            if not success:
                self.logger.error("Réassemblage parallèle échoué")
                return False
            
            self.logger.info(f"  Durée: {time.time() - phase_start:.2f}s")
        
        total_time = time.time() - total_start_time
        self.logger.success(f"Transfert parallèle terminé en {total_time:.2f}s !")
        return True

    def start_transfer_direct(self, source_dir, target_dir, device_id):
        """
        DIRECT TRANSFER MODE - Push files directly to final destination.
        
        This mode skips the temp folder + reassembly for small files:
        - Small files (<100MB): Pushed directly to target_dir
        - Large files (>100MB): Still use temp folder + chunk reassembly
        
        Benefits:
        - No cleanup phase for small files
        - No move phase for small files
        - Simpler and faster for small file collections
        
        Limitations:
        - Large files still need chunking
        - Partial failures leave incomplete data at destination
        - No atomic commit (files appear as they transfer)
        
        Args:
            source_dir: Source directory path on PC
            target_dir: Target directory path on device (final destination)
            device_id: Device identifier
            
        Returns:
            True if successful, False otherwise
        """
        total_start_time = time.time()
        self.logger.info(f"=== TRANSFERT DIRECT vers {device_id} ===")
        self.logger.info(f"Source: {source_dir}")
        self.logger.info(f"Destination directe: {target_dir}")
        
        # Get thresholds
        direct_threshold = self.config.get("direct_push_threshold", 100 * 1024 * 1024)
        max_workers = self.config.get("parallel_processes", 4)
        resume_enabled = self.config.get("resume_transfer", True)
        
        # === 0. PRE-APK FLOW ===
        if self.config.get("pre_apk_enabled", True):
            self.logger.info("Phase 0: Pré-APK...")
            pre_apk_mgr = PreApkManager(
                self.adb, 
                self.logger, 
                self.config,
                modal_callback=self.modal_callback
            )
            if not pre_apk_mgr.run_pre_transfer(device_id):
                self.logger.error("Pré-APK flow annulé ou échoué")
                return False
        
        # === 1. SCAN AND CATEGORIZE FILES ===
        phase_start = time.time()
        self.logger.info("Phase 1: Analyse des fichiers...")
        
        source_path = Path(source_dir)
        direct_files = []  # Files to push directly: (local_path, relative_path, size)
        large_files = []   # Files that need chunking: (local_path, size)
        total_size = 0
        
        for root, dirs, files in os.walk(source_path):
            # Skip chunk folders
            dirs[:] = [d for d in dirs if not d.endswith('_chunks')]
            
            for file in files:
                file_path = Path(root) / file
                try:
                    file_size = file_path.stat().st_size
                    rel_path = file_path.relative_to(source_path)
                    total_size += file_size
                    
                    if file_size > direct_threshold:
                        large_files.append((file_path, file_size))
                    else:
                        direct_files.append((file_path, str(rel_path).replace('\\', '/'), file_size))
                except OSError as e:
                    self.logger.error(f"Erreur accès fichier {file_path}: {e}")
        
        self.logger.info(f"  {len(direct_files)} fichiers directs ({sum(f[2] for f in direct_files) / (1024*1024):.1f} MB)")
        self.logger.info(f"  {len(large_files)} grands fichiers ({sum(f[1] for f in large_files) / (1024*1024):.1f} MB)")
        self.logger.info(f"  Durée: {time.time() - phase_start:.2f}s")
        
        # === 2. CREATE TARGET DIRECTORIES ===
        phase_start = time.time()
        self.logger.info("Phase 2: Création des répertoires...")
        
        # Collect unique directories to create
        target_dirs = set()
        target_dirs.add(target_dir)
        for _, rel_path, _ in direct_files:
            parent = os.path.dirname(rel_path)
            if parent:
                target_dirs.add(f"{target_dir}/{parent}".replace('\\', '/'))
        
        # Batch create directories
        if target_dirs:
            mkdir_commands = [f"mkdir -p '{_escape_shell_path(d)}'" for d in sorted(target_dirs)]
            self.adb.run_shell_batch(mkdir_commands, device_id)
        
        self.logger.info(f"  {len(target_dirs)} répertoires créés")
        self.logger.info(f"  Durée: {time.time() - phase_start:.2f}s")
        
        # === 3. GET REMOTE FILE INFO FOR RESUME ===
        remote_file_cache = {}
        if resume_enabled and direct_files:
            phase_start = time.time()
            self.logger.info("Phase 3: Vérification fichiers existants...")
            remote_file_cache = self._get_remote_file_info_bulk(target_dir, device_id)
            self.logger.info(f"  {len(remote_file_cache)} fichiers distants trouvés")
            self.logger.info(f"  Durée: {time.time() - phase_start:.2f}s")
        
        # === 4. DIRECT PUSH SMALL FILES ===
        if direct_files:
            phase_start = time.time()
            self.logger.info(f"Phase 4: Push direct de {len(direct_files)} fichiers...")
            
            files_to_push = []
            skipped = 0
            
            for local_path, rel_path, file_size in direct_files:
                remote_path = f"{target_dir}/{rel_path}".replace('\\', '/')
                
                # Resume check
                if resume_enabled and rel_path in remote_file_cache:
                    if remote_file_cache[rel_path] == file_size:
                        skipped += 1
                        continue
                
                files_to_push.append((str(local_path), remote_path, file_size))
            
            if skipped > 0:
                self.logger.info(f"  Resume: {skipped} fichiers déjà présents")
            
            # Parallel push
            successful = 0
            failed = 0
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for local_path, remote_path, file_size in files_to_push:
                    future = executor.submit(
                        self.adb.run_command,
                        f'push "{local_path}" "{remote_path}"',
                        device_id
                    )
                    futures[future] = (local_path, remote_path)
                
                completed = 0
                total = len(files_to_push)
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        if result is not None:
                            successful += 1
                        else:
                            failed += 1
                            file_info = futures[future]
                            self.logger.error(f"  Échec: {Path(file_info[0]).name}")
                    except Exception as e:
                        failed += 1
                        self.logger.error(f"  Exception: {e}")
                    
                    completed += 1
                    if completed % 20 == 0:
                        self.logger.info(f"  Progression: {completed}/{total}")
            
            self.logger.info(f"  Réussis: {successful}, Échoués: {failed}, Ignorés: {skipped}")
            self.logger.info(f"  Durée: {time.time() - phase_start:.2f}s")
            
            if failed > 0:
                self.logger.warning(f"  {failed} fichiers n'ont pas été transférés")
        
        # === 5. HANDLE LARGE FILES (CHUNKING) ===
        if large_files:
            phase_start = time.time()
            self.logger.info(f"Phase 5: Traitement de {len(large_files)} grands fichiers...")
            
            # These need temp folder + reassembly
            remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                self.temp_dir = Path(temp_dir)
                self.files_to_chunk = [f[0] for f in large_files]
                self.files_to_batch = []  # No bundling for direct mode
                self.manifests = []
                
                # Chunk large files
                self.logger.info("  Chunking des grands fichiers...")
                worker_config = self.get_worker_config()
                
                if len(self.files_to_chunk) >= 2:
                    self.manifests = ParallelChunker.chunk_files_parallel(
                        files=self.files_to_chunk,
                        source_folder=source_path,
                        output_folder=self.temp_dir,
                        chunk_size=self.config.get("chunk_size", 100 * 1024 * 1024),
                        workers=worker_config.chunking_workers,
                        logger=self.logger,
                        persistent_chunks=False
                    )
                else:
                    for file_path in self.files_to_chunk:
                        manifest = FileChunker.chunk_file(
                            file_path=file_path,
                            source_folder=source_path,
                            output_folder=self.temp_dir,
                            chunk_size_bytes=self.config.get("chunk_size", 100 * 1024 * 1024),
                            progress_callback=self.logger.info,
                            logger=self.logger,
                            persistent_chunks=False,
                        )
                        self.manifests.append(manifest)
                
                # Transfer chunks to temp
                self.logger.info("  Transfert des chunks...")
                stats = self.parallel_transfer(remote_temp_dir, device_id)
                
                if stats is None:
                    self.logger.error("  Transfert des chunks échoué")
                    return False
                
                # Reassemble directly to target
                self.logger.info("  Réassemblage vers destination finale...")
                device_pool = DeviceWorkerPool(
                    self.adb,
                    device_id,
                    self.logger,
                    self.config
                )
                
                success = device_pool.run_full_reassembly_flow(
                    manifests=self.manifests,
                    remote_temp_dir=remote_temp_dir,
                    target_dir=target_dir
                )
                
                if not success:
                    self.logger.error("  Réassemblage échoué")
                    return False
            
            self.logger.info(f"  Durée: {time.time() - phase_start:.2f}s")
        
        total_time = time.time() - total_start_time
        self.logger.success(f"Transfert direct terminé en {total_time:.2f}s !")
        return True

    def prepare_transfer(self, source_dir, output_dir):
        """
        Prepare files for transfer (factorization): chunk and bundle to output_dir.
        Saves a transfer_state.json for later use.
        """
        try:
            self.logger.info(f"Préparation du transfert (factorisation) dans {output_dir}...")
            
            output_path = Path(output_dir)
            if not output_path.exists():
                output_path.mkdir(parents=True)
            
            # CRITICAL: Reset all lists before scanning to avoid stale data
            self.manifests = []
            self.files_to_chunk = []
            self.files_to_batch = []
            
            # 1. Scan files
            self.logger.info("Analyse des fichiers...")
            self.scan_files(source_dir)
            self.logger.info(f"{len(self.files_to_chunk)} fichiers à fragmenter.")
            self.logger.info(f"{len(self.files_to_batch)} fichiers à traiter en lots.")

            # 2. Process files using PARALLEL processing
            chunking_start_time = time.time()
            self.logger.info("Traitement parallèle des fichiers...")
            self.process_files_parallel(Path(source_dir), output_folder=output_path, use_persistent_chunks=False)
            chunking_time = time.time() - chunking_start_time
            self.logger.info(f"Temps de traitement parallèle: {chunking_time:.2f} secondes.")
            
            # 3. Save transfer state - normalize all paths to use forward slashes
            normalized_manifests = []
            for manifest in self.manifests:
                m = manifest.copy()
                if 'chunk_folder' in m:
                    m['chunk_folder'] = m['chunk_folder'].replace('\\', '/')
                if 'persistent_source' in m and m['persistent_source']:
                    m['persistent_source'] = m['persistent_source'].replace('\\', '/')
                normalized_manifests.append(m)
            
            state = {
                "manifests": normalized_manifests,
                "timestamp": time.time(),
                "source_dir": source_dir
            }
            with open(output_path / "transfer_state.json", "w") as f:
                json.dump(state, f, indent=2)
                
            self.logger.success(f"Préparation terminée dans {output_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la préparation: {e}")
            return False

    def transfer_from_prepared_folder(self, prepared_dir, target_dir, device_id):
        """
        Transfer pre-processed files from prepared_dir to device without reanalysis.
        """
        try:
            self.logger.info(f"[{device_id}] Démarrage du transfert depuis dossier préparé: {prepared_dir}")
            
            # === 0. PRE-APK FLOW (also for prepared folder transfers!) ===
            if self.config.get("pre_apk_enabled", True):
                self.logger.info(f"[{device_id}] Phase 0: Pré-APK...")
                pre_apk_mgr = PreApkManager(
                    self.adb, 
                    self.logger, 
                    self.config,
                    modal_callback=self.modal_callback
                )
                if not pre_apk_mgr.run_pre_transfer(device_id):
                    self.logger.error(f"[{device_id}] Pré-APK flow annulé ou échoué")
                    return False
            
            prepared_path = Path(prepared_dir)
            
            # Load state
            state_file = prepared_path / "transfer_state.json"
            if not state_file.exists():
                self.logger.error(f"[{device_id}] Fichier d'état introuvable dans {prepared_dir}")
                # Fallback: try to reconstruct state? For now, fail.
                return False
                
            with open(state_file, "r") as f:
                state = json.load(f)
            
            # Normalize paths in loaded manifests (ensure forward slashes for Android)
            loaded_manifests = state.get("manifests", [])
            self.manifests = []
            for manifest in loaded_manifests:
                m = manifest.copy()
                if 'chunk_folder' in m:
                    m['chunk_folder'] = m['chunk_folder'].replace('\\', '/')
                if 'persistent_source' in m and m['persistent_source']:
                    m['persistent_source'] = m['persistent_source'].replace('\\', '/')
                self.manifests.append(m)
            
            # Clear file lists - we're loading from prepared folder, not rescanning
            self.files_to_chunk = []
            self.files_to_batch = []
            
            self.logger.info(f"[{device_id}] {len(self.manifests)} manifestes chargés.")
            
            # Initialize temp_dir to point to prepared_dir for parallel_transfer to work
            # Note: parallel_transfer expects self.temp_dir to contain the bundles and chunks
            original_temp_dir = getattr(self, 'temp_dir', None)
            self.temp_dir = prepared_path
            self.is_prepared_folder_transfer = True  # Prevent cleanup from deleting reusable chunks
            
            try:
                # 3. Transfer files
                self.logger.info(f"[{device_id}] Transfert des fichiers...")
                remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")
                success = self.parallel_transfer(remote_temp_dir, device_id)
                if not success:
                    return False
                    
                self.logger.success(f"[{device_id}] Transfert terminé.")
                
                # 4. Reassemble using parallel DeviceWorkerPool
                self.logger.info(f"[{device_id}] Phase 4: Réassemblage parallèle sur l'appareil...")
                device_pool = DeviceWorkerPool(
                    self.adb,
                    device_id,
                    self.logger,
                    self.config
                )
                
                return device_pool.run_full_reassembly_flow(
                    manifests=self.manifests,
                    remote_temp_dir=remote_temp_dir,
                    target_dir=target_dir
                )

            finally:
                # Restore temp_dir just in case (though object might be discarded)
                if original_temp_dir:
                    self.temp_dir = original_temp_dir
                    
        except Exception as e:
            self.logger.error(f"[{device_id}] Erreur lors du transfert factorisé: {e}")
            import traceback
            traceback.print_exc()
            return False

    def transfer_only(self, source_dir, target_dir, device_id):
        """
        Transfer files to device without reassembly (for multi-device parallel transfer).
        
        Returns:
            True if transfer successful, False otherwise
        """
        try:
            self.logger.info(f"[{device_id}] Initialisation du transfert direct...")

            # Note: Termux check removed - now done at startup

            with tempfile.TemporaryDirectory() as temp_dir:
                self.temp_dir = Path(temp_dir)

                # 1. Scan files
                self.logger.info(f"[{device_id}] Analyse des fichiers...")
                self.scan_files(source_dir)
                self.logger.info(f"[{device_id}] {len(self.files_to_chunk)} fichiers à fragmenter, {len(self.files_to_batch)} en lots.")

                # 2. Process files (chunking and batching)
                self.logger.info(f"[{device_id}] Préparation des fichiers...")
                self.process_files(Path(source_dir))

                # 3. Transfer files
                self.logger.info(f"[{device_id}] Transfert des fichiers...")
                remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")
                self.parallel_transfer(remote_temp_dir, device_id)

                self.logger.success(f"[{device_id}] Transfert terminé.")
                return True

        except Exception as e:
            self.logger.error(f"[{device_id}] Erreur lors du transfert: {e}")
            return False

    def scan_files(self, source_dir):
        """Scan directory for files, split into large (chunk) and small (batch) lists.
        
        If SJF scheduling is enabled, files are sorted by size (smallest first)
        to improve perceived performance by completing more files sooner.
        """
        small_file_threshold = self.config.get("small_file_threshold", 10 * 1024 * 1024)
        
        # Temporary list to store files with their sizes for sorting
        files_with_sizes = []
        
        for root, dirs, files in os.walk(source_dir):
            # Skip chunk folders - don't descend into them
            dirs[:] = [d for d in dirs if not d.endswith('_chunks')]
            
            for file in files:
                file_path = Path(root) / file
                try:
                    file_size = file_path.stat().st_size
                    files_with_sizes.append((file_path, file_size))
                except OSError as e:
                    self.logger.error(f"Erreur lors de l'accès au fichier {file_path}: {e}")
        
        # Apply SJF (Shortest Job First) scheduling if enabled
        if self.config.get("sjf_scheduling", True):
            files_with_sizes.sort(key=lambda x: x[1])  # Sort by size, smallest first
            self.logger.info("SJF scheduling activé: fichiers triés par taille")
        
        # Split into large and small files
        for file_path, file_size in files_with_sizes:
            if file_size > small_file_threshold:
                self.files_to_chunk.append(file_path)
            else:
                self.files_to_batch.append((file_path, file_size))  # Store size for bin packing

    def process_files(self, source_dir: Path, output_folder: Path = None, use_persistent_chunks: bool = True):
        """
        Process files: chunk large files and batch small files into bundles.
        
        Args:
            source_dir: Source directory path.
            output_folder: Directory where chunks and bundles will be created.
                           Defaults to self.temp_dir if None.
            use_persistent_chunks: If True, chunks are created next to source (caching).
                                   If False, chunks are created in output_folder.
        """
        if output_folder is None:
            output_folder = self.temp_dir

        self.logger.info(f"Traitement des fichiers dans {output_folder} (persist: {use_persistent_chunks})...")

        # Process large files
        for file_path in self.files_to_chunk:
            manifest = FileChunker.chunk_file(
                file_path=file_path,
                source_folder=source_dir,
                output_folder=output_folder,
                chunk_size_bytes=self.config.get("chunk_size", 100 * 1024 * 1024),
                progress_callback=self.logger.info,
                logger=self.logger,
                persistent_chunks=use_persistent_chunks,  # Explicitly controlled
            )
            self.manifests.append(manifest)

            # Note: No copy needed! Transfer will read directly from persistent_source

        # Process small files - Create ZIP bundles using bin packing for efficient transfer
        # The unified.sh script on device already handles bundle_*.zip extraction
        if self.files_to_batch:
            target_bundle_size = self.config.get("bundle_size", 50 * 1024 * 1024)  # 50MB default
            
            # Use First Fit Decreasing (FFD) bin packing algorithm
            bundles = self._bin_pack_files(self.files_to_batch, target_bundle_size)
            
            self.logger.info(f"Création de {len(bundles)} bundle(s) ZIP pour {len(self.files_to_batch)} petits fichiers...")
            
            for i, bundle_files in enumerate(bundles):
                bundle_name = f"bundle_batch_{i:03d}.zip" if len(bundles) > 1 else "bundle_batch.zip"
                bundle_path = output_folder / bundle_name
                
                with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
                    # Use compression level 1 (fastest) - we want speed, not max compression
                    for file_path, file_size in bundle_files:
                        rel_path = file_path.relative_to(source_dir)
                        zf.write(file_path, arcname=str(rel_path))
                
                bundle_size_mb = bundle_path.stat().st_size / (1024 * 1024)
                self.logger.success(f"Bundle {bundle_name}: {bundle_size_mb:.2f} MB ({len(bundle_files)} fichiers)")

    def process_files_parallel(
        self,
        source_dir: Path,
        output_folder: Path = None,
        use_persistent_chunks: bool = True,
        device_id: str = None
    ):
        """
        Process files with parallel workers for chunking and zipping.
        
        Uses ProcessPoolExecutor for CPU-bound chunking and zipping operations.
        Falls back to sequential processing for small file counts.
        
        Args:
            source_dir: Source directory path.
            output_folder: Directory where chunks and bundles will be created.
            use_persistent_chunks: If True, chunks are created next to source.
            device_id: Optional device ID for batch push mode.
        """
        if output_folder is None:
            output_folder = self.temp_dir
        
        worker_config = self.get_worker_config()
        
        self.logger.info(f"Traitement parallèle: {len(self.files_to_chunk)} grands, "
                        f"{len(self.files_to_batch)} petits fichiers...")
        
        # === PARALLEL CHUNKING ===
        if self.files_to_chunk:
            # Only use parallel for 2+ files
            if len(self.files_to_chunk) >= 2:
                self.logger.info(f"Chunking parallèle avec {worker_config.chunking_workers} workers...")
                self.manifests = ParallelChunker.chunk_files_parallel(
                    files=self.files_to_chunk,
                    source_folder=source_dir,
                    output_folder=output_folder,
                    chunk_size=self.config.get("chunk_size", 100 * 1024 * 1024),
                    workers=worker_config.chunking_workers,
                    logger=self.logger,
                    persistent_chunks=use_persistent_chunks
                )
            else:
                # Sequential for single file
                for file_path in self.files_to_chunk:
                    manifest = FileChunker.chunk_file(
                        file_path=file_path,
                        source_folder=source_dir,
                        output_folder=output_folder,
                        chunk_size_bytes=self.config.get("chunk_size", 100 * 1024 * 1024),
                        progress_callback=self.logger.info,
                        logger=self.logger,
                        persistent_chunks=use_persistent_chunks,
                    )
                    self.manifests.append(manifest)
        
        # === SMALL FILES: ZIP or BATCH PUSH ===
        if self.files_to_batch:
            target_bundle_size = self.config.get("bundle_size", 50 * 1024 * 1024)
            bundles = bin_pack_files(self.files_to_batch, target_bundle_size)
            
            if worker_config.small_file_mode == "batch_push" and device_id:
                # Push files directly without zipping
                self.logger.info(f"Push direct des {len(self.files_to_batch)} petits fichiers...")
                remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")
                
                success, ok, fail = ParallelBatchPusher.push_files_parallel(
                    files_with_sizes=self.files_to_batch,
                    source_dir=source_dir,
                    remote_dir=remote_temp_dir,
                    device_id=device_id,
                    adb=self.adb,
                    workers=worker_config.zipping_workers,
                    logger=self.logger
                )
                
                if not success:
                    self.logger.warning(f"Certains fichiers n'ont pas été transférés: {fail} échecs")
            else:
                # Create ZIP bundles
                if len(bundles) >= 2:
                    # Parallel zipping for multiple bundles
                    self.logger.info(f"Création parallèle de {len(bundles)} bundle(s) "
                                    f"avec {worker_config.zipping_workers} workers...")
                    ParallelZipper.create_bundles_parallel(
                        bundles=bundles,
                        source_dir=source_dir,
                        output_folder=output_folder,
                        workers=worker_config.zipping_workers,
                        logger=self.logger
                    )
                else:
                    # Sequential for single bundle
                    self.logger.info(f"Création de {len(bundles)} bundle(s) ZIP...")
                    for i, bundle_files in enumerate(bundles):
                        bundle_name = f"bundle_batch_{i:03d}.zip" if len(bundles) > 1 else "bundle_batch.zip"
                        bundle_path = output_folder / bundle_name
                        
                        with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
                            for file_path, file_size in bundle_files:
                                rel_path = file_path.relative_to(source_dir)
                                zf.write(file_path, arcname=str(rel_path))
                        
                        bundle_size_mb = bundle_path.stat().st_size / (1024 * 1024)
                        self.logger.success(f"Bundle {bundle_name}: {bundle_size_mb:.2f} MB")
        
        self.logger.success("Traitement des fichiers terminé")
    
    def _bin_pack_files(self, files_with_sizes, target_size):
        """Pack files into bundles using First Fit Decreasing algorithm.
        
        Args:
            files_with_sizes: List of (file_path, file_size) tuples
            target_size: Target size per bundle in bytes
            
        Returns:
            List of bundles, where each bundle is a list of (file_path, file_size) tuples
        """
        # Sort by size descending (FFD algorithm)
        sorted_files = sorted(files_with_sizes, key=lambda x: x[1], reverse=True)
        
        bundles = []
        bundle_sizes = []
        
        for file_path, file_size in sorted_files:
            # Find first bundle that can fit this file
            placed = False
            for i, current_size in enumerate(bundle_sizes):
                if current_size + file_size <= target_size:
                    bundles[i].append((file_path, file_size))
                    bundle_sizes[i] += file_size
                    placed = True
                    break
            
            # If no bundle can fit, create a new one
            if not placed:
                bundles.append([(file_path, file_size)])
                bundle_sizes.append(file_size)
        
        return bundles

    def _get_remote_file_info_bulk(self, remote_dir: str, device_id: str) -> dict[str, int]:
        """Get sizes of all files in a remote directory in one call.
        
        Returns:
            Dictionary mapping relative filename (from remote_dir) to size in bytes.
        """
        file_info = {}
        # Use find to get all files and their sizes recursively
        # format: path:size
        cmd = f'shell "find \'{_escape_shell_path(remote_dir)}\' -type f -exec stat -c \'%n:%s\' {{}} + 2>/dev/null"'
        result = self.adb.run_command(cmd, device_id)
        
        if result:
            for line in result:
                try:
                    if ':' in line:
                        # Find the last colon to handle filenames containing colons
                        path, size_str = line.rsplit(':', 1)
                        # Get path relative to remote_dir
                        try:
                            rel_path = os.path.relpath(path, remote_dir).replace('\\', '/')
                            file_info[rel_path] = int(size_str)
                        except Exception:
                            continue
                except (ValueError, IndexError):
                    continue
        return file_info

    def parallel_transfer(self, remote_temp_dir, device_id):
        """Transfer chunks individually with per-device worker pool.
        
        Features:
        - Resume support: skips chunks that already exist with correct size
        - Multiple bundle support: handles multiple ZIP bundles from bin packing
        
        Returns:
            TransferStats on success, None on failure
        """
        phase_start = time.time()
        
        # Initialize transfer stats
        stats = TransferStats(
            start_time=time.time(),
            device_id=device_id
        )
        
        max_workers = self.config.get("parallel_processes", 4)
        resume_enabled = self.config.get("resume_transfer", True)
        skip_resume_check = self.config.get("skip_resume_check", False)  # Fast mode: skip remote scan
        
        self.logger.info(f"[{device_id}] 📊 parallel_transfer démarré (workers={max_workers}, resume={resume_enabled})")
        
        # Bulk fetch remote file info for resume support
        # Skip if skip_resume_check is enabled (for faster fresh transfers)
        remote_file_cache = {}
        if resume_enabled and not skip_resume_check:
            resume_start = time.time()
            self.logger.info(f"[{device_id}] Récupération de l'état du dossier distant...")
            remote_file_cache = self._get_remote_file_info_bulk(remote_temp_dir, device_id)
            self.logger.info(f"[{device_id}] ⏱️ Resume check: {time.time() - resume_start:.2f}s ({len(remote_file_cache)} fichiers distants)")
        elif skip_resume_check:
            self.logger.info(f"[{device_id}] Mode rapide: vérification resume ignorée")

        # Collect all files to transfer (chunks + metadata + batch files)
        files_to_transfer = []
        skipped_files = 0
        future_to_file = {}  # Map futures to file info for tracking
        
        # Collect all remote directories to create (batched mkdir)
        remote_dirs_to_create = set()
        remote_dirs_to_create.add(remote_temp_dir)
        
        # First pass: collect chunk info and directories
        for manifest in self.manifests:
            # Use persistent source if available (no copy needed!), otherwise use temp folder
            if manifest.get('persistent_source'):
                chunk_folder_path = Path(manifest['persistent_source'])
            else:
                chunk_folder_path = self.temp_dir / manifest["chunk_folder"]

            remote_chunk_dir_rel = manifest['chunk_folder']
            remote_chunk_dir = f"{remote_temp_dir}/{remote_chunk_dir_rel}".replace('\\', '/')
            
            # Collect directory for batched creation
            remote_dirs_to_create.add(remote_chunk_dir)

            # Get all chunk files and metadata
            chunk_files = sorted(chunk_folder_path.glob("chunk_*.bin"))
            metadata_file = chunk_folder_path / "chunk_metadata.json"
            
            # Add each chunk file to transfer list (with resume check using cache)
            for chunk_file in chunk_files:
                rel_chunk_path = f"{remote_chunk_dir_rel}/{chunk_file.name}".replace('\\', '/')
                remote_path = f"{remote_temp_dir}/{rel_chunk_path}".replace('\\', '/')
                local_size = chunk_file.stat().st_size
                
                # Resume support: check cache instead of per-file ADB call
                if resume_enabled and rel_chunk_path in remote_file_cache:
                    if remote_file_cache[rel_chunk_path] == local_size:
                        skipped_files += 1
                        continue  # Skip this file
                
                files_to_transfer.append((str(chunk_file), remote_path, local_size))
            
            # Add metadata file (always transfer metadata)
            if metadata_file.exists():
                remote_metadata_path = f"{remote_chunk_dir}/chunk_metadata.json".replace('\\', '/')
                files_to_transfer.append((str(metadata_file), remote_metadata_path, metadata_file.stat().st_size))
        
        # Batch create all remote directories in a single ADB call
        if remote_dirs_to_create:
            mkdir_start = time.time()
            mkdir_commands = [f"mkdir -p '{_escape_shell_path(d)}'" for d in sorted(remote_dirs_to_create)]
            self.logger.info(f"[{device_id}] Création de {len(mkdir_commands)} répertoires distants (batch)...")
            self.adb.run_shell_batch(mkdir_commands, device_id)
            self.logger.info(f"[{device_id}] ⏱️ Mkdir batch: {time.time() - mkdir_start:.2f}s")
        
        if skipped_files > 0:
            self.logger.info(f"[{device_id}] Resume: {skipped_files} fichiers déjà présents, ignorés")
        
        # Find and ADD bundle ZIP files to parallel transfer queue (instead of sequential transfer)
        bundle_files = list(self.temp_dir.glob("bundle_batch*.zip"))
        bundles_to_transfer = 0
        
        for bundle_path in bundle_files:
            remote_bundle_path = f"{remote_temp_dir}/{bundle_path.name}".replace('\\', '/')
            bundle_size = bundle_path.stat().st_size
            
            # Resume support for bundles using cache
            if resume_enabled and bundle_path.name in remote_file_cache:
                if remote_file_cache[bundle_path.name] == bundle_size:
                    self.logger.info(f"[{device_id}] Resume: {bundle_path.name} déjà présent, ignoré")
                    continue
            
            # Add bundle to parallel transfer queue (not sequential!)
            files_to_transfer.append((str(bundle_path), remote_bundle_path, bundle_size))
            bundles_to_transfer += 1
            bundle_size_mb = bundle_size / (1024 * 1024)
            self.logger.info(f"[{device_id}] Bundle ajouté à la file: {bundle_path.name} ({bundle_size_mb:.2f} MB)")
        
        if bundles_to_transfer > 0:
            self.logger.info(f"[{device_id}] {bundles_to_transfer} bundle(s) ajouté(s) au transfert parallèle")

        # Calculate total bytes to transfer
        total_bytes = sum(size for _, _, size in files_to_transfer)
        total_mb = total_bytes / (1024 * 1024)
        
        # Transfer all files in parallel using worker pool
        self.logger.info(f"[{device_id}] 🚚 Démarrage transfert: {len(files_to_transfer)} fichiers ({total_mb:.1f} MB) avec {max_workers} workers...")
        transfer_loop_start = time.time()
        
        # Track transfer results
        transfer_results = {
            'successful': [],
            'failed': []
        }
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            for local_path, remote_path, file_size in files_to_transfer:
                future = executor.submit(
                    self.adb.run_command,
                    f'push "{local_path}" "{remote_path}"',
                    device_id
                )
                futures.append(future)
                future_to_file[future] = (local_path, remote_path)
            
            # Wait for all transfers to complete
            completed = 0
            total_files = len(files_to_transfer)
            for future in concurrent.futures.as_completed(futures):
                # Check for cancellation
                if self.cancelled:
                    self.logger.info(f"[{device_id}] Transfert annulé par l'utilisateur")
                    executor.shutdown(wait=False, cancel_futures=True)
                    return None

                try:
                    result = future.result()
                    file_info = future_to_file[future]
                    transfer_results['successful'].append(file_info)
                    completed += 1
                    
                    # Calculate progress (files transfer = 20-80% of total progress)
                    progress = 20 + int((completed / total_files) * 60)
                    
                    # Call progress callback if set
                    if self.progress_callback:
                        self.progress_callback(progress, f"Transfert {completed}/{total_files}")
                    
                    # Log progress every 10 files
                    if completed % 10 == 0:
                        self.logger.info(f"[{device_id}] Progression: {completed}/{total_files} ({progress}%)")
                except Exception as e:
                    file_info = future_to_file[future]
                    transfer_results['failed'].append(file_info)
                    self.logger.error(f"[{device_id}] Échec transfert: {Path(file_info[0]).name} - {e}")
        
        # Check for failed transfers
        if transfer_results['failed']:
            self.logger.warning(f"[{device_id}] {len(transfer_results['failed'])} fichiers échoués")

            # Retry failed chunks if enabled
            if self.config.get("retry_failed_chunks", True):
                if self._retry_failed_chunks(transfer_results['failed'], device_id):
                    self.logger.success(f"[{device_id}] Tous les fichiers échoués ont été retransférés")
                else:
                    self.logger.error(f"[{device_id}] Certains fichiers n'ont pas pu être transférés")
                    return None

        self.logger.success(f"[{device_id}] Transfert terminé: {len(files_to_transfer)} fichiers")

        # Post-transfer verification (BEFORE cleanup so we can retry if needed)
        # Skip if skip_early_verification is enabled (user trusts ADB push)
        skip_early = self.config.get("skip_early_verification", False)
        verify_transfer = self.config.get("verify_transfer", True) and not skip_early
        
        if verify_transfer:
            if not self._verify_transfer_on_device(remote_temp_dir, device_id):
                self.logger.error(f"[{device_id}] Vérification échouée")
                return None
        elif skip_early:
            self.logger.info(f"[{device_id}] Vérification précoce ignorée (mode rapide)")

        # Aggressive cleanup: delete local chunk files AFTER successful verification
        # Note: Skip cleanup entirely for prepared folder transfers (chunks should be reusable)
        if self.is_prepared_folder_transfer:
            self.logger.info(f"[{device_id}] Transfert depuis dossier préparé - chunks conservés pour réutilisation")
        elif self.config.get("aggressive_temp_cleanup", True):
            self.logger.info(f"[{device_id}] Nettoyage des fichiers temporaires locaux...")
            cleaned_files = 0
            for manifest in self.manifests:
                # Only clean temp folder (skip persistent chunks - they're reusable)
                if not manifest.get('persistent_source'):
                    chunk_folder_path = self.temp_dir / manifest["chunk_folder"]
                    if chunk_folder_path.exists():
                        # Delete only .bin files, keep metadata for verification
                        chunk_files = list(chunk_folder_path.glob("chunk_*.bin"))
                        for chunk_file in chunk_files:
                            try:
                                chunk_file.unlink()
                                cleaned_files += 1
                            except Exception as e:
                                self.logger.warning(f"[{device_id}] Impossible de supprimer {chunk_file.name}: {e}")

            if cleaned_files > 0:
                self.logger.info(f"[{device_id}] Nettoyage terminé: {cleaned_files} fichiers supprimés")
            else:
                self.logger.info(f"[{device_id}] Aucun fichier temporaire à nettoyer (utilisation de chunks persistants)")

        # Populate final stats
        stats.end_time = time.time()
        stats.bytes_transferred = sum(size for _, _, size in files_to_transfer)
        stats.files_count = len(files_to_transfer) + len(bundle_files)
        stats.chunks_count = sum(1 for f, _, _ in files_to_transfer if 'chunk_' in str(f))
        stats.bundles_count = len(bundle_files)
        
        # Store stats for later retrieval
        self._last_transfer_stats = stats
        
        return stats

    def _retry_failed_chunks(self, failed_files: list, device_id: str, max_retries: int = 3) -> bool:
        """Retry transferring failed files.
        
        Args:
            failed_files: List of (local_path, remote_path) or (local_path, remote_path, size) tuples
            device_id: Device identifier
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if all files were successfully transferred, False otherwise
        """
        if not failed_files:
            return True
            
        self.logger.info(f"[{device_id}] Tentative de retransfert de {len(failed_files)} fichiers...")
        
        for attempt in range(1, max_retries + 1):
            still_failed = []
            
            for file_info in failed_files:
                # Handle both (local, remote) and (local, remote, size) tuples
                local_path = file_info[0]
                remote_path = file_info[1]
                
                local_file = Path(local_path)
                if not local_file.exists():
                    self.logger.error(f"[{device_id}] Fichier source introuvable: {local_path}")
                    still_failed.append(file_info)
                    continue
                
                # Try to push the file again
                self.logger.info(f"[{device_id}] Tentative {attempt}/{max_retries}: {local_file.name}")
                
                # Make sure remote directory exists
                remote_dir = str(Path(remote_path).parent).replace('\\', '/')
                self.adb.run_command(f'shell "mkdir -p \'{_escape_shell_path(remote_dir)}\'"', device_id)
                
                # Push the file
                result = self.adb.run_command(f'push "{local_path}" "{remote_path}"', device_id)
                
                if result is None:
                    self.logger.error(f"[{device_id}] Échec du transfert: {local_file.name}")
                    still_failed.append(file_info)
                else:
                    self.logger.success(f"[{device_id}] Retransfert réussi: {local_file.name}")
            
            if not still_failed:
                self.logger.success(f"[{device_id}] Tous les fichiers ont été retransférés")
                return True
            
            failed_files = still_failed
            
            if attempt < max_retries:
                self.logger.warning(f"[{device_id}] {len(still_failed)} fichiers encore en échec, nouvelle tentative...")
        
        self.logger.error(f"[{device_id}] {len(failed_files)} fichiers n'ont pas pu être transférés après {max_retries} tentatives")
        return False

    def _verify_transfer_on_device(self, remote_temp_dir, device_id, _depth=0):
        """Verify all files (chunks and batch) were transferred correctly.

        Args:
            remote_temp_dir: Remote directory path
            device_id: Device identifier
            _depth: Internal recursion depth counter (max 1 re-verification after retry)
        """
        # Prevent infinite recursion - allow max 100 re-verification after retry
        if _depth > 100:
            self.logger.error(f"[{device_id}] Max verification depth reached, abandoning retry")
            return False

        self.logger.info(f"[{device_id}] Vérification des fichiers transférés...")

        # Bulk fetch remote file info for verification
        remote_file_cache = self._get_remote_file_info_bulk(remote_temp_dir, device_id)

        verification_failed = False
        missing_files = []  # Track missing files for retry
        
        # --- 1. Verify Chunks ---
        for manifest in self.manifests:
            chunk_folder = manifest['chunk_folder']
            remote_chunk_dir = f"{remote_temp_dir}/{chunk_folder}".replace('\\', '/')

            # Use persistent source if available (where chunks actually are), otherwise temp folder
            if manifest.get('persistent_source'):
                local_chunk_dir = Path(manifest['persistent_source'])
            else:
                local_chunk_dir = self.temp_dir / manifest['chunk_folder']
            
            # 1.1 Check metadata file exists in cache
            rel_metadata_path = f"{chunk_folder}/chunk_metadata.json".replace('\\', '/')
            metadata_path = f"{remote_temp_dir}/{rel_metadata_path}"
            
            if rel_metadata_path not in remote_file_cache:
                self.logger.error(f"[{device_id}] Metadata manquant: {chunk_folder}")
                verification_failed = True
                # Add metadata to retry list
                local_metadata = local_chunk_dir / "chunk_metadata.json"
                if local_metadata.exists():
                    missing_files.append((str(local_metadata), metadata_path))
                continue
            
            # 1.2 Compare chunks in cache with expected chunks
            for chunk_info in manifest['chunks']:
                rel_chunk_path = f"{chunk_folder}/{chunk_info['filename']}".replace('\\', '/')
                remote_chunk = f"{remote_temp_dir}/{rel_chunk_path}"
                expected_size = chunk_info['size']
                
                if rel_chunk_path not in remote_file_cache:
                    self.logger.error(f"[{device_id}] Chunk manquant: {rel_chunk_path}")
                    verification_failed = True
                    local_chunk = local_chunk_dir / chunk_info['filename']
                    if local_chunk.exists():
                        missing_files.append((str(local_chunk), remote_chunk))
                elif self.config.get("verify_sizes", True):
                    device_size = remote_file_cache[rel_chunk_path]
                    if device_size != expected_size:
                        self.logger.error(
                            f"[{device_id}] Taille incorrecte {chunk_info['filename']}: "
                            f"{device_size} vs {expected_size} bytes"
                        )
                        verification_failed = True
                        local_chunk = local_chunk_dir / chunk_info['filename']
                        if local_chunk.exists():
                            missing_files.append((str(local_chunk), remote_chunk))

        # --- 2. Verify Bundle ZIPs ---
        # Verify all bundle ZIP files (supports multiple bundles from bin packing)
        bundle_files = list(self.temp_dir.glob("bundle_batch*.zip"))
        for bundle_path in bundle_files:
            remote_bundle_path = f"{remote_temp_dir}/{bundle_path.name}".replace('\\', '/')
            
            if bundle_path.name not in remote_file_cache:
                self.logger.error(f"[{device_id}] {bundle_path.name} manquant sur l'appareil")
                verification_failed = True
                missing_files.append((str(bundle_path), remote_bundle_path))
            elif self.config.get("verify_sizes", True):
                device_size = remote_file_cache[bundle_path.name]
                local_size = bundle_path.stat().st_size
                
                if device_size != local_size:
                    self.logger.error(
                        f"[{device_id}] Taille incorrecte {bundle_path.name}: "
                        f"{device_size} vs {local_size} bytes"
                    )
                    verification_failed = True
                    missing_files.append((str(bundle_path), remote_bundle_path))
                else:
                    self.logger.success(f"[{device_id}] {bundle_path.name} vérifié ({local_size / (1024*1024):.2f} MB)")

        # If verification failed, try to retry missing files
        if verification_failed and missing_files:
            self.logger.warning(f"[{device_id}] Tentative de retransfert de {len(missing_files)} fichiers manquants...")
            if self._retry_failed_chunks(missing_files, device_id):
                self.logger.success(f"[{device_id}] ✅ Tous les fichiers manquants ont été retransférés")
                # Re-verify after retry (increment depth to prevent infinite recursion)
                return self._verify_transfer_on_device(remote_temp_dir, device_id, _depth + 1)
            else:
                self.logger.error(f"[{device_id}] ❌ Échec du retransfert de certains fichiers")
                return False
        
        if verification_failed:
            self.logger.error(f"[{device_id}] ❌ Vérification échouée")
            return False
        
        self.logger.success(f"[{device_id}] ✅ Tous les fichiers vérifiés")
        return True