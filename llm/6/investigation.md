# Investigation Report: ADB Transfer Tool Performance & Issues

## 1. Small Files Transfer Slowness
**Files Analyzed:** `src/core/transfer.py`, `src/core/file_chunker.py`, `src/utils/adb.py`

### Findings:
*   **Batching Mechanism:** The tool *does* have a batching mechanism.
    *   Files smaller than `small_file_threshold` (default 10MB) are grouped into bundles.
    *   `TransferManager.process_files` calls `_bin_pack_files` to group them into chunks of `bundle_size` (default 50MB).
    *   These are zipped into `bundle_batch_XXX.zip` using Python's `zipfile` module (compression level 1).
*   **Transfer Method:**
    *   `parallel_transfer` iterates over all chunks and bundles.
    *   It uses a `ThreadPoolExecutor` (default 4 workers) to run `adb.run_command` for each file.
*   **Bottlenecks:**
    *   **ADB Process Overhead:** `src/utils/adb.py` uses `subprocess.Popen` for every single command. Even with batching, if there are many chunks (e.g., a 10GB file -> 100 chunks), this spawns 100 processes. For small files that *aren't* batched (if configuration allows) or just the overhead of `adb push` for many bundles can be significant.
    *   **Python Zipping:** Zipping is done in the main thread (sequentially for all bundles) before transfer starts. This delays the start of the transfer.

## 2. Reassembly Slowness
**Files Analyzed:** `src/core/reassembly.py`, `src/utils/unified.sh`

### Findings:
*   **Critical Bottleneck Identified:** The `unified.sh` script used for reassembly is extremely inefficient.
    *   It uses a `while` loop to iterate through every chunk index:
        ```bash
        while [ $CHUNK_INDEX -lt $NUM_CHUNKS ]; do
            # ...
            cat "$CHUNK_FILE" >> "$OUTPUT_FILE" 2>/dev/null
            # ...
        done
        ```
    *   **Why it's slow:** This executes the `cat` command and opens/closes the output file `N` times (where `N` is the number of chunks). On Android's shell, forking a process is expensive. For a large file with 1000 chunks, this is 1000 process forks.
*   **Solution:** The script should be refactored to use shell glob expansion, which is a single command:
    ```bash
    cat "$CHUNK_DIR"/chunk_*.bin > "$OUTPUT_FILE"
    ```
    (Note: `chunk_0000.bin` naming ensures correct alphabetical order).

## 3. Caching Mechanisms
**Files Analyzed:** `src/core/file_chunker.py`, `src/core/transfer.py`

### Findings:
*   **Local Caching:** `FileChunker` has a `persistent_chunks` mode. It checks if chunks exist and verifies their MD5. This prevents re-chunking files that haven't changed.
*   **Remote Resume:** `TransferManager.parallel_transfer` has a "resume" feature (`_check_remote_file_exists`).
    *   **Bottleneck:** This function calls `adb shell stat` for **every single chunk** before transferring.
    *   This introduces massive latency (Network/ADB round-trip time * Number of chunks). If you have 500 chunks, that's 500 individual ADB commands just to check existence.

## 4. Memory Leak in Logs
**Files Analyzed:** `src/main.py`

### Findings:
*   **Current Implementation:** The `Application.log` method **already implements** a 5000-line limit:
    ```python
    if line_count > 5000:
        lines_to_delete = line_count - 5000
        self.progress_text.delete("1.0", f"{lines_to_delete + 1}.0")
    ```
*   **Observation:** The limit is strictly enforced. However, large amounts of text manipulation in Tkinter (deleting from start) can be sluggish if logs are spamming rapidly (e.g., inside a tight loop).

## 5. UI Feedback & Errors (Cancel Button)
**Files Analyzed:** `src/main.py`, `src/utils/adb.py`, `src/core/transfer.py`

### Findings:
*   **Cancel Logic:** `TransferManager` has a `cancelled` flag. It is checked in the loop that processes `concurrent.futures`.
*   **Blocking Issue:** `adb.run_command` uses `subprocess.Popen(...).communicate()` (implicitly via reading stdout). This is a **blocking call**.
    *   If `adb push` stalls (e.g., network timeout, bad cable), the Python thread waits indefinitely (or until system timeout).
    *   The `cancelled` flag is only checked *after* a command returns.
*   **UI Freeze:** Since the worker threads are blocked, they cannot acknowledge the cancellation immediately.

## Recommendations for Fixes

1.  **Optimize Reassembly:** Rewrite `unified.sh` to use `cat chunk_*.bin > out` instead of a loop.
2.  **Optimize Transfer/Caching:**
    *   Disable `_check_remote_file_exists` (resume) by default or optimize it to check *all* files in one command (`ls -l` or `find`) and parse the output locally, instead of 1 call per file.
3.  **Optimize ADB Calls:** Use a persistent ADB server connection or minimize shell calls (batch commands).
4.  **Fix Cancel Button:** Use `subprocess.Popen` with a timeout or allow the main thread to kill the subprocesses when cancel is requested (requires tracking active Popen objects).
