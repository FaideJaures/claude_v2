# Implementation Plan for Performance & Fixes

Based on the investigation in `investigation.md`, here is the plan to resolve the identified issues.

## 1. Optimize Reassembly (`src/utils/unified.sh`)
**Goal:** Drastically reduce reassembly time by removing the per-chunk process forking loop.

*   **Current:**
    ```bash
    while [ $CHUNK_INDEX -lt $NUM_CHUNKS ]; do
        cat "$CHUNK_FILE" >> "$OUTPUT_FILE"
        ...
    done
    ```
*   **Proposed:**
    *   Use shell glob expansion which is sorted alphabetically by default (and our chunks are named `chunk_0000.bin`).
    *   **New Logic:**
        ```bash
        # Verify at least one chunk exists
        if ls "$CHUNK_DIR"/chunk_*.bin >/dev/null 2>&1; then
            cat "$CHUNK_DIR"/chunk_*.bin > "$OUTPUT_FILE"
        else
            log_error "No chunks found"
        fi
        ```
    *   This reduces 1000+ operations to 1 operation.

## 2. Optimize Transfer Resume & Verification (`src/core/transfer.py`)
**Goal:** Eliminate network latency overhead from per-file ADB calls.

*   **Current:**
    *   `_check_remote_file_exists` calls `adb shell stat ...` for *each* chunk.
    *   `_verify_transfer_on_device` calls `adb shell stat ...` for *each* chunk.
*   **Proposed:**
    *   **Bulk Check:** Before the loop, execute **one** command: `adb shell find 'remote_dir' -name "chunk_*.bin" -printf "%f:%s\n"` (or `ls -l` if `find` features are limited on Android, though usually `ls -l` works).
    *   Parse the output into a dictionary: `remote_files = {'chunk_0000.bin': size, ...}`.
    *   Modify `_check_remote_file_exists` and `_verify_transfer_on_device` to look up in this local dictionary instead of calling ADB.

## 3. Fix Cancel Button (`src/utils/adb.py`, `src/core/transfer.py`)
**Goal:** Make the "Cancel" button work immediately, even if ADB is hanging.

*   **Current:** `adb.run_command` uses `subprocess.Popen(...).communicate()` which blocks until the process finishes.
*   **Proposed:**
    *   **Track Processes:** In `Adb` class, maintain a list/set of active `subprocess.Popen` objects.
        ```python
        self.active_processes = set()
        # In run_command:
        proc = subprocess.Popen(...)
        self.active_processes.add(proc)
        try:
             stdout, stderr = proc.communicate()
        finally:
             self.active_processes.discard(proc)
        ```
    *   **Kill Method:** Add a `terminate_all()` method to `Adb` that iterates `active_processes` and calls `proc.kill()`.
    *   **Integration:** In `TransferManager.cancel()` and `ReassemblyManager.cancel()`, call `self.adb.terminate_all()`.
 This will immediately unblock the waiting threads (raising an Exception or returning None), allowing the cancellation logic to proceed.

## 4. Optimize Logging (`src/main.py`)
**Goal:** Prevent UI freeze when thousands of logs are generated rapidly.

*   **Current:** `Application.log` updates the Tkinter widget immediately on every call.
*   **Proposed:**
    *   **Batching:** Use a `queue.Queue` for log messages.
    *   Update `log()` to just `queue.put()`.
    *   Create a `_process_log_queue` method called via `self.after(100, ...)` that pulls all available messages from the queue (up to a limit, say 100) and inserts them into the `Text` widget in one go.
    *   This decouples the business logic speed from the UI rendering speed.

## 5. Execution Order
1.  **Refactor `unified.sh`** (Highest Impact / Lowest Risk).
2.  **Modify `adb.py`** to support process tracking and termination (Critical for UX).
3.  **Refactor `transfer.py`** to use bulk file listing (High Impact on latency).
4.  **Update `main.py`** for log batching (Quality of Life).

