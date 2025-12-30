# claude_v2/src/core/transfer.py
import os
import tempfile
import shutil
import concurrent.futures
import zipfile
from pathlib import Path
import shlex
import time

from core.file_chunker import FileChunker
from utils.adb import Adb

from utils.termux import TermuxInstaller
from core.reassembly import ReassemblyManager

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
        self.cancelled = False

    def cancel(self):
        """Cancel transfer operations."""
        self.cancelled = True
        self.logger.info("Transfert annulé par l'utilisateur")

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
                return
            
            self.logger.info(f"Temps de réassemblage des fichiers: {reassembly_time:.2f} secondes.")

            # Note: Cleanup is now handled by reassembly_manager

        total_time = time.time() - total_start_time
        self.logger.success(f"Transfert terminé avec succès en {total_time:.2f} secondes !")

    def transfer_only(self, source_dir, target_dir, device_id):
        """
        Transfer files to device without reassembly (for multi-device parallel transfer).

        Returns:
            True if transfer successful, False otherwise
        """
        try:
            self.logger.info(f"[{device_id}] Initialisation du transfert...")

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

    def process_files(self, source_dir: Path):
        # Process large files
        for file_path in self.files_to_chunk:
            manifest = FileChunker.chunk_file(
                file_path=file_path,
                source_folder=source_dir,
                output_folder=self.temp_dir,
                chunk_size_bytes=self.config.get("chunk_size", 100 * 1024 * 1024),
                progress_callback=self.logger.info,
                logger=self.logger,
                persistent_chunks=True,  # Enable persistent chunks
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
                bundle_path = self.temp_dir / bundle_name
                
                with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
                    # Use compression level 1 (fastest) - we want speed, not max compression
                    for file_path, file_size in bundle_files:
                        rel_path = file_path.relative_to(source_dir)
                        zf.write(file_path, arcname=str(rel_path))
                
                bundle_size_mb = bundle_path.stat().st_size / (1024 * 1024)
                self.logger.success(f"Bundle {bundle_name}: {bundle_size_mb:.2f} MB ({len(bundle_files)} fichiers)")
    
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

    def parallel_transfer(self, remote_temp_dir, device_id):
        """Transfer chunks individually with per-device worker pool.
        
        Features:
        - Resume support: skips chunks that already exist with correct size
        - Multiple bundle support: handles multiple ZIP bundles from bin packing
        """
        max_workers = self.config.get("parallel_processes", 4)
        resume_enabled = self.config.get("resume_transfer", True)
        
        # Create remote temp dir
        self.adb.run_command(f'shell "mkdir -p {remote_temp_dir}"', device_id)

        # Collect all files to transfer (chunks + metadata + batch files)
        files_to_transfer = []
        skipped_files = 0
        future_to_file = {}  # Map futures to file info for tracking
        
        # Add chunk files with resume support
        for manifest in self.manifests:
            # Use persistent source if available (no copy needed!), otherwise use temp folder
            if manifest.get('persistent_source'):
                chunk_folder_path = Path(manifest['persistent_source'])
            else:
                chunk_folder_path = self.temp_dir / manifest["chunk_folder"]

            remote_chunk_dir = f"{remote_temp_dir}/{manifest['chunk_folder']}".replace('\\', '/')

            # Create remote chunk directory
            self.adb.run_command(f'shell "mkdir -p {remote_chunk_dir}"', device_id)

            # Get all chunk files and metadata
            chunk_files = sorted(chunk_folder_path.glob("chunk_*.bin"))
            metadata_file = chunk_folder_path / "chunk_metadata.json"
            
            # Add each chunk file to transfer list (with resume check)
            for chunk_file in chunk_files:
                remote_path = f"{remote_chunk_dir}/{chunk_file.name}".replace('\\', '/')
                local_size = chunk_file.stat().st_size
                
                # Resume support: check if file already exists with correct size
                if resume_enabled:
                    if self._check_remote_file_exists(remote_path, local_size, device_id):
                        skipped_files += 1
                        continue  # Skip this file
                
                files_to_transfer.append((str(chunk_file), remote_path, local_size))
            
            # Add metadata file (always transfer metadata)
            if metadata_file.exists():
                remote_metadata_path = f"{remote_chunk_dir}/chunk_metadata.json".replace('\\', '/')
                files_to_transfer.append((str(metadata_file), remote_metadata_path, metadata_file.stat().st_size))
        
        if skipped_files > 0:
            self.logger.info(f"[{device_id}] Resume: {skipped_files} fichiers déjà présents, ignorés")
        
        # Find and transfer all bundle ZIP files (supports multiple bundles from bin packing)
        bundle_files = list(self.temp_dir.glob("bundle_batch*.zip"))
        bundles_transferred = 0
        
        for bundle_path in bundle_files:
            remote_bundle_path = f"{remote_temp_dir}/{bundle_path.name}".replace('\\', '/')
            bundle_size = bundle_path.stat().st_size
            
            # Resume support for bundles too
            if resume_enabled and self._check_remote_file_exists(remote_bundle_path, bundle_size, device_id):
                self.logger.info(f"[{device_id}] Resume: {bundle_path.name} déjà présent, ignoré")
                continue
            
            bundle_size_mb = bundle_size / (1024 * 1024)
            self.logger.info(f"[{device_id}] Transfert de {bundle_path.name} ({bundle_size_mb:.2f} MB)...")
            try:
                self.adb.run_command(f'push "{bundle_path}" "{remote_bundle_path}"', device_id)
                bundles_transferred += 1
                self.logger.success(f"[{device_id}] {bundle_path.name} transféré avec succès")
            except Exception as e:
                self.logger.error(f"[{device_id}] Échec du transfert de {bundle_path.name}: {e}")
        
        # Transfer all files in parallel using worker pool
        self.logger.info(f"[{device_id}] Transfert de {len(files_to_transfer)} fichiers avec {max_workers} workers...")
        
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
            for future in concurrent.futures.as_completed(futures):
                # Check for cancellation
                if self.cancelled:
                    self.logger.info(f"[{device_id}] Transfert annulé par l'utilisateur")
                    executor.shutdown(wait=False, cancel_futures=True)
                    return False

                try:
                    result = future.result()
                    file_info = future_to_file[future]
                    transfer_results['successful'].append(file_info)
                    completed += 1
                    if completed % 10 == 0:  # Log progress every 10 files
                        progress = (completed / len(files_to_transfer)) * 100
                        self.logger.info(f"[{device_id}] Progression: {completed}/{len(files_to_transfer)} ({progress:.1f}%)")
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
                    return False

        self.logger.success(f"[{device_id}] Transfert terminé: {len(files_to_transfer)} fichiers")

        # Post-transfer verification (BEFORE cleanup so we can retry if needed)
        if self.config.get("verify_transfer", True):
            if not self._verify_transfer_on_device(remote_temp_dir, device_id):
                self.logger.error(f"[{device_id}] Vérification échouée")
                return False

        # Aggressive cleanup: delete local chunk files AFTER successful verification
        # Note: For persistent chunks, we keep them for reuse across transfers
        # Only temp folder files (non-persistent) would be cleaned here
        if self.config.get("aggressive_temp_cleanup", True):
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

        return True
    
    def _check_remote_file_exists(self, remote_path, expected_size, device_id):
        """Check if a remote file exists and has the expected size.
        
        Used for resume support - skip chunks that are already transferred.
        
        Args:
            remote_path: Path on the Android device
            expected_size: Expected file size in bytes
            device_id: Device identifier
            
        Returns:
            True if file exists with matching size, False otherwise
        """
        try:
            result = self.adb.run_command(
                f'shell "stat -c%s {remote_path} 2>/dev/null"',
                device_id
            )
            if result:
                remote_size = int(''.join(result).strip())
                return remote_size == expected_size
        except (ValueError, Exception):
            pass
        return False
    
    def _retry_failed_chunks(self, failed_files, device_id, max_retries=3):
        """Retry transferring failed chunks."""
        max_retries = self.config.get("max_retries", 3)
        self.logger.info(f"[{device_id}] Nouvelle tentative pour {len(failed_files)} fichiers...")
        
        still_failed = list(failed_files)
        
        for retry in range(max_retries):
            if not still_failed:
                break
            
            self.logger.info(f"[{device_id}] Tentative {retry + 1}/{max_retries}")
            
            retry_failed = []
            for local_path, remote_path in still_failed:
                try:
                    self.adb.run_command(
                        f'push "{local_path}" "{remote_path}"',
                        device_id
                    )
                    self.logger.success(f"[{device_id}] ✅ Réussi: {Path(local_path).name}")
                except Exception as e:
                    retry_failed.append((local_path, remote_path))
                    self.logger.error(f"[{device_id}] ❌ Échec: {Path(local_path).name}")
            
            still_failed = retry_failed
        
        return len(still_failed) == 0
    
    def _verify_transfer_on_device(self, remote_temp_dir, device_id, _depth=0):
        """Verify all files (chunks and batch) were transferred correctly.

        Args:
            remote_temp_dir: Remote directory path
            device_id: Device identifier
            _depth: Internal recursion depth counter (max 1 re-verification after retry)
        """
        # Prevent infinite recursion - allow max 1 re-verification after retry
        if _depth > 1:
            self.logger.error(f"[{device_id}] Max verification depth reached, abandoning retry")
            return False

        self.logger.info(f"[{device_id}] Vérification des fichiers transférés...")

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
            
            # 1.1 Check metadata file exists
            metadata_path = f"{remote_chunk_dir}/chunk_metadata.json"
            result = self.adb.run_command(
                f'shell "[ -f {metadata_path} ] && echo exists"',
                device_id
            )
            if not result or 'exists' not in ''.join(result):
                self.logger.error(f"[{device_id}] Metadata manquant: {chunk_folder}")
                verification_failed = True
                # Add metadata to retry list
                local_metadata = local_chunk_dir / "chunk_metadata.json"
                if local_metadata.exists():
                    missing_files.append((str(local_metadata), metadata_path))
                continue
            
            # 1.2 Get list of chunks on device
            result = self.adb.run_command(
                f'shell "ls {remote_chunk_dir}/chunk_*.bin 2>/dev/null"',
                device_id
            )
            
            if result:
                device_chunks = set(Path(line.strip()).name for line in result if line.strip())
            else:
                device_chunks = set()
            
            # 1.3 Compare with expected chunks
            expected_chunks = set(chunk_info['filename'] for chunk_info in manifest['chunks'])
            missing = expected_chunks - device_chunks
            
            if missing:
                self.logger.error(
                    f"[{device_id}] {len(missing)} chunks manquants dans {chunk_folder}:"
                )
                for chunk_name in sorted(missing):
                    self.logger.error(f"[{device_id}]   - {chunk_name}")
                    # Add to retry list
                    local_chunk = local_chunk_dir / chunk_name
                    remote_chunk = f"{remote_chunk_dir}/{chunk_name}"
                    if local_chunk.exists():
                        missing_files.append((str(local_chunk), remote_chunk))
                
                verification_failed = True
                continue
            
            # 1.4 Verify chunk sizes (fast and reliable)
            if self.config.get("verify_sizes", True):
                for chunk_info in manifest['chunks']:
                    chunk_file = f"{remote_chunk_dir}/{chunk_info['filename']}"
                    result = self.adb.run_command(
                        f'shell "stat -c%s {chunk_file} 2>/dev/null"',
                        device_id
                    )
                    if result:
                        try:
                            device_size = int(''.join(result).strip())
                            expected_size = chunk_info['size']
                            
                            if device_size != expected_size:
                                self.logger.error(
                                    f"[{device_id}] Taille incorrecte {chunk_info['filename']}: "
                                    f"{device_size} vs {expected_size} bytes"
                                )
                                verification_failed = True
                                # Add to retry list
                                local_chunk = local_chunk_dir / chunk_info['filename']
                                if local_chunk.exists():
                                    missing_files.append((str(local_chunk), chunk_file))
                        except ValueError:
                            self.logger.error(f"[{device_id}] Impossible de vérifier la taille de {chunk_info['filename']}")
                            verification_failed = True

        # --- 2. Verify Bundle ZIPs ---
        # Verify all bundle ZIP files (supports multiple bundles from bin packing)
        bundle_files = list(self.temp_dir.glob("bundle_batch*.zip"))
        for bundle_path in bundle_files:
            remote_bundle_path = f"{remote_temp_dir}/{bundle_path.name}".replace('\\', '/')
            
            # Verify bundle ZIP exists and has correct size
            result = self.adb.run_command(
                f'shell "stat -c%s {remote_bundle_path} 2>/dev/null"',
                device_id
            )
            
            if not result:
                self.logger.error(f"[{device_id}] {bundle_path.name} manquant sur l'appareil")
                verification_failed = True
                missing_files.append((str(bundle_path), remote_bundle_path))
            elif self.config.get("verify_sizes", True):
                try:
                    device_size = int(''.join(result).strip())
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
                except ValueError:
                    self.logger.warning(f"[{device_id}] Impossible de vérifier la taille de {bundle_path.name}")

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