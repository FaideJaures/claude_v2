# Multi-Worker Transfer Refactor - TODO

## Phase 1: Pre-APK Flow ✓

- [x] Create `src/core/pre_apk_manager.py`
  - [x] `PreApkManager` class
  - [x] `get_apk_file()` - find APK in pre-apk folder
  - [x] `get_package_name_from_apk()` - extract via aapt
  - [x] `is_installed()` - check if installed
  - [x] `uninstall()` - remove if present
  - [x] `install()` - install APK
  - [x] `launch_app()` - open app
  - [x] `ensure_unlocked()` - unlock screen
  - [x] `run_pre_transfer()` - full flow with modal

## Phase 2: PC-Side Parallel Workers ✓

- [x] Create `src/core/parallel_workers.py`
  - [x] `WorkerConfig` dataclass
  - [x] `ParallelChunker.chunk_files_parallel()`
  - [x] `ParallelZipper.create_bundles_parallel()`
  - [x] `ParallelBatchPusher.push_files_parallel()`

## Phase 3: Device-Side Parallel Workers ✓

- [x] Create `src/core/device_workers.py`
  - [x] `DeviceWorkerPool` class
  - [x] `reassemble_parallel()` - parallel cat commands
  - [x] `unzip_parallel()` - parallel unzip
  - [x] `move_parallel()` - parallel mv to final dest
  - [x] `run_full_reassembly_flow()` - orchestrates all phases

## Phase 4: Configuration ✓

- [x] Update `src/config.py`
  - [x] Add worker count defaults
  - [x] Add `small_file_mode` default
  - [x] Add `pre_apk_enabled` default

## Phase 5: Integration ✓

- [x] Update `src/core/transfer.py`
  - [x] Import new modules
  - [x] Add `get_worker_config()` method
  - [x] Add `process_files_parallel()` method
  - [x] Add `start_transfer_parallel()` - full pipeline

## Phase 6: UI ✓

- [x] Add `PreApkConfirmationModal` to `src/ui/modal_dialog.py`
- [ ] Add worker count spinboxes to main.py (optional - can use config.json)
- [ ] Add small file mode dropdown to main.py (optional)

## Phase 7: Verification (Manual)

- [ ] Test pre-APK flow with actual APK
- [ ] Test parallel chunking with multiple large files
- [ ] Test parallel zipping with many small files
- [ ] Test batch push option
- [ ] Test device-side parallel operations
- [ ] Test multi-device independence

## Notes

- To use parallel transfer, call `transfer_manager.start_transfer_parallel()` instead of `start_transfer()`
- Place a single APK file in `pre-apk/` folder to enable pre-APK flow
- Worker counts can be configured in config.json or via UI (when implemented)
