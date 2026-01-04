# Implementation Plan - Fixes & Optimizations

## 1. Critical Fix: Path Quoting in ADB Commands
**Problem:** Spaces in file/folder names (e.g., "Screen Recordings") cause `adb shell` commands to fail (syntax errors in `mkdir`, `stat`, `[ -f ]`). This causes transfer verification to fail, which in turn aborts the reassembly phase.
**Fix:**
- In `src/core/transfer.py`, wrap all remote path variables in single quotes `'...'` within the `adb shell` strings.
- Example: `f'shell "mkdir -p \'{remote_temp_dir}\'"'`

## 2. Fix: Transfer Folder Creation Logic
**Problem:** User reports artifacts (chunks/bundles) might be mixing with the original folder or not initializing correctly.
**Analysis:**
- `process_files` uses `FileChunker`. If `persistent_chunks=True`, it might be writing to the source dir instead of the output `transfer_folder`.
- We need to ensure that when "Create Transfer Folder" is used, ALL artifacts (chunks, bundles, manifests) go solely into that folder, leaving the source pristine.
**Fix:**
- Verify `process_files` call in `create_transfer_folder_action`.
- Ensure `use_persistent_chunks` is set correctly (False for "Create Transfer Folder" mode, or pointing to the transfer folder).

## 3. Fix: Timer Start
**Problem:** Timer doesn't start on "Start Transfer".
**Fix:**
- In `src/main.py`, `start_transfer_thread` sets `self.transfer_start_time` and calls `self.update_timer()`.
- Ensure `self.timer_running` is set to `True` *before* `update_timer` is called.
- Ensure the `update_timer` loop is robust (it uses `after`, which is good).
- Check if `is_transferring` flag interference exists.

## 4. Optimization: "Noises" & Resume Speed (Bulk Check)
**Problem:** "Noises" in logs refer to thousands of `stat` commands checking for file existence. This is slow.
**Fix:**
- **Bulk Check:** Instead of `stat` per file, run `ls -R` or `find` on the remote temp directory *once* at the start.
- Parse the output into a set of existing files (with sizes).
- Use this in-memory set for `_check_remote_file_exists`.

## 5. UI & Logic Cleanup
- **Reassembly:** Fixing the quoting (Step 1) will allow verification to pass, which will naturally unblock Phase 2 (Reassembly).
- **Logs:** Memory leak fixed (already done).

---

## Execution Order
1. **Fix Quoting (Critical):** `src/core/transfer.py`.
2. **Fix Timer:** `src/main.py`.
3. **Verify/Fix Transfer Folder Logic:** `src/core/transfer.py`.
4. **Implement Bulk Resume Check:** `src/core/transfer.py` (Optimization).
