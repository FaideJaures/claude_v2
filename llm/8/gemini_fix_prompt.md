# Gemini Task: Fix Multi-Worker Transfer Integration

## Context

I've created new modules for parallel transfer but they're not being used correctly. The transfer runs but:

1. Pre-APK is NOT being installed, no dialog shows
2. Workers are not logging - parallel processing doesn't seem to work
3. UI settings for worker counts are not implemented
4. Logs are minimal

## Files Created (review these first)

- `src/core/pre_apk_manager.py` - Pre-APK install/open/modal flow
- `src/core/parallel_workers.py` - PC-side parallel chunking/zipping
- `src/core/device_workers.py` - Device-side parallel ADB operations
- `src/config.py` - Has new defaults (DEFAULT_CHUNKING_WORKERS, etc.)

## Issues to Fix

### Issue 1: Pre-APK Flow Not Executing

**Problem**: `run_pre_transfer()` in `pre_apk_manager.py` is not being called or failing silently.

**Debug Steps**:

1. Check if `start_transfer_parallel()` in `transfer.py` is actually being called (not the old `start_transfer()`)
2. Verify `modal_callback` is properly passed from main.py to TransferManager to PreApkManager
3. The dialog uses `PreApkConfirmationModal` from `ui/modal_dialog.py` - verify it's in the imports
4. Make sure `show_reassembly_modal()` in main.py handles `modal_type == "pre_apk_confirmation"`

**Fix**: Add print statements or use logger to trace execution. Ensure the modal_callback chain is:

```
main.py: self.transfer_manager.modal_callback = self.show_reassembly_modal
transfer.py: pre_apk_mgr = PreApkManager(..., modal_callback=self.modal_callback)
pre_apk_manager.py: self.modal_callback("pre_apk_confirmation", device_id=..., app_name=...)
```

### Issue 2: Workers Not Logging/Working

**Problem**: `ParallelChunker`, `ParallelZipper` in `parallel_workers.py` are not showing logs.

**Debug**:

1. Check if `process_files_parallel()` in `transfer.py` is being called instead of `process_files()`
2. The parallel methods need to pass `logger=self.logger` correctly
3. ProcessPoolExecutor logs don't appear in main thread - need to collect and log results

**Fix**: In `transfer.py`, ensure `process_files_parallel()` is called and has proper logging:

```python
def process_files_parallel(self, ...):
    self.logger.info("=== STARTING PARALLEL PROCESSING ===")
    # ... rest of method with self.logger.info() calls
```

### Issue 3: UI Settings Not Updated

**Problem**: No spinboxes for worker counts in Settings UI.

**Fix**: In `main.py` class `SettingsWindow`, add spinboxes for:

- `chunking_workers` (default 4)
- `zipping_workers` (default 10)
- `reassembly_workers` (default 4)
- `unzip_workers` (default 10)
- `final_move_workers` (default 10)
- `small_file_mode` ("zip" or "batch_push" dropdown)
- `pre_apk_enabled` (checkbox)

Add to `create_widgets()` method and save in `save_and_close()`.

### Issue 4: More Logging Needed

**Fix**: Add logging at these key points:

1. Start of `start_transfer_parallel()` - log all config values
2. Before/after each phase (pre-APK, chunking, zipping, transfer, reassembly)
3. In parallel workers - log number of workers spawned and results
4. In device_workers - log each ADB command result

## Testing After Fix

1. Run transfer with a file in `pre-apk/` folder
2. Check logs for: "Phase 0: Pré-APK", "Chunking parallèle", etc.
3. Verify dialog appears for pre-APK confirmation
4. Open Settings and confirm new worker spinboxes appear

## Code Locations

- `src/main.py`: Lines 1166-1292 (start_transfer_thread), Lines 68-291 (SettingsWindow)
- `src/core/transfer.py`: Lines 227-333 (start_transfer_parallel)
- `src/core/pre_apk_manager.py`: Lines 315-395 (run_pre_transfer)
- `src/ui/modal_dialog.py`: Lines 122-230 (PreApkConfirmationModal)

## Important: The Transfer Flow Should Be

1. User clicks "Transférer"
2. `start_transfer_thread()` → `run_transfer()` calls `transfer_manager.start_transfer_parallel()`
3. `start_transfer_parallel()` Phase 0: Creates `PreApkManager`, calls `run_pre_transfer()`
4. `run_pre_transfer()` finds APK, installs it, calls `modal_callback("pre_apk_confirmation")`
5. `show_reassembly_modal()` in main.py shows `PreApkConfirmationModal`
6. User clicks OK, flow continues to Phase 1, 2, 3, 4...

Fix any breaks in this chain!
