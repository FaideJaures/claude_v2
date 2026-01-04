import os
import shutil
from pathlib import Path
import logging

class TransferFolderManager:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def get_transfer_folder_path(self, source_folder: str) -> Path:
        """
        Returns the path of the sibling _for_transfer folder.
        Example: C:/Data/MyFolder -> C:/Data/MyFolder_for_transfer
        """
        source_path = Path(source_folder)
        # Handle trailing slashes if any
        if source_folder.endswith(os.sep):
            source_path = Path(source_folder[:-1])
            
        parent = source_path.parent
        name = source_path.name
        return parent / f"{name}_for_transfer"

    # create_transfer_folder is removed as it's superseded by TransferManager.prepare_transfer
    # which handles chunking and bundling instead of raw copy.


    def delete_transfer_folder(self, source_folder: str) -> bool:
        """
        Deletes the corresponding _for_transfer folder if it exists.
        """
        dest_path = self.get_transfer_folder_path(source_folder)

        if not dest_path.exists():
            if self.logger:
                self.logger.warning(f"Transfer folder does not exist: {dest_path}")
            return False

        try:
            if self.logger:
                self.logger.info(f"Deleting {dest_path}...")
            
            # Use shutil.rmtree to remove the directory tree
            shutil.rmtree(dest_path)
            
            if self.logger:
                self.logger.success(f"Dossier de transfert supprimé: {dest_path}")
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error deleting transfer folder: {e}")
            return False
            
    def exists(self, source_folder: str) -> bool:
        """Check if transfer folder exists."""
        return self.get_transfer_folder_path(source_folder).exists()
