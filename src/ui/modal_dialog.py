# claude_v2/src/ui/modal_dialog.py
import tkinter as tk
from tkinter import font as tkfont, messagebox

class BaseModal(tk.Toplevel):
    def __init__(self, master, title, message, device_id=None, on_cancel=None):
        super().__init__(master)

        # Add device ID to title if provided
        if device_id:
            self.title(f"[{device_id}] {title}")
        else:
            self.title(title)

        self.geometry("600x400")
        self.configure(bg="#f0f0f0")
        self.transient(master)
        self.grab_set()

        self.message_label = tk.Label(
            self,
            text=message,
            justify=tk.LEFT,
            wraplength=560,
            bg="#f0f0f0",
            font=("Arial", 11)
        )
        self.message_label.pack(pady=20, padx=20)

        self.button_frame = tk.Frame(self, bg="#f0f0f0")
        self.button_frame.pack(pady=20)

        self.on_cancel = on_cancel
        if on_cancel:
            self.cancel_button = tk.Button(
                self.button_frame,
                text="Annuler",
                command=self.cancel,
                bg="#e74c3c",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=20,
                pady=10
            )
            self.cancel_button.pack(side=tk.LEFT, padx=10)

        # Handle force close (X button)
        self.protocol("WM_DELETE_WINDOW", self._on_force_close)

    def _on_force_close(self):
        """Handle force close (X button) - triggers cancel."""
        if self.on_cancel:
            self.on_cancel()
        self.destroy()

    def cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.destroy()

class WaitModal(tk.Toplevel):
    """Modal for operations where user just needs to wait (no buttons)."""
    def __init__(self, master, title, message, device_id=None, on_cancel=None):
        super().__init__(master)

        # Add device ID to title if provided
        if device_id:
            self.title(f"[{device_id}] {title}")
        else:
            self.title(title)

        self.geometry("600x400")
        self.configure(bg="#e8f4f8")
        self.transient(master)
        self.grab_set()

        self.message_label = tk.Label(
            self,
            text=message,
            justify=tk.LEFT,
            wraplength=560,
            bg="#e8f4f8",
            font=("Arial", 11)
        )
        self.message_label.pack(pady=20, padx=20)

        self.on_cancel = on_cancel
        # Handle force close (X button)
        if on_cancel:
            self.protocol("WM_DELETE_WINDOW", self._on_force_close)
        else:
            # If no specific cancel callback, just destroy
            self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _on_force_close(self):
        """Handle force close (X button) - triggers cancel."""
        if self.on_cancel:
            self.on_cancel()
        self.destroy()

class TransferScriptModal(BaseModal):
    def __init__(self, master, device_id=None, **kwargs):
        super().__init__(
            master,
            "Transfert du Script",
            "Le script de réassemblage 'unified.sh' va être transféré sur votre appareil.",
            device_id=device_id,
            **kwargs
        )
        self.ok_button = tk.Button(
            self.button_frame,
            text="Continuer",
            command=self.destroy,
            bg="#27ae60",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=30,
            pady=12
        )
        self.ok_button.pack(side=tk.LEFT, padx=10)


class PreApkConfirmationModal(tk.Toplevel):
    """Modal for pre-APK confirmation before transfer starts."""
    def __init__(self, master, app_name="Application", device_id=None, on_done=None, on_cancel=None):
        super().__init__(master)

        if device_id:
            self.title(f"[{device_id}] Pré-Transfert: {app_name}")
        else:
            self.title(f"Pré-Transfert: {app_name}")

        self.geometry("700x500")
        self.configure(bg="#e3f2fd")
        self.transient(master)
        self.grab_set()

        self.on_done = on_done
        self.on_cancel = on_cancel
        self.result = False

        # Title frame
        title_frame = tk.Frame(self, bg="#1976d2", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        title_label = tk.Label(
            title_frame,
            text=f"📱 Pré-Transfert: {app_name}",
            bg="#1976d2",
            fg="white",
            font=("Arial", 16, "bold")
        )
        title_label.pack(expand=True)

        # Main content
        content_frame = tk.Frame(self, bg="#e3f2fd")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # Instructions
        instruction = tk.Label(
            content_frame,
            text="Une application a été installée et ouverte sur votre appareil.\n\n"
                 "Veuillez suivre les instructions à l'écran de l'appareil\n"
                 "puis cliquez sur 'Continuer le transfert' pour poursuivre.",
            bg="#e3f2fd",
            font=("Arial", 13),
            justify=tk.CENTER,
            wraplength=640
        )
        instruction.pack(pady=(20, 30))

        # Info box
        info_frame = tk.Frame(content_frame, bg="#bbdefb", relief=tk.RAISED, borderwidth=3)
        info_frame.pack(fill=tk.X, pady=20, padx=20)

        info_label = tk.Label(
            info_frame,
            text=f"📦 Application: {app_name}\n\n"
                 "👉 Assurez-vous que l'application est ouverte sur votre appareil",
            bg="#bbdefb",
            font=("Arial", 12),
            justify=tk.CENTER,
            pady=20
        )
        info_label.pack()

        # Buttons
        button_frame = tk.Frame(self, bg="#e3f2fd")
        button_frame.pack(pady=25)

        ok_button = tk.Button(
            button_frame,
            text="✓ Continuer le transfert",
            command=self.done,
            bg="#27ae60",
            fg="white",
            font=("Arial", 13, "bold"),
            padx=35,
            pady=18
        )
        ok_button.pack(side=tk.LEFT, padx=10)

        cancel_button = tk.Button(
            button_frame,
            text="Annuler",
            command=self.cancel,
            bg="#e74c3c",
            fg="white",
            font=("Arial", 11),
            padx=20,
            pady=18
        )
        cancel_button.pack(side=tk.LEFT, padx=10)

        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def done(self):
        self.result = True
        if self.on_done:
            self.on_done()
        self.destroy()

    def cancel(self):
        self.result = False
        if self.on_cancel:
            self.on_cancel()
        self.destroy()

class TermuxInstallModal(BaseModal):
    def __init__(self, master, device_id=None, **kwargs):
        super().__init__(
            master,
            "Installation de Termux",
            "Termux n'est pas installé. L'application va maintenant tenter de l'installer.\n\n"
            "Veuillez accepter l'installation sur votre appareil.",
            device_id=device_id,
            **kwargs
        )
        self.ok_button = tk.Button(
            self.button_frame,
            text="Continuer",
            command=self.destroy,
            bg="#27ae60",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=30,
            pady=12
        )
        self.ok_button.pack(side=tk.LEFT, padx=10)

class OpenTermuxModal(tk.Toplevel):
    """Enhanced modal asking user if Termux opened."""
    def __init__(self, master, device_id=None, on_done=None):
        super().__init__(master)

        if device_id:
            self.title(f"[{device_id}] Étape 1: Termux va s'ouvrir")
        else:
            self.title("Étape 1: Termux va s'ouvrir")

        self.geometry("700x550")
        self.configure(bg="#fff3cd")
        self.transient(master)
        self.grab_set()

        # Title frame
        title_frame = tk.Frame(self, bg="#ffc107", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        title_label = tk.Label(
            title_frame,
            text="📱 ÉTAPE 1: Termux va s'ouvrir",
            bg="#ffc107",
            fg="#000",
            font=("Arial", 16, "bold")
        )
        title_label.pack(expand=True)

        # Main content
        content_frame = tk.Frame(self, bg="#fff3cd")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # Main instruction
        instruction = tk.Label(
            content_frame,
            text="Termux va s'ouvrir automatiquement sur votre téléphone.\n\n"
                 "Une fenêtre de permission peut apparaître.",
            bg="#fff3cd",
            font=("Arial", 13),
            justify=tk.LEFT,
            wraplength=640
        )
        instruction.pack(pady=(10, 30))

        # Action required box
        action_frame = tk.Frame(content_frame, bg="#ff9800", relief=tk.RAISED, borderwidth=4)
        action_frame.pack(fill=tk.X, pady=20, padx=20)

        action_label = tk.Label(
            action_frame,
            text="👉 ACTION REQUISE:\nAppuyez sur 'AUTORISER'",
            bg="#ff9800",
            fg="white",
            font=("Arial", 15, "bold"),
            pady=25,
            justify=tk.CENTER
        )
        action_label.pack()

        # Spacer
        tk.Label(content_frame, text="", bg="#fff3cd").pack(pady=10)

        # Buttons
        button_frame = tk.Frame(self, bg="#fff3cd")
        button_frame.pack(pady=20)

        self.on_done = on_done
        yes_button = tk.Button(
            button_frame,
            text="✓ J'ai appuyé sur Autoriser",
            command=self.done,
            bg="#27ae60",
            fg="white",
            font=("Arial", 13, "bold"),
            padx=35,
            pady=18
        )
        yes_button.pack(side=tk.LEFT, padx=10)
        
        help_button = tk.Button(
            button_frame,
            text="❓ Aide / Problème",
            command=self.show_help,
            bg="#3498db",
            fg="white",
            font=("Arial", 11),
            padx=20,
            pady=18
        )
        help_button.pack(side=tk.LEFT, padx=10)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def done(self):
        if self.on_done:
            self.on_done()
        self.destroy()
        
    def show_help(self):
        messagebox.showinfo(
            "Aide - Termux",
            "Si vous avez cliqué sur 'Refuser' par erreur:\n\n"
            "1. Allez dans Paramètres Android > Applications > Termux\n"
            "2. Allez dans Permissions\n"
            "3. Activez toutes les permissions demandées\n"
            "4. Revenez à cette application\n\n"
            "Si Termux ne s'ouvre pas:\n"
            "• Vérifiez que votre téléphone est déverrouillé\n"
            "• Essayez d'ouvrir Termux manuellement"
        )


class FirstAuthorizationModal(BaseModal):
    """This modal is now removed - merged into OpenTermuxModal"""
    def __init__(self, master, device_id=None, **kwargs):
        super().__init__(
            master,
            "Première Autorisation",
            "Termux est en cours d'initialisation.\n\nVeuillez attendre que Termux soit complètement ouvert, puis cliquez sur 'Continuer'.",
            device_id=device_id,
            **kwargs
        )
        self.ok_button = tk.Button(
            self.button_frame,
            text="Continuer",
            command=self.destroy,
            bg="#27ae60",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=30,
            pady=12
        )
        self.ok_button.pack(side=tk.LEFT, padx=10)

class StoragePermissionModal(tk.Toplevel):
    """Enhanced modal for storage permission setup."""
    def __init__(self, master, device_id=None, on_done=None):
        super().__init__(master)

        if device_id:
            self.title(f"[{device_id}] Étape 2: Permission de Stockage")
        else:
            self.title("Étape 2: Permission de Stockage")

        self.geometry("750x600")
        self.configure(bg="#e1f5e1")
        self.transient(master)
        self.grab_set()

        # Title frame
        title_frame = tk.Frame(self, bg="#4caf50", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        title_label = tk.Label(
            title_frame,
            text="💾 ÉTAPE 2: Permission de Stockage",
            bg="#4caf50",
            fg="white",
            font=("Arial", 16, "bold")
        )
        title_label.pack(expand=True)

        # Main content
        content_frame = tk.Frame(self, bg="#e1f5e1")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # Introduction
        intro = tk.Label(
            content_frame,
            text="Une fenêtre de paramètres va s'ouvrir maintenant.",
            bg="#e1f5e1",
            font=("Arial", 13),
            justify=tk.LEFT,
            wraplength=690
        )
        intro.pack(pady=(10, 20))

        # Instructions frame
        instructions_frame = tk.Frame(content_frame, bg="#c8e6c9", relief=tk.RAISED, borderwidth=3)
        instructions_frame.pack(fill=tk.X, pady=10, padx=10)

        instructions_title = tk.Label(
            instructions_frame,
            text="📋 INSTRUCTIONS:",
            bg="#c8e6c9",
            font=("Arial", 13, "bold"),
            pady=10
        )
        instructions_title.pack()

        # Step 1
        step1 = tk.Label(
            instructions_frame,
            text="1️⃣  Cherchez 'Termux' dans la liste",
            bg="#c8e6c9",
            font=("Arial", 12),
            justify=tk.LEFT,
            anchor="w",
            padx=20,
            pady=5
        )
        step1.pack(fill=tk.X)

        # Step 2
        step2 = tk.Label(
            instructions_frame,
            text="2️⃣  Activez l'interrupteur pour Termux",
            bg="#c8e6c9",
            font=("Arial", 12),
            justify=tk.LEFT,
            anchor="w",
            padx=20,
            pady=5
        )
        step2.pack(fill=tk.X)

        # Step 3
        step3 = tk.Label(
            instructions_frame,
            text="3️⃣  Appuyez sur le bouton RETOUR de votre téléphone",
            bg="#c8e6c9",
            font=("Arial", 12),
            justify=tk.LEFT,
            anchor="w",
            padx=20,
            pady=5
        )
        step3.pack(fill=tk.X)

        tk.Label(instructions_frame, text="", bg="#c8e6c9", pady=5).pack()

        # Action box
        action_frame = tk.Frame(content_frame, bg="#ff5722", relief=tk.RAISED, borderwidth=4)
        action_frame.pack(fill=tk.X, pady=20, padx=10)

        action_label = tk.Label(
            action_frame,
            text="👉 Vous devriez revenir à l'écran noir de Termux",
            bg="#ff5722",
            fg="white",
            font=("Arial", 14, "bold"),
            pady=20
        )
        action_label.pack()

        # Button
        button_frame = tk.Frame(self, bg="#e1f5e1")
        button_frame.pack(pady=20)

        self.on_done = on_done
        done_button = tk.Button(
            button_frame,
            text="✓ C'est fait, je suis sur Termux",
            command=self.done,
            bg="#27ae60",
            fg="white",
            font=("Arial", 13, "bold"),
            padx=35,
            pady=18
        )
        done_button.pack(side=tk.LEFT, padx=10)
        
        help_button = tk.Button(
            button_frame,
            text="❓ Aide / Problème",
            command=self.show_help,
            bg="#3498db",
            fg="white",
            font=("Arial", 11),
            padx=20,
            pady=18
        )
        help_button.pack(side=tk.LEFT, padx=10)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def done(self):
        if self.on_done:
            self.on_done()
        self.destroy()
        
    def show_help(self):
        messagebox.showinfo(
            "Aide - Permission de Stockage",
            "Si vous ne trouvez pas Termux dans la liste:\n"
            "• Utilisez la barre de recherche en haut\n"
            "• Tapez 'Termux'\n\n"
            "Si vous avez désactivé le toggle par erreur:\n"
            "1. Retournez dans Paramètres > Applications > Termux\n"
            "2. Cliquez sur 'Permissions' ou 'Stockage'\n"
            "3. Activez 'Accès à tous les fichiers'\n\n"
            "Si vous êtes perdu:\n"
            "• Appuyez sur le bouton RETOUR plusieurs fois\n"
            "• Cherchez l'icône Termux (fond noir avec >_)\n"
            "• Ouvrez Termux manuellement"
        )


class ToggleConfirmationModal(tk.Toplevel):
    """Enhanced modal for toggling Termux in the list and clicking return."""
    def __init__(self, master, on_done, device_id=None, **kwargs):
        super().__init__(master)

        if device_id:
            self.title(f"[{device_id}] Étape 3: Retour à Termux")
        else:
            self.title("Étape 3: Retour à Termux")

        self.geometry("750x650")
        self.configure(bg="#e8f4f8")
        self.transient(master)
        self.grab_set()

        # Title frame
        title_frame = tk.Frame(self, bg="#2196f3", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        title_label = tk.Label(
            title_frame,
            text="🔄 ÉTAPE 3: Retournez à Termux",
            bg="#2196f3",
            fg="white",
            font=("Arial", 16, "bold")
        )
        title_label.pack(expand=True)

        # Main content
        content_frame = tk.Frame(self, bg="#e8f4f8")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        intro_label = tk.Label(
            content_frame,
            text="Vous devriez maintenant être revenu sur l'écran noir de Termux.\n\n"
                 "Si ce n'est pas le cas :",
            bg="#e8f4f8",
            font=("Arial", 13),
            justify=tk.LEFT,
            wraplength=690
        )
        intro_label.pack(pady=(10, 15))

        # Step 1
        step1_frame = tk.Frame(content_frame, bg="#fff9c4", relief=tk.RAISED, borderwidth=3)
        step1_frame.pack(fill=tk.X, pady=8, padx=15)

        step1_label = tk.Label(
            step1_frame,
            text="1️⃣  Utilisez le bouton RETOUR ou le bouton MULTITÂCHE",
            bg="#fff9c4",
            font=("Arial", 12, "bold"),
            justify=tk.LEFT,
            pady=12,
            padx=15
        )
        step1_label.pack(anchor=tk.W)

        # Step 2
        step2_frame = tk.Frame(content_frame, bg="#c5e1a5", relief=tk.RAISED, borderwidth=3)
        step2_frame.pack(fill=tk.X, pady=8, padx=15)

        step2_label = tk.Label(
            step2_frame,
            text="2️⃣  Sélectionnez l'application TERMUX",
            bg="#c5e1a5",
            font=("Arial", 12, "bold"),
            justify=tk.LEFT,
            pady=12,
            padx=15
        )
        step2_label.pack(anchor=tk.W)

        # Confirmation question
        confirm_frame = tk.Frame(content_frame, bg="#9c27b0", relief=tk.RAISED, borderwidth=4)
        confirm_frame.pack(fill=tk.X, pady=20, padx=15)

        confirm_label = tk.Label(
            confirm_frame,
            text="✓ Êtes-vous de retour sur Termux ?",
            bg="#9c27b0",
            fg="white",
            font=("Arial", 14, "bold"),
            pady=18
        )
        confirm_label.pack()

        # Buttons
        button_frame = tk.Frame(self, bg="#e8f4f8")
        button_frame.pack(pady=20)

        self.on_done = on_done
        yes_button = tk.Button(
            button_frame,
            text="✓ Oui, je suis sur Termux",
            command=self.done,
            bg="#27ae60",
            fg="white",
            font=("Arial", 13, "bold"),
            padx=35,
            pady=18
        )
        yes_button.pack(side=tk.LEFT, padx=10)
        
        help_button = tk.Button(
            button_frame,
            text="❓ Aide",
            command=self.show_help,
            bg="#3498db",
            fg="white",
            font=("Arial", 11),
            padx=20,
            pady=18
        )
        help_button.pack(side=tk.LEFT, padx=10)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def done(self):
        if self.on_done:
            self.on_done()
        self.destroy()
        
    def show_help(self):
        messagebox.showinfo(
            "Aide - Retour à Termux",
            "Pour retourner à Termux:\n\n"
            "1. Appuyez sur le bouton RETOUR (◀) de votre téléphone\n"
            "   OU\n"
            "2. Appuyez sur le bouton MULTITÂCHE (⊡) et sélectionnez Termux\n\n"
            "Termux a un fond noir avec le symbole >_ en blanc.\n\n"
            "Si vous ne le trouvez pas:\n"
            "• Ouvrez le tiroir d'applications\n"
            "• Cherchez l'icône Termux\n"
            "• Appuyez dessus pour l'ouvrir"
        )


class CommandExecutionModal(tk.Toplevel):
    """Modal for command execution."""
    def __init__(self, master, command, device_id=None):
        super().__init__(master)
        
        if device_id:
            self.title(f"[{device_id}] Exécution de la Commande")
        else:
            self.title("Exécution de la Commande")
        
        self.geometry("700x450")
        self.configure(bg="#e8f4f8")
        self.transient(master)
        self.grab_set()
        
        # Title frame
        title_frame = tk.Frame(self, bg="#2196f3", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="⚙️ Exécution de la Commande",
            bg="#2196f3",
            fg="white",
            font=("Arial", 16, "bold")
        )
        title_label.pack(expand=True)
        
        # Content
        content_frame = tk.Frame(self, bg="#e8f4f8")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        intro = tk.Label(
            content_frame,
            text="La commande suivante va être exécutée dans Termux:",
            bg="#e8f4f8",
            font=("Arial", 12),
            justify=tk.LEFT
        )
        intro.pack(pady=(10, 15))
        
        # Command box
        cmd_frame = tk.Frame(content_frame, bg="#f5f5f5", relief=tk.SUNKEN, borderwidth=2)
        cmd_frame.pack(fill=tk.X, pady=10, padx=10)
        
        cmd_label = tk.Label(
            cmd_frame,
            text=command,
            bg="#f5f5f5",
            font=("Courier", 11),
            justify=tk.LEFT,
            wraplength=620,
            pady=15,
            padx=15
        )
        cmd_label.pack()
        
        # Warning
        warning = tk.Label(
            content_frame,
            text="⏳ Ne touchez à rien sur votre appareil.\n\nVeuillez patienter...",
            bg="#e8f4f8",
            font=("Arial", 12, "bold"),
            justify=tk.CENTER,
            fg="#e67e22"
        )
        warning.pack(pady=20)
        
        self.protocol("WM_DELETE_WINDOW", self.destroy)

class ReassemblyProgressModal(tk.Toplevel):
    """Modal for reassembly progress."""
    def __init__(self, master, device_id=None, on_cancel=None):
        super().__init__(master)
        
        if device_id:
            self.title(f"[{device_id}] Réassemblage en Cours")
        else:
            self.title("Réassemblage en Cours")
        
        self.geometry("700x400")
        self.configure(bg="#fff3e0")
        self.transient(master)
        self.grab_set()
        
        # Title frame
        title_frame = tk.Frame(self, bg="#ff9800", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="🔄 Réassemblage en Cours",
            bg="#ff9800",
            fg="white",
            font=("Arial", 16, "bold")
        )
        title_label.pack(expand=True)
        
        # Content
        content_frame = tk.Frame(self, bg="#fff3e0")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)
        
        # Progress box
        progress_frame = tk.Frame(content_frame, bg="#ffecb3", relief=tk.RAISED, borderwidth=3)
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        message = tk.Label(
            progress_frame,
            text="⏳ Le réassemblage des fichiers est en cours.\n\n"
                 "Cela peut prendre plusieurs minutes\nselon la taille des fichiers.\n\n"
                 "Veuillez patienter et ne touchez à rien...",
            bg="#ffecb3",
            font=("Arial", 13),
            justify=tk.CENTER,
            pady=30
        )
        message.pack(expand=True)
        
        self.on_cancel = on_cancel
        
        # Add Close/Cancel button
        button_frame = tk.Frame(self, bg="#fff3e0")
        button_frame.pack(pady=20)
        
        close_button = tk.Button(
            button_frame,
            text="Fermer / Annuler",
            command=self.cancel,
            bg="#e74c3c",
            fg="white",
            font=("Arial", 11),
            padx=20,
            pady=10
        )
        close_button.pack()

        # Handle force close (X button)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.destroy()

class FinalMoveModal(tk.Toplevel):
    """Modal for final file move."""
    def __init__(self, master, destination, device_id=None, **kwargs):
        super().__init__(master)
        
        if device_id:
            self.title(f"[{device_id}] Déplacement Final")
        else:
            self.title("Déplacement Final")
        
        self.geometry("700x400")
        self.configure(bg="#e1f5e1")
        self.transient(master)
        self.grab_set()
        
        # Title frame
        title_frame = tk.Frame(self, bg="#4caf50", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="📁 Déplacement Final",
            bg="#4caf50",
            fg="white",
            font=("Arial", 16, "bold")
        )
        title_label.pack(expand=True)
        
        # Content
        content_frame = tk.Frame(self, bg="#e1f5e1")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        message = tk.Label(
            content_frame,
            text="Les fichiers réassemblés vont être déplacés vers:",
            bg="#e1f5e1",
            font=("Arial", 12),
            justify=tk.LEFT
        )
        message.pack(pady=(20, 15))
        
        # Destination box
        dest_frame = tk.Frame(content_frame, bg="#c8e6c9", relief=tk.RAISED, borderwidth=3)
        dest_frame.pack(fill=tk.X, pady=10, padx=20)
        
        dest_label = tk.Label(
            dest_frame,
            text=f"📁 {destination}",
            bg="#c8e6c9",
            font=("Arial", 13, "bold"),
            pady=20,
            padx=20,
            wraplength=600
        )
        dest_label.pack()
        
        # Button
        button_frame = tk.Frame(self, bg="#e1f5e1")
        button_frame.pack(pady=20)
        
        ok_button = tk.Button(
            button_frame,
            text="Continuer",
            command=self.destroy,
            bg="#27ae60",
            fg="white",
            font=("Arial", 13, "bold"),
            padx=35,
            pady=18
        )
        ok_button.pack()
        
        self.protocol("WM_DELETE_WINDOW", self.destroy)

class CompletionModal(tk.Toplevel):
    """Modal for completion."""
    def __init__(self, master, destination, device_id=None, **kwargs):
        super().__init__(master)
        
        if device_id:
            self.title(f"[{device_id}] ✅ Terminé!")
        else:
            self.title("✅ Terminé!")
        
        self.geometry("700x450")
        self.configure(bg="#e8f5e9")
        self.transient(master)
        self.grab_set()
        
        # Title frame
        title_frame = tk.Frame(self, bg="#4caf50", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="✅ Terminé!",
            bg="#4caf50",
            fg="white",
            font=("Arial", 18, "bold")
        )
        title_label.pack(expand=True)
        
        # Content
        content_frame = tk.Frame(self, bg="#e8f5e9")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        # Success box
        success_frame = tk.Frame(content_frame, bg="#81c784", relief=tk.RAISED, borderwidth=4)
        success_frame.pack(fill=tk.X, pady=15, padx=20)
        
        success_msg = tk.Label(
            success_frame,
            text="✅ Le réassemblage et le déplacement\nsont terminés avec succès!",
            bg="#81c784",
            fg="white",
            font=("Arial", 14, "bold"),
            justify=tk.CENTER,
            pady=20
        )
        success_msg.pack()
        
        # Location info
        location_label = tk.Label(
            content_frame,
            text="📁 Vos fichiers se trouvent maintenant dans:",
            bg="#e8f5e9",
            font=("Arial", 12),
            justify=tk.LEFT
        )
        location_label.pack(pady=(20, 10))
        
        dest_label = tk.Label(
            content_frame,
            text=destination,
            bg="#e8f5e9",
            font=("Arial", 12, "bold"),
            fg="#2e7d32",
            wraplength=620
        )
        dest_label.pack(pady=(0, 15))
        
        final_msg = tk.Label(
            content_frame,
            text="Vous pouvez maintenant utiliser vos fichiers sur votre téléphone.",
            bg="#e8f5e9",
            font=("Arial", 11),
            justify=tk.CENTER
        )
        final_msg.pack(pady=10)
        
        # Button
        button_frame = tk.Frame(self, bg="#e8f5e9")
        button_frame.pack(pady=20)
        
        ok_button = tk.Button(
            button_frame,
            text="Fermer",
            command=self.destroy,
            bg="#27ae60",
            fg="white",
            font=("Arial", 13, "bold"),
            padx=40,
            pady=18
        )
        ok_button.pack()
        
        self.protocol("WM_DELETE_WINDOW", self.destroy)

# Multi-Device Modals (for parallel reassembly on all devices)

class MultiDeviceModal(tk.Toplevel):
    """Modal for multi-device operations (informational with button)."""
    def __init__(self, master, title, message, on_cancel=None):
        super().__init__(master)
        self.title(f"[{title}] - Multi-Appareils")
        self.geometry("700x450")
        self.configure(bg="#f0f0f0")
        self.transient(master)
        self.grab_set()

        self.message_label = tk.Label(
            self,
            text=message,
            justify=tk.LEFT,
            wraplength=660,
            bg="#f0f0f0",
            font=("Arial", 11)
        )
        self.message_label.pack(pady=20, padx=20)

        self.button_frame = tk.Frame(self, bg="#f0f0f0")
        self.button_frame.pack(pady=20)

        self.ok_button = tk.Button(
            self.button_frame,
            text="Continuer",
            command=self.destroy,
            bg="#27ae60",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=30,
            pady=12
        )
        self.ok_button.pack(side=tk.LEFT, padx=10)

        self.on_cancel = on_cancel
        if on_cancel:
            self.cancel_button = tk.Button(
                self.button_frame,
                text="Annuler",
                command=self.cancel,
                bg="#e74c3c",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=20,
                pady=10
            )
            self.cancel_button.pack(side=tk.LEFT, padx=10)

        # Handle force close (X button)
        self.protocol("WM_DELETE_WINDOW", self._on_force_close)

    def _on_force_close(self):
        """Handle force close (X button) - triggers cancel."""
        if self.on_cancel:
            self.on_cancel()
        self.destroy()

    def cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.destroy()

class MultiDeviceWaitModal(tk.Toplevel):
    """Modal for multi-device operations where user just needs to wait (no buttons)."""
    def __init__(self, master, title, message, on_cancel=None):
        super().__init__(master)
        self.title(f"[{title}] - Multi-Appareils")
        self.geometry("700x450")
        self.configure(bg="#e8f4f8")
        self.transient(master)
        self.grab_set()

        self.message_label = tk.Label(
            self,
            text=message,
            justify=tk.LEFT,
            wraplength=660,
            bg="#e8f4f8",
            font=("Arial", 11)
        )
        self.message_label.pack(pady=20, padx=20)

        self.on_cancel = on_cancel
        # Handle force close (X button)
        if on_cancel:
            self.protocol("WM_DELETE_WINDOW", self._on_force_close)
        else:
            # If no specific cancel callback, just destroy
            self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _on_force_close(self):
        """Handle force close (X button) - triggers cancel."""
        if self.on_cancel:
            self.on_cancel()
        self.destroy()

class MultiDeviceConfirmationModal(tk.Toplevel):
    """Modal for confirming action on all devices."""
    def __init__(self, master, message, on_done, on_cancel=None):
        super().__init__(master)
        self.title("[Confirmation] - Multi-Appareils")
        self.geometry("700x450")
        self.configure(bg="#fff3cd")
        self.transient(master)
        self.grab_set()

        self.message_label = tk.Label(
            self,
            text=message,
            justify=tk.LEFT,
            wraplength=660,
            bg="#fff3cd",
            font=("Arial", 11)
        )
        self.message_label.pack(pady=20, padx=20)

        self.button_frame = tk.Frame(self, bg="#fff3cd")
        self.button_frame.pack(pady=20)

        self.on_done = on_done
        self.done_button = tk.Button(
            self.button_frame,
            text="✓ C'est fait",
            command=self.done,
            bg="#27ae60",
            fg="white",
            font=("Arial", 12, "bold"),
            padx=30,
            pady=15
        )
        self.done_button.pack(side=tk.LEFT, padx=10)

        self.on_cancel = on_cancel
        if on_cancel:
            self.cancel_button = tk.Button(
                self.button_frame,
                text="Annuler",
                command=self.cancel,
                bg="#e74c3c",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=20,
                pady=10
            )
            self.cancel_button.pack(side=tk.LEFT, padx=10)

        # Handle force close (X button)
        self.protocol("WM_DELETE_WINDOW", self._on_force_close)

    def _on_force_close(self):
        """Handle force close (X button) - triggers cancel."""
        if self.on_cancel:
            self.on_cancel()
        self.destroy()

    def done(self):
        if self.on_done:
            self.on_done()
        self.destroy()

    def cancel(self):
        if self.on_cancel:
            self.on_cancel()
        self.destroy()
