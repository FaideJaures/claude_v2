# claude_v2/src/config.py

# Default number of parallel ADB processes
DEFAULT_PARALLEL_PROCESSES = 4

# Default chunk size for large files (in bytes)
# 100 MB
DEFAULT_CHUNK_SIZE = 100 * 1024 * 1024

# Default threshold for small files (in bytes)
# Files smaller than this will be batched together.
# 10 MB
DEFAULT_SMALL_FILE_THRESHOLD = 10 * 1024 * 1024

# Temporary directory on the Android device
DEFAULT_REMOTE_TEMP_DIR = "/sdcard/transfer_temp"

# Aggressive temp cleanup during transfer
DEFAULT_AGGRESSIVE_TEMP_CLEANUP = True

# Auto-unlock device settings
DEFAULT_UNLOCK_DEVICE = True
DEFAULT_UNLOCK_METHOD = "password"
DEFAULT_UNLOCK_SECRET = "0000"

# Auto-detect storage permission
DEFAULT_AUTO_DETECT_PERMISSION = True

# === NEW OPTIMIZATION OPTIONS ===

# Use ADB Shell mode instead of Termux (Termux-free operation)
# When True, reassembly uses direct ADB shell commands instead of Termux
DEFAULT_USE_ADB_SHELL_MODE = True

# Resume support - skip chunks that already exist on device
# Saves time when transfer was interrupted
DEFAULT_RESUME_TRANSFER = True

# SJF (Shortest Job First) scheduling - transfer smaller files first
# Improves perceived performance by completing more files sooner
DEFAULT_SJF_SCHEDULING = True

# Optimal bundle size for small file ZIP bundles (in bytes)
# Used by bin packing algorithm - 50 MB is a good balance
DEFAULT_BUNDLE_SIZE = 50 * 1024 * 1024
