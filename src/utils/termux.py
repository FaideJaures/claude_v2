# claude_v2/src/utils/termux.py
import os
from utils.adb import Adb

class TermuxInstaller:
    def __init__(self, logger, adb: Adb):
        self.logger = logger
        self.adb = adb

    def is_termux_installed(self, device_id):
        """Check if Termux is installed on the device."""
        self.logger.info(f"Vérification de l'installation de Termux sur l'appareil {device_id}...")
        output = self.adb.run_command("shell pm list packages com.termux", device_id)
        if output and "package:com.termux" in ''.join(output):
            self.logger.success("Termux est déjà installé.")
            return True
        else:
            self.logger.info("Termux n'est pas installé.")
            return False

    def install_termux(self, device_id):
        """Install Termux on the device."""
        self.logger.info(f"[{device_id}] Installation de Termux...")

        # Path to the Termux APK - check both locations
        from pathlib import Path
        apk_path = Path(r"C:\\Users\\hp\\Desktop\\goo\\claude_v2\\apk\\termux.apk")
        if not apk_path.exists():
            apk_path = Path("apk/termux.apk")
        if not apk_path.exists():
            self.logger.error(f"Erreur: Le fichier termux.apk n'a pas été trouvé dans claude_v2/apk/ ou apk/")
            return False

        # Install the APK
        output = self.adb.run_command(f'install -r "{apk_path}"', device_id)
        if output and "Success" in ''.join(output):
            self.logger.success(f"[{device_id}] Termux installé avec succès.")
            return True
        else:
            self.logger.error(f"[{device_id}] Échec de l'installation de Termux.")
            return False
