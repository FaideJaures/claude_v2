# claude_v2/src/utils/tools_manager.py
"""
Bundled Tools Manager

This module manages external tools (like ADB) that are bundled with the application.
It provides a centralized way to locate tool executables, whether running from:
- Source code (development mode)
- PyInstaller bundle (.exe distribution)

This allows the application to run in any environment without requiring
external tools to be installed in the system PATH.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ToolsManager:
    """
    Manages bundled tools like ADB, fastboot, etc.
    
    Priority order for finding tools:
    1. Bundled tools directory (platform-tools)
    2. System PATH (fallback)
    """
    
    # Tool definitions: name -> relative path within platform-tools
    TOOLS = {
        "adb": "adb.exe",
        "fastboot": "fastboot.exe",
        "sqlite3": "sqlite3.exe",
    }
    
    # Required DLLs that must be present with adb.exe
    ADB_DEPENDENCIES = [
        "AdbWinApi.dll",
        "AdbWinUsbApi.dll",
        "libwinpthread-1.dll",
    ]
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure single instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._tools_dir = None
        self._tool_paths = {}
        self._initialize_paths()
    
    def _get_base_path(self) -> Path:
        """
        Get the base path for the application.
        
        When running from PyInstaller bundle, sys._MEIPASS points to the temp
        directory where bundled files are extracted.
        When running from source, we use the project root.
        """
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            # sys._MEIPASS is the temp folder where PyInstaller extracts files
            return Path(sys._MEIPASS)
        else:
            # Running from source code
            # Navigate from src/utils/ to project root
            return Path(__file__).parent.parent.parent
    
    def _initialize_paths(self):
        """Initialize tool paths based on current execution context."""
        base_path = self._get_base_path()
        
        # Look for platform-tools directory
        tools_dir = base_path / "platform-tools"
        
        if tools_dir.exists():
            self._tools_dir = tools_dir
            # Pre-cache all tool paths
            for tool_name, tool_file in self.TOOLS.items():
                tool_path = tools_dir / tool_file
                if tool_path.exists():
                    self._tool_paths[tool_name] = str(tool_path)
    
    def get_tool_path(self, tool_name: str) -> str:
        """
        Get the full path to a tool executable.
        
        Args:
            tool_name: Name of the tool (e.g., "adb", "fastboot")
            
        Returns:
            Full path to the tool if bundled, otherwise just the tool name
            (to use system PATH as fallback).
        """
        # Check if we have a bundled version
        if tool_name in self._tool_paths:
            return self._tool_paths[tool_name]
        
        # Fallback to system PATH
        return tool_name
    
    def get_adb_path(self) -> str:
        """Get the path to ADB executable."""
        return self.get_tool_path("adb")
    
    def get_fastboot_path(self) -> str:
        """Get the path to fastboot executable."""
        return self.get_tool_path("fastboot")
    
    def is_tool_bundled(self, tool_name: str) -> bool:
        """Check if a tool is available in the bundle."""
        return tool_name in self._tool_paths
    
    def get_tools_directory(self) -> Optional[Path]:
        """Get the platform-tools directory path."""
        return self._tools_dir
    
    def verify_adb_dependencies(self) -> Tuple[bool, List[str]]:
        """
        Verify that all ADB dependencies (DLLs) are present.
        
        Returns:
            Tuple of (all_present: bool, missing_files: list)
        """
        if self._tools_dir is None:
            return False, ["platform-tools directory not found"]
        
        missing = []
        for dll in self.ADB_DEPENDENCIES:
            dll_path = self._tools_dir / dll
            if not dll_path.exists():
                missing.append(dll)
        
        return len(missing) == 0, missing
    
    def get_environment_for_tool(self, tool_name: str) -> Optional[Dict[str, str]]:
        """
        Get environment variables needed to run a tool.
        
        For ADB, we need to ensure the DLLs can be found.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Dict of environment variables to add, or None if not needed.
        """
        if tool_name == "adb" and self._tools_dir:
            # Add platform-tools to PATH for DLL resolution
            env = os.environ.copy()
            current_path = env.get("PATH", "")
            tools_path = str(self._tools_dir)
            if tools_path not in current_path:
                env["PATH"] = tools_path + os.pathsep + current_path
            return env
        return None


# Singleton instance for easy access
_tools_manager = None


def get_tools_manager() -> ToolsManager:
    """Get the global ToolsManager instance."""
    global _tools_manager
    if _tools_manager is None:
        _tools_manager = ToolsManager()
    return _tools_manager


def get_adb_path() -> str:
    """Convenience function to get ADB path."""
    return get_tools_manager().get_adb_path()


def get_fastboot_path() -> str:
    """Convenience function to get fastboot path."""
    return get_tools_manager().get_fastboot_path()


def is_adb_bundled() -> bool:
    """Check if ADB is bundled with the application."""
    return get_tools_manager().is_tool_bundled("adb")
