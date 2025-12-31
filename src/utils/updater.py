# claude_v2/src/utils/updater.py
"""
Git-based auto-updater for the ADB Transfer Tool.
Checks for updates on startup and pulls from remote repository.
"""

import subprocess
import os
import sys
from pathlib import Path


class AutoUpdater:
    """Handles automatic updates via git pull."""
    
    def __init__(self, logger=None):
        self.logger = logger
        self.app_dir = self._get_app_directory()
    
    def _get_app_directory(self):
        """Get the root directory of the application."""
        if hasattr(sys, '_MEIPASS'):
            # Running as compiled exe - git pull won't work
            return None
        
        # Get the src folder's parent (project root)
        current_file = Path(__file__).resolve()
        return current_file.parent.parent.parent  # utils -> src -> project_root
    
    def _log(self, message, level="info"):
        """Log a message if logger is available."""
        if self.logger:
            if level == "success":
                self.logger.success(message)
            elif level == "error":
                self.logger.error(message)
            else:
                self.logger.info(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    def is_git_repo(self):
        """Check if the app directory is a git repository."""
        if not self.app_dir:
            return False
        
        git_dir = self.app_dir / ".git"
        return git_dir.exists()
    
    def check_for_updates(self):
        """Check if there are remote updates available.
        
        Returns:
            tuple: (has_updates: bool, message: str)
        """
        if not self.app_dir or not self.is_git_repo():
            return False, "Not a git repository"
        
        try:
            # Fetch remote changes without merging
            result = subprocess.run(
                ["git", "fetch"],
                cwd=str(self.app_dir),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return False, f"Fetch failed: {result.stderr}"
            
            # Check if local is behind remote
            result = subprocess.run(
                ["git", "status", "-uno"],
                cwd=str(self.app_dir),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output = result.stdout.lower()
            if "behind" in output:
                return True, "Updates available"
            elif "ahead" in output:
                return False, "Local is ahead of remote"
            else:
                return False, "Already up to date"
                
        except subprocess.TimeoutExpired:
            return False, "Timeout checking for updates"
        except FileNotFoundError:
            return False, "Git not found"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def pull_updates(self):
        """Pull updates from the remote repository.
        
        Returns:
            tuple: (success: bool, message: str, needs_restart: bool)
        """
        if not self.app_dir or not self.is_git_repo():
            return False, "Not a git repository", False
        
        self._log("Mise à jour en cours...")
        
        try:
            # Stash any local changes first
            subprocess.run(
                ["git", "stash"],
                cwd=str(self.app_dir),
                capture_output=True,
                timeout=10
            )
            
            # Pull changes
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=str(self.app_dir),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                # Try to restore stashed changes
                subprocess.run(["git", "stash", "pop"], cwd=str(self.app_dir), capture_output=True)
                return False, f"Pull failed: {result.stderr}", False
            
            output = result.stdout
            
            if "Already up to date" in output:
                return True, "Déjà à jour", False
            else:
                self._log("Mise à jour réussie!", "success")
                return True, "Mise à jour téléchargée", True
                
        except subprocess.TimeoutExpired:
            return False, "Timeout during update", False
        except FileNotFoundError:
            return False, "Git not found", False
        except Exception as e:
            return False, f"Error: {str(e)}", False
    
    def get_current_version(self):
        """Get the current git commit hash or tag."""
        if not self.app_dir or not self.is_git_repo():
            return "unknown"
        
        try:
            # Try to get tag first
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                cwd=str(self.app_dir),
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            
            # Fall back to short commit hash
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(self.app_dir),
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            
            return "unknown"
            
        except Exception:
            return "unknown"


def check_and_update_on_startup(logger=None, auto_update=True):
    """Check for updates on application startup.
    
    Args:
        logger: Optional logger instance
        auto_update: If True, automatically pull updates
        
    Returns:
        bool: True if restart is needed
    """
    updater = AutoUpdater(logger)
    
    if not updater.is_git_repo():
        return False
    
    has_updates, message = updater.check_for_updates()
    
    if has_updates and auto_update:
        success, msg, needs_restart = updater.pull_updates()
        return needs_restart
    
    return False
