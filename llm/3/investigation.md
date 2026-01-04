# Investigation Report

## 1. Small Files Transfer Slowness

**Findings:**
- **Mechanism:** Small files are indeed batched into ZIP bundles using a bin-packing algorithm in `src/core/transfer.py`. This is good.
- **The Bottleneck:** The primary issue lies in the "Resume Check" logic. For every chunk or bundle, the `TransferManager` calls `_check_remote_file_exists` (invoking `adb shell stat`).
- **Impact:** Each `adb` call spawns a new subprocess. Even if files are bundled, if you have many bundles, the overhead of spawning thousands of `adb.exe` processes dominates the transfer time.
- **Root Cause Location:** `src/core/transfer.py` inside `parallel_transfer` and `_check_remote_file_exists`.

**Recommendations:**
- **Bulk Check:** Implement a single `adb shell ls -R` or `find` command at the start to get a list of all existing remote files at once, rather than checking one by one.
- **Disable Check for Small Bundles:** If a file/bundle is small, the cost of checking might be higher than just re-uploading.

## 2. Reassembly Slowness

**Findings:**
- **Script Efficiency:** The `src/utils/unified.sh` script uses a shell `while` loop to iterate through chunks and `cat` them into the final file. Shell loops on Android (especially via Termux or limited shells) are slow.
- **Polling Latency:** The `ReassemblyManager` in Python polls the device status every 5 seconds. If a reassembly takes 1 second, the user might wait up to 6 seconds to see it finish.
- **Root Cause Location:** `src/utils/unified.sh` (Phase 1 logic) and `src/core/reassembly.py`.

**Recommendations:**
- **Optimize Script:** Use globbing where possible (e.g., `cat chunk_* > output`) instead of a loop, or check if `cat` can accept multiple arguments efficiently on the target device.
- **Reduce Polling:** Decrease the polling interval (e.g., to 1 or 2 seconds) or use a "push" notification (e.g., creating a completion file) to signal the end more immediately.

## 3. Caching Performance

**Findings:**
- **History Manager:** `src/core/history_manager.py` loads and **completely re-writes** the JSON history file every time a record is added. As the history grows, this IO operation becomes blocking and slow.
- **Hashing:** `FileChunker` calculates MD5 hashes for caching. For GB-sized files, MD5 calculation in pure Python (or even optimized) is CPU intensive and delays the start of the transfer.

**Recommendations:**
- **Append-Only / Rolling Log:** Refactor `HistoryManager` to append to a log or only write to disk periodically/on exit.
- **Faster Hashing:** Use a faster non-cryptographic hash (like xxHash) or, for the purpose of "resume", rely on file size + modification time (mtime) + partial hash (first/last 1MB) to speed up checks significantly.

## 4. Endless Logs (Memory Leak)

**Findings:**
- **Unbounded Growth:** The `log` method in `src/main.py` (`Application` class) simply appends text to the `tk.Text` widget (`self.progress_text.insert`).
- **No Cleanup:** There is no logic to remove old lines. This causes the widget to hold an infinite amount of text, consuming memory and slowing down the UI rendering over time.

**Recommendations:**
- **Line Capping:** Modify the `log` function to check the number of lines (`self.progress_text.index('end-1c')`). If it exceeds 5000, delete the lines from the top (`1.0` to `2.0`, repeated as needed).

## 5. UI Feedback & ADB Errors

**Findings:**
- **No Timeouts:** `src/utils/adb.py` executes commands using `subprocess.Popen` but often without a `timeout`. If an ADB command hangs (common with wireless ADB or unstable connections), the entire Python thread hangs, freezing the UI.
- **Log Flooding:** The UI tries to display every single log line from ADB. If ADB outputs verbose data, it floods the main thread, causing lag ("Not Responding").
- **Error Swallowing:** Some exceptions might be caught generically without giving the user specific "Actionable" advice (e.g., "Check your USB cable" vs just "Error").

**Recommendations:**
- **Timeouts:** Add a `timeout` parameter to `Adb.run_command` and handle `subprocess.TimeoutExpired`.
- **Log Throttling:** Don't print every ADB output line to the GUI. Show high-level status ("Transferring...", "Reassembling...") and keep verbose logs in a file or a separate "Debug" window/tab.
