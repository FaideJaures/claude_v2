# claude_v2/src/utils/adb.py
import subprocess
import shlex

class Adb:
    def __init__(self, logger):
        self.logger = logger

    def run_command(self, command, device_id=None):
        adb_path = "adb"
        
        if device_id:
            command_list = [adb_path, "-s", device_id] + shlex.split(command)
        else:
            command_list = [adb_path] + shlex.split(command)
        
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
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            output_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.logger.info(output.strip())
                    output_lines.append(output.strip())

            rc = process.poll()
            if rc != 0:
                self.logger.error(f"Erreur lors de l'exécution de la commande ADB. Code de sortie: {rc}")
                return None
            
            return output_lines

        except FileNotFoundError:
            self.logger.error("Erreur: L'exécutable 'adb' est introuvable. Veuillez l'installer et l'ajouter à votre PATH.")
            return None
        except Exception as e:
            self.logger.error(f"Une erreur inattendue est survenue: {e}")
            return None

    def check_adb(self):
        self.logger.info("Vérification de l'installation d'ADB...")
        output = self.run_command("version")
        if output and "Android Debug Bridge version" in output[0]:
            self.logger.success("ADB est installé.")
            return True
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

    def get_devices_detailed(self) -> list[dict]:
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
                
                display_name = f"{icon} {device_id} ({model})"

                devices.append({
                    "id": device_id,
                    "type": conn_type,
                    "display_name": display_name,
                    "model": model,
                    "raw_line": line
                })

        return devices

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

    def get_device_ip(self, device_id: str) -> str | None:
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