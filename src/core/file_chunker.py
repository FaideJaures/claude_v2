"""
Integrated File Chunker - Prepares large files for transfer
Runs chunk_prepare.py functionality before transfer starts
"""

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable

class FileChunker:
    """
    Provides static methods for chunking files.
    """

    @staticmethod
    def chunk_file(
        file_path: Path,
        source_folder: Path,
        output_folder: Path,
        chunk_size_bytes: int,
        progress_callback: Optional[Callable[[str], None]] = None,
        logger=None,
        persistent_chunks: bool = True,
    ) -> Dict:
        """
        Chunk a single large file.

        Args:
            file_path: Path to the file to chunk
            source_folder: The root source folder
            output_folder: The root output folder for all chunks
            chunk_size_bytes: The size of each chunk in bytes
            progress_callback: Optional callback for progress updates
            logger: Optional logger instance
            persistent_chunks: If True, create chunks next to source file; if False, in output_folder
        """
        # Calculate relative path from source folder
        try:
            rel_path = file_path.relative_to(source_folder)
        except ValueError:
            rel_path = Path(file_path.name)

        # Create output directory for this file's chunks
        chunk_dir_name = f"{file_path.stem}_chunks"

        if persistent_chunks:
            # Create chunk folder next to the source file
            chunk_output_dir = file_path.parent / chunk_dir_name
        else:
            # Create chunk folder in temp directory
            chunk_output_dir = output_folder / rel_path.parent / chunk_dir_name

        # Check if chunks already exist and are valid
        if persistent_chunks and chunk_output_dir.exists():
            metadata_path = chunk_output_dir / "chunk_metadata.json"
            if metadata_path.exists():
                if logger: logger.info(f"Vérification des chunks existants pour: {file_path.name}")

                # Try to load existing metadata
                try:
                    with open(metadata_path, 'r') as f:
                        existing_metadata = json.load(f)

                    # Verify file hasn't changed (check MD5 and size)
                    current_size = file_path.stat().st_size
                    current_md5 = FileChunker._calculate_md5(file_path)

                    if (existing_metadata.get('original_size') == current_size and
                        existing_metadata.get('original_md5') == current_md5 and
                        existing_metadata.get('num_chunks') == len(list(chunk_output_dir.glob('chunk_*.bin')))):

                        if logger: logger.info(f"✓ Chunks existants valides trouvés pour {file_path.name}, réutilisation...")
                        if progress_callback:
                            progress_callback(f"Réutilisation des chunks existants pour {file_path.name}")

                        # Update the chunk_folder path in metadata for output_folder
                        if not persistent_chunks:
                            existing_metadata['chunk_folder'] = str(chunk_output_dir.relative_to(output_folder))
                            existing_metadata['persistent_source'] = None
                        else:
                            # For persistent chunks, we need to copy to output folder
                            copy_dest = output_folder / rel_path.parent / chunk_dir_name
                            existing_metadata['chunk_folder'] = str(copy_dest.relative_to(output_folder))
                            # IMPORTANT: Set persistent_source so transfer.py knows to copy the chunks
                            existing_metadata['persistent_source'] = str(chunk_output_dir)

                        return existing_metadata

                    else:
                        if logger: logger.info(f"Chunks existants obsolètes, rechunking nécessaire...")
                        # Delete old chunks
                        shutil.rmtree(chunk_output_dir)

                except Exception as e:
                    if logger: logger.warning(f"Erreur lors de la vérification des chunks existants: {e}")
                    # Continue with fresh chunking

        chunk_output_dir.mkdir(parents=True, exist_ok=True)

        if logger: logger.info(f"Chunking: {file_path.name} -> {chunk_output_dir}")

        # Calculate MD5 checksum of original file
        if progress_callback:
            progress_callback(f"Calculating checksum for {file_path.name}...")

        original_md5 = FileChunker._calculate_md5(file_path)

        # Get file size
        file_size = file_path.stat().st_size
        num_chunks = (file_size + chunk_size_bytes - 1) // chunk_size_bytes

        if logger: logger.info(f"Splitting {file_path.name} into {num_chunks} chunks...")

        # Determine the path to use in metadata
        if persistent_chunks:
            # For persistent chunks, metadata should point to where chunks will be copied in output_folder
            copy_dest = output_folder / rel_path.parent / chunk_dir_name
            metadata_chunk_folder = str(copy_dest.relative_to(output_folder))
        else:
            metadata_chunk_folder = str(chunk_output_dir.relative_to(output_folder))

        chunk_info = {
            "original_file": str(rel_path),
            "original_size": file_size,
            "original_md5": original_md5,
            "chunk_folder": metadata_chunk_folder,
            "chunk_size": chunk_size_bytes,
            "num_chunks": num_chunks,
            "chunks": [],
            "persistent_source": str(chunk_output_dir) if persistent_chunks else None  # Track original location
        }

        # Split file into chunks
        with open(file_path, 'rb') as source_file:
            for i in range(num_chunks):
                chunk_filename = f"chunk_{i:04d}.bin"
                chunk_path = chunk_output_dir / chunk_filename

                # Read chunk data
                chunk_data = source_file.read(chunk_size_bytes)
                actual_chunk_size = len(chunk_data)

                # Write chunk
                with open(chunk_path, 'wb') as chunk_file:
                    chunk_file.write(chunk_data)

                # Calculate chunk checksum
                chunk_md5 = hashlib.md5(chunk_data).hexdigest()

                chunk_info["chunks"].append({
                    "index": i,
                    "filename": chunk_filename,
                    "size": actual_chunk_size,
                    "md5": chunk_md5
                })

                # Progress update
                if progress_callback:
                    progress = (i + 1) / num_chunks * 100
                    progress_callback(
                        f"Chunking {file_path.name}: {i + 1}/{num_chunks} ({progress:.1f}%)"
                    )

        # Create metadata file in chunk directory
        metadata_path = chunk_output_dir / "chunk_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(chunk_info, f, indent=2)

        if logger: logger.info(f"Chunked successfully: {file_path.name} ({num_chunks} chunks)")
        
        return chunk_info

    @staticmethod
    def _calculate_md5(file_path: Path, chunk_size: int = 8192) -> str:
        """Calculate MD5 checksum of a file"""
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                md5.update(data)
        return md5.hexdigest()

    @staticmethod
    def generate_unified_reassembly_script(output_folder: Path, logger=None):
        """Generate the unified reassembly script in the output folder"""
        script_path = output_folder / "unified-reassemble.sh"
        
        script_content = '''#!/system/bin/sh
# Unified reassembly script for ADB Transfer
# Handles chunked files - restores original files from chunks
#
# Usage: sh unified-reassemble.sh
# Run this script in the transfer root directory

# Simple output functions
log_info() {
    echo "[INFO] "
}

log_error() {
    echo "[ERROR] "
}

log_success() {
    echo "[SUCCESS] "
}

TRANSFER_ROOT="$(pwd)"

log_info "========================================================"
log_info "ADB Transfer - File Reassembly"
log_info "========================================================"
log_info "Transfer root: $TRANSFER_ROOT"
echo ""

# Statistics
TOTAL_CHUNKS=0
SUCCESS_CHUNKS=0
FAILED_CHUNKS=0

log_info "Scanning for chunked files..."

# Find all chunk folders
CHUNK_FOLDERS=$(find "$TRANSFER_ROOT" -type d -name "*_chunks" 2>/dev/null | sort)

if [ -z "$CHUNK_FOLDERS" ]; then
    log_info "No chunked files found"
    exit 0
fi

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
    ORIGINAL_REL_PATH=$(grep -o '"original_file"[[:space:]]*:[[:space:]]*"[^"]*"' "$METADATA_FILE" | sed 's/.*"original_file"[[:space:]]*:[[:space:]]*"\\([^"]*\\)".*/\\1/')

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

echo ""
log_info "========================================================"
log_success "REASSEMBLY COMPLETE"
log_info "========================================================"
echo "Total chunked files: $TOTAL_CHUNKS"
echo "Successful: $SUCCESS_CHUNKS"
echo "Failed: $FAILED_CHUNKS"
echo "Location: $TRANSFER_ROOT"
log_info "========================================================"

# Exit code
if [ "$FAILED_CHUNKS" -gt 0 ]; then
    exit 1
fi

exit 0
'''
        
        # Write script with Unix line endings
        with open(script_path, 'w', newline='\n') as f:
            f.write(script_content)
            
        if logger: logger.info(f"Generated reassembly script: {script_path}")