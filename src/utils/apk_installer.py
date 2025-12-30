import os
from pathlib import Path

class ApkInstaller:
    def __init__(self, adb, logger):
        self.adb = adb
        self.logger = logger

    def install_apks(self, apk_folder, device_id=None):
        """
        Installs all APKs from the specified folder to the device.
        """
        apk_path = Path(apk_folder)
        if not apk_path.exists():
            self.logger.error(f"Dossier APK introuvable: {apk_folder}")
            return

        apks = list(apk_path.glob("*.apk"))
        if not apks:
            self.logger.info("Aucun fichier APK trouvé.")
            return

        self.logger.info(f"Installation de {len(apks)} APK(s)...")

        for apk in apks:
            self.logger.info(f"Installation de {apk.name}...")
            # -r: reinstall if needed, -g: grant permissions
            result = self.adb.run_command(f'install -r -g "{apk}"', device_id)
            
            # Check for success in output (standard adb output)
            success = False
            if result:
                for line in result:
                    if "Success" in line:
                        success = True
                        break
            
            if success:
                self.logger.success(f"Successfully installed {apk.name}")
            else:
                self.logger.error(f"Failed to install {apk.name}")
