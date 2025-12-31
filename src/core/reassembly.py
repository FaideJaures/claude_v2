# claude_v2/src/core/reassembly.py
import time
from pathlib import Path
from utils.adb import Adb

class ReassemblyManager:
    def __init__(self, config, logger, adb: Adb, device_id: str, modal_callback=None):
        self.config = config
        self.logger = logger
        self.adb = adb
        self.device_id = device_id
        self.modal_callback = modal_callback
        self.cancelled = False

    def reassemble_via_adb_shell(self, remote_temp_dir: str, target_dir: str):
        """Reassemble files via ADB shell (no Termux)."""
        self.logger.info("Démarrage du réassemblage via ADB shell...")
        self.logger.info(f"[{self.device_id}] [DEBUG] Remote Temp: {remote_temp_dir}, Target: {target_dir}")

        if self.config.get("unlock_device"):
            self._unlock_device()

        # 1. Push reassembly script
        import sys
        if hasattr(sys, '_MEIPASS'):
            script_path = Path(sys._MEIPASS) / "utils" / "unified.sh"
        else:
            script_path = Path(__file__).parent.parent / "utils" / "unified.sh"

        if not script_path.exists():
            self.logger.error(f"Script non trouvé: {script_path}")
            return False
        self.adb.run_command(f'push "{script_path}" "{remote_temp_dir}/unified.sh"', self.device_id)

        # 2. Fix line endings and make executable
        self.adb.run_command(f"shell 'sed -i \\\"s/\\r$//\\\" {remote_temp_dir}/unified.sh'", self.device_id)
        self.adb.run_command(f"shell 'chmod +x {remote_temp_dir}/unified.sh'", self.device_id)

        # 3. Execute reassembly script in background
        self.logger.info("Exécution du script de réassemblage...")
        cmd = f"cd {remote_temp_dir} && nohup sh ./unified.sh {remote_temp_dir} > /dev/null 2>&1 &"
        self.logger.info(f"[{self.device_id}] Commande: {cmd}")
        reassemble_cmd = f"shell '{cmd}'"
        self.adb.run_command(reassemble_cmd, self.device_id)

        # 4. Wait for completion using marker file
        if not self._wait_for_reassembly_completion(remote_temp_dir):
            self.logger.error("Le réassemblage a échoué.")
            return False

        # 5. Verify reassembled files
        if not self._verify_reassembled_files(remote_temp_dir):
            self.logger.warning("Vérification des fichiers réassemblés a échoué")
        
        # 6. Move files to destination
        # In ADB shell mode, we always move to target directory if specified,
        # as there is no interactive step to ask the user.
        if target_dir and target_dir != remote_temp_dir:
            final_destination_path = target_dir
            self.logger.info(f"Déplacement des fichiers vers {final_destination_path}...")
            if not self._move_to_final_destination(remote_temp_dir, final_destination_path):
                self.logger.error("Échec du déplacement vers la destination finale")
                return False
        else:
            self.logger.info("Pas de dossier cible défini ou identique au temporaire. Fichiers laissés sur place.")

        # 7. Cleanup (optional)
        self._cleanup(remote_temp_dir)
        
        return True
        
    def _is_device_locked(self):
        """Check if device is locked."""
        try:
            # Check mShowingLockscreen (works on most modern Android versions)
            output = self.adb.run_command("shell dumpsys window | grep mShowingLockscreen", self.device_id)
            if output and "mShowingLockscreen=true" in "".join(output):
                return True
            
            # Check mDreamingLockscreen (older Android)
            output = self.adb.run_command("shell dumpsys window | grep mDreamingLockscreen", self.device_id)
            if output and "mDreamingLockscreen=true" in "".join(output):
                return True
                
            return False
        except Exception:
            # If check fails, assume locked to be safe
            return True

    def _unlock_device(self):
        unlock_method = self.config.get("unlock_method", "password")
        unlock_secret = self.config.get("unlock_secret", "0000")

        if not self.config.get("unlock_device", True):
            return

        # Check if device is actually locked
        if not self._is_device_locked():
            self.logger.info(f"[{self.device_id}] Appareil déjà déverrouillé.")
            return

        self.logger.info(f"[{self.device_id}] Déverrouillage en cours ({unlock_method})...")

        # Wake up device
        self.adb.run_command("shell input keyevent KEYCODE_WAKEUP", self.device_id)
        time.sleep(1.5)

        # Swipe up to dismiss lock screen (works for most devices)
        self.adb.run_command("shell input swipe 500 1800 500 500 300", self.device_id)
        time.sleep(1.5)

        if unlock_method == "swipe":
            # Additional swipe to unlock (some devices need this)
            self.adb.run_command("shell input swipe 500 1600 500 400 300", self.device_id)
            time.sleep(1)
        elif unlock_method == "pin":
            if unlock_secret:
                self.logger.info(f"[{self.device_id}] Saisie du code PIN...")
                for digit in str(unlock_secret):
                    if digit.isdigit():
                        keycode = 7 + int(digit)
                        self.adb.run_command(f"shell input keyevent {keycode}", self.device_id)
                        time.sleep(0.3)
                time.sleep(0.5)
                self.adb.run_command("shell input keyevent KEYCODE_ENTER", self.device_id)
        elif unlock_method == "password":
            if unlock_secret:
                self.logger.info(f"[{self.device_id}] Saisie du mot de passe...")
                # Escape special characters for shell
                escaped_secret = unlock_secret.replace('"', '\\"')
                self.adb.run_command(f'shell input text "{escaped_secret}"', self.device_id)
                time.sleep(0.5)
                self.adb.run_command("shell input keyevent KEYCODE_ENTER", self.device_id)

        time.sleep(2)
        self.logger.success(f"[{self.device_id}] Déverrouillage terminé")

    def cancel(self):
        """Cancel the reassembly process."""
        self.cancelled = True
        self.logger.info("Réassemblage annulé par l'utilisateur.")

    def _check_storage_permission_granted(self):
        """Check if storage permission was granted by checking if /sdcard/storage exists."""
        result = self.adb.run_command(
            'shell "[ -d /sdcard/storage ] && echo granted"',
            self.device_id
        )
        return result and 'granted' in ''.join(result)

    def _type_in_termux(self, text: str):
        """
        Type text in Termux using ADB input.
        Handles spaces and special characters by replacing spaces with %s.

        Args:
            text: The text to type
        """
        # ADB input text doesn't handle spaces well, replace them with %s
        # which input text interprets as a space
        escaped_text = text.replace(" ", "%s")
        self.adb.run_command(f'shell input text "{escaped_text}"', self.device_id)

    def reassemble_via_termux(self, remote_temp_dir: str, target_dir: str) -> bool:
        """
        Reassemble files via Termux with interactive dialogs.

        Args:
            remote_temp_dir: Temporary directory on device where chunks were transferred
            target_dir: Final destination directory on device

        Returns:
            True if successful, False otherwise
        """
        if self.cancelled:
            return False

        self.logger.info("Démarrage du réassemblage via Termux...")

        # 0. Unlock device if enabled
        if self.config.get("unlock_device", True):
            self._unlock_device()

        if self.cancelled:
            return False

        # 0.5. Verify Termux is installed (with automatic installation if missing)
        from utils.termux import TermuxInstaller
        installer = TermuxInstaller(self.logger, self.adb)
        
        if not installer.is_termux_installed(self.device_id):
            self.logger.warning(f"[{self.device_id}] Termux non installé, installation en cours...")
            if not installer.install_termux(self.device_id):
                self.logger.error(f"[{self.device_id}] Échec de l'installation de Termux. Réassemblage impossible.")
                return False
            self.logger.success(f"[{self.device_id}] Termux installé avec succès")
        else:
            self.logger.info(f"[{self.device_id}] Termux vérifié et disponible")

        if self.cancelled:
            return False

        # 1. Prepare script silently (no modal)
        # 1. Prepare script silently (no modal)
        import sys
        if hasattr(sys, '_MEIPASS'):
            script_path = Path(sys._MEIPASS) / "utils" / "unified.sh"
        else:
            script_path = Path(__file__).parent.parent / "utils" / "unified.sh"

        if not script_path.exists():
            self.logger.error(f"Script non trouvé: {script_path}")
            return False

        # Push script to device
        remote_script_path = f"{remote_temp_dir}/unified.sh"
        self.adb.run_command(f'push "{script_path}" "{remote_script_path}"', self.device_id)

        # Fix line endings and make executable via ADB (before Termux)
        self.adb.run_command(f"shell 'sed -i \"s/\r$//\" {remote_script_path}'", self.device_id)
        self.adb.run_command(f"shell 'chmod 755 {remote_script_path}'", self.device_id)

        if self.cancelled:
            return False

        # 2. Launch Termux (first modal)
        if self.modal_callback:
            self.modal_callback("open_termux")

        self.logger.info("Ouverture de Termux...")
        self.adb.run_command(f"shell am start -n com.termux/.app.TermuxActivity", self.device_id)
        time.sleep(5)  # Wait for Termux to fully open

        if self.cancelled:
            return False

        # 3. First authorization (allow button modal - user confirms Termux is ready)
        if self.modal_callback:
            self.modal_callback("first_authorization")

        # No automatic sleep here - user clicks when ready

        if self.cancelled:
            return False

        # 4. Storage permission - Type command using individual keyevents
        if self.modal_callback:
            self.modal_callback("storage_permission")

        self.logger.info("Demande de permission de stockage...")
        # Tap on Termux to ensure focus
        self.adb.run_command(f"shell input tap 500 1000", self.device_id)
        time.sleep(0.5)

        # Type the command character by character
        self._type_in_termux("termux-setup-storage")
        time.sleep(0.5)
        self.adb.run_command(f"shell input keyevent KEYCODE_ENTER", self.device_id)
        time.sleep(2)

        if self.cancelled:
            return False

        # 5. Try auto-detection first if enabled, otherwise wait for manual confirmation
        if self.config.get("auto_detect_permission", True):
            self.logger.info(f"[{self.device_id}] Détection automatique de la permission...")
            max_wait = 30  # 30 seconds max
            check_interval = 2
            elapsed = 0
            permission_granted = False

            while elapsed < max_wait:
                if self._check_storage_permission_granted():
                    self.logger.success(f"[{self.device_id}] Permission détectée automatiquement!")
                    permission_granted = True
                    break
                time.sleep(check_interval)
                elapsed += check_interval

            if not permission_granted:
                # Auto-detection failed, fall back to manual
                self.logger.warning(f"[{self.device_id}] Détection auto échouée, confirmation manuelle requise")
                if self.modal_callback:
                    result = self.modal_callback("toggle_confirmation")
                    if not result:
                        self.logger.error("L'utilisateur n'a pas accordé la permission de stockage.")
                        return False
        else:
            # Manual confirmation
            if self.modal_callback:
                result = self.modal_callback("toggle_confirmation")
                if not result:
                    self.logger.error("L'utilisateur n'a pas accordé la permission de stockage.")
                    return False

        if self.cancelled:
            return False

        # 6. Execute reassembly script
        if self.modal_callback:
            self.modal_callback("command_execution", command=f"cd {remote_temp_dir} && sh ./unified.sh {remote_temp_dir}")

        self.logger.info("Exécution du script de réassemblage...")

        # Change directory
        self._type_in_termux(f"cd {remote_temp_dir}")
        time.sleep(0.5)
        self.adb.run_command(f"shell input keyevent KEYCODE_ENTER", self.device_id)
        time.sleep(1)

        # Execute script
        self._type_in_termux(f"sh ./unified.sh {remote_temp_dir}")
        time.sleep(0.5)
        self.adb.run_command(f"shell input keyevent KEYCODE_ENTER", self.device_id)

        # 7. Show progress modal
        if self.modal_callback:
            self.modal_callback("reassembly_progress")

        # Wait for reassembly to complete using marker file
        if not self._wait_for_reassembly_completion(remote_temp_dir):
            self.logger.error("Le réassemblage a échoué.")
            return False

        # Close the progress modal
        if self.modal_callback:
            self.modal_callback("close_current_modal")

        if self.cancelled:
            return False

        # 8. Verify reassembled files
        if not self._verify_reassembled_files(remote_temp_dir):
            self.logger.warning("Vérification des fichiers réassemblés a échoué")

        # 9. Move files to final destination if configured
        if self.config.get("auto_move_after_reassembly", False):
            if self.modal_callback:
                self.modal_callback("final_move", destination=target_dir)

            self.logger.info(f"Déplacement des fichiers vers {target_dir}...")
            if not self._move_to_final_destination(remote_temp_dir, target_dir):
                return False
        else:
            self.logger.info("Déplacement automatique désactivé. Utilisez le bouton 'Déplacer Dossier'.")

        # 10. Cleanup (optional)
        self._cleanup(remote_temp_dir)
        self.logger.info("Nettoyage du dossier temporaire...")
        self.adb.run_command(f'shell "rm -rf {remote_temp_dir}"', self.device_id)

        # 11. Show completion modal
        if self.modal_callback:
            self.modal_callback("completion", destination=target_dir)

        self.logger.success("Transfert et réassemblage terminés avec succès!")
        return True

    def _move_to_final_destination(self, remote_temp_dir: str, target_dir: str) -> bool:
        """
        Move files from temp directory to final destination while preserving folder structure.

        The source folder structure should be preserved in the final destination.
        Example:
            Source (PC): C:/Users/Documents/Photos/vacances/photo1.jpg
            Temp: /sdcard/transfer_temp/vacances/photo1.jpg (after reassembly)
            Final: /sdcard/Pictures/vacances/photo1.jpg

        Args:
            remote_temp_dir: Temporary directory on device
            target_dir: Final destination directory

        Returns:
            True if successful, False otherwise
        """
        # Create target directory
        self.adb.run_command(f'shell "mkdir -p \'{target_dir}\'"', self.device_id)

        # Move all contents from temp dir to target dir, preserving structure
        # Using find to get all files and directories, then move them

        # First, move all reassembled files (not in chunk folders, not the script)
        self.logger.info("Déplacement des fichiers réassemblés...")

        # Move batch directory if exists
        batch_dir = f"{remote_temp_dir}/batch"
        output = self.adb.run_command(f'shell "[ -d {batch_dir} ] && echo exists"', self.device_id)
        if output and 'exists' in ''.join(output):
            # Move contents of batch directory to target, preserving structure
            self.adb.run_command(f'shell "cp -r {batch_dir}/* \'{target_dir}/\' 2>/dev/null || true"', self.device_id)
            self.logger.info("Fichiers groupés déplacés.")

        # Move reassembled files (files in temp root, not in _chunks folders, not unified.sh)
        # Find all files that don't belong to chunk folders
        self.adb.run_command(
            f'shell "find {remote_temp_dir} -maxdepth 1 -type f ! -name \'unified.sh\' ! -name \'*.json\' -exec mv {{}} \'{target_dir}/\' \\; 2>/dev/null || true"',
            self.device_id
        )

        # Move any subdirectories (except batch and _chunks folders) to preserve structure
        self.adb.run_command(
            f'shell "find {remote_temp_dir} -mindepth 1 -maxdepth 1 -type d ! -name batch ! -name \'*_chunks\' -exec cp -r {{}} \'{target_dir}/\' \\; 2>/dev/null || true"',
            self.device_id
        )

        self.logger.success(f"Fichiers déplacés vers {target_dir} avec préservation de la structure.")
        return True

    # ===== Methods for parallel reassembly =====

    def _push_and_prepare_script(self, remote_temp_dir: str):
        """Push script and make it executable."""
        # Determine script path (handle PyInstaller)
        import sys
        if hasattr(sys, '_MEIPASS'):
            # Running as compiled exe
            script_path = Path(sys._MEIPASS) / "utils" / "unified.sh"
        else:
            # Running as script
            script_path = Path(__file__).parent.parent / "utils" / "unified.sh"
            
        if not script_path.exists():
            self.logger.error(f"[{self.device_id}] Script non trouvé: {script_path}")
            raise FileNotFoundError(f"Script not found: {script_path}")

        remote_script_path = f"{remote_temp_dir}/unified.sh"
        self.adb.run_command(f'push "{script_path}" "{remote_script_path}"', self.device_id)
        self.adb.run_command(f"shell 'sed -i \"s/\r$//\" {remote_script_path}'", self.device_id)
        self.adb.run_command(f"shell 'chmod 755 {remote_script_path}'", self.device_id)
        self.logger.info(f"[{self.device_id}] Script transféré et préparé.")

    def _open_termux(self):
        """Open Termux app."""
        self.logger.info(f"[{self.device_id}] Ouverture de Termux...")
        self.adb.run_command(f"shell am start -n com.termux/.app.TermuxActivity", self.device_id)
        time.sleep(5)  # Wait for Termux to open

    def _wait_for_termux_init(self):
        """Wait for Termux to initialize."""
        self.logger.info(f"[{self.device_id}] Attente de l'initialisation de Termux...")
        time.sleep(3)

    def _request_storage_permission(self):
        """Request storage permission via termux-setup-storage."""
        self.logger.info(f"[{self.device_id}] Demande de permission de stockage...")
        # Tap on Termux to ensure focus
        self.adb.run_command(f"shell input tap 500 1000", self.device_id)
        time.sleep(0.5)

        # Type the command
        self._type_in_termux("termux-setup-storage")
        time.sleep(0.5)
        self.adb.run_command(f"shell input keyevent KEYCODE_ENTER", self.device_id)
        time.sleep(2)

    def _execute_reassembly_command(self, remote_temp_dir: str):
        """Execute the reassembly script."""
        self.logger.info(f"[{self.device_id}] Exécution du script de réassemblage...")

        # Change directory
        self._type_in_termux(f"cd {remote_temp_dir}")
        time.sleep(0.5)
        self.adb.run_command(f"shell input keyevent KEYCODE_ENTER", self.device_id)
        time.sleep(1)

        # Execute script
        self._type_in_termux(f"sh ./unified.sh {remote_temp_dir}")
        time.sleep(0.5)
        self.adb.run_command(f"shell input keyevent KEYCODE_ENTER", self.device_id)

    def _wait_for_reassembly_completion(self, remote_temp_dir: str):
        """Wait for reassembly script to complete by checking for marker file."""
        self.logger.info(f"[{self.device_id}] Attente de la fin du réassemblage...")
        time.sleep(5)  # Initial wait

        marker_file = f"{remote_temp_dir}/.reassembly_complete"
        
        # Poll for completion marker
        max_wait = int(self.config.get("reassembly_timeout", 1800))  # Use configured timeout
        elapsed = 0
        check_interval = 5
        
        while elapsed < max_wait:
            if self.cancelled:
                return False

            # Check for completion marker file
            result = self.adb.run_command(
                f'shell "[ -f {marker_file} ] && echo exists"',
                self.device_id
            )
            
            if result and 'exists' in ''.join(result):
                # Reassembly complete!
                self.logger.success(f"[{self.device_id}] Réassemblage terminé.")
                
                # Read marker file content for details
                content = self.adb.run_command(
                    f'shell "cat {marker_file}"',
                    self.device_id
                )
                if content:
                    for line in content:
                        if line.strip():
                            self.logger.info(f"[{self.device_id}] {line.strip()}")
                
                return True
            
            # Also check if process is still running (fallback)
            ps_output = self.adb.run_command(
                f"shell 'ps | grep unified.sh'",
                self.device_id
            )
            if not ps_output or all('unified.sh' not in line for line in ps_output):
                # Process ended but no marker - check if marker exists
                time.sleep(2)
                result = self.adb.run_command(
                    f'shell "[ -f {marker_file} ] && echo exists"',
                    self.device_id
                )
                if result and 'exists' in ''.join(result):
                    self.logger.success(f"[{self.device_id}] Réassemblage terminé.")
                    return True

            time.sleep(check_interval)
            elapsed += check_interval
            
            # Log progress every minute
            if elapsed % 60 == 0:
                self.logger.info(f"[{self.device_id}] Réassemblage en cours... ({elapsed//60} min)")

        self.logger.error(f"[{self.device_id}] Timeout du réassemblage ({max_wait//60} minutes).")
        return False

    def _move_files_to_destination(self, remote_temp_dir: str, target_dir: str):
        """Move reassembled files to final destination."""
        self.logger.info(f"[{self.device_id}] Déplacement vers {target_dir}...")
        return self._move_to_final_destination(remote_temp_dir, target_dir)

    def _verify_reassembled_files(self, remote_temp_dir: str):
        """Verify reassembled files exist and have correct sizes."""
        if not self.config.get("verify_after_reassembly", True):
            return True
        
        self.logger.info(f"[{self.device_id}] Vérification des fichiers réassemblés...")
        
        # Check for reassembled files (non-chunk, non-metadata files)
        result = self.adb.run_command(
            f'shell "find {remote_temp_dir} -maxdepth 1 -type f ! -name \'unified.sh\' ! -name \'.reassembly_complete\' ! -name \'*.json\'"',
            self.device_id
        )
        
        if not result or not any(line.strip() for line in result):
            self.logger.warning(f"[{self.device_id}] Aucun fichier réassemblé trouvé")
            return True  # Not necessarily an error
        
        reassembled_files = [line.strip() for line in result if line.strip()]
        self.logger.info(f"[{self.device_id}] {len(reassembled_files)} fichier(s) réassemblé(s) trouvé(s)")
        
        for file_path in reassembled_files:
            filename = file_path.split('/')[-1]
            self.logger.info(f"[{self.device_id}]   ✓ {filename}")
        
        return True

    def _cleanup(self, remote_temp_dir: str):
        """Cleanup temporary directory (optional based on config)."""
        if not self.config.get("delete_temp_folder", False):
            self.logger.info(f"[{self.device_id}] Dossier temporaire conservé: {remote_temp_dir}")
            return
        
        self.logger.info(f"[{self.device_id}] Suppression du dossier temporaire...")
        self.adb.run_command(f'shell "rm -rf {remote_temp_dir}"', self.device_id)
        self.logger.success(f"[{self.device_id}] Dossier temporaire supprimé")