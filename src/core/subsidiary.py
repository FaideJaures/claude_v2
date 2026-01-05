# src/core/subsidiary.py
"""Subsidiary folder management for incremental transfers."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SubsidiaryFolder:
    """
    Represents a subsidiary folder to be injected into the main transfer target.
    
    Attributes:
        source_path: Path to the source folder on PC
        injection_path: Where to place contents in target (empty = root merge)
    """
    source_path: str
    injection_path: str = ""
    
    @property
    def name(self) -> str:
        """Get folder name from path."""
        return Path(self.source_path).name
    
    @property
    def prepared_folder(self) -> Path:
        """Get sibling _for_transfer folder path."""
        src = Path(self.source_path)
        return src.parent / f"{src.name}_for_transfer"
    
    @property
    def has_prepared(self) -> bool:
        """Check if _for_transfer folder exists."""
        return self.prepared_folder.exists()
    
    def get_display(self) -> str:
        """Get display string for UI listbox."""
        status = "✓ prêt" if self.has_prepared else "✗ à préparer"
        path = self.injection_path or "(racine)"
        return f"📁 {self.name} → {path} [{status}]"
    
    def to_dict(self) -> dict:
        """Serialize for config storage."""
        return {
            "source_path": self.source_path,
            "injection_path": self.injection_path
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SubsidiaryFolder":
        """Deserialize from config."""
        return cls(
            source_path=data.get("source_path", ""),
            injection_path=data.get("injection_path", "")
        )
