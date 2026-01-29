# claude_v2/src/utils/adb.py
import subprocess
import shlex
import os
import threading
from typing import Dict, List, Optional

# Import tools manager for bundled ADB
from utils.tools_manager import get_tools_manager


class Adb:
    def __init__(self, logger):
        self.logger = logger
        self._tools_manager = get_tools_manager()
        self._active_processes = set()
        self._processes_lock = threading.Lock()

    def run_command(self, command, device_id=None):
        # Use bundled ADB if available, otherwise fall back to system PATH
        adb_path = self._tools_manager.get_adb_path()
        
        # Get environment with proper PATH for DLL resolution
        env = self._tools_manager.get_environment_for_tool("adb")
        
        if device_id:
            command_list = [adb_path, "-s", device_id] + shlex.split(command)
        else:
            command_list = [adb_path] + shlex.split(command)
        
        # Only log commands in verbose mode (reduces noise significantly)
        if getattr(self.logger, 'verbose', False):
            self.logger.info(f"Exécution de la commande: {' '.join(command_list)}")
        
        try:
            # Suppress window creation on Windows
            startupinfo = None
            if hasattr(subprocess, 'STARTUPINFO'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            process = subprocess.Popen(
                command_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                env=env  # Use modified environment for bundled tool DLL resolution
            )
            
            with self._processes_lock:
                self._active_processes.add(process)

            try:
                output_lines = []
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        output_lines.append(output.strip())

                rc = process.poll()
            finally:
                with self._processes_lock:
                    self._active_processes.discard(process)

            if rc != 0:
                # Only log errors (not every failed command - some are expected like stat on missing files)
                if getattr(self.logger, 'verbose', False):
                    self.logger.error(f"Erreur ADB (code {rc}): {' '.join(command_list[:3])}...")
                return None
            
            return output_lines

        except FileNotFoundError:
            self.logger.error("Erreur: L'exécutable 'adb' est introuvable. Veuillez l'installer et l'ajouter à votre PATH.")
            return None
        except Exception as e:
            # If we're cancelling, an error is expected
            if getattr(self, '_cancelling', False):
                return None
            self.logger.error(f"Une erreur inattendue est survenue: {e}")
            return None

    def run_shell_batch(self, commands: list, device_id: str = None, separator: str = " && ") -> list:
        """
        Execute multiple shell commands in a single ADB call.
        
        Combines commands with the specified separator (default: &&) to reduce
        ADB call overhead. Useful for bulk operations like mkdir, chmod, etc.
        
        Args:
            commands: List of shell command strings (without 'shell' prefix)
            device_id: Target device identifier
            separator: Command separator (default " && " for sequential execution)
            
        Returns:
            Combined output lines from all commands, or None on error
            
        Example:
            adb.run_shell_batch([
                "mkdir -p /sdcard/folder1",
                "mkdir -p /sdcard/folder2",
                "mkdir -p /sdcard/folder3"
            ], device_id)
        """
        if not commands:
            return []
        
        # Escape each command and combine
        combined = separator.join(commands)
        return self.run_command(f'shell "{combined}"', device_id)

    def run_push_batch(self, file_mappings: list, device_id: str = None) -> tuple:
        """
        Push multiple files in sequence (not truly parallel, but reduces overhead).
        
        For truly parallel push, use ThreadPoolExecutor with individual run_command calls.
        This method is for when you want simple sequential multi-file push.
        
        Args:
            file_mappings: List of (local_path, remote_path) tuples
            device_id: Target device identifier
            
        Returns:
            Tuple of (success_count, failed_count, failed_files)
        """
        success = 0
        failed = 0
        failed_files = []
        
        for local_path, remote_path in file_mappings:
            result = self.run_command(f'push "{local_path}" "{remote_path}"', device_id)
            if result is not None:
                success += 1
            else:
                failed += 1
                failed_files.append((local_path, remote_path))
        
        return success, failed, failed_files

    def terminate_all(self):
        """Terminate all active ADB processes."""
        self._cancelling = True
        with self._processes_lock:
            for process in self._active_processes:
                try:
                    process.terminate()
                    # Wait briefly for termination
                    # process.wait(timeout=0.5)
                except Exception:
                    try:
                        process.kill()
                    except:
                        pass
            self._active_processes.clear()
        self._cancelling = False

    def check_adb(self):
        """
        Check if ADB is available and report whether bundled or system version is used.
        """
        self.logger.info("Vérification de l'installation d'ADB...")
        
        # Report which ADB is being used
        if self._tools_manager.is_tool_bundled("adb"):
            adb_path = self._tools_manager.get_adb_path()
            self.logger.info(f"Utilisation d'ADB intégré: {adb_path}")
            
            # Verify DLL dependencies
            deps_ok, missing = self._tools_manager.verify_adb_dependencies()
            if not deps_ok:
                self.logger.warning(f"DLLs manquantes: {', '.join(missing)}")
        else:
            self.logger.info("Utilisation d'ADB système (PATH)")
        
        output = self.run_command("version")
        if output and len(output) > 0 and "Android Debug Bridge version" in output[0]:
            self.logger.success("ADB est installé et fonctionnel.")
            return True
        else:
            if self._tools_manager.is_tool_bundled("adb"):
                self.logger.error("ADB intégré trouvé mais ne fonctionne pas. Vérifiez les DLLs.")
            else:
                self.logger.error("ADB n'est pas installé ou n'est pas dans le PATH.")
            return False
            
    def get_devices(self):
        """
        Legacy method kept for compatibility. 
        Returns simple list of device serials/IPs.
        """
        detailed = self.get_devices_detailed()
        return [d["id"] for d in detailed]

    def get_devices_detailed(self) -> List[Dict]:
        """
        Get connected devices with detailed info including connection type.

        Returns:
            List of dicts with keys: id, type ('usb' or 'wifi'), display_name, model
        """
        # Using -l to get model info
        output = self.run_command("devices -l")
        if not output:
            return []

        devices = []
        # Output format example:
        # List of devices attached
        # 8A2X0032D      device product:bramble model:Pixel_4a_(5G) device:bramble transport_id:1
        # 192.168.1.105:5555 device product:bramble model:Pixel_4a_(5G) device:bramble transport_id:2
        
        for line in output[1:]:  # Skip header
            if "device" in line and not line.startswith("List of"):
                parts = line.split()
                device_id = parts[0]

                # Determine connection type
                if ":" in device_id and "." in device_id:
                    # IP:port format = WiFi
                    conn_type = "wifi"
                    icon = "📶"
                else:
                    # Serial number = USB
                    conn_type = "usb"
                    icon = "🔌"

                # Extract model
                model = "Inconnu"
                for part in parts:
                    if part.startswith("model:"):
                        model = part.replace("model:", "").replace("_", " ")
                        break
                
                # Get Bluetooth name (do this quietly without logging)
                bt_result = self.run_command("shell settings get secure bluetooth_name", device_id)
                bluetooth_name = "Unknown"
                if bt_result and bt_result[0] and bt_result[0].strip() != "null":
                    bluetooth_name = bt_result[0].strip()

                display_name = f"{icon} {device_id} ({model} - {bluetooth_name})"

                devices.append({
                    "id": device_id,
                    "type": conn_type,
                    "display_name": display_name,
                    "model": model,
                    "bluetooth_name": bluetooth_name,
                    "raw_line": line
                })

        return devices

    def get_bluetooth_name(self, device_id: str) -> str:
        """
        Get the Bluetooth name of a device.
        This is the user-friendly name shown in Bluetooth settings.

        Args:
            device_id: Device serial or IP:port

        Returns:
            Bluetooth name or "Unknown" if not found
        """
        result = self.run_command("shell settings get secure bluetooth_name", device_id)
        if result and result[0] and result[0].strip() and result[0].strip() != "null":
            return result[0].strip()
        return "Unknown"

    def enable_tcpip(self, device_id: str, port: int = 5555) -> bool:
        """
        Enable TCP/IP mode on a USB-connected device.
        """
        self.logger.info(f"[{device_id}] Activation ADB TCP/IP sur le port {port}...")
        result = self.run_command(f"tcpip {port}", device_id)
        # tcpip command often returns nothing on success, or "restarting in TCP mode port: 5555"
        if result is None: 
            return False # Error executing command
        return True

    def connect_wifi(self, ip: str, port: int = 5555) -> bool:
        """
        Connect to a device over WiFi.
        """
        self.logger.info(f"Connexion ADB à {ip}:{port}...")
        result = self.run_command(f"connect {ip}:{port}")
        
        if result:
            combined_output = " ".join(result).lower()
            if "connected to" in combined_output:
                return True
            if "already connected" in combined_output:
                return True
        return False

    def disconnect_wifi(self, ip: str, port: int = 5555) -> bool:
        """
        Disconnect a WiFi device.
        """
        self.logger.info(f"Déconnexion de {ip}:{port}...")
        result = self.run_command(f"disconnect {ip}:{port}")
        return result is not None

    def get_device_ip(self, device_id: str) -> Optional[str]:
        """
        Get the IP address of the device (scanning all interfaces).
        Prioritizes wlan, then eth, then others. Excludes localhost.
        """
        # Try to get all IP addresses
        cmd = "shell ip -4 addr show"
        output = self.run_command(cmd, device_id)
        
        if not output:
            return None

        candidates = []
        
        current_interface = ""
        for line in output:
            line = line.strip()
            # Detect interface name (e.g., "21: wlan0: ...")
            if ": " in line and "<" in line and ">" in line:
                parts = line.split(": ")
                if len(parts) >= 2:
                    current_interface = parts[1].split("@")[0] # handle wlan0@if21 cases
            
            # Detect IP (e.g., "inet 192.168.1.50/24 ...")
            if line.startswith("inet ") and "127.0.0.1" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    ip_cidr = parts[1]
                    ip = ip_cidr.split("/")[0]
                    candidates.append((current_interface, ip))

        if not candidates:
            return None

        # Priority: wlan > eth > others
        # Check wlan first
        for iface, ip in candidates:
            if "wlan" in iface:
                return ip
        
        # Check eth next
        for iface, ip in candidates:
            if "eth" in iface:
                return ip
                
        # Return first valid candidate if no preferred interface found
        return candidates[0][1]