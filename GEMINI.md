# ADB Transfer Tool - Context & Documentation

## 1. Project Overview
**ADB Transfer Tool** is a high-performance Python application designed to optimize file transfers between a PC and Android devices via ADB (Android Debug Bridge). It addresses the performance bottlenecks of standard `adb push` by implementing:
- **Smart Chunking:** Splits large files (>100MB) into smaller chunks for parallel transfer.
- **Small File Bundling:** Groups small files (<10MB) into ZIP bundles to reduce protocol overhead.
- **Parallel Transfer:** Uses multiple threads/processes to saturate USB bandwidth.
- **Multi-Device Support:** Can transfer to multiple connected devices simultaneously.

## 2. Technical Stack
- **Language:** Python 3.10+
- **GUI Framework:** Tkinter (Standard Python GUI)
- **Core Dependency:** ADB (Android Debug Bridge) - must be in system PATH or provided in `platform-tools`.
- **Packaging:** PyInstaller (generates single-file executable).
- **Target OS:** Windows (primary), but Python code is likely cross-platform (Linux/macOS support possible if ADB is available).

## 3. Project Architecture

### Directory Structure
```
claude_v2/
├── src/
│   ├── main.py              # Entry point & Main GUI Controller
│   ├── config.py            # Default configuration constants
│   ├── core/
│   │   ├── transfer.py      # Core transfer logic & parallel orchestration
│   │   ├── file_chunker.py  # File splitting logic
│   │   ├── reassembly.py    # Logic for reassembling files on Android
│   │   └── subsidiary.py    # Handling of subsidiary folders
│   ├── ui/
│   │   ├── modal_dialog.py  # Dialog windows (progress, confirmation)
│   │   └── ...
│   └── utils/
│       ├── adb.py           # ADB command wrapper
│       ├── termux.py        # Termux interaction helpers
│       ├── tools_manager.py # Management of external tools
│       └── folder_manager.py# Folder preparation logic
├── apk/                     # Contains helper APKs (e.g., Termux)
├── build.bat                # Build script for Windows
├── adb_transfer.spec        # PyInstaller specification file
└── README.md                # General user documentation
```

### Key Modules
- **`src/main.py`:** Initializes the Tkinter application, handles UI events, and orchestrates the transfer process. It manages the device list and configuration window.
- **`src/core/transfer.py`:** The brain of the operation. It scans directories, decides whether to chunk or bundle files, and manages the worker pools for parallel transfer.
- **`src/core/reassembly.py`:** Handles the operations on the Android device side, either via direct `adb shell` commands or by orchestrating scripts inside Termux.
- **`src/utils/adb.py`:** A wrapper class around the `adb` executable to execute commands and parse output.

## 4. Development Workflow

### Prerequisites
1.  Python 3.10 or higher.
2.  `adb` installed and accessible in the system PATH.
3.  Standard Python libraries (mostly built-in), plus any specified in `requirements.txt` (if present, otherwise standard lib + `tkinter` which is usually included).

### Running from Source
```bash
cd src
python main.py
```

### Building the Executable
The project uses `PyInstaller` to create a standalone `.exe`.
```batch
# Run the build script
build.bat
# OR directly via PyInstaller
pyinstaller adb_transfer.spec
```
Output will be in `dist/ADB_Transfer_Tool.exe`.

## 5. Key Features & logic
- **SJF Scheduling:** Shortest Job First scheduling is used to prioritize small files, giving faster feedback to the user.
- **Resume Capability:** Checks for existing chunks/files on the device to avoid re-transferring data.
- **Reassembly:**
    - **ADB Shell Mode (Default):** Uses standard shell commands (`cat`, `unzip` if available) to reassemble files.
    - **Termux Mode:** Pushes a script to Termux for more robust handling if standard shell tools are insufficient.
- **Configuration:** Settings are stored in `config.json` in the root directory.

## 6. Common Tasks
- **Adding a new Setting:**
    1.  Add default in `src/config.py`.
    2.  Add UI control in `SettingsWindow` class in `src/main.py`.
    3.  Update `save_and_close` in `src/main.py` to persist it.
- **Modifying Transfer Logic:** Check `src/core/transfer.py` for how files are queued and processed.
- **Updating UI:** `src/main.py` contains the bulk of the UI code (Tkinter).

## 7. Troubleshooting
- **ADB Not Found:** Ensure `platform-tools` is in your Windows PATH.
- **Device Not Listed:** Check USB debugging is enabled and the device is authorized.
- **Permission Denied:** The tool tries to handle permissions automatically, but sometimes manual intervention on the device is required (especially for storage access).
