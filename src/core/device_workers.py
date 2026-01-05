# claude_v2/src/core/device_workers.py
"""
Device Workers - Parallel ADB shell operations for device-side processing.

Manages multiple concurrent ADB shell sessions for:
- Reassembly: cat chunk files in parallel
- Unzipping: unzip bundles in parallel
- Final move: move files to destination in parallel

Each device gets its own DeviceWorkerPool for independent processing.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

from utils.adb import Adb


def _escape_shell_path(path: str) -> str:
    """Escape a path for use in shell single-quoted strings."""
    return path.replace("'", "'\\''") if path else path


class DeviceWorkerPool:
    """
    Manages parallel ADB shell sessions for a single device.
    
    Provides parallel execution of device-side operations like
    reassembly, unzipping, and file moving.
    """
    
    def __init__(self, adb: Adb, device_id: str, logger, config: dict = None):
        """
        Initialize DeviceWorkerPool.
        
        Args:
            adb: ADB utility instance
            device_id: Target device identifier
            logger: Logger instance
            config: Optional configuration dictionary
        """
        self.adb = adb
        self.device_id = device_id
        self.logger = logger
        self.config = config or {}
        
        # Default worker counts
        self.reassembly_workers = self.config.get("reassembly_workers", 4)
        self.unzip_workers = self.config.get("unzip_workers", 10)
        self.final_move_workers = self.config.get("final_move_workers", 10)
    
    def _run_shell_command(self, command: str) -> tuple[bool, list[str]]:
        """
        Run a shell command on the device.
        
        Args:
            command: Shell command to run
            
        Returns:
            Tuple of (success, output_lines)
        """
        try:
            result = self.adb.run_command(f'shell "{command}"', self.device_id)
            return True, result if result else []
        except Exception as e:
            self.logger.error(f"[{self.device_id}] Shell error: {e}")
            return False, []
    
    def _reassemble_single_chunk_folder(self, chunk_folder: str, output_path: str) -> bool:
        """
        Reassemble a single chunk folder into the original file.
        
        Uses cat to concatenate all chunk files.
        
        Args:
            chunk_folder: Path to chunk folder on device
            output_path: Path for output file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            escaped_folder = _escape_shell_path(chunk_folder)
            escaped_output = _escape_shell_path(output_path)
            
            # Ensure output directory exists
            output_parent = str(Path(output_path).parent).replace('\\', '/')
            self._run_shell_command(f"mkdir -p '{_escape_shell_path(output_parent)}'")
            
            # Concatenate all chunk files in order
            # Note: chunks are named chunk_000.bin, chunk_001.bin, etc. so glob sort works
            cmd = f"cat '{escaped_folder}'/chunk_*.bin > '{escaped_output}'"
            success, output = self._run_shell_command(cmd)
            
            if not success:
                return False
            
            # Verify output file was created
            verify_cmd = f"test -f '{escaped_output}' && echo 'OK'"
            success, output = self._run_shell_command(verify_cmd)
            
            if output and 'OK' in ''.join(output):
                # Clean up chunk folder
                self._run_shell_command(f"rm -rf '{escaped_folder}'")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"[{self.device_id}] Reassembly error for {chunk_folder}: {e}")
            return False
    
    def reassemble_parallel(
        self,
        chunk_folders: list[dict],
        remote_temp_dir: str,
        workers: int = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> tuple[bool, int, int]:
        """
        Reassemble chunk folders in parallel.
        
        Each worker handles one chunk folder at a time.
        
        Args:
            chunk_folders: List of manifest dicts with chunk_folder and output info
            remote_temp_dir: Remote temp directory path
            workers: Number of parallel workers (default: self.reassembly_workers)
            progress_callback: Optional callback(completed, total)
            
        Returns:
            Tuple of (all_success, successful_count, failed_count)
        """
        if not chunk_folders:
            return True, 0, 0
        
        workers = workers or self.reassembly_workers
        
        self.logger.info(f"[{self.device_id}] Réassemblage parallèle: {len(chunk_folders)} fichiers avec {workers} workers...")
        
        successful = 0
        failed = 0
        total = len(chunk_folders)
        
        def reassemble_one(manifest: dict) -> bool:
            """Reassemble one chunk folder."""
            chunk_folder = manifest.get('chunk_folder', '')
            original_file = manifest.get('original_file', '')
            
            # Build paths
            chunk_path = f"{remote_temp_dir}/{chunk_folder}".replace('\\', '/')
            
            # Output path is next to chunk folder (remove _chunks suffix)
            chunk_basename = Path(chunk_folder).name
            if chunk_basename.endswith('_chunks'):
                output_name = Path(original_file).name
                output_dir = str(Path(chunk_folder).parent).replace('\\', '/')
                output_path = f"{remote_temp_dir}/{output_dir}/{output_name}".replace('//', '/')
            else:
                output_path = f"{remote_temp_dir}/{original_file}".replace('\\', '/')
            
            return self._reassemble_single_chunk_folder(chunk_path, output_path)
        
        # Use ThreadPoolExecutor for parallel ADB sessions
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(reassemble_one, manifest): manifest
                for manifest in chunk_folders
            }
            
            for future in as_completed(futures):
                manifest = futures[future]
                try:
                    if future.result():
                        successful += 1
                    else:
                        failed += 1
                        self.logger.error(f"[{self.device_id}] Échec réassemblage: {manifest.get('original_file', 'unknown')}")
                except Exception as e:
                    failed += 1
                    self.logger.error(f"[{self.device_id}] Exception réassemblage: {e}")
                
                if progress_callback:
                    progress_callback(successful + failed, total)
                
                if (successful + failed) % 5 == 0:
                    self.logger.info(f"[{self.device_id}] Réassemblage: {successful + failed}/{total}")
        
        self.logger.info(f"[{self.device_id}] Réassemblage terminé: {successful} réussis, {failed} échecs")
        return failed == 0, successful, failed
    
    def _unzip_single_bundle(self, bundle_path: str, extract_to: str) -> bool:
        """
        Unzip a single bundle on device.
        
        Args:
            bundle_path: Path to ZIP file on device
            extract_to: Directory to extract to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            escaped_bundle = _escape_shell_path(bundle_path)
            escaped_dest = _escape_shell_path(extract_to)
            
            # Check if unzip is available
            unzip_cmd = "unzip"
            check_cmd = "command -v unzip >/dev/null 2>&1 && echo 'OK'"
            success, output = self._run_shell_command(check_cmd)
            
            if not output or 'OK' not in ''.join(output):
                # Try busybox unzip
                check_cmd = "test -f /data/local/tmp/busybox && echo 'OK'"
                success, output = self._run_shell_command(check_cmd)
                if output and 'OK' in ''.join(output):
                    unzip_cmd = "/data/local/tmp/busybox unzip"
                else:
                    self.logger.error(f"[{self.device_id}] unzip not available on device")
                    return False
            
            # Extract bundle
            cmd = f"{unzip_cmd} -o -q '{escaped_bundle}' -d '{escaped_dest}'"
            success, output = self._run_shell_command(cmd)
            
            if success:
                # Remove bundle after extraction
                self._run_shell_command(f"rm -f '{escaped_bundle}'")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"[{self.device_id}] Unzip error for {bundle_path}: {e}")
            return False
    
    def unzip_parallel(
        self,
        bundle_files: list[str],
        remote_temp_dir: str,
        workers: int = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> tuple[bool, int, int]:
        """
        Unzip multiple bundles in parallel.
        
        Args:
            bundle_files: List of bundle filenames (relative to remote_temp_dir)
            remote_temp_dir: Remote temp directory path
            workers: Number of parallel workers (default: self.unzip_workers)
            progress_callback: Optional callback(completed, total)
            
        Returns:
            Tuple of (all_success, successful_count, failed_count)
        """
        if not bundle_files:
            return True, 0, 0
        
        workers = workers or self.unzip_workers
        
        self.logger.info(f"[{self.device_id}] Décompression parallèle: {len(bundle_files)} bundles avec {workers} workers...")
        
        successful = 0
        failed = 0
        total = len(bundle_files)
        
        def unzip_one(bundle_name: str) -> bool:
            """Unzip one bundle."""
            bundle_path = f"{remote_temp_dir}/{bundle_name}".replace('\\', '/')
            return self._unzip_single_bundle(bundle_path, remote_temp_dir)
        
        # Use ThreadPoolExecutor for parallel ADB sessions
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(unzip_one, bundle): bundle
                for bundle in bundle_files
            }
            
            for future in as_completed(futures):
                bundle = futures[future]
                try:
                    if future.result():
                        successful += 1
                        self.logger.success(f"[{self.device_id}] Bundle extrait: {bundle}")
                    else:
                        failed += 1
                        self.logger.error(f"[{self.device_id}] Échec extraction: {bundle}")
                except Exception as e:
                    failed += 1
                    self.logger.error(f"[{self.device_id}] Exception extraction: {e}")
                
                if progress_callback:
                    progress_callback(successful + failed, total)
        
        self.logger.info(f"[{self.device_id}] Décompression terminée: {successful} réussis, {failed} échecs")
        return failed == 0, successful, failed
    
    def _move_single_item(self, source: str, dest: str) -> bool:
        """
        Move a single file or directory to destination.
        
        Args:
            source: Source path on device
            dest: Destination path on device
            
        Returns:
            True if successful, False otherwise
        """
        try:
            escaped_source = _escape_shell_path(source)
            escaped_dest = _escape_shell_path(dest)
            
            # Ensure destination parent directory exists
            dest_parent = str(Path(dest).parent).replace('\\', '/')
            self._run_shell_command(f"mkdir -p '{_escape_shell_path(dest_parent)}'")
            
            # Move file/directory
            cmd = f"mv '{escaped_source}' '{escaped_dest}'"
            success, output = self._run_shell_command(cmd)
            
            return success
            
        except Exception as e:
            self.logger.error(f"[{self.device_id}] Move error {source} -> {dest}: {e}")
            return False
    
    def move_parallel(
        self,
        file_mappings: list[tuple[str, str]],
        workers: int = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> tuple[bool, int, int]:
        """
        Move files to final destination in parallel.
        
        Args:
            file_mappings: List of (source_path, dest_path) tuples
            workers: Number of parallel workers (default: self.final_move_workers)
            progress_callback: Optional callback(completed, total)
            
        Returns:
            Tuple of (all_success, successful_count, failed_count)
        """
        if not file_mappings:
            return True, 0, 0
        
        workers = workers or self.final_move_workers
        
        self.logger.info(f"[{self.device_id}] Déplacement parallèle: {len(file_mappings)} éléments avec {workers} workers...")
        
        successful = 0
        failed = 0
        total = len(file_mappings)
        
        # Use ThreadPoolExecutor for parallel ADB sessions
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._move_single_item, src, dst): (src, dst)
                for src, dst in file_mappings
            }
            
            for future in as_completed(futures):
                src, dst = futures[future]
                try:
                    if future.result():
                        successful += 1
                    else:
                        failed += 1
                        self.logger.warning(f"[{self.device_id}] Échec déplacement: {Path(src).name}")
                except Exception as e:
                    failed += 1
                    self.logger.error(f"[{self.device_id}] Exception déplacement: {e}")
                
                if progress_callback:
                    progress_callback(successful + failed, total)
                
                if (successful + failed) % 10 == 0:
                    self.logger.info(f"[{self.device_id}] Déplacement: {successful + failed}/{total}")
        
        self.logger.info(f"[{self.device_id}] Déplacement terminé: {successful} réussis, {failed} échecs")
        return failed == 0, successful, failed
    
    def get_remote_files(self, remote_dir: str, pattern: str = "*") -> list[str]:
        """
        List files matching pattern in remote directory.
        
        Args:
            remote_dir: Directory to list
            pattern: Glob pattern for files
            
        Returns:
            List of file paths
        """
        try:
            escaped_dir = _escape_shell_path(remote_dir)
            cmd = f"find '{escaped_dir}' -maxdepth 1 -name '{pattern}' -type f 2>/dev/null"
            success, output = self._run_shell_command(cmd)
            
            if success and output:
                return [f.strip() for f in output if f.strip()]
            return []
            
        except Exception:
            return []
    
    def get_chunk_folders(self, remote_dir: str) -> list[str]:
        """
        Find all chunk folders in remote directory.
        
        Args:
            remote_dir: Directory to search
            
        Returns:
            List of chunk folder paths
        """
        try:
            escaped_dir = _escape_shell_path(remote_dir)
            cmd = f"find '{escaped_dir}' -type d -name '*_chunks' 2>/dev/null"
            success, output = self._run_shell_command(cmd)
            
            if success and output:
                return [f.strip() for f in output if f.strip()]
            return []
            
        except Exception:
            return []
    
    def run_full_reassembly_flow(
        self,
        manifests: list[dict],
        remote_temp_dir: str,
        target_dir: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> bool:
        """
        Run the complete reassembly flow: reassemble chunks, unzip bundles, move to destination.
        
        Args:
            manifests: List of manifest dictionaries from transfer
            remote_temp_dir: Remote temp directory
            target_dir: Final destination directory
            progress_callback: Optional callback(phase, completed, total)
            
        Returns:
            True if all operations successful, False otherwise
        """
        all_success = True
        
        # 1. Reassemble chunk folders
        if manifests:
            self.logger.info(f"[{self.device_id}] Phase 1: Réassemblage des chunks...")
            success, ok, fail = self.reassemble_parallel(
                manifests,
                remote_temp_dir,
                progress_callback=lambda c, t: progress_callback("reassembly", c, t) if progress_callback else None
            )
            if not success:
                all_success = False
        
        # 2. Unzip bundles
        bundle_files = self.get_remote_files(remote_temp_dir, "bundle_*.zip")
        if bundle_files:
            # Extract just the filenames
            bundle_names = [Path(f).name for f in bundle_files]
            
            self.logger.info(f"[{self.device_id}] Phase 2: Extraction des bundles...")
            success, ok, fail = self.unzip_parallel(
                bundle_names,
                remote_temp_dir,
                progress_callback=lambda c, t: progress_callback("unzip", c, t) if progress_callback else None
            )
            if not success:
                all_success = False
        
        # 3. Move to final destination
        # List all files in temp dir (after reassembly and extraction)
        self.logger.info(f"[{self.device_id}] Phase 3: Déplacement vers destination finale...")
        
        # Move entire temp contents to target
        escaped_temp = _escape_shell_path(remote_temp_dir)
        escaped_target = _escape_shell_path(target_dir)
        
        # Create target directory
        self._run_shell_command(f"mkdir -p '{escaped_target}'")
        
        # Use rsync-like approach: move contents, not the folder itself
        # First, get list of items to move
        cmd = f"ls -1 '{escaped_temp}' 2>/dev/null"
        success, items = self._run_shell_command(cmd)
        
        if items:
            # Filter out metadata files and create mappings
            file_mappings = []
            for item in items:
                item = item.strip()
                if item and not item.startswith('.') and item not in ['transfer_state.json', 'unified.sh']:
                    src = f"{remote_temp_dir}/{item}".replace('\\', '/')
                    dst = f"{target_dir}/{item}".replace('\\', '/')
                    file_mappings.append((src, dst))
            
            if file_mappings:
                success, ok, fail = self.move_parallel(
                    file_mappings,
                    progress_callback=lambda c, t: progress_callback("move", c, t) if progress_callback else None
                )
                if not success:
                    all_success = False
        
        # 4. Cleanup temp directory
        if self.config.get("cleanup_temp", True):
            self.logger.info(f"[{self.device_id}] Nettoyage du dossier temporaire...")
            self._run_shell_command(f"rm -rf '{escaped_temp}'")
        
        return all_success
