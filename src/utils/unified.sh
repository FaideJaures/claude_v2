#!/system/bin/sh
# Unified reassembly script for ADB Transfer
# Handles both chunked files and bundled ZIP archives
# Restores original folder structure on Android device
#
# Usage: sh unified.sh <transfer_root>
# Example: sh unified.sh /sdcard/adb

# Simple output functions
log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1"
}

log_success() {
    echo "[SUCCESS] $1"
}

log_warning() {
    echo "[WARNING] $1"
}

# Check for transfer root argument
if [ -z "$1" ]; then
    log_error "No transfer root specified"
    echo "Usage: sh unified.sh <transfer_root>"
    echo "Example: sh unified.sh /sdcard/adb"
    exit 1
fi

TRANSFER_ROOT="$1"

log_info "========================================================"
log_info "ADB Transfer - Unified Reassembly"
log_info "========================================================"
log_info "Transfer root: $TRANSFER_ROOT"
echo ""

# Statistics
TOTAL_CHUNKS=0
SUCCESS_CHUNKS=0
FAILED_CHUNKS=0
TOTAL_BUNDLES=0
SUCCESS_BUNDLES=0
FAILED_BUNDLES=0

# ============================================================
# PART 1: REASSEMBLE CHUNKED FILES
# ============================================================

log_info "PHASE 1: Scanning for chunked files..."

# Find all chunk folders recursively
CHUNK_FOLDERS=$(find "$TRANSFER_ROOT" -type d -name "*_chunks" 2>/dev/null | sort)

if [ -z "$CHUNK_FOLDERS" ]; then
    log_info "No chunked files found"
else
    # Process each chunk folder
    for CHUNK_DIR in $CHUNK_FOLDERS; do
        TOTAL_CHUNKS=$((TOTAL_CHUNKS + 1))

        # Get chunk folder name and parent directory
        CHUNK_BASENAME=$(basename "$CHUNK_DIR")
        CHUNK_PARENT=$(dirname "$CHUNK_DIR")

        # Read metadata to get original filename with extension
        METADATA_FILE="$CHUNK_DIR/chunk_metadata.json"

        if [ ! -f "$METADATA_FILE" ]; then
            log_error "  Metadata not found: $METADATA_FILE"
            FAILED_CHUNKS=$((FAILED_CHUNKS + 1))
            continue
        fi

        # Extract original filename from metadata JSON
        # The "original_file" field contains the relative path with extension
        ORIGINAL_REL_PATH=$(grep -o '"original_file"[[:space:]]*:[[:space:]]*"[^"]*"' "$METADATA_FILE" | sed 's/.*"original_file"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

        if [ -z "$ORIGINAL_REL_PATH" ]; then
            log_error "  Could not extract original filename from metadata"
            FAILED_CHUNKS=$((FAILED_CHUNKS + 1))
            continue
        fi

        # Get just the filename with extension from the relative path
        ORIGINAL_NAME=$(basename "$ORIGINAL_REL_PATH")

        # Output file will be in same directory as chunk folder
        OUTPUT_FILE="$CHUNK_PARENT/$ORIGINAL_NAME"

        log_info "Processing chunked file: $ORIGINAL_NAME"
        log_info "  Chunk folder: $CHUNK_DIR"
        log_info "  Output: $OUTPUT_FILE"

        # Count chunks
        NUM_CHUNKS=$(ls -1 "$CHUNK_DIR"/chunk_*.bin 2>/dev/null | wc -l)

        if [ "$NUM_CHUNKS" -eq 0 ]; then
            log_error "  No chunk files found"
            FAILED_CHUNKS=$((FAILED_CHUNKS + 1))
            continue
        fi

        log_info "  Chunks to reassemble: $NUM_CHUNKS"

        # Remove output file if exists
        rm -f "$OUTPUT_FILE"

        # Reassemble chunks using cat (in correct order)
        CHUNK_INDEX=0
        FAILED_CHUNK=0

        while [ $CHUNK_INDEX -lt $NUM_CHUNKS ]; do
            CHUNK_FILE=$(printf "$CHUNK_DIR/chunk_%04d.bin" $CHUNK_INDEX)

            if [ ! -f "$CHUNK_FILE" ]; then
                log_error "  Missing chunk: chunk_$(printf '%04d' $CHUNK_INDEX).bin"
                FAILED_CHUNK=1
                break
            fi

            # Append chunk to output
            cat "$CHUNK_FILE" >> "$OUTPUT_FILE" 2>/dev/null
            if [ $? -ne 0 ]; then
                log_error "  Failed to read chunk_$(printf '%04d' $CHUNK_INDEX).bin"
                FAILED_CHUNK=1
                break
            fi

            CHUNK_INDEX=$((CHUNK_INDEX + 1))

            # Progress indicator
            PROGRESS=$((CHUNK_INDEX * 100 / NUM_CHUNKS))
            echo "  Progress: $CHUNK_INDEX/$NUM_CHUNKS ($PROGRESS%)"
        done

        # Check if reassembly succeeded
        if [ "$FAILED_CHUNK" -eq 1 ]; then
            log_error "  Reassembly failed - chunk errors"
            rm -f "$OUTPUT_FILE" 2>/dev/null
            FAILED_CHUNKS=$((FAILED_CHUNKS + 1))
            continue
        fi

        if [ ! -f "$OUTPUT_FILE" ]; then
            log_error "  Reassembly failed - output file not created"
            FAILED_CHUNKS=$((FAILED_CHUNKS + 1))
            continue
        fi

        # Get file size
        if [ -f "$OUTPUT_FILE" ]; then
            FILE_SIZE=$(stat -c%s "$OUTPUT_FILE" 2>/dev/null || stat -f%z "$OUTPUT_FILE" 2>/dev/null || echo "0")
            FILE_SIZE_GB=$(awk "BEGIN {printf \"%.2f\", $FILE_SIZE / (1024*1024*1024)}")

            log_success "  Reassembled: ${FILE_SIZE_GB} GB"

            # Delete chunk folder now that file is reassembled
            log_info "  Cleaning up chunk folder..."
            rm -rf "$CHUNK_DIR" 2>/dev/null
            if [ $? -eq 0 ]; then
                log_info "  Chunk folder deleted"
            else
                log_error "  Could not delete chunk folder (check permissions)"
            fi

            SUCCESS_CHUNKS=$((SUCCESS_CHUNKS + 1))
        else
            log_error "  Output file not created"
            FAILED_CHUNKS=$((FAILED_CHUNKS + 1))
        fi
    done

    # Cleanup chunking manifest file if all succeeded
    if [ "$SUCCESS_CHUNKS" -eq "$TOTAL_CHUNKS" ] && [ "$TOTAL_CHUNKS" -gt 0 ]; then
        MANIFEST_FILE="$TRANSFER_ROOT/chunking_manifest.json"
        if [ -f "$MANIFEST_FILE" ]; then
            rm -f "$MANIFEST_FILE" 2>/dev/null
            log_info "Removed chunking manifest file"
        fi
    fi
fi

echo ""

# ============================================================
# PART 2: EXTRACT BUNDLED ZIP FILES
# ============================================================

log_info "PHASE 2: Scanning for bundled archives..."

# Find all bundle ZIP files
BUNDLE_ZIPS=$(find "$TRANSFER_ROOT" -type f -name "bundle_*.zip" 2>/dev/null | sort)

if [ -z "$BUNDLE_ZIPS" ]; then
    log_info "No bundled archives found"
else
    # Check if unzip is available
    UNZIP_CMD=""
    if command -v unzip >/dev/null 2>&1; then
        UNZIP_CMD="unzip"
    elif [ -f /system/xbin/unzip ]; then
        UNZIP_CMD="/system/xbin/unzip"
    elif [ -f /data/local/tmp/busybox ]; then
        UNZIP_CMD="/data/local/tmp/busybox unzip"
    else
        log_warning "unzip not found - bundled archives cannot be extracted"
        log_warning "Please install busybox or unzip on device"
        UNZIP_CMD=""
    fi

    if [ -n "$UNZIP_CMD" ]; then
        # Process each bundle ZIP
        for BUNDLE_ZIP in $BUNDLE_ZIPS; do
            TOTAL_BUNDLES=$((TOTAL_BUNDLES + 1))

            BUNDLE_BASENAME=$(basename "$BUNDLE_ZIP")
            BUNDLE_PARENT=$(dirname "$BUNDLE_ZIP")

            log_info "Processing bundle: $BUNDLE_BASENAME"
            log_info "  Bundle location: $BUNDLE_ZIP"
            log_info "  Extract to: $BUNDLE_PARENT"

            # Get bundle size
            BUNDLE_SIZE=$(stat -c%s "$BUNDLE_ZIP" 2>/dev/null || stat -f%z "$BUNDLE_ZIP" 2>/dev/null || echo "0")
            BUNDLE_SIZE_MB=$(awk "BEGIN {printf \"%.2f\", $BUNDLE_SIZE / (1024*1024)}")
            log_info "  Bundle size: ${BUNDLE_SIZE_MB} MB"

            # Extract bundle to parent directory (preserving folder structure)
            $UNZIP_CMD -o -q "$BUNDLE_ZIP" -d "$BUNDLE_PARENT" 2>/dev/null
            EXTRACT_RESULT=$?

            if [ $EXTRACT_RESULT -eq 0 ]; then
                log_success "  Bundle extracted successfully"

                # Delete ZIP after successful extraction
                log_info "  Cleaning up bundle ZIP..."
                rm -f "$BUNDLE_ZIP" 2>/dev/null
                if [ $? -eq 0 ]; then
                    log_info "  Bundle ZIP deleted"
                else
                    log_warning "  Could not delete bundle ZIP"
                fi

                SUCCESS_BUNDLES=$((SUCCESS_BUNDLES + 1))
            else
                log_error "  Bundle extraction failed (exit code: $EXTRACT_RESULT)"
                FAILED_BUNDLES=$((FAILED_BUNDLES + 1))
            fi
        done

        # Cleanup bundling manifest file if all succeeded
        if [ "$SUCCESS_BUNDLES" -eq "$TOTAL_BUNDLES" ] && [ "$TOTAL_BUNDLES" -gt 0 ]; then
            MANIFEST_FILE="$TRANSFER_ROOT/bundling_manifest.json"
            if [ -f "$MANIFEST_FILE" ]; then
                rm -f "$MANIFEST_FILE" 2>/dev/null
                log_info "Removed bundling manifest file"
            fi
        fi
    else
        # No unzip available - mark all as failed
        for BUNDLE_ZIP in $BUNDLE_ZIPS; do
            TOTAL_BUNDLES=$((TOTAL_BUNDLES + 1))
            FAILED_BUNDLES=$((FAILED_BUNDLES + 1))
        done
    fi
fi

echo ""

# ============================================================
# FINAL SUMMARY
# ============================================================

log_info "========================================================"
log_success "REASSEMBLY COMPLETE"
log_info "========================================================"

if [ "$TOTAL_CHUNKS" -gt 0 ]; then
    echo "Chunked Files:"
    echo "  Total: $TOTAL_CHUNKS"
    echo "  Successful: $SUCCESS_CHUNKS"
    echo "  Failed: $FAILED_CHUNKS"
fi

if [ "$TOTAL_BUNDLES" -gt 0 ]; then
    echo "Bundled Archives:"
    echo "  Total: $TOTAL_BUNDLES"
    echo "  Successful: $SUCCESS_BUNDLES"
    echo "  Failed: $FAILED_BUNDLES"
fi

if [ "$TOTAL_CHUNKS" -eq 0 ] && [ "$TOTAL_BUNDLES" -eq 0 ]; then
    echo "No chunked files or bundles found - nothing to process"
fi

echo "Location: $TRANSFER_ROOT"
log_info "========================================================"

# Create completion marker file
MARKER_FILE="$TRANSFER_ROOT/.reassembly_complete"
echo "Reassembly completed at: $(date)" > "$MARKER_FILE"
echo "Total chunks: $TOTAL_CHUNKS" >> "$MARKER_FILE"
echo "Successful chunks: $SUCCESS_CHUNKS" >> "$MARKER_FILE"
echo "Failed chunks: $FAILED_CHUNKS" >> "$MARKER_FILE"
echo "Total bundles: $TOTAL_BUNDLES" >> "$MARKER_FILE"
echo "Successful bundles: $SUCCESS_BUNDLES" >> "$MARKER_FILE"
echo "Failed bundles: $FAILED_BUNDLES" >> "$MARKER_FILE"
log_info "Completion marker created: $MARKER_FILE"

# Exit code
TOTAL_FAILED=$((FAILED_CHUNKS + FAILED_BUNDLES))
if [ "$TOTAL_FAILED" -gt 0 ]; then
    exit 1
fi

exit 0