# TODO List - Multi-Worker Transfer Fixes

- [x] **UI Updates (`src/main.py`)**
    - [x] Add `chunking_workers` spinbox (default 4) to `SettingsWindow`
    - [x] Add `zipping_workers` spinbox (default 10) to `SettingsWindow`
    - [x] Add `reassembly_workers` spinbox (default 4) to `SettingsWindow`
    - [x] Add `unzip_workers` spinbox (default 10) to `SettingsWindow`
    - [x] Add `final_move_workers` spinbox (default 10) to `SettingsWindow`
    - [x] Add `small_file_mode` dropdown ("zip", "batch_push") to `SettingsWindow`
    - [x] Add `pre_apk_enabled` checkbox to `SettingsWindow`
    - [x] Update `save_and_close` to persist these new settings.

- [x] **Worker Logging Fixes (`src/core/parallel_workers.py`)**
    - [x] Modify `_chunk_single_file` to return status/log messages.
    - [x] Modify `_create_single_bundle` to return status/log messages.
    - [x] Update `ParallelChunker.chunk_files_parallel` to log returned messages from workers.
    - [x] Update `ParallelZipper.create_bundles_parallel` to log returned messages from workers.

- [x] **Refactor Multi-Device Transfer (`src/main.py`)**
    - [x] In `run_multi_device_transfer`, implement `PreApkManager` flow for all devices.
    - [x] Replace `transfer_manager.scan_files` + `process_files` with `transfer_manager.process_files_parallel`.
    - [x] Ensure `process_files_parallel` uses the config values for worker counts.

- [x] **Cleanup**
    - [x] Remove legacy sequential processing code from `run_multi_device_transfer` if no longer needed as fallback.
    - [x] Ensure imports are clean.

- [ ] **Final Report**
    - [ ] Generate `llm/9/summary_report.md` with details of changes.