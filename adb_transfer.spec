# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ADB Transfer Tool
Creates a single portable .exe with all dependencies bundled
"""

import sys
from pathlib import Path

block_cipher = None

# Get the source directory
src_dir = Path('src')

# Data files to include
datas = [
    (str(src_dir / 'utils' / 'unified.sh'), 'utils'),  # Shell script for device
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'tkinter',
    'tkinter.filedialog',
    'tkinter.messagebox',
]

a = Analysis(
    [str(src_dir / 'main.py')],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ADB_Transfer_Tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: icon='app_icon.ico'
)
