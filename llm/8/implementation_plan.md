# Multi-Worker Transfer Refactor

## Overview

Major refactor to parallelize all transfer phases: chunking, zipping, transfer, reassembly, unzipping, and final move. Adds pre-APK installation at transfer start and per-device independent worker pools.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         PC SIDE                                  │
├──────────────────────────────────────────────────────────────────┤
│  1. Pre-APK Install → Open → Modal wait for user OK             │
│                                                                  │
│  2. CHUNKING (4 workers)          3. ZIPPING (10 workers)       │
│     ProcessPoolExecutor              ProcessPoolExecutor         │
│     ┌─────┬─────┬─────┬─────┐       ┌─────┬─────┬───...───┐     │
│     │ W1  │ W2  │ W3  │ W4  │       │ W1  │ W2  │   W10   │     │
│     └─────┴─────┴─────┴─────┘       └─────┴─────┴─────────┘     │
│                                  OR                              │
│                              BATCH PUSH (option)                 │
│                                                                  │
│  4. TRANSFER (parallel push per device)                         │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                       DEVICE SIDE                                │
├──────────────────────────────────────────────────────────────────┤
│  5. REASSEMBLY (4 workers)        6. UNZIP (10 workers)         │
│     Multiple ADB shell sessions      Multiple ADB shell sessions │
│     ┌─────┬─────┬─────┬─────┐       ┌─────┬─────┬───...───┐     │
│     │ S1  │ S2  │ S3  │ S4  │       │ S1  │ S2  │   S10   │     │
│     └─────┴─────┴─────┴─────┘       └─────┴─────┴─────────┘     │
│                                                                  │
│  7. MOVE TO FINAL (10 workers) - Multiple ADB shell sessions    │
└──────────────────────────────────────────────────────────────────┘
```

**Per-Device Independence**: Each connected device gets its own worker pools. Device A's 4 reassembly workers don't interfere with Device B's.

---

## Worker Count Defaults

| Phase      | Workers | Location |
| ---------- | ------- | -------- |
| Chunking   | 4       | PC       |
| Zipping    | 10      | PC       |
| Reassembly | 4       | Device   |
| Unzipping  | 10      | Device   |
| Final Move | 10      | Device   |

---

## File Changes

### [NEW] `src/core/pre_apk_manager.py`

Handles pre-APK installation and opening before transfer starts.

```python
class PreApkManager:
    """Manages pre-transfer APK installation and confirmation."""

    def __init__(self, adb, logger, modal_callback=None):
        self.adb = adb
        self.logger = logger
        self.modal_callback = modal_callback
        self.pre_apk_path = Path("pre-apk")

    def get_apk_file(self) -> Optional[Path]:
        """Return the single APK file in pre-apk folder, or None."""
        apks = list(self.pre_apk_path.glob("*.apk"))
        return apks[0] if apks else None

    def get_package_name(self, apk_path: Path) -> str:
        """Extract package name from APK using aapt."""
        ...

    def is_installed(self, device_id: str, package_name: str) -> bool:
        """Check if package is installed on device."""
        ...

    def uninstall(self, device_id: str, package_name: str) -> bool:
        """Uninstall package from device."""
        ...

    def install(self, device_id: str, apk_path: Path) -> bool:
        """Install APK on device."""
        ...

    def launch_app(self, device_id: str, package_name: str) -> bool:
        """Open the app using monkey or am start."""
        ...

    def ensure_unlocked(self, device_id: str) -> bool:
        """Unlock device screen if locked."""
        ...

    def run_pre_transfer(self, device_id: str) -> bool:
        """
        Full pre-transfer flow:
        1. Check for APK file
        2. Ensure device unlocked
        3. Uninstall if already installed
        4. Install APK
        5. Launch app
        6. Show modal for user to press OK
        """
        ...
```

---

### [NEW] `src/core/parallel_workers.py`

Shared worker pool infrastructure for parallel operations.

```python
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass

@dataclass
class WorkerConfig:
    chunking_workers: int = 4
    zipping_workers: int = 10
    reassembly_workers: int = 4
    unzip_workers: int = 10
    final_move_workers: int = 10

class ParallelChunker:
    """Parallel file chunking using ProcessPoolExecutor."""

    @staticmethod
    def chunk_files_parallel(
        files: list[Path],
        source_folder: Path,
        output_folder: Path,
        chunk_size: int,
        workers: int = 4,
        progress_callback=None
    ) -> list[dict]:
        """Chunk multiple files in parallel."""
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(
                    FileChunker.chunk_file,
                    file_path, source_folder, output_folder, chunk_size
                )
                for file_path in files
            ]
            # Collect results with progress tracking
            ...

class ParallelZipper:
    """Parallel ZIP bundle creation."""

    @staticmethod
    def create_bundles_parallel(
        bundles: list[list[tuple]],
        source_dir: Path,
        output_folder: Path,
        workers: int = 10
    ) -> list[Path]:
        """Create multiple ZIP bundles in parallel."""
        ...

class ParallelBatchPusher:
    """Alternative: push small files directly in batches."""

    @staticmethod
    def push_files_parallel(
        files: list[Path],
        source_dir: Path,
        remote_dir: str,
        device_id: str,
        adb,
        workers: int = 10
    ) -> bool:
        """Push files directly without zipping."""
        ...
```

---

### [NEW] `src/core/device_workers.py`

Manages parallel ADB shell sessions for device-side operations.

```python
class DeviceWorkerPool:
    """Manages parallel ADB shell sessions for a single device."""

    def __init__(self, adb, device_id: str, logger):
        self.adb = adb
        self.device_id = device_id
        self.logger = logger

    def reassemble_parallel(
        self,
        chunk_folders: list[str],
        workers: int = 4
    ) -> bool:
        """
        Reassemble chunk folders in parallel.
        Each worker handles a subset of chunk folders.
        """
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Partition chunk_folders among workers
            futures = []
            for folder in chunk_folders:
                futures.append(
                    executor.submit(self._reassemble_single, folder)
                )
            ...

    def _reassemble_single(self, chunk_folder: str) -> bool:
        """Reassemble a single chunk folder via ADB shell."""
        cmd = f'shell "cat \'{chunk_folder}\'/chunk_*.bin > output && rm -rf \'{chunk_folder}\'"'
        ...

    def unzip_parallel(
        self,
        zip_files: list[str],
        workers: int = 10
    ) -> bool:
        """Unzip multiple bundles in parallel."""
        ...

    def move_parallel(
        self,
        file_mappings: list[tuple[str, str]],  # (source, dest)
        workers: int = 10
    ) -> bool:
        """Move files to final destination in parallel."""
        ...
```

---

### [MODIFY] `src/config.py`

Add worker count configuration defaults.

```diff
+ # === WORKER POOL SETTINGS ===
+
+ # PC-side workers
+ DEFAULT_CHUNKING_WORKERS = 4
+ DEFAULT_ZIPPING_WORKERS = 10
+
+ # Device-side workers
+ DEFAULT_REASSEMBLY_WORKERS = 4
+ DEFAULT_UNZIP_WORKERS = 10
+ DEFAULT_FINAL_MOVE_WORKERS = 10
+
+ # Small file handling mode: "zip" or "batch_push"
+ DEFAULT_SMALL_FILE_MODE = "zip"
```

---

### [MODIFY] `src/core/transfer.py`

Integrate parallel workers and pre-APK flow.

#### Key Changes:

1. **Import new modules**
2. **Add PreApkManager to init**
3. **Modify `start_transfer()` to:**
   - Call `pre_apk_manager.run_pre_transfer()` first
   - Use `ParallelChunker` instead of sequential chunking
   - Use `ParallelZipper` OR `ParallelBatchPusher` based on config
4. **Modify reassembly call to use `DeviceWorkerPool`**

```python
def start_transfer(self, source_dir, target_dir, device_id):
    # 0. Pre-APK flow
    pre_apk_mgr = PreApkManager(self.adb, self.logger, self.modal_callback)
    if not pre_apk_mgr.run_pre_transfer(device_id):
        self.logger.error("Pre-APK flow cancelled or failed")
        return False

    # 1. Scan files (unchanged)
    self.scan_files(source_dir)

    # 2. Parallel chunking
    worker_config = self._get_worker_config()
    manifests = ParallelChunker.chunk_files_parallel(
        self.files_to_chunk,
        Path(source_dir),
        self.temp_dir,
        self.config.get("chunk_size"),
        workers=worker_config.chunking_workers
    )

    # 3. Parallel zipping OR batch push
    if self.config.get("small_file_mode", "zip") == "zip":
        ParallelZipper.create_bundles_parallel(...)
    else:
        ParallelBatchPusher.push_files_parallel(...)

    # 4. Transfer to device (existing parallel logic)
    ...

    # 5. Device-side parallel operations
    device_pool = DeviceWorkerPool(self.adb, device_id, self.logger)
    device_pool.reassemble_parallel(chunk_folders, worker_config.reassembly_workers)
    device_pool.unzip_parallel(zip_files, worker_config.unzip_workers)
    device_pool.move_parallel(file_mappings, worker_config.final_move_workers)
```

---

### [MODIFY] `src/main.py`

Add UI controls for worker configuration.

#### New Settings Section:

```python
# In _create_settings_tab():

# Worker Settings Frame
worker_frame = ttk.LabelFrame(settings_tab, text="Workers")

ttk.Label(worker_frame, text="Chunking (PC):").grid(row=0, column=0)
self.chunking_workers_var = tk.IntVar(value=4)
ttk.Spinbox(worker_frame, from_=1, to=16,
            textvariable=self.chunking_workers_var).grid(row=0, column=1)

ttk.Label(worker_frame, text="Zipping (PC):").grid(row=1, column=0)
self.zipping_workers_var = tk.IntVar(value=10)
# ... etc for all worker types

# Small file mode
ttk.Label(worker_frame, text="Small files:").grid(row=5, column=0)
self.small_file_mode_var = tk.StringVar(value="zip")
ttk.Combobox(worker_frame,
             values=["zip", "batch_push"],
             textvariable=self.small_file_mode_var).grid(row=5, column=1)
```

---

## Verification Plan

### Automated Tests

```bash
# Test parallel chunking
python -c "from core.parallel_workers import ParallelChunker; ..."

# Test device worker pool
python -c "from core.device_workers import DeviceWorkerPool; ..."
```

### Manual Verification

1. **Pre-APK Flow**: Connect device, start transfer, verify:

   - APK installs (or uninstalls first if present)
   - App opens
   - Modal appears on PC
   - Transfer continues after OK

2. **Parallel Chunking**: Transfer folder with multiple large files (>100MB each), verify:

   - Multiple chunk operations happen simultaneously
   - All manifests created correctly

3. **Parallel Zipping vs Batch Push**:

   - Test with "zip" mode: verify bundles created
   - Test with "batch_push" mode: verify files pushed directly

4. **Device Parallel Ops**: Monitor ADB logs during:

   - Reassembly: should see multiple cat commands
   - Unzip: should see multiple unzip processes
   - Move: should see multiple mv commands

5. **Multi-Device**: Connect 2+ devices, start transfer to all, verify:
   - Each device progresses independently
   - Worker counts are per-device
