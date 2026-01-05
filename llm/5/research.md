# Transfer Bug Analysis - Session 5

## Date: 2026-01-05

## Issues Identified from Logs

### Critical Bug 1: Stale Manifests Being Loaded

**Symptom:**

```
[23:51:00] 11 manifestes chargés.  ← New folder has 0 chunk manifests
[23:50:53] 0 fichiers à fragmenter.  ← The NEW folder has NO files to chunk
```

**Root Cause:**

- `transfer_from_prepared_folder()` loads manifests from `transfer_state.json`
- When user prepares a NEW folder (test_for_transfer), the old `transfer_state.json` from a previous Video transfer is being loaded
- The `prepare_transfer()` method should completely replace the state file, not append

**Location:** `src/core/transfer.py` - `transfer_from_prepared_folder()` and `prepare_transfer()`

---

### Critical Bug 2: All Chunks Missing After Transfer

**Symptom:**

```
[23:50:04] Transfert de 11 fichiers avec 10 workers...
[23:50:04] Transfert terminé: 11 fichiers
[23:50:05] 2 chunks manquants dans Screen Recording 2025-03-07 024014_chunks
... ALL chunks are missing!
```

**Root Cause:**

- Bundles (ZIP files) transfer successfully
- But chunk files fail to transfer
- The `mkdir -p` for remote chunk directories likely fails due to unescaped spaces
- Or the `adb push` command fails silently for paths with spaces

**Location:** `src/core/transfer.py` - `parallel_transfer()` lines 400-420

---

### Critical Bug 3: Windows Backslash in Remote Path

**Symptom:**

```
[23:50:06] 3 chunks manquants dans brawl_montage\bh_ranked_reddit_idle_chunks:
                                               ^ BACKSLASH should be /
```

**Root Cause:**

- The `chunk_folder` from manifest contains Windows-style backslash
- When constructing `remote_chunk_dir`, the `.replace('\\', '/')` isn't catching all cases
- The manifest itself may have stored the path with backslashes

**Location:**

- `src/core/transfer.py` - `parallel_transfer()` line 398
- `src/core/file_chunker.py` - where manifest is created

---

## Fix Plan

### Fix 1: Reset manifestsbefore new preparation

- In `prepare_transfer()`, ensure `self.manifests = []` is called BEFORE scanning
- The `transfer_state.json` should only contain manifests from the current preparation

### Fix 2: Ensure remote directories are created with proper escaping

- The `mkdir -p` command needs proper quoting for paths with spaces
- Already added `_escape_shell_path()` but need to verify it's being used for mkdir

### Fix 3: Normalize paths in manifest to use forward slashes

- When storing `chunk_folder` in manifest, convert all `\` to `/`
- When reading manifest, also normalize paths

### Fix 4: Verify push commands work for paths with spaces

- ADB push should handle spaces in paths if properly quoted
- May need to escape the remote path in push command

---

## Files to Modify

1. `src/core/transfer.py`

   - `prepare_transfer()` - reset manifests
   - `parallel_transfer()` - verify mkdir and push escaping
   - `_verify_transfer_on_device()` - path normalization

2. `src/core/file_chunker.py`
   - Ensure chunk_folder uses forward slashes in manifest

---

## Fixes Applied

### Fix 1: Reset manifests before scanning ✅

**File:** `src/core/transfer.py` - `prepare_transfer()`

```python
# CRITICAL: Reset all lists before scanning to avoid stale data
self.manifests = []
self.files_to_chunk = []
self.files_to_batch = []
```

### Fix 2: Normalize paths when saving state ✅

**File:** `src/core/transfer.py` - `prepare_transfer()`

- All paths now converted to forward slashes before saving to `transfer_state.json`

### Fix 3: Normalize paths when loading manifests ✅

**File:** `src/core/transfer.py` - `transfer_from_prepared_folder()`

- Paths normalized after loading
- File lists cleared to prevent stale chunk data

### Fix 4: Normalize paths at source ✅

**File:** `src/core/file_chunker.py` - `chunk_file()`

- `original_file`, `chunk_folder`, and `persistent_source` all normalized to forward slashes
