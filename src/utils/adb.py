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
        self.logger.info("Recherche des appareils connectés...")
        output = self.run_command("devices")
        if not output:
            return []
        
        devices = []
        for line in output[1:]:
            if "device" in line:
                devices.append(line.split("\t")[0])
        
        if devices:
            self.logger.info(f"Appareils trouvés: {devices}")
        else:
            self.logger.info("Aucun appareil trouvé.")
            
        return devices