import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import threading
import time
import tempfile
from pathlib import Path
from config import (
    DEFAULT_PARALLEL_PROCESSES,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SMALL_FILE_THRESHOLD,
    DEFAULT_REMOTE_TEMP_DIR,
    DEFAULT_AGGRESSIVE_TEMP_CLEANUP,
    DEFAULT_UNLOCK_DEVICE,
    DEFAULT_UNLOCK_METHOD,
    DEFAULT_UNLOCK_SECRET,
    DEFAULT_AUTO_DETECT_PERMISSION,
    DEFAULT_USE_ADB_SHELL_MODE,
    DEFAULT_RESUME_TRANSFER,
    DEFAULT_SJF_SCHEDULING,
    DEFAULT_BUNDLE_SIZE,
)
from core.transfer import TransferManager
from utils.adb import Adb
from utils.apk_installer import ApkInstaller
from ui.modal_dialog import (
    TransferScriptModal,
    TermuxInstallModal,
    OpenTermuxModal,
    FirstAuthorizationModal,
    StoragePermissionModal,
    ToggleConfirmationModal,
    CommandExecutionModal,
    ReassemblyProgressModal,
    FinalMoveModal,
    CompletionModal
)

class SimpleLogger:
    def __init__(self, log_func):
        self.log_func = log_func

    def info(self, message):
        self.log_func(message, "info")

    def error(self, message):
        self.log_func(message, "error")

    def success(self, message):
        self.log_func(message, "success")
    
    def warning(self, message):
        self.log_func(message, "info")  # Display warnings as info (blue color)

class SettingsWindow(tk.Toplevel):
    def __init__(self, master=None, config=None):
        super().__init__(master)
        self.title("Paramètres - Optimisations v2")
        self.geometry("650x900")  # Taller window to show more settings
        self.config = config

        self.create_widgets()

    def create_widgets(self):
        # Create canvas with scrollbar
        canvas = tk.Canvas(self)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Parallel processes
        parallel_frame = tk.Frame(scrollable_frame)
        parallel_frame.pack(pady=10, padx=10, fill=tk.X)
        parallel_label = tk.Label(parallel_frame, text="Processus parallèles:")
        parallel_label.pack(side=tk.LEFT)
        self.parallel_processes = tk.IntVar(value=self.config.get("parallel_processes", DEFAULT_PARALLEL_PROCESSES))
        parallel_entry = tk.Entry(parallel_frame, textvariable=self.parallel_processes)
        parallel_entry.pack(side=tk.RIGHT)

        # Chunk size
        chunk_frame = tk.Frame(scrollable_frame)
        chunk_frame.pack(pady=10, padx=10, fill=tk.X)
        chunk_label = tk.Label(chunk_frame, text="Taille des morceaux (Mo):")
        chunk_label.pack(side=tk.LEFT)
        self.chunk_size_mb = tk.IntVar(value=self.config.get("chunk_size", DEFAULT_CHUNK_SIZE) // (1024 * 1024))
        chunk_entry = tk.Entry(chunk_frame, textvariable=self.chunk_size_mb)
        chunk_entry.pack(side=tk.RIGHT)

        # Small file threshold
        small_file_frame = tk.Frame(scrollable_frame)
        small_file_frame.pack(pady=10, padx=10, fill=tk.X)
        small_file_label = tk.Label(small_file_frame, text="Seuil des petits fichiers (Mo):")
        small_file_label.pack(side=tk.LEFT)
        self.small_file_threshold_mb = tk.IntVar(value=self.config.get("small_file_threshold", DEFAULT_SMALL_FILE_THRESHOLD) // (1024 * 1024))
        small_file_entry = tk.Entry(small_file_frame, textvariable=self.small_file_threshold_mb)
        small_file_entry.pack(side=tk.RIGHT)

        # Remote temp dir
        remote_dir_frame = tk.Frame(scrollable_frame)
        remote_dir_frame.pack(pady=10, padx=10, fill=tk.X)
        remote_dir_label = tk.Label(remote_dir_frame, text="Dossier temporaire distant:")
        remote_dir_label.pack(side=tk.LEFT)
        self.remote_temp_dir = tk.StringVar(value=self.config.get("remote_temp_dir", DEFAULT_REMOTE_TEMP_DIR))
        remote_dir_entry = tk.Entry(remote_dir_frame, textvariable=self.remote_temp_dir)
        remote_dir_entry.pack(side=tk.RIGHT)

        # Unlock device
        unlock_frame = tk.Frame(scrollable_frame)
        unlock_frame.pack(pady=10, padx=10, fill=tk.X)
        self.unlock_device = tk.BooleanVar(value=self.config.get("unlock_device", False))
        unlock_check = tk.Checkbutton(unlock_frame, text="Déverrouiller l'appareil", variable=self.unlock_device)
        unlock_check.pack(side=tk.LEFT)

        # Unlock method
        unlock_method_frame = tk.Frame(scrollable_frame)
        unlock_method_frame.pack(pady=10, padx=10, fill=tk.X)
        unlock_method_label = tk.Label(unlock_method_frame, text="Méthode de déverrouillage:")
        unlock_method_label.pack(side=tk.LEFT)
        self.unlock_method = tk.StringVar(value=self.config.get("unlock_method", "password"))
        unlock_method_menu = tk.OptionMenu(unlock_method_frame, self.unlock_method, "password", "pin", "swipe")
        unlock_method_menu.pack(side=tk.RIGHT)

        # Unlock secret
        unlock_secret_frame = tk.Frame(scrollable_frame)
        unlock_secret_frame.pack(pady=10, padx=10, fill=tk.X)
        unlock_secret_label = tk.Label(unlock_secret_frame, text="Code/Mot de passe:")
        unlock_secret_label.pack(side=tk.LEFT)
        self.unlock_secret = tk.StringVar(value=self.config.get("unlock_secret", "0000"))
        unlock_secret_entry = tk.Entry(unlock_secret_frame, textvariable=self.unlock_secret, show="*")
        unlock_secret_entry.pack(side=tk.RIGHT)

        # Use Termux for reassembly
        use_termux_frame = tk.Frame(scrollable_frame)
        use_termux_frame.pack(pady=10, padx=10, fill=tk.X)
        self.use_termux_for_reassembly = tk.BooleanVar(value=self.config.get("use_termux_for_reassembly", True))
        use_termux_check = tk.Checkbutton(use_termux_frame, text="Utiliser Termux pour le réassemblage", variable=self.use_termux_for_reassembly)
        use_termux_check.pack(side=tk.LEFT)

        # Auto move after reassembly
        auto_move_frame = tk.Frame(scrollable_frame)
        auto_move_frame.pack(pady=10, padx=10, fill=tk.X)
        self.auto_move_after_reassembly = tk.BooleanVar(value=self.config.get("auto_move_after_reassembly", False))
        auto_move_check = tk.Checkbutton(auto_move_frame, text="Déplacer automatiquement après réassemblage", variable=self.auto_move_after_reassembly)
        auto_move_check.pack(side=tk.LEFT)

        # Delete temp folder
        delete_temp_frame = tk.Frame(scrollable_frame)
        delete_temp_frame.pack(pady=10, padx=10, fill=tk.X)
        self.delete_temp_folder = tk.BooleanVar(value=self.config.get("delete_temp_folder", False))
        delete_temp_check = tk.Checkbutton(delete_temp_frame, text="Supprimer le dossier temporaire automatiquement", variable=self.delete_temp_folder)
        delete_temp_check.pack(side=tk.LEFT)

        # Verify after reassembly
        verify_after_frame = tk.Frame(scrollable_frame)
        verify_after_frame.pack(pady=10, padx=10, fill=tk.X)
        self.verify_after_reassembly = tk.BooleanVar(value=self.config.get("verify_after_reassembly", True))
        verify_after_check = tk.Checkbutton(verify_after_frame, text="Vérifier les fichiers après réassemblage", variable=self.verify_after_reassembly)
        verify_after_check.pack(side=tk.LEFT)

        # Aggressive temp cleanup
        aggressive_cleanup_frame = tk.Frame(scrollable_frame)
        aggressive_cleanup_frame.pack(pady=10, padx=10, fill=tk.X)
        self.aggressive_temp_cleanup = tk.BooleanVar(value=self.config.get("aggressive_temp_cleanup", True))
        aggressive_cleanup_check = tk.Checkbutton(aggressive_cleanup_frame, text="Nettoyage agressif du dossier temporaire", variable=self.aggressive_temp_cleanup)
        aggressive_cleanup_check.pack(side=tk.LEFT)

        # Auto-detect permission
        auto_detect_frame = tk.Frame(scrollable_frame)
        auto_detect_frame.pack(pady=10, padx=10, fill=tk.X)
        self.auto_detect_permission = tk.BooleanVar(value=self.config.get("auto_detect_permission", True))
        auto_detect_check = tk.Checkbutton(auto_detect_frame, text="Détection automatique de la permission de stockage", variable=self.auto_detect_permission)
        auto_detect_check.pack(side=tk.LEFT)

        # Reassembly Timeout
        timeout_frame = tk.Frame(scrollable_frame)
        timeout_frame.pack(pady=10, padx=10, fill=tk.X)
        timeout_label = tk.Label(timeout_frame, text="Timeout réassemblage (sec):")
        timeout_label.pack(side=tk.LEFT)
        self.reassembly_timeout = tk.IntVar(value=self.config.get("reassembly_timeout", 1800))
        timeout_entry = tk.Entry(timeout_frame, textvariable=self.reassembly_timeout)
        timeout_entry.pack(side=tk.RIGHT)

        # === OPTIMIZATION SETTINGS SECTION ===
        opt_separator = tk.Label(scrollable_frame, text="━━━ Optimisations de Transfert ━━━", font=("Arial", 10, "bold"))
        opt_separator.pack(pady=(20, 10))

        # ADB Shell Mode (Termux-free)
        adb_shell_frame = tk.Frame(scrollable_frame)
        adb_shell_frame.pack(pady=10, padx=10, fill=tk.X)
        self.use_adb_shell_mode = tk.BooleanVar(value=self.config.get("use_adb_shell_mode", True))
        adb_shell_check = tk.Checkbutton(adb_shell_frame, text="Mode ADB Shell (sans Termux)", variable=self.use_adb_shell_mode)
        adb_shell_check.pack(side=tk.LEFT)

        # Resume transfer
        resume_frame = tk.Frame(scrollable_frame)
        resume_frame.pack(pady=10, padx=10, fill=tk.X)
        self.resume_transfer = tk.BooleanVar(value=self.config.get("resume_transfer", True))
        resume_check = tk.Checkbutton(resume_frame, text="Reprendre transfert (ignorer fichiers existants)", variable=self.resume_transfer)
        resume_check.pack(side=tk.LEFT)

        # SJF Scheduling
        sjf_frame = tk.Frame(scrollable_frame)
        sjf_frame.pack(pady=10, padx=10, fill=tk.X)
        self.sjf_scheduling = tk.BooleanVar(value=self.config.get("sjf_scheduling", True))
        sjf_check = tk.Checkbutton(sjf_frame, text="SJF: Transférer petits fichiers en premier", variable=self.sjf_scheduling)
        sjf_check.pack(side=tk.LEFT)

        # Bundle size
        bundle_frame = tk.Frame(scrollable_frame)
        bundle_frame.pack(pady=10, padx=10, fill=tk.X)
        bundle_label = tk.Label(bundle_frame, text="Taille des bundles ZIP (Mo):")
        bundle_label.pack(side=tk.LEFT)
        self.bundle_size_mb = tk.IntVar(value=self.config.get("bundle_size", 50 * 1024 * 1024) // (1024 * 1024))
        bundle_entry = tk.Entry(bundle_frame, textvariable=self.bundle_size_mb)
        bundle_entry.pack(side=tk.RIGHT)

        # Save button
        save_button = tk.Button(scrollable_frame, text="Enregistrer", command=self.save_and_close)
        save_button.pack(pady=20)

    def save_and_close(self):
        self.config["parallel_processes"] = self.parallel_processes.get()
        self.config["chunk_size"] = self.chunk_size_mb.get() * 1024 * 1024
        self.config["small_file_threshold"] = self.small_file_threshold_mb.get() * 1024 * 1024
        self.config["remote_temp_dir"] = self.remote_temp_dir.get()
        self.config["unlock_device"] = self.unlock_device.get()
        self.config["unlock_method"] = self.unlock_method.get()
        self.config["unlock_secret"] = self.unlock_secret.get()
        # Note: final_destination_path removed from UI but kept in config for backward compatibility
        self.config["use_termux_for_reassembly"] = self.use_termux_for_reassembly.get()
        self.config["auto_move_after_reassembly"] = self.auto_move_after_reassembly.get()
        self.config["delete_temp_folder"] = self.delete_temp_folder.get()
        self.config["verify_after_reassembly"] = self.verify_after_reassembly.get()
        self.config["aggressive_temp_cleanup"] = self.aggressive_temp_cleanup.get()
        self.config["auto_detect_permission"] = self.auto_detect_permission.get()
        self.config["reassembly_timeout"] = self.reassembly_timeout.get()
        # New optimization settings
        self.config["use_adb_shell_mode"] = self.use_adb_shell_mode.get()
        self.config["resume_transfer"] = self.resume_transfer.get()
        self.config["sjf_scheduling"] = self.sjf_scheduling.get()
        self.config["bundle_size"] = self.bundle_size_mb.get() * 1024 * 1024
        self.master.save_config()
        self.destroy()

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("Outil de Transfert de Fichiers ADB")
        self.master.geometry("800x600")
        self.pack(fill=tk.BOTH, expand=True)
        
        self.config = self.load_config()
        self.create_widgets()
        self.logger = SimpleLogger(self.log)

        self.adb = Adb(self.logger)
        self.transfer_manager = TransferManager(self.config, self.logger)

        # Setup modal callback for reassembly
        self.transfer_manager.modal_callback = self.show_reassembly_modal
        self.current_modal = None
        self.modal_result = None

        # Cancel operation tracking
        self.cancel_requested = False
        self.cancel_lock = threading.Lock()
        self.current_reassembly_managers = {}

        self.check_adb_and_populate_devices()
        self.check_and_install_termux_on_devices()
        self.source_dir.set(self.config.get("source_dir", ""))
        self.target_dir.set(self.config.get("target_dir", ""))

    def load_config(self):
        config_path = "config.json"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
        else:
            config = {}
            
        config.setdefault("parallel_processes", DEFAULT_PARALLEL_PROCESSES)
        config.setdefault("chunk_size", DEFAULT_CHUNK_SIZE)
        config.setdefault("small_file_threshold", DEFAULT_SMALL_FILE_THRESHOLD)
        config.setdefault("remote_temp_dir", DEFAULT_REMOTE_TEMP_DIR)
        config.setdefault("aggressive_temp_cleanup", DEFAULT_AGGRESSIVE_TEMP_CLEANUP)
        config.setdefault("source_dir", "")
        config.setdefault("target_dir", "")
        config.setdefault("unlock_device", DEFAULT_UNLOCK_DEVICE)
        config.setdefault("unlock_method", DEFAULT_UNLOCK_METHOD)
        config.setdefault("unlock_secret", DEFAULT_UNLOCK_SECRET)
        config.setdefault("auto_detect_permission", DEFAULT_AUTO_DETECT_PERMISSION)
        config.setdefault("final_destination_path", "")
        # New optimization options
        config.setdefault("use_adb_shell_mode", DEFAULT_USE_ADB_SHELL_MODE)
        config.setdefault("resume_transfer", DEFAULT_RESUME_TRANSFER)
        config.setdefault("sjf_scheduling", DEFAULT_SJF_SCHEDULING)
        config.setdefault("bundle_size", DEFAULT_BUNDLE_SIZE)

        return config

    def save_config(self):
        self.config["source_dir"] = self.source_dir.get()
        self.config["target_dir"] = self.target_dir.get()
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=4)
        self.logger.success("Configuration enregistrée.")


    def create_widgets(self):
        self.source_dir = tk.StringVar()
        self.target_dir = tk.StringVar()
        self.selected_devices = []  # Liste des appareils sélectionnés
        self.all_devices = []  # Liste de tous les appareils disponibles

        # Top bar with settings and device selection
        top_bar = tk.Frame(self)
        top_bar.pack(fill=tk.X, side=tk.TOP, padx=10, pady=5)

        self.settings_button = tk.Button(top_bar, text="Paramètres", command=self.open_settings)
        self.settings_button.pack(side=tk.RIGHT, padx=5)

        save_button = tk.Button(top_bar, text="Enregistrer", command=self.save_config)
        save_button.pack(side=tk.RIGHT)

        # Device selection frame
        device_frame = tk.Frame(top_bar)
        device_frame.pack(side=tk.LEFT, expand=True, fill=tk.X)

        device_label = tk.Label(device_frame, text="Appareils:")
        device_label.pack(side=tk.LEFT, padx=5)

        # Listbox for device selection with scrollbar
        listbox_frame = tk.Frame(device_frame)
        listbox_frame.pack(side=tk.LEFT, padx=5)

        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        self.device_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE,
                                         height=3, width=30,
                                         yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.device_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.device_listbox.pack(side=tk.LEFT)

        # Buttons frame
        button_frame = tk.Frame(device_frame)
        button_frame.pack(side=tk.LEFT, padx=5)

        refresh_button = tk.Button(button_frame, text="Actualiser", command=self.populate_devices)
        refresh_button.pack(pady=2)

        select_all_button = tk.Button(button_frame, text="Tous les appareils", command=self.select_all_devices)
        select_all_button.pack(pady=2)

        clear_button = tk.Button(button_frame, text="Désélectionner", command=self.clear_device_selection)
        clear_button.pack(pady=2)


        # Source directory selection
        source_frame = tk.Frame(self, bd=2, relief=tk.GROOVE)
        source_frame.pack(pady=10, padx=10, fill=tk.X)

        source_label = tk.Label(source_frame, text="Dossier Source:")
        source_label.pack(side=tk.LEFT, padx=5, pady=5)

        source_entry = tk.Entry(source_frame, textvariable=self.source_dir, width=50)
        source_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5, pady=5)

        source_button = tk.Button(source_frame, text="Parcourir...", command=self.browse_source)
        source_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Target directory selection
        target_frame = tk.Frame(self, bd=2, relief=tk.GROOVE)
        target_frame.pack(pady=10, padx=10, fill=tk.X)

        target_label = tk.Label(target_frame, text="Dossier Cible sur l'appareil:")
        target_label.pack(side=tk.LEFT, padx=5, pady=5)

        target_entry = tk.Entry(target_frame, textvariable=self.target_dir, width=50)
        target_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5, pady=5)

        # Transfer button
        self.transfer_button = tk.Button(self, text="Démarrer le Transfert", command=self.start_transfer_thread)
        self.transfer_button.pack(pady=10)

        # Additional action buttons frame
        action_buttons_frame = tk.Frame(self)
        action_buttons_frame.pack(pady=5)

        # Termux workflow button
        self.termux_workflow_button = tk.Button(
            action_buttons_frame, 
            text="Workflow Termux", 
            command=self.start_termux_workflow
        )
        self.termux_workflow_button.pack(side=tk.LEFT, padx=5)

        # Move folder button
        self.move_folder_button = tk.Button(
            action_buttons_frame, 
            text="Déplacer Dossier", 
            command=self.manual_move_folder
        )
        self.move_folder_button.pack(side=tk.LEFT, padx=5)

        # Delete temp files button
        self.delete_temp_button = tk.Button(
            action_buttons_frame, 
            text="Supprimer Fichiers Temporaires", 
            command=self.delete_temp_files
        )
        self.delete_temp_button.pack(side=tk.LEFT, padx=5)

        # APK installer button
        self.apk_install_button = tk.Button(
            action_buttons_frame, 
            text="Installer APKs", 
            command=self.install_apks
        )
        self.apk_install_button.pack(side=tk.LEFT, padx=5)

        # Transfer timer
        self.timer_label = tk.Label(self, text="Durée: 00:00:00", font=("Arial", 12, "bold"))
        self.timer_label.pack(pady=5)
        self.transfer_start_time = None
        self.timer_running = False

        # Progress display
        progress_frame = tk.Frame(self, bd=2, relief=tk.GROOVE)
        progress_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        progress_label = tk.Label(progress_frame, text="Progression:")
        progress_label.pack(pady=5)

        self.progress_text = tk.Text(progress_frame, height=20)
        self.progress_text.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
        self.progress_text.tag_config("success", foreground="green")
        self.progress_text.tag_config("error", foreground="red")
        self.progress_text.tag_config("info", foreground="blue")


    def check_adb_and_populate_devices(self):
        if self.adb.check_adb():
            self.populate_devices()
        else:
            messagebox.showerror("Erreur ADB", "ADB n'est pas installé ou n'est pas dans le PATH. Veuillez l'installer pour continuer.")

    def check_and_install_termux_on_devices(self):
        """
        Check Termux on all connected devices at startup (informational only).
        
        Note: Termux installation now happens at transfer start (per-device).
        This startup check is kept for informational purposes only.
        """
        devices = self.adb.get_devices()
        if not devices:
            return

        self.logger.info("=== Vérification de Termux sur les appareils ===")

        for device_id in devices:
            from utils.termux import TermuxInstaller
            installer = TermuxInstaller(self.logger, self.adb)

            if not installer.is_termux_installed(device_id):
                self.logger.info(f"[{device_id}] Termux non installé (sera installé au démarrage du transfert)")
            else:
                self.logger.success(f"[{device_id}] Termux déjà installé")

        self.logger.info("=== Vérification Termux terminée ===\n")

    def populate_devices(self):
        """Populate the device listbox with connected devices."""
        devices = self.adb.get_devices()
        self.all_devices = devices

        # Clear listbox
        self.device_listbox.delete(0, tk.END)

        if devices:
            for device in devices:
                self.device_listbox.insert(tk.END, device)
            self.logger.info(f"{len(devices)} appareil(s) trouvé(s).")
        else:
            messagebox.showwarning("Aucun appareil", "Aucun appareil ADB n'a été trouvé.")

    def select_all_devices(self):
        """Select all devices in the listbox."""
        self.device_listbox.select_set(0, tk.END)
        count = self.device_listbox.size()
        self.logger.info(f"Tous les appareils sélectionnés ({count} appareil(s)).")

    def clear_device_selection(self):
        """Clear device selection."""
        self.device_listbox.selection_clear(0, tk.END)
        self.logger.info("Sélection des appareils effacée.")

    def get_selected_devices(self):
        """Get list of selected device IDs."""
        selected_indices = self.device_listbox.curselection()
        return [self.all_devices[i] for i in selected_indices]


    def open_settings(self):
        SettingsWindow(self, self.config)

    def browse_source(self):
        directory = filedialog.askdirectory()
        self.source_dir.set(directory)

    def start_transfer_thread(self):
        source = self.source_dir.get()
        target = self.target_dir.get()
        devices = self.get_selected_devices()

        if not source or not target:
            messagebox.showerror("Erreur", "Veuillez sélectionner un dossier source et un dossier cible.")
            return

        if not devices:
            messagebox.showerror("Erreur", "Veuillez sélectionner au moins un appareil.")
            return

        self.save_config()

        self.transfer_button.config(state=tk.DISABLED)
        self.settings_button.config(state=tk.DISABLED)

        # Start multi-device transfer
        transfer_thread = threading.Thread(target=self.run_multi_device_transfer, args=(source, target, devices))
        transfer_thread.start()

    def update_timer(self):
        """Update the transfer timer display."""
        if self.timer_running and self.transfer_start_time:
            elapsed = time.time() - self.transfer_start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            self.timer_label.config(text=f"Durée: {hours:02d}:{minutes:02d}:{seconds:02d}")
            # Schedule next update
            self.after(1000, self.update_timer)

    def run_multi_device_transfer(self, source, target, devices):
        """Run transfer to multiple devices in parallel with per-device worker pools."""
        import time

        # Reset cancel flag
        with self.cancel_lock:
            self.cancel_requested = False

        # Start timer
        self.transfer_start_time = time.time()
        self.timer_running = True
        self.after(100, self.update_timer)

        self.logger.info(f"===== Transfert vers {len(devices)} appareil(s) =====")

        # Dictionary to track results for each device
        transfer_results = {}

        # Prepare files once (chunking, batching)
        self.logger.info("Préparation des fichiers...")
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup transfer manager with temp directory
            self.transfer_manager.temp_dir = Path(temp_dir)
            self.transfer_manager.files_to_chunk = []
            self.transfer_manager.files_to_batch = []
            self.transfer_manager.manifests = []
            
            # Scan and process files once
            self.transfer_manager.scan_files(source)
            self.transfer_manager.process_files(Path(source))
            
            self.logger.info(f"Fichiers préparés: {len(self.transfer_manager.manifests)} fichiers fragmentés, {len(self.transfer_manager.files_to_batch)} fichiers groupés")

            # Check for cancellation before Phase 1
            with self.cancel_lock:
                if self.cancel_requested:
                    self.logger.info("Opération annulée par l'utilisateur")
                    self.timer_running = False
                    self.transfer_button.config(state=tk.NORMAL)
                    self.settings_button.config(state=tk.NORMAL)
                    return

            # Phase 1: Transfer to all devices in parallel
            self.logger.info("\nPHASE 1: Transfert parallèle vers tous les appareils...")

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(devices)) as executor:
                futures = {}
                for device_id in devices:
                    future = executor.submit(self._transfer_to_single_device, device_id, temp_dir)
                    futures[future] = device_id

                # Wait for all transfers to complete
                for future in concurrent.futures.as_completed(futures):
                    device_id = futures[future]
                    try:
                        success = future.result()
                        transfer_results[device_id] = {
                            'transfer_success': success,
                            'reassembly_success': False
                        }
                        if success:
                            self.logger.success(f"[{device_id}] Transfert terminé avec succès.")
                        else:
                            self.logger.error(f"[{device_id}] Transfert échoué.")
                    except Exception as e:
                        self.logger.error(f"[{device_id}] Erreur lors du transfert: {e}")
                        transfer_results[device_id] = {
                            'transfer_success': False,
                            'reassembly_success': False
                        }

        # Get list of devices that succeeded transfer
        successful_devices = [d for d in devices if transfer_results[d]['transfer_success']]

        if not successful_devices:
            self.logger.error("Aucun appareil n'a réussi le transfert. Arrêt.")
            self.timer_running = False
            self.transfer_button.config(state=tk.NORMAL)
            self.settings_button.config(state=tk.NORMAL)
            return

        # Check for cancellation before Phase 2
        with self.cancel_lock:
            if self.cancel_requested:
                self.logger.info("Opération annulée par l'utilisateur")
                self.timer_running = False
                self.transfer_button.config(state=tk.NORMAL)
                self.settings_button.config(state=tk.NORMAL)
                return

        # Phase 2: Reassemble on ALL devices in PARALLEL with synchronized modals
        self.logger.info(f"\nPHASE 2: Réassemblage parallèle sur {len(successful_devices)} appareil(s)...")

        try:
            success = self._parallel_reassembly_on_all_devices(source, target, successful_devices, transfer_results)
        except Exception as e:
            self.logger.error(f"Erreur lors du réassemblage parallèle: {e}")

        # Phase 3: Show summary
        self.logger.info("\n===== RÉSUMÉ FINAL =====")
        success_count = sum(1 for r in transfer_results.values() if r['transfer_success'] and r['reassembly_success'])
        total_count = len(devices)

        self.logger.info(f"Total: {total_count} appareil(s)")
        self.logger.success(f"Réussi: {success_count} appareil(s)")
        self.logger.error(f"Échoué: {total_count - success_count} appareil(s)")

        for device_id, result in transfer_results.items():
            if result['transfer_success'] and result['reassembly_success']:
                self.logger.success(f"  ✓ {device_id}: Transfert et réassemblage OK")
            elif result['transfer_success']:
                self.logger.error(f"  ✗ {device_id}: Transfert OK, réassemblage échoué")
            else:
                self.logger.error(f"  ✗ {device_id}: Transfert échoué")

        self.logger.info("=" * 50)

        # Stop timer
        self.timer_running = False
        elapsed = time.time() - self.transfer_start_time
        self.logger.info(f"Durée totale: {int(elapsed//3600):02d}:{int((elapsed%3600)//60):02d}:{int(elapsed%60):02d}")

        # Re-enable buttons
        self.transfer_button.config(state=tk.NORMAL)
        self.settings_button.config(state=tk.NORMAL)

    def _transfer_to_single_device(self, device_id, temp_dir):
        """Transfer files to a single device with its own worker pool."""
        try:
            self.logger.info(f"[{device_id}] Démarrage du transfert...")
            
            # Check and install Termux if needed (moved from startup to transfer start)
            from utils.termux import TermuxInstaller
            installer = TermuxInstaller(self.logger, self.adb)
            
            if not installer.is_termux_installed(device_id):
                self.logger.info(f"[{device_id}] Termux non installé, installation en cours...")
                if not installer.install_termux(device_id):
                    self.logger.error(f"[{device_id}] Échec de l'installation de Termux. Transfert annulé.")
                    return False
                self.logger.success(f"[{device_id}] Termux installé avec succès")
            else:
                self.logger.info(f"[{device_id}] Termux déjà installé")
            
            # Create device-specific transfer manager
            from core.transfer import TransferManager
            transfer_mgr = TransferManager(self.config, self.logger)
            transfer_mgr.temp_dir = Path(temp_dir)
            transfer_mgr.manifests = self.transfer_manager.manifests
            transfer_mgr.files_to_batch = self.transfer_manager.files_to_batch
            
            # Transfer with per-device parallelism
            remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")
            transfer_mgr.parallel_transfer(remote_temp_dir, device_id)
            
            return True
        except Exception as e:
            self.logger.error(f"[{device_id}] Erreur: {e}")
            return False

    def start_termux_workflow(self):
        """Run Termux setup workflow only (no file transfer)."""
        devices = self.get_selected_devices()
        if not devices:
            messagebox.showerror("Erreur", "Veuillez sélectionner au moins un appareil.")
            return
        
        self.logger.info("===== Workflow Termux =====")
        
        # Run workflow in thread
        def workflow_thread():
            from core.reassembly import ReassemblyManager
            from utils.termux import TermuxInstaller
            
            for device_id in devices:
                self.logger.info(f"[{device_id}] Vérification de Termux...")
                
                # Check and install Termux if needed
                installer = TermuxInstaller(self.logger, self.adb)
                if not installer.is_termux_installed(device_id):
                    self.logger.info(f"[{device_id}] Termux non installé, installation en cours...")
                    if not installer.install_termux(device_id):
                        self.logger.error(f"[{device_id}] Échec de l'installation de Termux")
                        continue
                
                # Create reassembly manager for Termux workflow
                reassembly_mgr = ReassemblyManager(
                    self.config, 
                    self.logger, 
                    self.adb, 
                    device_id,
                    modal_callback=lambda modal_type, **kwargs: self.show_device_reassembly_modal(device_id, modal_type, **kwargs)
                )
                
                # Open Termux and guide through setup
                self.logger.info(f"[{device_id}] Ouverture de Termux...")
                self.adb.run_command("shell am start -n com.termux/.app.TermuxActivity", device_id)
                
                # Show modals for user guidance
                self.show_device_reassembly_modal(device_id, "open_termux")
                self.show_device_reassembly_modal(device_id, "first_authorization")
                self.show_device_reassembly_modal(device_id, "storage_permission")
                self.show_device_reassembly_modal(device_id, "toggle_confirmation")
                
                self.logger.success(f"[{device_id}] Workflow Termux terminé")
        
        threading.Thread(target=workflow_thread, daemon=True).start()

    def manual_move_folder(self):
        """Manually move files from temp folder to final destination."""
        devices = self.get_selected_devices()
        if not devices:
            messagebox.showerror("Erreur", "Veuillez sélectionner au moins un appareil.")
            return
        
        # Ask for destination
        target = self.target_dir.get()
        if not target:
            messagebox.showerror("Erreur", "Veuillez spécifier un dossier de destination.")
            return
        
        confirm = messagebox.askyesno(
            "Confirmation",
            f"Déplacer les fichiers de /sdcard/transfer_temp vers {target} sur {len(devices)} appareil(s)?"
        )
        
        if not confirm:
            return
        
        self.logger.info("===== Déplacement Manuel =====")
        
        def move_thread():
            from core.reassembly import ReassemblyManager
            
            for device_id in devices:
                self.logger.info(f"[{device_id}] Déplacement vers {target}...")
                
                reassembly_mgr = ReassemblyManager(
                    self.config, 
                    self.logger, 
                    self.adb, 
                    device_id
                )
                
                remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")
                
                # Verify files exist first
                if reassembly_mgr._verify_reassembled_files(remote_temp_dir):
                    # Move files
                    if reassembly_mgr._move_to_final_destination(remote_temp_dir, target):
                        self.logger.success(f"[{device_id}] Fichiers déplacés avec succès")
                    else:
                        self.logger.error(f"[{device_id}] Échec du déplacement")
                else:
                    self.logger.warning(f"[{device_id}] Aucun fichier à déplacer")
        
        threading.Thread(target=move_thread, daemon=True).start()

    def delete_temp_files(self):
        """Delete temporary files on selected devices."""
        devices = self.get_selected_devices()
        if not devices:
            messagebox.showerror("Erreur", "Veuillez sélectionner au moins un appareil.")
            return
        
        confirm = messagebox.askyesno(
            "Confirmation",
            f"Supprimer le dossier /sdcard/transfer_temp sur {len(devices)} appareil(s)?\n\nCette action est irréversible!"
        )
        
        if not confirm:
            return
        
        self.logger.info("===== Suppression Fichiers Temporaires =====")
        
        def delete_thread():
            remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")
            
            for device_id in devices:
                self.logger.info(f"[{device_id}] Suppression de {remote_temp_dir}...")
                
                try:
                    self.adb.run_command(f'shell "rm -rf {remote_temp_dir}"', device_id)
                    self.logger.success(f"[{device_id}] Dossier temporaire supprimé")
                except Exception as e:
                    self.logger.error(f"[{device_id}] Erreur: {e}")
        
        threading.Thread(target=delete_thread, daemon=True).start()

    def install_apks(self):
        """Install APKs from the apk folder to selected devices."""
        devices = self.get_selected_devices()
        if not devices:
            messagebox.showerror("Erreur", "Veuillez sélectionner au moins un appareil.")
            return
        
        # Get the apk folder path (relative to the project root)
        apk_folder = Path(__file__).parent.parent / "apk"
        
        if not apk_folder.exists():
            messagebox.showerror("Erreur", f"Dossier APK introuvable: {apk_folder}")
            return
        
        apks = list(apk_folder.glob("*.apk"))
        if not apks:
            messagebox.showinfo("Info", "Aucun fichier APK trouvé dans le dossier apk/")
            return
        
        confirm = messagebox.askyesno(
            "Installation APKs",
            f"Installer {len(apks)} APK(s) sur {len(devices)} appareil(s)?\n\n" +
            "\n".join([f"  • {apk.name}" for apk in apks])
        )
        
        if not confirm:
            return
        
        self.logger.info("===== Installation des APKs =====")
        
        def install_thread():
            apk_installer = ApkInstaller(self.adb, self.logger)
            
            for device_id in devices:
                self.logger.info(f"[{device_id}] Vérification et installation des APKs...")
                
                # Get list of already installed packages
                result = self.adb.run_command("shell pm list packages", device_id)
                installed_packages = set()
                if result:
                    for line in result:
                        if line.startswith("package:"):
                            installed_packages.add(line.replace("package:", "").strip())
                
                for apk in apks:
                    # Extract package name from APK (simplified - uses filename)
                    apk_name = apk.stem.lower()
                    
                    # Check if likely already installed (naive check based on filename)
                    already_installed = any(apk_name in pkg for pkg in installed_packages)
                    
                    if already_installed:
                        self.logger.info(f"[{device_id}] {apk.name} semble déjà installé, vérification...")
                    
                    # Install anyway (reinstall if needed)
                    self.logger.info(f"[{device_id}] Installation de {apk.name}...")
                    result = self.adb.run_command(f'install -r -g "{apk}"', device_id)
                    
                    success = False
                    if result:
                        for line in result:
                            if "Success" in line:
                                success = True
                                break
                    
                    if success:
                        self.logger.success(f"[{device_id}] ✅ {apk.name} installé avec succès")
                    else:
                        self.logger.error(f"[{device_id}] ❌ Échec de l'installation de {apk.name}")
                
                self.logger.info(f"[{device_id}] Installation des APKs terminée")
            
            self.logger.success("===== Installation des APKs terminée =====")
        
        threading.Thread(target=install_thread, daemon=True).start()

    def _parallel_reassembly_on_all_devices(self, source, target, devices, transfer_results):
        """
        Reassemble files on ALL devices in parallel with synchronized modals.
        One modal for all devices at each step.
        """
        from core.reassembly import ReassemblyManager
        import concurrent.futures
        import threading

        remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")

        # Create reassembly managers for all devices
        managers = {}
        for device_id in devices:
            managers[device_id] = ReassemblyManager(
                self.config,
                self.logger,
                self.adb,
                device_id,
                modal_callback=None  # We'll handle modals centrally
            )

        # Store managers for cancellation
        self.current_reassembly_managers = managers

        # STEP 0: Prepare scripts silently (before threads start)
        self.logger.info("Préparation des scripts de réassemblage...")
        for device_id in devices:
            managers[device_id]._push_and_prepare_script(remote_temp_dir)

        # Synchronization events for each step
        step_ready = {}  # When all threads ready for next step
        step_complete = {}  # When step is complete for a thread

        # Determine steps based on config
        use_termux = self.config.get("use_termux_for_reassembly", True)
        
        if use_termux:
            steps = [
                "open_termux",
                "first_authorization",
                "storage_permission",
                "toggle_confirmation",
                "command_execution",
                "reassembly_progress",
                "final_move",
                "completion"
            ]
        else:
            # ADB Shell Mode steps
            # We use a simplified flow for ADB-only reassembly
            steps = ["adb_reassembly"]

        for step in steps:
            step_ready[step] = threading.Barrier(len(devices) + 1)  # +1 for main thread
            step_complete[step] = threading.Barrier(len(devices) + 1)

        # Thread function for each device
        def reassembly_thread(device_id):
            try:
                manager = managers[device_id]

                # Unlock device before starting
                if self.config.get("unlock_device", True):
                    manager._unlock_device()

                if not use_termux:
                    # ADB Shell Mode
                    step_ready["adb_reassembly"].wait()
                    
                    # Run the full ADB reassembly process
                    # This includes push script, execute, wait, verify, move, cleanup
                    success = manager.reassemble_via_adb_shell(remote_temp_dir, target)
                    
                    step_complete["adb_reassembly"].wait()
                    
                    transfer_results[device_id]['reassembly_success'] = success
                    if success:
                        self.logger.success(f"[{device_id}] Réassemblage ADB terminé.")
                    else:
                        self.logger.error(f"[{device_id}] Réassemblage ADB échoué.")
                    return

                # Termux Mode Steps
                # Step 1: Open Termux
                step_ready["open_termux"].wait()
                manager._open_termux()
                step_complete["open_termux"].wait()

                # Step 2: First authorization (user confirms ready)
                step_ready["first_authorization"].wait()
                manager._wait_for_termux_init()
                step_complete["first_authorization"].wait()

                # Step 3: Storage permission
                step_ready["storage_permission"].wait()
                manager._request_storage_permission()
                step_complete["storage_permission"].wait()

                # Step 4: Confirm permission
                step_ready["toggle_confirmation"].wait()
                # User confirms via modal
                step_complete["toggle_confirmation"].wait()

                # Step 5: Execute command
                step_ready["command_execution"].wait()
                manager._execute_reassembly_command(remote_temp_dir)
                step_complete["command_execution"].wait()

                # Step 6: Wait for reassembly
                step_ready["reassembly_progress"].wait()
                manager._wait_for_reassembly_completion(remote_temp_dir)
                step_complete["reassembly_progress"].wait()

                # Step 7: Final move
                step_ready["final_move"].wait()
                manager._move_files_to_destination(remote_temp_dir, target)
                step_complete["final_move"].wait()

                # Step 8: Completion
                step_ready["completion"].wait()
                manager._cleanup(remote_temp_dir)
                step_complete["completion"].wait()

                transfer_results[device_id]['reassembly_success'] = True
                self.logger.success(f"[{device_id}] Réassemblage terminé.")

            except Exception as e:
                self.logger.error(f"[{device_id}] Erreur lors du réassemblage: {e}")
                transfer_results[device_id]['reassembly_success'] = False

        # Start threads for all devices
        threads = []
        for device_id in devices:
            t = threading.Thread(target=reassembly_thread, args=(device_id,))
            t.start()
            threads.append(t)

        # Main thread: show modals at each step
        device_list_str = ", ".join(devices)

        for step in steps:
            # Wait for all threads to be ready
            step_ready[step].wait()

            # Show modal for this step (one modal for all devices)
            if step == "toggle_confirmation":
                # This one needs user confirmation
                result = self.show_multi_device_modal(step, devices=devices)
                if not result:
                    self.logger.error("Utilisateur a annulé.")
                    # Signal threads to complete anyway
                    step_complete[step].wait()
                    return False
            elif step == "adb_reassembly":
                # Show progress modal for ADB reassembly
                self.show_multi_device_modal("reassembly_progress", devices=devices)
            else:
                # Other modals are informational
                self.show_multi_device_modal(step, devices=devices)

            # Signal threads to proceed
            step_complete[step].wait()

        # Wait for all threads to finish
        for t in threads:
            t.join()

        return True

    def _reassemble_on_device(self, source, target, device_id):
        """Reassemble files on a single device with modals (DEPRECATED - use parallel version)."""
        try:
            self.logger.info(f"[{device_id}] Démarrage du réassemblage...")

            # Create reassembly manager
            from core.reassembly import ReassemblyManager
            remote_temp_dir = self.config.get("remote_temp_dir", "/sdcard/transfer_temp")

            reassembly_manager = ReassemblyManager(
                self.config,
                self.logger,
                self.adb,
                device_id,
                modal_callback=lambda modal_type, **kwargs: self.show_device_reassembly_modal(device_id, modal_type, **kwargs)
            )

            success = reassembly_manager.reassemble_via_termux(remote_temp_dir, target)
            return success
        except Exception as e:
            self.logger.error(f"[{device_id}] Erreur: {e}")
            return False

    def show_multi_device_modal(self, modal_type: str, devices=None):
        """
        Show modal for multiple devices at once.
        Now uses the redesigned individual modals for better UX.
        """
        if not devices:
            devices = []

        device_list_str = "\n".join([f"  • {d}" for d in devices])
        count = len(devices)

        # Close previous modal if exists
        if self.current_modal:
            try:
                self.current_modal.destroy()
            except:
                pass

        self.modal_result = None

        # Use the REDESIGNED modals instead of old MultiDevice modals
        if modal_type == "transfer_script":
            from ui.modal_dialog import TransferScriptModal
            # Show for first device (or no device_id for generic)
            device_id = f"{count} appareils" if count > 1 else (devices[0] if devices else None)
            self.current_modal = TransferScriptModal(self, device_id=device_id, on_cancel=self._on_modal_cancel)
            self.wait_window(self.current_modal)

        elif modal_type == "open_termux":
            from ui.modal_dialog import OpenTermuxModal
            # Show redesigned OpenTermuxModal
            device_id = f"{count} appareils" if count > 1 else (devices[0] if devices else None)
            self.current_modal = OpenTermuxModal(self, device_id=device_id, on_done=lambda: None)
            self.wait_window(self.current_modal)

        elif modal_type == "first_authorization":
            # This step is merged into open_termux modal - skip it
            pass

        elif modal_type == "storage_permission":
            from ui.modal_dialog import StoragePermissionModal
            # Show redesigned StoragePermissionModal
            device_id = f"{count} appareils" if count > 1 else (devices[0] if devices else None)
            self.current_modal = StoragePermissionModal(self, device_id=device_id, on_done=lambda: None)
            self.wait_window(self.current_modal)

        elif modal_type == "toggle_confirmation":
            from ui.modal_dialog import ToggleConfirmationModal
            # Show redesigned ToggleConfirmationModal
            device_id = f"{count} appareils" if count > 1 else (devices[0] if devices else None)
            self.current_modal = ToggleConfirmationModal(
                self, 
                on_done=self._on_permission_granted,
                device_id=device_id
            )
            self.wait_window(self.current_modal)
            return self.modal_result

        elif modal_type == "command_execution":
            from ui.modal_dialog import CommandExecutionModal
            # Show redesigned CommandExecutionModal
            device_id = f"{count} appareils" if count > 1 else (devices[0] if devices else None)
            command = "cd /sdcard/adb && bash unified"
            self.current_modal = CommandExecutionModal(self, command, device_id=device_id)
            self.current_modal.update()  # Force display

        elif modal_type == "reassembly_progress":
            from ui.modal_dialog import ReassemblyProgressModal
            # Show redesigned ReassemblyProgressModal
            device_id = f"{count} appareils" if count > 1 else (devices[0] if devices else None)
            self.current_modal = ReassemblyProgressModal(self, device_id=device_id, on_cancel=self._on_modal_cancel)
            self.current_modal.update()  # Force display

        elif modal_type == "final_move":
            from ui.modal_dialog import FinalMoveModal
            # Show redesigned FinalMoveModal
            device_id = f"{count} appareils" if count > 1 else (devices[0] if devices else None)
            destination = self.target_dir.get() if hasattr(self, 'target_dir') else "/sdcard/destination"
            self.current_modal = FinalMoveModal(self, destination, device_id=device_id)
            self.wait_window(self.current_modal)

        elif modal_type == "completion":
            from ui.modal_dialog import CompletionModal
            # Show redesigned CompletionModal
            device_id = f"{count} appareils" if count > 1 else (devices[0] if devices else None)
            destination = self.target_dir.get() if hasattr(self, 'target_dir') else "/sdcard/destination"
            self.current_modal = CompletionModal(self, destination, device_id=device_id)
            self.wait_window(self.current_modal)

        return True

    def show_device_reassembly_modal(self, device_id, modal_type: str, **kwargs):
        """Show reassembly modal with device ID in title."""
        # Add device_id to kwargs so modals can display it
        kwargs['device_id'] = device_id

        # Call original modal function
        return self.show_reassembly_modal(modal_type, **kwargs)
    
    def show_reassembly_modal(self, modal_type: str, **kwargs):
        """Show appropriate modal based on type and wait for completion."""
        # Extract device_id if present
        device_id = kwargs.get("device_id", None)

        # Special case: just close current modal
        if modal_type == "close_current_modal":
            if self.current_modal:
                try:
                    self.current_modal.destroy()
                    self.current_modal = None
                except:
                    pass
            return True

        # Close previous modal if exists
        if self.current_modal:
            try:
                self.current_modal.destroy()
            except:
                pass

        self.modal_result = None

        # Create appropriate modal
        if modal_type == "transfer_script":
            self.current_modal = TransferScriptModal(self, device_id=device_id, on_cancel=self._on_modal_cancel)
            self.wait_window(self.current_modal)  # Wait for user to click "Continuer"

        elif modal_type == "termux_install":
            self.current_modal = TermuxInstallModal(self, device_id=device_id, on_cancel=self._on_modal_cancel)
            self.wait_window(self.current_modal)  # Wait for user to click "Continuer"

        elif modal_type == "open_termux":
            # New enhanced modal asks user to confirm Termux opened
            self.current_modal = OpenTermuxModal(self, device_id=device_id, on_done=lambda: None)
            self.wait_window(self.current_modal)  # Wait for user to click "Oui, Termux est ouvert"

        elif modal_type == "first_authorization":
            # This step is now merged into open_termux modal - skip it
            pass

        elif modal_type == "storage_permission":
            # New enhanced modal asks user to click Allow button
            self.current_modal = StoragePermissionModal(self, device_id=device_id, on_done=lambda: None)
            self.wait_window(self.current_modal)  # Wait for user to click "J'ai cliqué sur AUTORISER"

        elif modal_type == "toggle_confirmation":
            self.current_modal = ToggleConfirmationModal(
                self,
                device_id=device_id,
                on_done=self._on_permission_granted,
                on_cancel=self._on_modal_cancel
            )
            # Wait for user action
            self.wait_window(self.current_modal)
            return self.modal_result

        elif modal_type == "command_execution":
            command = kwargs.get("command", "")
            self.current_modal = CommandExecutionModal(self, command, device_id=device_id)
            # This is a wait modal - no buttons, will be closed automatically
            self.current_modal.update()  # Force display

        elif modal_type == "reassembly_progress":
            self.current_modal = ReassemblyProgressModal(self, device_id=device_id, on_cancel=self._on_modal_cancel)
            # This is a wait modal - no buttons, will be closed automatically
            self.current_modal.update()  # Force display

        elif modal_type == "final_move":
            destination = kwargs.get("destination", "")
            self.current_modal = FinalMoveModal(self, destination, device_id=device_id, on_cancel=self._on_modal_cancel)
            self.wait_window(self.current_modal)  # Wait for user to click "Continuer"

        elif modal_type == "completion":
            destination = kwargs.get("destination", "")
            self.current_modal = CompletionModal(self, destination, device_id=device_id)
            self.wait_window(self.current_modal)

        return True
    
    def _on_permission_granted(self):
        """Called when user confirms storage permission was granted."""
        self.modal_result = True

    def _confirm_cancel_all_devices(self, device_count):
        """Show confirmation dialog for canceling all device operations."""
        return messagebox.askyesno(
            "Annuler l'opération",
            f"Voulez-vous annuler l'opération sur tous les {device_count} appareil(s)?\n\nCette action arrêtera toutes les opérations en cours."
        )

    def _on_modal_cancel(self):
        """Called when user cancels a modal."""
        # Get number of devices in current operation
        devices = self.get_selected_devices()
        if devices and len(devices) > 1:
            if self._confirm_cancel_all_devices(len(devices)):
                with self.cancel_lock:
                    self.cancel_requested = True
                self.modal_result = False
                # Cancel all reassembly managers
                if hasattr(self, 'current_reassembly_managers'):
                    for manager in self.current_reassembly_managers.values():
                        manager.cancel()
        else:
            self.modal_result = False
            if hasattr(self.transfer_manager, 'reassembly_manager'):
                self.transfer_manager.reassembly_manager.cancel()

    def log(self, message, tag="info"):
        self.progress_text.insert(tk.END, str(message) + "\n", tag)
        self.progress_text.see(tk.END)

def main():
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()

if __name__ == "__main__":
    main()
