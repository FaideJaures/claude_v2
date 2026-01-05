# Implementation Plan: Statistics & Queue System

## Overview

This plan implements three major features for the ADB Transfer Tool:

1. **Folder Statistics** - Show file/size info when selecting source folder
2. **Transfer Statistics** - Show speed/duration after transfer completes
3. **Transfer Queue** - Manage multiple transfers with subsidiary folder injection

---

## Phase 1: Folder Statistics

### 1.1 Create `analyze_folder()` Method

**File:** `src/core/transfer.py`

Add new method to `TransferManager` class:

```python
def analyze_folder(self, source_dir: str) -> dict:
    """
    Analyze a folder without modifying internal state.
    Returns statistics about what would be transferred.
    """
    # Create temporary lists (don't touch self.files_to_chunk etc.)
    files_to_chunk = []
    files_to_batch = []
    total_size = 0

    chunk_threshold = self.config.get("chunk_threshold_bytes", 100 * 1024 * 1024)

    source_path = Path(source_dir)
    for file_path in source_path.rglob("*"):
        if file_path.is_file():
            size = file_path.stat().st_size
            total_size += size
            if size >= chunk_threshold:
                files_to_chunk.append((file_path, size))
            else:
                files_to_batch.append((file_path, size))

    # Estimate chunks (100MB each)
    chunk_size = self.config.get("chunk_size_bytes", 100 * 1024 * 1024)
    estimated_chunks = sum(
        (size + chunk_size - 1) // chunk_size
        for _, size in files_to_chunk
    )

    # Estimate bundles (100MB each)
    bundle_size = self.config.get("bundle_size_mb", 100) * 1024 * 1024
    small_total = sum(size for _, size in files_to_batch)
    estimated_bundles = max(1, (small_total + bundle_size - 1) // bundle_size) if files_to_batch else 0

    return {
        "total_files": len(files_to_chunk) + len(files_to_batch),
        "total_size_bytes": total_size,
        "large_files_count": len(files_to_chunk),
        "small_files_count": len(files_to_batch),
        "estimated_chunks": estimated_chunks,
        "estimated_bundles": estimated_bundles,
    }
```

### 1.2 Add Stats Display to UI

**File:** `src/main.py`

In `create_widgets()`, after the source directory frame, add:

```python
# Folder stats label
self.folder_stats_label = tk.Label(
    source_frame,
    text="Sélectionnez un dossier source",
    fg="gray"
)
self.folder_stats_label.pack(anchor="w", padx=5)

# Trace source directory changes
self.source_dir.trace_add("write", self._on_source_changed)
```

Add callback method:

```python
def _on_source_changed(self, *args):
    """Update folder stats when source directory changes."""
    source = self.source_dir.get()
    if source and Path(source).exists():
        threading.Thread(
            target=self._analyze_and_display_stats,
            args=(source,),
            daemon=True
        ).start()
    else:
        self.folder_stats_label.config(
            text="Sélectionnez un dossier source",
            fg="gray"
        )

def _analyze_and_display_stats(self, source: str):
    """Analyze folder and update stats label (background thread)."""
    try:
        stats = self.transfer_manager.analyze_folder(source)
        size_str = self._format_size(stats["total_size_bytes"])
        text = (
            f"{stats['total_files']} fichiers | {size_str} | "
            f"{stats['large_files_count']} gros ({stats['estimated_chunks']} chunks) | "
            f"{stats['small_files_count']} petits ({stats['estimated_bundles']} bundles)"
        )
        self.master.after(0, lambda: self.folder_stats_label.config(text=text, fg="black"))
    except Exception as e:
        self.master.after(0, lambda: self.folder_stats_label.config(text=f"Erreur: {e}", fg="red"))

def _format_size(self, size_bytes: int) -> str:
    """Format bytes to human readable string."""
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / (1024**3):.2f} GB"
    elif size_bytes >= 1024 ** 2:
        return f"{size_bytes / (1024**2):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} B"
```

---

## Phase 2: Transfer Statistics

### 2.1 Create TransferStats Dataclass

**File:** `src/core/transfer.py`

Add at top of file after imports:

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TransferStats:
    """Statistics for a completed transfer."""
    start_time: float = 0.0
    end_time: float = 0.0
    bytes_transferred: int = 0
    files_count: int = 0
    chunks_count: int = 0
    bundles_count: int = 0
    device_id: str = ""

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time

    @property
    def speed_mbps(self) -> float:
        if self.duration_seconds > 0:
            return (self.bytes_transferred / (1024 * 1024)) / self.duration_seconds
        return 0.0

    def format_summary(self) -> str:
        duration = self.duration_seconds
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        size_mb = self.bytes_transferred / (1024 * 1024)
        return (
            f"Durée: {minutes}m {seconds}s\n"
            f"Vitesse: {self.speed_mbps:.2f} MB/s\n"
            f"Fichiers: {self.files_count}\n"
            f"Données: {size_mb:.2f} MB"
        )
```

### 2.2 Update `parallel_transfer()` to Return Stats

**File:** `src/core/transfer.py`

Modify `parallel_transfer()` to track and return stats:

```python
def parallel_transfer(self, remote_temp_dir, device_id) -> Optional[TransferStats]:
    """Transfer files in parallel to device. Returns TransferStats on success."""
    stats = TransferStats(
        start_time=time.time(),
        device_id=device_id
    )

    # ... existing transfer logic ...

    # After successful transfer, populate stats
    stats.end_time = time.time()
    stats.bytes_transferred = sum(size for _, _, size in files_to_transfer)
    stats.files_count = len(files_to_transfer)
    stats.chunks_count = sum(1 for f, _, _ in files_to_transfer if 'chunk_' in str(f))
    stats.bundles_count = sum(1 for f, _, _ in files_to_transfer if 'bundle_' in str(f))

    self._last_transfer_stats = stats  # Store for later retrieval
    return stats
```

### 2.3 Display Stats in Completion Popup

**File:** `src/main.py`

Modify `_cleanup_transfer_ui()`:

```python
def _cleanup_transfer_ui(self, success_count=None, total_count=None, stats: TransferStats = None):
    """Reset UI state after transfer ends."""
    # ... existing cleanup code ...

    # Show completion notification with stats
    if success_count is not None and total_count is not None:
        duration_str = f"{int(elapsed//60)}m {int(elapsed%60)}s"

        # Build stats message
        stats_msg = f"Durée: {duration_str}"
        if stats:
            stats_msg = stats.format_summary()

        if success_count == total_count:
            self.master.after(0, lambda: messagebox.showinfo(
                "Transfert Terminé ✓",
                f"Transfert réussi sur {success_count}/{total_count} appareil(s).\n\n{stats_msg}"
            ))
        # ... rest of conditions ...
```

---

## Phase 3: Subsidiary Folder Injection

### 3.1 Add Target Subfolder Field

**File:** `src/main.py`

In `create_widgets()`, after target directory:

```python
# Target subfolder (optional)
subfolder_frame = tk.Frame(target_frame)
subfolder_frame.pack(fill=tk.X)
tk.Label(subfolder_frame, text="Sous-dossier (opt.):").pack(side=tk.LEFT)
self.target_subfolder = tk.StringVar()
self.subfolder_entry = tk.Entry(subfolder_frame, textvariable=self.target_subfolder, width=30)
self.subfolder_entry.pack(side=tk.LEFT, padx=5)
tk.Label(subfolder_frame, text="(ex: data/2024)", fg="gray").pack(side=tk.LEFT)
```

### 3.2 Update Transfer to Use Subfolder

**File:** `src/main.py`

In `run_transfer()`, construct full target:

```python
target = self.target_dir.get()
subfolder = self.target_subfolder.get().strip()
if subfolder:
    target = f"{target}/{subfolder}".replace("\\", "/")
```

---

## Phase 4: Transfer Queue System (Deferred)

> **Note:** This phase is lower priority and will be implemented after the core statistics features are complete and tested.

### Components:

1. `TransferQueueItem` dataclass
2. `TransferQueue` class with persistence
3. Queue UI (listbox, buttons)
4. Sequential execution logic

### Files to Create:

- `src/core/transfer_queue.py`

### Files to Modify:

- `src/main.py` (add queue panel)
- `src/config.py` (add queue settings)

---

## Testing Checklist

### Phase 1 Tests:

- [ ] Stats appear when selecting folder with files
- [ ] Stats update when changing source folder
- [ ] Stats show correct file count and size
- [ ] UI doesn't freeze during analysis

### Phase 2 Tests:

- [ ] Stats calculated correctly after transfer
- [ ] Speed calculation is accurate
- [ ] Stats shown in completion popup
- [ ] Stats logged to console

### Phase 3 Tests:

- [ ] Subfolder field accepts input
- [ ] Files extracted to correct subdirectory on device
- [ ] Empty subfolder works (root target)
