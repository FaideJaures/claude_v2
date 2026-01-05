# ADB Transfer Tool - TODO

## Session 5 - Statistics & Queue System

---

## Phase 1: Folder Statistics (Priority: HIGH)

### 1.1 Add folder analysis function ✅

- [ ] **File:** `src/core/transfer.py`
- [ ] Create `analyze_folder(source_dir) -> dict` method in `TransferManager`
- [ ] Returns: `{total_files, total_size_bytes, large_files_count, small_files_count, estimated_chunks, estimated_bundles}`
- [ ] Uses existing `scan_files()` logic but doesn't modify state

### 1.2 Display stats in UI on folder selection

- [ ] **File:** `src/main.py`
- [ ] Add `folder_stats_label` widget below source directory entry
- [ ] Call `analyze_folder()` when source directory changes (`StringVar.trace()`)
- [ ] Display: "X files | Y MB | Z chunks | W bundles"
- [ ] Run analysis in background thread to avoid UI freeze

### 1.3 Format stats nicely

- [ ] **File:** `src/main.py`
- [ ] Create `_format_size(bytes) -> str` helper (KB/MB/GB)
- [ ] Color-code large transfers (>1GB = orange, >10GB = red)

---

## Phase 2: Transfer Statistics (Priority: HIGH)

### 2.1 Track transfer metrics during operation

- [ ] **File:** `src/core/transfer.py`
- [ ] Add `TransferStats` dataclass: `{start_time, end_time, bytes_transferred, files_count, chunks_count, bundles_count}`
- [ ] Update `parallel_transfer()` to track bytes as files complete
- [ ] Calculate speed: `bytes_transferred / elapsed_seconds`

### 2.2 Return stats from transfer methods

- [ ] **File:** `src/core/transfer.py`
- [ ] Modify `start_transfer()` to return `TransferStats` (or None on failure)
- [ ] Modify `transfer_from_prepared_folder()` to return `TransferStats`
- [ ] Modify `parallel_transfer()` to populate and return stats

### 2.3 Display stats in completion popup

- [ ] **File:** `src/main.py`
- [ ] Modify `_cleanup_transfer_ui()` to accept `TransferStats`
- [ ] Update completion messagebox to show:
  - Duration: Xm Ys
  - Speed: X.XX MB/s
  - Files: X transferred
  - Data: X.XX GB

### 2.4 Log stats summary

- [ ] **File:** `src/main.py`
- [ ] Add formatted stats to log output
- [ ] Include in history record

---

## Phase 3: Subsidiary Folder Injection (Priority: MEDIUM)

### 3.1 Add "target subfolder" field

- [ ] **File:** `src/main.py`
- [ ] Add optional `target_subfolder` entry below target directory
- [ ] If set, append to target path: `{target}/{subfolder}`
- [ ] Save in config for persistence

### 3.2 Support relative injection

- [ ] **File:** `src/core/transfer.py`
- [ ] Modify reassembly to use `target_dir + subfolder`
- [ ] **File:** `src/core/reassembly.py`
- [ ] Update `_move_to_final_destination()` to handle subfolder

### 3.3 Quick inject button

- [ ] **File:** `src/main.py`
- [ ] Add "Inject Folder" button next to Transfer
- [ ] Opens dialog to select subsidiary folder
- [ ] Auto-sets source and prompts for subfolder name

---

## Phase 4: Transfer Queue System (Priority: LOW)

### 4.1 Queue data structure

- [ ] **File:** `src/core/transfer_queue.py` (NEW)
- [ ] Create `TransferQueueItem` dataclass: `{source, target, subfolder, status, prepared_path}`
- [ ] Create `TransferQueue` class with add/remove/reorder methods

### 4.2 Queue UI

- [ ] **File:** `src/main.py`
- [ ] Add queue listbox widget
- [ ] Add/Remove/Move Up/Move Down buttons
- [ ] Show status for each item (pending/transferring/done/failed)

### 4.3 Sequential queue execution

- [ ] **File:** `src/main.py`
- [ ] "Start Queue" button to process all items
- [ ] Transfer each item in order
- [ ] Update status as each completes
- [ ] Stop on failure or continue option

### 4.4 Save/Load queue

- [ ] **File:** `src/core/transfer_queue.py`
- [ ] Save queue to JSON file
- [ ] Load queue from JSON file
- [ ] Auto-save on exit if queue not empty

---

## Verification Checklist

- [ ] Folder stats update when changing source directory
- [ ] Transfer stats shown in completion popup
- [ ] Stats match actual transferred data
- [ ] Subsidiary injection works to correct path
- [ ] Queue processes items in order
- [ ] Queue persists between sessions
