# WiFi Batch Transfer Enhancement - Implementation Plan

## Executive Summary

Enhance the ADB Transfer Tool to support:

1. **WiFi-based transfers** via ADB over TCP
2. **Batch processing** of fixed device sets with configurable batch sizes
3. **Device tracking** with JSON-based persistence
4. **Headless API** for integration with external Python/web systems

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        ENHANCED ARCHITECTURE                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────────────┐  │
│  │ Device Manager │ ←→ │ Batch Processor │ ←→ │ TransferService (API)  │  │
│  │  (WiFi + USB)  │    │ (Queue + Pool)  │    │ (Headless Core Logic)  │  │
│  └────────────────┘    └────────────────┘    └────────────────────────┘  │
│          ↓                     ↓                         ↓               │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────────────┐  │
│  │ devices.json   │    │ history.json   │    │  Existing Core Modules │  │
│  │ (Known Devices)│    │ (Processed)    │    │  (transfer.py, etc.)   │  │
│  └────────────────┘    └────────────────┘    └────────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     │                           │
              ┌──────┴──────┐            ┌───────┴──────┐
              │  GUI Mode   │            │ CLI / Python │
              │  (main.py)  │            │ Integration  │
              └─────────────┘            └──────────────┘
```

---

## Phase 1: WiFi Support & Core Refactoring

### 1.1 WiFi Connection Support

#### [MODIFY] [adb.py](file:///c:/Users/hp/Desktop/claude_v2/src/utils/adb.py)

Add WiFi connection methods:

```python
class Adb:
    # Existing methods...

    def enable_tcpip(self, device_id: str, port: int = 5555) -> bool:
        """Enable TCP/IP mode on a USB-connected device."""
        result = self.run_command(f"tcpip {port}", device_id)
        return result is not None

    def connect_wifi(self, ip: str, port: int = 5555) -> bool:
        """Connect to a device over WiFi."""
        result = self.run_command(f"connect {ip}:{port}")
        if result:
            return any("connected" in line.lower() for line in result)
        return False

    def disconnect_wifi(self, ip: str, port: int = 5555) -> bool:
        """Disconnect from a WiFi device."""
        result = self.run_command(f"disconnect {ip}:{port}")
        return result is not None

    def get_device_ip(self, device_id: str) -> str | None:
        """Get IP address of a USB-connected device."""
        result = self.run_command("shell ip route | grep wlan0 | awk '{print $9}'", device_id)
        if result and result[0]:
            return result[0].strip()
        return None
```

---

### 1.2 TransferService API (Headless Core)

#### [NEW] [transfer_service.py](file:///c:/Users/hp/Desktop/claude_v2/src/api/transfer_service.py)

Decoupled service layer for external integration:

```python
"""
TransferService - Headless API for file transfers.

Usage (Python):
    from api.transfer_service import TransferService

    service = TransferService()

    # Single device transfer
    result = service.transfer_to_device(
        source="/path/to/files",
        target="/sdcard/Download",
        device_id="192.168.1.100:5555"
    )

    # Batch transfer
    results = service.batch_transfer(
        source="/path/to/files",
        target="/sdcard/Download",
        device_ids=["192.168.1.100:5555", "192.168.1.101:5555"],
        batch_size=5
    )
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable
import json
from pathlib import Path

class TransferStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class TransferResult:
    device_id: str
    status: TransferStatus
    files_transferred: int = 0
    bytes_transferred: int = 0
    duration_seconds: float = 0
    error_message: str | None = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

class TransferService:
    def __init__(self, config: dict = None, logger=None):
        self.config = config or self._load_default_config()
        self.logger = logger or NullLogger()
        # Import existing core modules
        from core.transfer import TransferManager
        self.transfer_manager = TransferManager(self.config, self.logger)

    def transfer_to_device(self, source: str, target: str, device_id: str) -> TransferResult:
        """Transfer files to a single device."""
        pass

    def batch_transfer(
        self,
        source: str,
        target: str,
        device_ids: list[str],
        batch_size: int = 5,
        on_device_complete: Callable[[TransferResult], None] = None
    ) -> list[TransferResult]:
        """Transfer to multiple devices in batches."""
        pass

    def connect_device_wifi(self, ip: str, port: int = 5555) -> bool:
        """Connect to a device over WiFi."""
        pass

    def get_connected_devices(self) -> list[dict]:
        """Get all connected devices (USB + WiFi)."""
        pass
```

---

### 1.3 CLI Interface

#### [NEW] [cli.py](file:///c:/Users/hp/Desktop/claude_v2/src/cli.py)

Command-line interface for automation:

```python
"""
ADB Transfer Tool - CLI

Usage:
    python cli.py transfer --source C:\Files --target /sdcard/Download --devices 192.168.1.100
    python cli.py batch --source C:\Files --target /sdcard/Download --batch-size 5
    python cli.py devices --list
    python cli.py devices --connect 192.168.1.100
"""
import argparse
from api.transfer_service import TransferService

def main():
    parser = argparse.ArgumentParser(description="ADB Transfer Tool CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Transfer command
    transfer_parser = subparsers.add_parser("transfer", help="Transfer files to device(s)")
    transfer_parser.add_argument("--source", required=True)
    transfer_parser.add_argument("--target", required=True)
    transfer_parser.add_argument("--devices", nargs="+", required=True)

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Batch transfer to all known devices")
    batch_parser.add_argument("--source", required=True)
    batch_parser.add_argument("--target", required=True)
    batch_parser.add_argument("--batch-size", type=int, default=5)

    # Devices command
    devices_parser = subparsers.add_parser("devices", help="Manage devices")
    devices_parser.add_argument("--list", action="store_true")
    devices_parser.add_argument("--connect", metavar="IP")
    devices_parser.add_argument("--add", metavar="IP")

    args = parser.parse_args()
    # Handle commands...
```

---

## Phase 2: Batch Processing & Device Management

### 2.1 Device Manager

#### [NEW] [device_manager.py](file:///c:/Users/hp/Desktop/claude_v2/src/core/device_manager.py)

Manages a fixed set of known devices:

```python
"""
DeviceManager - Manages fixed device sets with WiFi support.

Storage: data/devices.json
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json

@dataclass
class Device:
    id: str                          # IP:port or USB serial
    name: str                        # Friendly name
    ip: str | None = None            # IP address for WiFi
    port: int = 5555                 # ADB port
    connection_type: str = "wifi"    # "usb" or "wifi"
    is_active: bool = True           # Include in batch operations
    last_seen: str | None = None     # Last successful connection
    last_transfer: str | None = None # Last successful transfer

class DeviceManager:
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.devices_file = self.data_dir / "devices.json"
        self.devices: dict[str, Device] = {}
        self._load()

    def add_device(self, name: str, ip: str, port: int = 5555) -> Device:
        """Add a new WiFi device to the known set."""
        device = Device(
            id=f"{ip}:{port}",
            name=name,
            ip=ip,
            port=port,
            connection_type="wifi"
        )
        self.devices[device.id] = device
        self._save()
        return device

    def remove_device(self, device_id: str) -> bool:
        """Remove a device from the known set."""
        if device_id in self.devices:
            del self.devices[device_id]
            self._save()
            return True
        return False

    def get_active_devices(self) -> list[Device]:
        """Get all devices marked as active."""
        return [d for d in self.devices.values() if d.is_active]

    def update_last_transfer(self, device_id: str):
        """Mark device as successfully transferred."""
        if device_id in self.devices:
            self.devices[device_id].last_transfer = datetime.now().isoformat()
            self._save()

    def _load(self):
        """Load devices from JSON file."""
        if self.devices_file.exists():
            data = json.loads(self.devices_file.read_text())
            self.devices = {d["id"]: Device(**d) for d in data.get("devices", [])}

    def _save(self):
        """Save devices to JSON file."""
        data = {"devices": [asdict(d) for d in self.devices.values()]}
        self.devices_file.write_text(json.dumps(data, indent=2))
```

---

### 2.2 Batch Processor

#### [NEW] [batch_processor.py](file:///c:/Users/hp/Desktop/claude_v2/src/core/batch_processor.py)

Processes devices in configurable batches:

```python
"""
BatchProcessor - Processes devices in configurable batches.

Example:
    processor = BatchProcessor(batch_size=5)
    results = processor.process_all(
        source="/path/to/files",
        target="/sdcard/Download",
        on_batch_complete=lambda batch: print(f"Batch done: {len(batch)} devices")
    )
"""
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable
import time

@dataclass
class BatchConfig:
    batch_size: int = 5                    # Devices per batch
    max_parallel_per_device: int = 4       # Parallel transfers per device
    inter_batch_delay: float = 2.0         # Seconds between batches
    retry_failed: bool = True              # Retry failed devices
    max_retries: int = 2                   # Max retry attempts

class BatchProcessor:
    def __init__(self, config: BatchConfig = None, transfer_service=None, device_manager=None):
        self.config = config or BatchConfig()
        self.transfer_service = transfer_service
        self.device_manager = device_manager
        self._cancelled = False

    def process_all(
        self,
        source: str,
        target: str,
        on_device_complete: Callable = None,
        on_batch_complete: Callable = None
    ) -> list:
        """Process all active devices in batches."""
        devices = self.device_manager.get_active_devices()
        results = []

        # Split into batches
        batches = [
            devices[i:i + self.config.batch_size]
            for i in range(0, len(devices), self.config.batch_size)
        ]

        for batch_num, batch in enumerate(batches, 1):
            if self._cancelled:
                break

            batch_results = self._process_batch(batch, source, target, on_device_complete)
            results.extend(batch_results)

            if on_batch_complete:
                on_batch_complete(batch_results, batch_num, len(batches))

            # Delay between batches (except for last)
            if batch_num < len(batches):
                time.sleep(self.config.inter_batch_delay)

        return results

    def _process_batch(self, devices: list, source: str, target: str, on_complete: Callable) -> list:
        """Process a single batch of devices in parallel."""
        results = []

        with ThreadPoolExecutor(max_workers=len(devices)) as executor:
            futures = {
                executor.submit(self._transfer_to_device, d, source, target): d
                for d in devices
            }

            for future in as_completed(futures):
                device = futures[future]
                result = future.result()
                results.append(result)

                if on_complete:
                    on_complete(result)

        return results

    def _transfer_to_device(self, device, source: str, target: str):
        """Transfer to a single device with connection handling."""
        # 1. Connect if WiFi device
        # 2. Transfer files
        # 3. Update device manager
        pass

    def cancel(self):
        """Cancel batch processing."""
        self._cancelled = True
```

---

### 2.3 Transfer History

#### [NEW] [history_manager.py](file:///c:/Users/hp/Desktop/claude_v2/src/core/history_manager.py)

Persists transfer history to JSON:

```python
"""
HistoryManager - Tracks processed devices and transfer history.

Storage: data/history.json
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json

@dataclass
class TransferRecord:
    device_id: str
    device_name: str
    source_path: str
    target_path: str
    status: str                      # "completed", "failed"
    files_count: int
    bytes_transferred: int
    duration_seconds: float
    started_at: str
    completed_at: str
    error_message: str | None = None

class HistoryManager:
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.history_file = self.data_dir / "history.json"
        self.records: list[TransferRecord] = []
        self._load()

    def add_record(self, record: TransferRecord):
        """Add a completed transfer record."""
        self.records.append(record)
        self._save()

    def get_recent(self, limit: int = 50) -> list[TransferRecord]:
        """Get most recent transfer records."""
        return sorted(self.records, key=lambda r: r.started_at, reverse=True)[:limit]

    def get_by_device(self, device_id: str) -> list[TransferRecord]:
        """Get all records for a specific device."""
        return [r for r in self.records if r.device_id == device_id]

    def get_failed(self) -> list[TransferRecord]:
        """Get all failed transfers."""
        return [r for r in self.records if r.status == "failed"]

    def clear_old_records(self, days: int = 30):
        """Remove records older than N days."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        self.records = [
            r for r in self.records
            if datetime.fromisoformat(r.started_at).timestamp() > cutoff
        ]
        self._save()

    def _load(self):
        if self.history_file.exists():
            data = json.loads(self.history_file.read_text())
            self.records = [TransferRecord(**r) for r in data.get("records", [])]

    def _save(self):
        data = {"records": [asdict(r) for r in self.records]}
        self.history_file.write_text(json.dumps(data, indent=2, default=str))
```

---

## Phase 3: Storage Structure

### Data Directory Layout

```
data/
├── devices.json      # Known device set
├── history.json      # Transfer history
└── config.json       # Runtime configuration (optional override)
```

### devices.json Example

```json
{
  "devices": [
    {
      "id": "192.168.1.100:5555",
      "name": "Warehouse Phone 1",
      "ip": "192.168.1.100",
      "port": 5555,
      "connection_type": "wifi",
      "is_active": true,
      "last_seen": "2025-12-31T10:30:00",
      "last_transfer": "2025-12-31T09:15:00"
    },
    {
      "id": "192.168.1.101:5555",
      "name": "Warehouse Phone 2",
      "ip": "192.168.1.101",
      "port": 5555,
      "connection_type": "wifi",
      "is_active": true,
      "last_seen": "2025-12-31T10:30:00",
      "last_transfer": null
    }
  ]
}
```

### history.json Example

```json
{
  "records": [
    {
      "device_id": "192.168.1.100:5555",
      "device_name": "Warehouse Phone 1",
      "source_path": "C:\\Files\\MediaBundle",
      "target_path": "/sdcard/Download",
      "status": "completed",
      "files_count": 150,
      "bytes_transferred": 524288000,
      "duration_seconds": 45.2,
      "started_at": "2025-12-31T09:14:00",
      "completed_at": "2025-12-31T09:14:45",
      "error_message": null
    }
  ]
}
```

---

## New Project Structure

```
src/
├── main.py                    # Existing GUI (updated to use new modules)
├── cli.py                     # [NEW] Command-line interface
├── config.py                  # Existing configuration
│
├── api/
│   └── transfer_service.py    # [NEW] Headless API layer
│
├── core/
│   ├── transfer.py           # Existing (minor updates)
│   ├── file_chunker.py       # Existing (no changes)
│   ├── reassembly.py         # Existing (no changes)
│   ├── device_manager.py     # [NEW] Device set management
│   ├── batch_processor.py    # [NEW] Batch processing logic
│   └── history_manager.py    # [NEW] Transfer history
│
├── utils/
│   ├── adb.py                # Existing (add WiFi methods)
│   ├── termux.py             # Existing (no changes)
│   └── updater.py            # Existing (no changes)
│
└── ui/
    └── modal_dialog.py       # Existing (no changes)

data/                          # [NEW] Runtime data directory
├── devices.json
└── history.json
```

---

## Usage Examples

### Python Integration

```python
from api.transfer_service import TransferService
from core.device_manager import DeviceManager

# Setup
service = TransferService()
device_mgr = DeviceManager()

# Add devices to the fixed set
device_mgr.add_device("Phone 1", "192.168.1.100")
device_mgr.add_device("Phone 2", "192.168.1.101")
device_mgr.add_device("Phone 3", "192.168.1.102")

# Batch transfer to all devices
results = service.batch_transfer(
    source="C:\\Files\\MediaBundle",
    target="/sdcard/Download",
    device_ids=[d.id for d in device_mgr.get_active_devices()],
    batch_size=5
)

# Check results
for result in results:
    print(f"{result.device_id}: {result.status.value}")
```

### CLI Usage

```bash
# Add devices
python cli.py devices --add "Phone 1:192.168.1.100"
python cli.py devices --add "Phone 2:192.168.1.101"

# List devices
python cli.py devices --list

# Batch transfer to all active devices
python cli.py batch --source "C:\Files" --target "/sdcard/Download" --batch-size 5

# Transfer to specific devices
python cli.py transfer --source "C:\Files" --target "/sdcard/Download" --devices 192.168.1.100 192.168.1.101
```

---

## Verification Plan

### Automated Tests

Since there are no existing unit tests in the codebase, verification will be manual.

### Manual Verification Steps

#### 1. WiFi Connection Test

```bash
# Step 1: Connect phone via USB, enable WiFi debugging
adb tcpip 5555

# Step 2: Disconnect USB, note the phone's IP address
adb shell ip route | grep wlan0 | awk '{print $9}'

# Step 3: Test connection
adb connect <IP>:5555
adb devices  # Should show <IP>:5555 as device
```

#### 2. Batch Processing Test

1. Add 3+ WiFi devices via CLI or devices.json
2. Run batch transfer with batch_size=2
3. Verify:
   - First 2 devices process in parallel
   - Delay between batches
   - All devices receive files

#### 3. History Persistence Test

1. Run a transfer
2. Check `data/history.json` contains the record
3. Restart app, verify history is loaded

---

## Next Steps

1. **Approve this plan**
2. I will implement in this order:
   - Phase 1: WiFi support in `adb.py`
   - Phase 1: `TransferService` API
   - Phase 1: CLI interface
   - Phase 2: Device & History managers
   - Phase 2: Batch processor
