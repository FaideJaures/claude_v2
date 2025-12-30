# claude_v2/src/ui/reassembly_dialog.py
import tkinter as tk
from tkinter import messagebox

class ReassemblyDialog(tk.Toplevel):
    def __init__(self, master, reassembly_manager, device_id, remote_temp_dir, target_dir):
        super().__init__(master)
        self.title("Assistant de Réassemblage Termux")
        self.geometry("600x400")
        self.reassembly_manager = reassembly_manager
        self.device_id = device_id
        self.remote_temp_dir = remote_temp_dir
        self.target_dir = target_dir
        
        self.step = 0
        self.steps = [
            self.step_1_intro,
            self.step_2_launch_termux,
            self.step_3_storage_permission,
            self.step_4_execute_script,
            self.step_5_finalize,
            self.step_6_end,
        ]
        
        self.create_widgets()
        self.next_step()

    def create_widgets(self):
        self.instructions = tk.Label(self, text="", justify=tk.LEFT, wraplength=580)
        self.instructions.pack(pady=20, padx=20)
        
        self.next_button = tk.Button(self, text="Suivant", command=self.next_step)
        self.next_button.pack(pady=10)
        
        self.cancel_button = tk.Button(self, text="Annuler", command=self.destroy)
        self.cancel_button.pack(pady=10)

    def next_step(self):
        if self.step < len(self.steps):
            self.steps[self.step]()
            self.step += 1
        else:
            self.destroy()

    def step_1_intro(self):
        self.instructions.config(text="Bienvenue dans l'assistant de réassemblage Termux.\n\n" 
                                      "Cet assistant vous guidera à travers les étapes nécessaires pour réassembler les fichiers sur votre appareil en utilisant Termux.\n\n" 
                                      "Cliquez sur 'Suivant' pour commencer.")

    def step_2_launch_termux(self):
        self.instructions.config(text="Étape 1: Lancement de Termux\n\n" 
                                      "L'application va maintenant tenter de lancer Termux sur votre appareil.\n\n" 
                                      "Veuillez vous assurer que votre appareil est déverrouillé.\n\n" 
                                      "Cliquez sur 'Suivant' pour lancer Termux.")
        self.next_button.config(command=self.do_step_2)
        
    def do_step_2(self):
        self.reassembly_manager.launch_termux(self.device_id)
        self.next_button.config(command=self.next_step)
        self.next_step()

    def step_3_storage_permission(self):
        self.instructions.config(text="Étape 2: Autorisation de stockage\n\n" 
                                      "L'application va maintenant demander l'autorisation d'accéder au stockage de votre appareil.\n\n" 
                                      "Dans Termux, une commande va être tapée pour vous. Vous devriez voir une fenêtre contextuelle vous demandant d'autoriser l'accès au stockage. Veuillez appuyer sur 'Autoriser'.\n\n" 
                                      "Cliquez sur 'Suivant' pour continuer.")
        self.next_button.config(command=self.do_step_3)
        
    def do_step_3(self):
        self.reassembly_manager.setup_storage_permission(self.device_id)
        response = messagebox.askyesno("Permission", "Avez-vous autorisé l'accès au stockage dans Termux?")
        if response:
            self.next_button.config(command=self.next_step)
            self.next_step()
        else:
            messagebox.showerror("Erreur", "L'autorisation de stockage est nécessaire pour continuer.")
            self.destroy()

    def step_4_execute_script(self):
        self.instructions.config(text="Étape 3: Exécution du script\n\n" 
                                      "L'application va maintenant exécuter le script de réassemblage dans Termux.\n\n" 
                                      "Cliquez sur 'Suivant' pour commencer le réassemblage.")
        self.next_button.config(command=self.do_step_4)
        
    def do_step_4(self):
        self.reassembly_manager.execute_reassembly_script(self.device_id, self.remote_temp_dir)
        self.next_button.config(command=self.next_step)
        self.next_step()

    def step_5_finalize(self):
        self.instructions.config(text="Étape 4: Finalisation\n\n" 
                                      "Le réassemblage est terminé. Les fichiers vont maintenant être déplacés vers leur destination finale.\n\n" 
                                      "Cliquez sur 'Suivant' pour finaliser.")
        self.next_button.config(command=self.do_step_5)
        
    def do_step_5(self):
        self.reassembly_manager.move_to_final_destination(self.device_id, self.remote_temp_dir, self.target_dir)
        self.next_button.config(command=self.next_step)
        self.next_step()
        
    def step_6_end(self):
        self.instructions.config(text="Le processus de réassemblage est terminé avec succès!")
        self.next_button.config(text="Terminer", command=self.destroy)
        self.cancel_button.pack_forget()
