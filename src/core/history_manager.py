"""
Transfer History Manager - Saves transfer records to JSON file.
"""
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class TransferRecord:
    """A single transfer record."""
    process_name: str
    device_id: str
    device_bluetooth_name: str
    status: str  # "completed" or "failed"
    files_count: int
    bytes_transferred: int
    duration_seconds: float
    started_at: str  # ISO format
    completed_at: str  # ISO format
    phases: dict  # {"phase1_start": "...", "phase1_end": "...", etc.}


class HistoryManager:
    """Manages transfer history persistence."""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.history_file = self.data_dir / "transfer_history.json"
        self.records: List[TransferRecord] = []
        self._load()

    def _load(self):
        """Load existing records from JSON file."""
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text(encoding='utf-8'))
                self.records = [TransferRecord(**r) for r in data.get("records", [])]
            except Exception:
                self.records = []

    def _save(self):
        """Save records to JSON file."""
        data = {"records": [asdict(r) for r in self.records]}
        self.history_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding='utf-8'
        )

    def add_record(self, record: TransferRecord):
        """Add a new transfer record."""
        self.records.append(record)
        self._save()

    def get_recent(self, limit: int = 50) -> List[TransferRecord]:
        """Get most recent records."""
        return sorted(self.records, key=lambda r: r.started_at, reverse=True)[:limit]

    def get_by_process(self, process_name: str) -> List[TransferRecord]:
        """Get all records for a specific process."""
        return [r for r in self.records if r.process_name == process_name]
