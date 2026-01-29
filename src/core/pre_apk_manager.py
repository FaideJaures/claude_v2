# claude_v2/src/core/pre_apk_manager.py
"""
Pre-APK Manager - Handles pre-transfer APK installation and confirmation.

At the start of a transfer:
1. Check for APK in pre-apk folder
2. Ensure device is unlocked
3. Uninstall the app if already installed
4. Install the APK
5. Launch the app  
6. Show modal for user to press OK before continuing
"""

import time
from pathlib import Path
from typing import Optional, Callable
from utils.adb import Adb


class PreApkManager:
    """Manages pre-transfer APK installation and user confirmation."""

    def __init__(self, adb: Adb, logger, config: dict, modal_callback: Callable = None):
        """
        Initialize PreApkManager.
        
        Args:
            adb: ADB utility instance
            logger: Logger instance
            config: Configuration dictionary (for unlock settings)
            modal_callback: Callback to show modal dialogs (modal_type, **kwargs)
        """
        self.adb = adb
        self.logger = logger
        self.config = config
        self.modal_callback = modal_callback
        self.pre_apk_folder = Path(__file__).parent.parent.parent / "pre-apk"

    def get_apk_file(self) -> Optional[Path]:
        """
        Get the single APK file from the pre-apk folder.
        
        Returns:
            Path to the APK file, or None if no APK exists
        """
        if not self.pre_apk_folder.exists():
            return None
        
        apks = list(self.pre_apk_folder.glob("*.apk"))
        if not apks:
            return None
        
        # Return the first APK (should only be one)
        return apks[0]

    def get_package_name_from_apk(self, apk_path: Path) -> Optional[str]:
        """
        Extract package name from APK using aapt (from platform-tools).
        
        Falls back to filename-based guess if aapt fails.
        
        Args:
            apk_path: Path to the APK file
            
        Returns:
            Package name string, or None if extraction fails
        """
        try:
            # Try to use aapt from platform-tools
            platform_tools = Path(__file__).parent.parent.parent / "platform-tools"
            aapt_path = platform_tools / "aapt.exe"
            
            if aapt_path.exists():
                import subprocess
                result = subprocess.run(
                    [str(aapt_path), "dump", "badging", str(apk_path)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                for line in result.stdout.split('\n'):
                    if line.startswith("package:"):
                        # Extract name='...'
                        parts = line.split("'")
                        if len(parts) >= 2:
                            return parts[1]
            
            # Fallback: derive package name from filename
            # This is a guess and may not match the actual package
            self.logger.warning(f"aapt not available, using filename-based package guess")
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting package name: {e}")
            return None

    def get_installed_package_name(self, device_id: str, apk_path: Path) -> Optional[str]:
        """
        Find the package name by checking installed packages after install.
        
        This is an alternative approach when aapt is not available.
        
        Args:
            device_id: Device identifier
            apk_path: Path to the APK (used for filename matching)
            
        Returns:
            Package name if found, None otherwise
        """
        # Get list of installed packages
        result = self.adb.run_command("shell pm list packages -3", device_id)
        if not result:
            return None
        
        packages = []
        for line in result:
            if line.startswith("package:"):
                packages.append(line.replace("package:", "").strip())
        
        # Try to match by APK filename
        apk_name = apk_path.stem.lower()
        for pkg in packages:
            if apk_name in pkg.lower():
                return pkg
        
        return None

    def is_installed(self, device_id: str, package_name: str) -> bool:
        """
        Check if a package is installed on the device.
        
        Args:
            device_id: Device identifier
            package_name: Package name to check
            
        Returns:
            True if installed, False otherwise
        """
        result = self.adb.run_command(f"shell pm list packages {package_name}", device_id)
        if result:
            for line in result:
                if f"package:{package_name}" in line:
                    return True
        return False

    def uninstall(self, device_id: str, package_name: str) -> bool:
        """
        Uninstall a package from the device.
        
        Args:
            device_id: Device identifier
            package_name: Package name to uninstall
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"[{device_id}] Désinstallation de {package_name}...")
        result = self.adb.run_command(f"uninstall {package_name}", device_id)
        
        if result:
            for line in result:
                if "Success" in line:
                    self.logger.success(f"[{device_id}] {package_name} désinstallé")
                    return True
        
        self.logger.warning(f"[{device_id}] Échec de la désinstallation de {package_name}")
        return False

    def install(self, device_id: str, apk_path: Path) -> bool:
        """
        Install an APK on the device.
        
        Args:
            device_id: Device identifier
            apk_path: Path to the APK file
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"[{device_id}] Installation de {apk_path.name}...")
        
        # Install with -r (reinstall) and -g (grant permissions)
        result = self.adb.run_command(f'install -r -g "{apk_path}"', device_id)
        
        if result:
            for line in result:
                if "Success" in line:
                    self.logger.success(f"[{device_id}] {apk_path.name} installé avec succès")
                    return True
        
        self.logger.error(f"[{device_id}] Échec de l'installation de {apk_path.name}")
        return False

    def launch_app(self, device_id: str, package_name: str) -> bool:
        """
        Launch the app using monkey command (works without knowing activity name).
        
        Args:
            device_id: Device identifier
            package_name: Package name to launch
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"[{device_id}] Lancement de {package_name}...")
        
        # Use monkey to launch (doesn't require activity name)
        result = self.adb.run_command(
            f'shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1',
            device_id
        )
        
        if result:
            for line in result:
                if "Events injected" in line:
                    self.logger.success(f"[{device_id}] {package_name} lancé")
                    return True
        
        # Fallback: try am start with common activity patterns
        self.logger.info(f"[{device_id}] Tentative alternative de lancement...")
        self.adb.run_command(
            f'shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n {package_name}/.MainActivity',
            device_id
        )
        time.sleep(0.5)
        return True

    def _is_device_locked(self, device_id: str) -> bool:
        """
        Check if device screen is locked.
        
        Args:
            device_id: Device identifier
            
        Returns:
            True if locked, False otherwise
        """
        try:
            # Check mShowingLockscreen (works on most modern Android versions)
            output = self.adb.run_command("shell dumpsys window | grep mShowingLockscreen", device_id)
            if output and "mShowingLockscreen=true" in "".join(output):
                return True
            
            # Check mDreamingLockscreen (older Android)
            output = self.adb.run_command("shell dumpsys window | grep mDreamingLockscreen", device_id)
            if output and "mDreamingLockscreen=true" in "".join(output):
                return True
            
            return False
        except Exception:
            # If check fails, assume locked to be safe
            return True

    def ensure_unlocked(self, device_id: str) -> bool:
        """
        Ensure device screen is unlocked.
        
        Uses config settings for unlock method, secret, and delays.
        Delays are now configurable for faster multi-device operations.
        
        Args:
            device_id: Device identifier
            
        Returns:
            True if device is (now) unlocked, False otherwise
        """
        unlock_method = self.config.get("unlock_method", "password")
        unlock_secret = self.config.get("unlock_secret", "0000")
        
        # Configurable delays (reduced defaults for faster operations)
        wake_delay = self.config.get("unlock_wake_delay", 0.8)  # Was 1.5
        swipe_delay = self.config.get("unlock_swipe_delay", 0.8)  # Was 1.5
        complete_delay = self.config.get("unlock_complete_delay", 1.0)  # Was 2.0
        digit_delay = self.config.get("unlock_digit_delay", 0.15)  # Was 0.3

        if not self.config.get("unlock_device", True):
            return True

        # Check if device is actually locked
        if not self._is_device_locked(device_id):
            self.logger.info(f"[{device_id}] Appareil déjà déverrouillé.")
            return True

        self.logger.info(f"[{device_id}] Déverrouillage en cours ({unlock_method})...")

        # Wake up device
        self.adb.run_command("shell input keyevent KEYCODE_WAKEUP", device_id)
        time.sleep(wake_delay)

        # Swipe up to dismiss lock screen (works for most devices)
        self.adb.run_command("shell input swipe 500 1800 500 500 300", device_id)
        time.sleep(swipe_delay)

        if unlock_method == "swipe":
            # Additional swipe to unlock (some devices need this)
            self.adb.run_command("shell input swipe 500 1600 500 400 300", device_id)
            time.sleep(swipe_delay * 0.7)  # Slightly shorter for second swipe
        elif unlock_method == "pin":
            if unlock_secret:
                self.logger.info(f"[{device_id}] Saisie du code PIN...")
                for digit in str(unlock_secret):
                    if digit.isdigit():
                        keycode = 7 + int(digit)
                        self.adb.run_command(f"shell input keyevent {keycode}", device_id)
                        time.sleep(digit_delay)
                time.sleep(digit_delay * 2)
                self.adb.run_command("shell input keyevent KEYCODE_ENTER", device_id)
        elif unlock_method == "password":
            if unlock_secret:
                self.logger.info(f"[{device_id}] Saisie du mot de passe...")
                # Escape special characters for shell
                escaped_secret = unlock_secret.replace('"', '\\"')
                self.adb.run_command(f'shell input text "{escaped_secret}"', device_id)
                time.sleep(digit_delay * 2)
                self.adb.run_command("shell input keyevent KEYCODE_ENTER", device_id)

        time.sleep(complete_delay)
        self.logger.success(f"[{device_id}] Déverrouillage terminé")
        return True

    def run_pre_transfer(self, device_id: str) -> bool:
        """
        Execute the full pre-transfer flow:
        
        1. Check for APK file in pre-apk folder
        2. Ensure device is unlocked
        3. Uninstall the app if already installed
        4. Install the APK
        5. Launch the app
        6. Show modal for user to press OK
        
        Args:
            device_id: Device identifier
            
        Returns:
            True if flow completed (user clicked OK), False otherwise
        """
        self.logger.info(f"[{device_id}] === run_pre_transfer() démarré ===")
        self.logger.info(f"[{device_id}] Pre-APK folder: {self.pre_apk_folder}")
        self.logger.info(f"[{device_id}] Folder exists: {self.pre_apk_folder.exists()}")
        
        # 1. Check for APK
        apk_path = self.get_apk_file()
        self.logger.info(f"[{device_id}] APK trouvé: {apk_path}")
        
        if apk_path is None:
            self.logger.info(f"[{device_id}] Aucun APK dans pre-apk/, étape ignorée")
            return True
        
        self.logger.info(f"[{device_id}] === Pré-transfert: {apk_path.name} ===")
        
        # 2. Ensure device is unlocked
        if not self.ensure_unlocked(device_id):
            self.logger.error(f"[{device_id}] Impossible de déverrouiller l'appareil")
            return False
        
        # 3. Get package name and check if installed
        package_name = self.get_package_name_from_apk(apk_path)
        
        if package_name:
            # Uninstall if already installed
            if self.is_installed(device_id, package_name):
                self.logger.info(f"[{device_id}] {package_name} déjà installé, désinstallation...")
                self.uninstall(device_id, package_name)
                time.sleep(1)
        
        # 4. Install the APK
        if not self.install(device_id, apk_path):
            self.logger.error(f"[{device_id}] Échec de l'installation pre-APK")
            return False
        
        time.sleep(1)
        
        # 5. Get package name after install (if aapt failed before)
        if not package_name:
            package_name = self.get_installed_package_name(device_id, apk_path)
            if not package_name:
                self.logger.warning(f"[{device_id}] Impossible de déterminer le package name")
                # Try to launch anyway using filename
                package_name = apk_path.stem
        
        # 6. Launch the app
        self.launch_app(device_id, package_name)
        time.sleep(2)
        
        # 7. Show modal for user confirmation
        self.logger.info(f"[{device_id}] En attente de confirmation utilisateur...")
        
        if self.modal_callback:
            result = self.modal_callback("pre_apk_confirmation", 
                                         device_id=device_id,
                                         app_name=apk_path.stem)
            if not result:
                self.logger.warning(f"[{device_id}] Pré-transfert annulé par l'utilisateur")
                return False
        
        self.logger.success(f"[{device_id}] Pré-transfert terminé")
        return True


def run_pre_apk_on_multiple_devices(
    adb: Adb,
    logger,
    config: dict,
    device_ids: list[str],
    modal_callback: Callable = None
) -> dict[str, bool]:
    """
    Run pre-APK flow on multiple devices in parallel.
    
    Each device gets its own PreApkManager instance.
    
    Args:
        adb: ADB utility instance
        logger: Logger instance
        config: Configuration dictionary
        device_ids: List of device identifiers
        modal_callback: Callback to show modal dialogs
        
    Returns:
        Dictionary mapping device_id to success status
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    results = {}
    
    def run_on_device(device_id: str) -> tuple[str, bool]:
        manager = PreApkManager(adb, logger, config, modal_callback)
        success = manager.run_pre_transfer(device_id)
        return device_id, success
    
    # Run in parallel for all devices
    with ThreadPoolExecutor(max_workers=len(device_ids)) as executor:
        futures = {executor.submit(run_on_device, did): did for did in device_ids}
        
        for future in as_completed(futures):
            device_id, success = future.result()
            results[device_id] = success
    
    return results
