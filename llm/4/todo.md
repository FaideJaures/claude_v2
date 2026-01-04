# Todo List

- [ ] **Fix Quoting in `src/core/transfer.py`**
    - [ ] `mkdir -p` commands
    - [ ] `stat` commands (resume check)
    - [ ] `stat` commands (verification)
    - [ ] `[ -f ]` tests (verification)
    - [ ] `ls` commands
    - [ ] `push` commands (ensure local/remote paths quoted)

- [ ] **Fix Timer in `src/main.py`**
    - [ ] Verify `transfer_start_time` initialization.
    - [ ] Ensure `update_timer` is called on the main thread.

- [ ] **Fix Transfer Folder Structure**
    - [ ] Ensure `process_files` respects the target `output_folder`.
    - [ ] Ensure source directory is not modified when creating a transfer folder.

- [ ] **Optimize Resume Check (Bulk Check)**
    - [ ] Replace per-file `stat` with `ls -Rl` or `find`.
    - [ ] Parse output to build existing file cache.

- [ ] **Verify Reassembly Trigger**
    - [ ] Ensure verification logic handles spaces correctly (part of quoting fix).
    - [ ] Confirm `run_multi_device_transfer` proceeds to Phase 2.
