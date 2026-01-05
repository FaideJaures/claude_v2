# Implementation Plan: Multi-Subsidiary Transfer

## Overview

Enable transferring multiple subsidiary folders alongside the main folder, each with its own injection path. Reuse pre-prepared `_for_transfer` folders for maximum efficiency.

---

## Architecture

```
Main Transfer:
  📁 Source/           →  📱 target/
  📁 Source_for_transfer/  (if exists, use it)

Subsidiary Transfers:
  📁 Subsidiary1/      →  📱 target/{injection_path1}
  📁 Subsidiary1_for_transfer/  (sibling, if exists)

  📁 Subsidiary2/      →  📱 target/{injection_path2}
  📁 Subsidiary2_for_transfer/  (sibling, if exists)
```

---

## File Changes

### [NEW] `src/core/subsidiary.py`

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SubsidiaryFolder:
    source_path: str
    injection_path: str = ""  # Empty = merge at root

    @property
    def name(self) -> str:
        return Path(self.source_path).name

    @property
    def prepared_folder(self) -> Path:
        """Sibling _for_transfer folder."""
        src = Path(self.source_path)
        return src.parent / f"{src.name}_for_transfer"

    @property
    def has_prepared(self) -> bool:
        return self.prepared_folder.exists()

    def get_display(self) -> str:
        status = "✓" if self.has_prepared else "✗"
        path = self.injection_path or "(racine)"
        return f"📁 {self.name} → {path} [{status}]"
```

---

### [MODIFY] `src/main.py`

#### UI Changes

1. Remove `target_subfolder` entry (lines ~547-553)
2. Add `subsidiaries: list[SubsidiaryFolder] = []`
3. Add subsidiary list panel with Listbox
4. Add buttons: Ajouter, Supprimer, Préparer

#### New Methods

```python
def _add_subsidiary(self):
    """Open dialog to add a subsidiary folder."""
    folder = filedialog.askdirectory(title="Sélectionner dossier subsidiaire")
    if folder:
        injection = simpledialog.askstring(
            "Chemin d'injection",
            "Où placer ce dossier dans la cible?\n(vide = racine)",
            initialvalue=""
        ) or ""
        sub = SubsidiaryFolder(folder, injection)
        self.subsidiaries.append(sub)
        self._refresh_subsidiary_list()

def _remove_subsidiary(self):
    """Remove selected subsidiary from list."""
    ...

def _prepare_subsidiary(self):
    """Create _for_transfer for selected subsidiary."""
    ...

def _refresh_subsidiary_list(self):
    """Update the subsidiary listbox display."""
    self.subsidiary_listbox.delete(0, tk.END)
    for sub in self.subsidiaries:
        self.subsidiary_listbox.insert(tk.END, sub.get_display())
```

#### Transfer Logic Update

```python
# In start_transfer_thread():
# After main transfer completes:
for sub in self.subsidiaries:
    sub_target = f"{target}/{sub.injection_path}".replace("//", "/")
    if sub.has_prepared:
        self.transfer_manager.transfer_from_prepared_folder(
            sub.prepared_folder, sub_target, device_id)
    else:
        self.transfer_manager.start_transfer(
            sub.source_path, sub_target, device_id)
```

---

### [MODIFY] `src/core/transfer.py`

No major changes needed - existing methods handle:

- `transfer_from_prepared_folder()` for prepared subsidiaries
- `start_transfer()` for unprepared subsidiaries
- `prepare_transfer()` for creating `_for_transfer`

---

## Verification Plan

1. **UI Test**: Add/remove subsidiaries, verify list updates
2. **Detection Test**: Add folder with existing `_for_transfer`, verify ✓ status
3. **Prepare Test**: Use "Préparer" button, verify folder created
4. **Transfer Test**: Run transfer with multiple subsidiaries
5. **Device Check**: Verify files appear in correct injection paths
