# Investigation Report: Multi-Worker Transfer Fixes

## Status Analysis

I have investigated the codebase to identify why the parallel transfer features are not working as expected. Here are the findings corresponding to the reported issues.

### 1. Pre-APK Flow Failure
**Root Cause:** Inconsistent implementation between Single-Device and Multi-Device transfers.

*   **Single Device:** `start_transfer_thread` calls `transfer_manager.start_transfer_parallel`. This method *does* correctly instantiate `PreApkManager` and call `run_pre_transfer`. If this is failing, it's likely a specific execution issue, but the logic is wired.
*   **Multi-Device:** `start_transfer_thread` calls `run_multi_device_transfer`.
    *   **Critical Flaw:** `run_multi_device_transfer` (lines 1250+ in `src/main.py`) implements a **completely manual, legacy workflow**.
    *   It calls `self.transfer_manager.scan_files()` and `self.transfer_manager.process_files()` (the *sequential* version).
    *   It **completely ignores** `PreApkManager`.
    *   It **completely ignores** `process_files_parallel`.
    *   It manually handles the thread pool for pushing files, bypassing the improved `parallel_transfer` logic in `TransferManager`.

**Conclusion:** The multi-device logic must be refactored to utilize the new `start_transfer_parallel` flow or explicitly invoke the new components (`PreApkManager`, `process_files_parallel`).

### 2. Worker Logging & Parallel Execution
**Root Cause:** Process boundaries and Legacy Calls.

*   **Logging:** In `src/core/parallel_workers.py`, the worker functions `_chunk_single_file` and `_create_single_bundle` are run in a `ProcessPoolExecutor`.
    *   The `logger` object (a `SimpleLogger` wrapping a Tkinter UI call) cannot be pickled and passed to another process.
    *   The code explicitly passes `logger=None` to the worker functions inside the `chunk_files_parallel` wrapper to avoid pickling errors.
    *   **Result:** Use `print()` inside workers (which might be captured if configured) or return log messages as part of the result tuple to be logged by the main process.
*   **Execution:** As noted above, multi-device transfers are calling `process_files` (sequential) instead of `process_files_parallel`, so parallel workers aren't even starting in that mode.

### 3. UI Settings Missing
**Root Cause:** Not Implemented.

*   `src/main.py`: The `SettingsWindow` class (`create_widgets` method) has not been updated.
*   It lacks entries for:
    *   `chunking_workers`
    *   `zipping_workers`
    *   `reassembly_workers`
    *   `unzip_workers`
    *   `final_move_workers`
    *   `small_file_mode`
    *   `pre_apk_enabled`
*   Consequently, `save_and_close` does not save these values to `config.json`.

### 4. Logging Gaps
*   `start_transfer_parallel` has good logging, but it's bypassed in multi-device mode.
*   Device-side ADB output logging needs to be ensured in `DeviceWorkerPool` (which I didn't verify deeply but `device_workers.py` likely needs similar logger handling as the PC-side workers if it uses processes).

## Recommended Fix Plan

1.  **Refactor `run_multi_device_transfer` in `src/main.py`:**
    *   It should use `PreApkManager` to install APKs on all devices (potentially in parallel).
    *   It should use `transfer_manager.process_files_parallel` instead of the sequential `process_files`.
    *   It should use `transfer_manager.parallel_transfer` (or a multi-device equivalent if `parallel_transfer` is strictly single-target).
    
2.  **Update `SettingsWindow` in `src/main.py`:**
    *   Add the missing spinboxes and checkboxes.
    *   Update `load_config` and `save_config`.

3.  **Fix Worker Logging:**
    *   Modify `_chunk_single_file` and `_create_single_bundle` to return stats/logs in their return value.
    *   Update the main process loop (`as_completed`) to log these returned messages.

4.  **Verify Pre-APK Modal:**
    *   The `PreApkConfirmationModal` is correctly implemented and handled in `show_reassembly_modal`. It just needs to be actually invoked during multi-device transfers.

This investigation confirms the prompt's suspicions and provides the roadmap for the fix.
