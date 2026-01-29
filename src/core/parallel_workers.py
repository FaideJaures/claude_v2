# claude_v2/src/core/parallel_workers.py
"""
Parallel Workers - Multi-process/thread workers for transfer operations.

PC-side workers:
- ParallelChunker: Chunk large files in parallel using ProcessPoolExecutor
- ParallelZipper: Create ZIP bundles in parallel using ProcessPoolExecutor
- ParallelBatchPusher: Push small files directly without zipping

This module provides the infrastructure for parallel file processing
before transfer to devices.
"""

import zipfile
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# Import FileChunker for individual file chunking
from core.file_chunker import FileChunker


@dataclass
class WorkerConfig:
    """Configuration for worker counts across all phases."""
    
    # PC-side workers
    chunking_workers: int = 4
    zipping_workers: int = 10
    
    # Device-side workers
    reassembly_workers: int = 4
    unzip_workers: int = 10
    final_move_workers: int = 10
    
    # Small file mode: "zip" or "batch_push"
    small_file_mode: str = "zip"


class ListLogger:
    """Simple logger that collects messages in a list for return from workers."""
    def __init__(self):
        self.logs = []

    def info(self, message):
        self.logs.append(("info", message))

    def error(self, message):
        self.logs.append(("error", message))

    def success(self, message):
        self.logs.append(("success", message))

    def warning(self, message):
        self.logs.append(("warning", message))


def _chunk_single_file(args: tuple) -> tuple:
    """
    Wrapper function for ProcessPoolExecutor chunking.
    
    Must be a top-level function (not a method) for pickle compatibility.
    
    Args:
        args: Tuple of (file_path, source_folder, output_folder, chunk_size, persistent_chunks)
        
    Returns:
        Tuple of (Chunk manifest dictionary, List of log messages)
    """
    file_path, source_folder, output_folder, chunk_size, persistent_chunks = args
    logger = ListLogger()
    
    try:
        manifest = FileChunker.chunk_file(
            file_path=Path(file_path),
            source_folder=Path(source_folder),
            output_folder=Path(output_folder),
            chunk_size_bytes=chunk_size,
            progress_callback=None,  # No callback in subprocess
            logger=logger,  # Pass our capturing logger
            persistent_chunks=persistent_chunks
        )
        return manifest, logger.logs
    except Exception as e:
        logger.error(f"Error chunking {Path(file_path).name}: {e}")
        raise e  # Re-raise to be caught by future.exception() but we lose logs if we don't catch there. 
                 # Better to return None manifest and logs.
                 # Actually, let's let exception propagate but maybe FileChunker logs before crash?
                 # If we return normally, we get logs. If exception, we get exception.
        return None, logger.logs


def _create_single_bundle(args: tuple) -> tuple:
    """
    Wrapper function for ProcessPoolExecutor zipping.
    
    Must be a top-level function (not a method) for pickle compatibility.
    
    Args:
        args: Tuple of (bundle_files, source_dir, bundle_path)
        
    Returns:
        Tuple of (Path to created bundle, List of log messages)
    """
    bundle_files, source_dir, bundle_path = args
    source_dir = Path(source_dir)
    bundle_path = Path(bundle_path)
    logger = ListLogger()
    
    try:
        with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
            for file_path, file_size in bundle_files:
                file_path = Path(file_path)
                rel_path = file_path.relative_to(source_dir)
                zf.write(file_path, arcname=str(rel_path))
        
        logger.success(f"Bundle created: {bundle_path.name} ({len(bundle_files)} files)")
        return bundle_path, logger.logs
    except Exception as e:
        logger.error(f"Error creating bundle {bundle_path.name}: {e}")
        return None, logger.logs


class ParallelChunker:
    """
    Parallel file chunking using ProcessPoolExecutor.
    
    Chunks multiple large files simultaneously for faster preparation.
    """
    
    @staticmethod
    def chunk_files_parallel(
        files: list[Path],
        source_folder: Path,
        output_folder: Path,
        chunk_size: int,
        workers: int = 4,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        logger=None,
        persistent_chunks: bool = True
    ) -> list[dict]:
        """
        Chunk multiple files in parallel.
        
        Args:
            files: List of file paths to chunk
            source_folder: Source directory root
            output_folder: Output directory for chunks
            chunk_size: Chunk size in bytes
            workers: Number of parallel workers (default: 4)
            progress_callback: Optional callback(completed, total, filename)
            logger: Optional logger instance
            persistent_chunks: If True, create chunks next to source file
            
        Returns:
            List of chunk manifest dictionaries
        """
        if not files:
            return []
        
        if logger:
            logger.info(f"Chunking parallèle: {len(files)} fichiers avec {workers} workers...")
        
        # Prepare arguments for each file
        args_list = [
            (str(f), str(source_folder), str(output_folder), chunk_size, persistent_chunks)
            for f in files
        ]
        
        manifests = []
        completed = 0
        total = len(files)
        
        # Use ProcessPoolExecutor for CPU-bound chunking
        with ProcessPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(_chunk_single_file, args): args[0]
                for args in args_list
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result, worker_logs = future.result()
                    
                    # Replay logs from worker
                    if logger and worker_logs:
                        for level, msg in worker_logs:
                            if level == "info": logger.info(msg)
                            elif level == "error": logger.error(msg)
                            elif level == "success": logger.success(msg)
                            elif level == "warning": logger.warning(msg)

                    if result:
                        manifests.append(result)
                        completed += 1
                        
                        if progress_callback:
                            progress_callback(completed, total, Path(file_path).name)
                        
                        if logger and completed % 5 == 0:
                            logger.info(f"Chunking: {completed}/{total} fichiers traités")
                    
                except Exception as e:
                    if logger:
                        logger.error(f"Erreur chunking {Path(file_path).name}: {e}")
                    # Continue with other files
        
        if logger:
            logger.success(f"Chunking parallèle terminé: {len(manifests)} fichiers")
        
        return manifests


class ParallelZipper:
    """
    Parallel ZIP bundle creation using ProcessPoolExecutor.
    
    Creates multiple ZIP bundles simultaneously for faster preparation.
    """
    
    @staticmethod
    def create_bundles_parallel(
        bundles: list[list[tuple]],
        source_dir: Path,
        output_folder: Path,
        workers: int = 10,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        logger=None
    ) -> list[Path]:
        """
        Create multiple ZIP bundles in parallel.
        
        Args:
            bundles: List of bundles, where each bundle is a list of (file_path, size) tuples
            source_dir: Source directory root (for relative paths in ZIP)
            output_folder: Output directory for bundles
            workers: Number of parallel workers (default: 10)
            progress_callback: Optional callback(completed, total, bundle_name)
            logger: Optional logger instance
            
        Returns:
            List of paths to created bundle files
        """
        if not bundles:
            return []
        
        if logger:
            logger.info(f"Création parallèle de {len(bundles)} bundle(s) avec {workers} workers...")
        
        # Generate bundle paths
        bundle_paths = []
        args_list = []
        
        for i, bundle_files in enumerate(bundles):
            bundle_name = f"bundle_batch_{i:03d}.zip" if len(bundles) > 1 else "bundle_batch.zip"
            bundle_path = output_folder / bundle_name
            bundle_paths.append(bundle_path)
            
            # Convert file paths to strings for pickle
            files_for_args = [(str(fp), sz) for fp, sz in bundle_files]
            args_list.append((files_for_args, str(source_dir), str(bundle_path)))
        
        created_paths = []
        completed = 0
        total = len(bundles)
        
        # Use ProcessPoolExecutor for CPU-bound zipping
        with ProcessPoolExecutor(max_workers=min(workers, len(bundles))) as executor:
            # Submit all tasks
            future_to_bundle = {
                executor.submit(_create_single_bundle, args): args[2]
                for args in args_list
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_bundle):
                bundle_path = future_to_bundle[future]
                try:
                    result_path, worker_logs = future.result()
                    
                    # Replay logs
                    if logger and worker_logs:
                        for level, msg in worker_logs:
                            if level == "info": logger.info(msg)
                            elif level == "error": logger.error(msg)
                            elif level == "success": logger.success(msg)
                            elif level == "warning": logger.warning(msg)
                    
                    if result_path:
                        created_paths.append(result_path)
                        completed += 1
                        
                        bundle_name = Path(bundle_path).name
                        if progress_callback:
                            progress_callback(completed, total, bundle_name)
                        
                        if logger:
                            bundle_size_mb = result_path.stat().st_size / (1024 * 1024)
                            logger.success(f"Bundle {bundle_name}: {bundle_size_mb:.2f} MB")
                        
                except Exception as e:
                    if logger:
                        logger.error(f"Erreur création bundle {Path(bundle_path).name}: {e}")
        
        if logger:
            logger.success(f"Création bundles terminée: {len(created_paths)} bundle(s)")
        
        return created_paths


class ParallelBatchPusher:
    """
    Alternative to zipping: push small files directly in parallel batches.
    
    Uses ThreadPoolExecutor (I/O bound) to push files without zipping.
    """
    
    @staticmethod
    def push_files_parallel(
        files_with_sizes: list[tuple[Path, int]],
        source_dir: Path,
        remote_dir: str,
        device_id: str,
        adb,
        workers: int = 10,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        logger=None
    ) -> tuple[bool, int, int]:
        """
        Push files directly to device without zipping.
        
        Args:
            files_with_sizes: List of (file_path, size) tuples
            source_dir: Source directory root
            remote_dir: Remote directory on device
            device_id: Target device ID
            adb: ADB utility instance
            workers: Number of parallel workers (default: 10)
            progress_callback: Optional callback(completed, total)
            logger: Optional logger instance
            
        Returns:
            Tuple of (success, successful_count, failed_count)
        """
        if not files_with_sizes:
            return True, 0, 0
        
        if logger:
            logger.info(f"[{device_id}] Push parallèle: {len(files_with_sizes)} fichiers avec {workers} workers...")
        
        def push_single_file(file_path: Path, size: int) -> bool:
            """Push a single file to device."""
            try:
                # Calculate relative path and create remote path
                rel_path = file_path.relative_to(source_dir)
                remote_path = f"{remote_dir}/{str(rel_path).replace(chr(92), '/')}"
                
                # Ensure parent directory exists on device
                remote_parent = str(Path(remote_path).parent).replace('\\', '/')
                adb.run_command(f'shell "mkdir -p \'{remote_parent}\'"', device_id)
                
                # Push file
                result = adb.run_command(f'push "{file_path}" "{remote_path}"', device_id)
                return True
                
            except Exception as e:
                if logger:
                    logger.error(f"[{device_id}] Échec push {file_path.name}: {e}")
                return False
        
        successful = 0
        failed = 0
        total = len(files_with_sizes)
        
        # Use ThreadPoolExecutor for I/O-bound pushing
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(push_single_file, fp, sz): fp
                for fp, sz in files_with_sizes
            }
            
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    if future.result():
                        successful += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                
                if progress_callback:
                    progress_callback(successful + failed, total)
                
                if logger and (successful + failed) % 20 == 0:
                    logger.info(f"[{device_id}] Push: {successful + failed}/{total}")
        
        if logger:
            logger.info(f"[{device_id}] Push terminé: {successful} réussis, {failed} échecs")
        
        return failed == 0, successful, failed


def bin_pack_files(files_with_sizes: list[tuple[Path, int]], target_size: int) -> list[list[tuple]]:
    """
    Pack files into bundles using First Fit Decreasing algorithm.
    
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
