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

# === FAST MODE OPTIONS ===
# These options skip redundant verifications for maximum speed

# Skip verification AFTER pushing chunks (before reassembly)
# The final verification after reassembly still happens
# Safe to skip: we trust ADB push succeeded if no error was thrown
DEFAULT_SKIP_EARLY_VERIFICATION = False

# Skip verification of existing local chunks (reuse without checking)
# Safe to skip: chunks on disk are unlikely to be corrupted
DEFAULT_TRUST_LOCAL_CHUNKS = False

# Skip size verification during transfer checks
# Safe to skip: if file was pushed without error, size is correct
DEFAULT_SKIP_SIZE_VERIFICATION = False

# === WIFI & AUTO-REFRESH SETTINGS ===

# Device list refresh interval in milliseconds
DEFAULT_REFRESH_INTERVAL = 3000

# Automatically connect to known WiFi devices on startup
DEFAULT_AUTO_CONNECT_WIFI = True

# === WORKER POOL SETTINGS ===
# Multi-worker parallelism for faster processing

# PC-side workers (chunking large files)
# Uses ProcessPoolExecutor for CPU-bound operations
DEFAULT_CHUNKING_WORKERS = 4

# PC-side workers (zipping small files into bundles)
# Uses ProcessPoolExecutor for CPU-bound operations
DEFAULT_ZIPPING_WORKERS = 10

# Device-side workers (reassembling chunks via cat)
# Uses ThreadPoolExecutor with multiple ADB sessions
DEFAULT_REASSEMBLY_WORKERS = 4

# Device-side workers (unzipping bundles)
# Uses ThreadPoolExecutor with multiple ADB sessions
DEFAULT_UNZIP_WORKERS = 10

# Device-side workers (moving files to final destination)
# Uses ThreadPoolExecutor with multiple ADB sessions
DEFAULT_FINAL_MOVE_WORKERS = 10

# Small file handling mode: "zip" or "batch_push"
# "zip" - Bundle small files into ZIP archives (default, more efficient)
# "batch_push" - Push files directly without zipping (simpler but slower)
DEFAULT_SMALL_FILE_MODE = "zip"

# Enable pre-APK installation before transfer
# If enabled, installs and opens the APK from pre-apk/ folder before transfer
DEFAULT_PRE_APK_ENABLED = True

# === UNLOCK DELAY SETTINGS ===
# Configurable delays for device unlock (reduced for faster multi-device operations)

# Delay after wake up command (seconds)
DEFAULT_UNLOCK_WAKE_DELAY = 0.8

# Delay after swipe gesture (seconds)
DEFAULT_UNLOCK_SWIPE_DELAY = 0.8

# Delay after unlock completion (seconds)
DEFAULT_UNLOCK_COMPLETE_DELAY = 1.0

# Delay between PIN/password digit inputs (seconds)
DEFAULT_UNLOCK_DIGIT_DELAY = 0.15

# === FAST MODE SETTINGS ===

# Skip remote file check during resume (for guaranteed fresh transfers)
# When True, doesn't scan remote directory for existing files
# Faster but won't skip already-transferred files
DEFAULT_SKIP_RESUME_CHECK = False

# === DIRECT TRANSFER MODE ===
# Direct transfer mode pushes files directly to destination without temp folder
# Benefits: No cleanup, no move phase, simpler flow
# Limitations: Large files still need chunking in temp, no atomic commit

# Enable direct transfer mode
DEFAULT_DIRECT_TRANSFER_MODE = False

# Threshold for direct push (files smaller than this go directly to destination)
# Files larger than this threshold are chunked and reassembled via temp folder
# Default: Same as chunking threshold (100MB)
DEFAULT_DIRECT_PUSH_THRESHOLD = 100 * 1024 * 1024