# TODO - ADB Transfer Tool Refactor

## Priority 1: Logger Scroll Fix 🔧

- [ ] Modify `log()` in `main.py` to check scroll position before auto-scrolling
- [ ] Test with real transfer to verify behavior
- File: `src/main.py`, line 1833-1835

## Priority 2: ADB-Only Transfer Fix 🐛

- [ ] Add debug logging to `reassemble_via_adb_shell()`
- [ ] Check if `unified.sh` creates marker file correctly
- [ ] Verify script execution with `sh` (not bash)
- [ ] Capture reassembly script output instead of `/dev/null`
- [ ] Test full ADB-only flow on real device
- Files: `src/core/reassembly.py`, `src/utils/unified.sh`

## Priority 3: Transfer Folder Factorization 🆕

- [ ] Create `TransferFolderManager` class in new file
- [ ] Add "Créer Dossier Transfer" button
- [ ] Add "Supprimer Dossier Transfer" button
- [ ] Add settings option to auto-use transfer folder
- [ ] Integrate with transfer flow
- Files: `src/utils/folder_manager.py` (new), `src/main.py`

---

## Quick Reference

| Task           | File(s)                    | Complexity | Est. Time |
| -------------- | -------------------------- | ---------- | --------- |
| Logger Scroll  | main.py                    | Low        | 15 min    |
| ADB Debug      | reassembly.py, unified.sh  | Medium     | 1-2 hrs   |
| Folder Feature | folder_manager.py, main.py | Medium     | 1 hr      |
