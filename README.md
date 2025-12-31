# 📱 ADB Transfer Tool

**Outil de transfert de fichiers haute performance via ADB pour Android**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://github.com)

---

## 📋 Table des Matières

- [Aperçu](#-aperçu)
- [Fonctionnalités](#-fonctionnalités)
- [Installation](#-installation)
- [Utilisation](#-utilisation)
- [Configuration](#-configuration)
- [Architecture](#-architecture)
- [Développement](#-développement)
- [Dépannage](#-dépannage)

---

## 🎯 Aperçu

ADB Transfer Tool est une application de transfert de fichiers optimisée pour transférer rapidement de grandes quantités de données vers des appareils Android via USB. L'outil divise intelligemment les fichiers volumineux en morceaux (chunks) et regroupe les petits fichiers en archives ZIP pour maximiser la vitesse de transfert.

### Problème Résolu

Le transfert de fichiers via `adb push` standard est lent pour :

- **Fichiers volumineux** : ADB a une limite de bande passante par flux
- **Nombreux petits fichiers** : Chaque fichier nécessite une négociation de protocole

### Solution

| Type de Fichier              | Stratégie                                 | Avantage                     |
| ---------------------------- | ----------------------------------------- | ---------------------------- |
| **Gros fichiers** (>10 Mo)   | Découpage en chunks + transfert parallèle | Sature la bande passante USB |
| **Petits fichiers** (<10 Mo) | Regroupement en bundles ZIP               | 1 transfert au lieu de 1000+ |

---

## ✨ Fonctionnalités

### Transfert Optimisé

- ⚡ **Transfert parallèle** - Plusieurs flux simultanés (configurable)
- 📦 **Chunking intelligent** - Découpe les gros fichiers en morceaux de 100 Mo
- 🗜️ **Bundling ZIP** - Regroupe les petits fichiers en archives optimales (~50 Mo)
- 🔄 **Reprise de transfert** - Ignore les fichiers déjà transférés
- 📊 **Ordonnancement SJF** - Petits fichiers en premier pour une complétion plus rapide

### Gestion des Appareils

- 📱 **Multi-appareils** - Transfert simultané vers plusieurs appareils
- 🔓 **Déverrouillage automatique** - Support PIN/mot de passe/swipe
- 🛠️ **Mode sans Termux** - Fonctionne en mode ADB Shell (recommandé)
- 📲 **Installation APK** - Installe les outils depuis le dossier `apk/`

### Mises à Jour

- 🔄 **Auto-update Git** - Vérifie les mises à jour au démarrage
- 📋 **Affichage version** - Version affichée dans la barre de titre

### Interface

- 🎨 **Interface graphique** - Application Tkinter intuitive
- 📁 **Sélection de dossiers** - Parcourir source et destination
- 📜 **Journal en direct** - Suivi du transfert en temps réel
- ⚙️ **Paramètres organisés** - 3 sections claires avec codes couleur

---

## 📥 Installation

### Option 1 : Exécutable Portable (Recommandé)

Téléchargez `ADB_Transfer_Tool.exe` depuis les [Releases](https://github.com/FaideJaures/adb-transfer/releases) et exécutez-le directement.

> ⚠️ **Prérequis** : ADB doit être installé et accessible dans le PATH.

### Option 2 : Depuis les Sources

```bash
# Cloner le dépôt
git clone https://github.com/FaideJaures/adb-transfer.git
cd adb-transfer

# Installer les dépendances (aucune dépendance externe requise!)
# L'application utilise uniquement la bibliothèque standard Python

# Lancer l'application
cd src
python main.py
```

### Prérequis

| Composant | Version | Notes                                                 |
| --------- | ------- | ----------------------------------------------------- |
| Python    | 3.10+   | Requis uniquement pour l'exécution depuis les sources |
| ADB       | Récent  | Doit être dans le PATH système                        |
| Windows   | 10/11   | Testé sur Windows 11                                  |

---

## 🚀 Utilisation

### Démarrage Rapide

1. **Connectez** votre appareil Android via USB
2. **Activez** le débogage USB sur l'appareil
3. **Lancez** l'application (`python src/main.py` ou `.exe`)
4. **Sélectionnez** l'appareil dans la liste
5. **Choisissez** le dossier source (PC) et destination (Android)
6. **Cliquez** sur "Transférer"

### Interface Principale

```
┌─────────────────────────────────────────────────────┐
│  Outil de Transfert ADB - v1.0.0                    │
├─────────────────────────────────────────────────────┤
│  Appareils :                                        │
│  ☑ ABC123DEF (Samsung Galaxy S21)                   │
│  ☑ XYZ789GHI (Xiaomi Redmi Note)                    │
├─────────────────────────────────────────────────────┤
│  Source : C:\Users\Documents\Media                  │
│  Destination : /sdcard/Download                     │
├─────────────────────────────────────────────────────┤
│  [Transférer] [Paramètres] [Installer APKs]         │
├─────────────────────────────────────────────────────┤
│  Journal :                                          │
│  [INFO] Scan de 1500 fichiers...                    │
│  [INFO] Création de 3 bundles ZIP...                │
│  [SUCCESS] Transfert terminé en 2m30s               │
└─────────────────────────────────────────────────────┘
```

### Boutons d'Action

| Bouton                    | Fonction                                        |
| ------------------------- | ----------------------------------------------- |
| **Transférer**            | Démarre le transfert des fichiers               |
| **Paramètres**            | Ouvre la fenêtre de configuration               |
| **Installer APKs**        | Installe les APK du dossier `apk/`              |
| **Workflow Termux**       | Lance le workflow Termux (si activé)            |
| **Déplacer Dossier**      | Déplace les fichiers vers la destination finale |
| **Supprimer Temporaires** | Nettoie le dossier temporaire sur l'appareil    |

---

## ⚙️ Configuration

### Fenêtre Paramètres

La fenêtre de paramètres est organisée en **4 sections** :

#### 🔵 Section Transfert

| Paramètre                  | Défaut                | Description                            |
| -------------------------- | --------------------- | -------------------------------------- |
| Processus parallèles       | 4                     | Nombre de transferts simultanés        |
| Taille chunks (Mo)         | 100                   | Taille des morceaux pour gros fichiers |
| Seuil petits fichiers (Mo) | 10                    | Fichiers < ce seuil sont bundlés       |
| Taille bundles ZIP (Mo)    | 50                    | Taille cible des archives ZIP          |
| Dossier distant            | /sdcard/transfer_temp | Dossier temporaire sur l'appareil      |

#### 🟢 Section Optimisations

| Paramètre                  | Défaut | Description                       |
| -------------------------- | ------ | --------------------------------- |
| Reprendre transfert        | ✅     | Ignore les fichiers déjà présents |
| Petits fichiers en premier | ✅     | Ordonnancement SJF                |
| Vérifier après transfert   | ✅     | Vérifie l'intégrité des fichiers  |
| Déplacer vers destination  | ❌     | Déplace automatiquement après     |
| Supprimer temp après       | ❌     | Nettoie le dossier temporaire     |

#### � Section Mode Rapide

> **Ignorer les vérifications redondantes pour plus de vitesse**

| Paramètre                        | Défaut | Description                                    |
| -------------------------------- | ------ | ---------------------------------------------- |
| Ignorer vérification après push  | ❌     | Skip la vérification post-transfert            |
| Faire confiance aux chunks       | ❌     | Ne pas re-vérifier les chunks locaux existants |
| Ignorer vérification des tailles | ❌     | Skip les comparaisons de tailles               |

> ⚠️ **Note** : La vérification finale après réassemblage reste active pour garantir l'intégrité.

#### �🟠 Section Appareil

| Paramètre            | Défaut   | Description                             |
| -------------------- | -------- | --------------------------------------- |
| Mode sans Termux     | ✅       | Utilise ADB Shell (recommandé)          |
| Déverrouiller auto   | ❌       | Déverrouille l'appareil automatiquement |
| Méthode              | password | Type de déverrouillage                  |
| Code/Mot de passe    | 0000     | Secret de déverrouillage                |
| Détecter permissions | ✅       | Détecte les permissions auto            |
| Timeout (sec)        | 1800     | Timeout pour le réassemblage            |

### Fichier config.json

La configuration est sauvegardée dans `config.json` à la racine :

```json
{
  "parallel_processes": 4,
  "chunk_size": 104857600,
  "small_file_threshold": 10485760,
  "bundle_size": 52428800,
  "remote_temp_dir": "/sdcard/transfer_temp",
  "resume_transfer": true,
  "sjf_scheduling": true,
  "use_adb_shell_mode": true,
  "auto_update": true,
  "skip_early_verification": false,
  "trust_local_chunks": false,
  "skip_size_verification": false
}
```

---

## 🏗️ Architecture

### Structure du Projet

```
claude_v2/
├── src/
│   ├── main.py              # Point d'entrée, interface Tkinter
│   ├── config.py            # Constantes de configuration
│   ├── core/
│   │   ├── transfer.py      # Gestionnaire de transfert
│   │   ├── file_chunker.py  # Découpage des gros fichiers
│   │   └── reassembly.py    # Réassemblage sur l'appareil
│   ├── utils/
│   │   ├── adb.py           # Wrapper ADB
│   │   ├── apk_installer.py # Installation d'APK
│   │   ├── updater.py       # Auto-update Git
│   │   ├── termux.py        # Gestion Termux
│   │   └── unified.sh       # Script shell pour l'appareil
│   └── ui/
│       └── modal_dialog.py  # Fenêtres modales
├── apk/                      # APK à installer (Termux, etc.)
├── dist/                     # Exécutable compilé
├── config.json              # Configuration utilisateur
├── build.bat                # Script de compilation
└── adb_transfer.spec        # Configuration PyInstaller
```

### Flux de Transfert

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUX DE TRANSFERT                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. SCAN                                                    │
│     └─> Parcourt le dossier source                          │
│         └─> Classe les fichiers : gros vs petits            │
│             └─> Ordonne par taille (SJF)                    │
│                                                             │
│  2. PRÉPARATION                                             │
│     ├─> Gros fichiers : découpage en chunks de 100 Mo       │
│     └─> Petits fichiers : bundling en ZIP de 50 Mo          │
│                                                             │
│  3. TRANSFERT                                               │
│     └─> Transfert parallèle (4 workers par défaut)          │
│         ├─> Chunks : push individuels                       │
│         └─> Bundles : push des fichiers ZIP                 │
│                                                             │
│  4. VÉRIFICATION                                            │
│     └─> Compare tailles locales vs distantes                │
│         └─> Retransfert des fichiers manquants              │
│                                                             │
│  5. RÉASSEMBLAGE (sur l'appareil)                           │
│     ├─> Extraction des bundles ZIP                          │
│     └─> Réassemblage des chunks                             │
│                                                             │
│  6. DÉPLACEMENT (optionnel)                                 │
│     └─> Déplace vers la destination finale                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Algorithmes Clés

#### Ordonnancement SJF (Shortest Job First)

Les fichiers sont triés par taille croissante pour maximiser le nombre de fichiers complétés rapidement.

#### Bin Packing FFD (First Fit Decreasing)

Les petits fichiers sont regroupés en bundles de taille optimale (~50 Mo) pour minimiser le nombre de transferts.

#### Reprise de Transfert

Avant chaque transfert, vérifie si le fichier existe déjà avec la bonne taille sur l'appareil.

---

## 👨‍💻 Développement

### Lancer en Mode Développement

```bash
cd src
python main.py
```

### Compiler l'Exécutable

```bash
# Option 1 : Script batch
build.bat

# Option 2 : Commande directe
cd src
pyinstaller --onefile --windowed --name ADB_Transfer_Tool main.py
```

> ⚠️ **Note Python 3.13** : Si vous avez NumPy installé, désinstallez-le temporairement avant la compilation (incompatibilité connue).

### Structure des Modules

| Module            | Responsabilité                               |
| ----------------- | -------------------------------------------- |
| `main.py`         | Interface utilisateur, orchestration         |
| `transfer.py`     | Logique de transfert, parallélisation        |
| `file_chunker.py` | Découpage et métadonnées des chunks          |
| `reassembly.py`   | Réassemblage côté appareil                   |
| `adb.py`          | Encapsulation des commandes ADB              |
| `updater.py`      | Vérification et application des mises à jour |

### Ajouter une Fonctionnalité

1. Identifiez le module concerné
2. Ajoutez la logique dans le module approprié
3. Mettez à jour l'interface dans `main.py` si nécessaire
4. Testez avec `python main.py`
5. Recompilez avec `build.bat`

---

## 🔧 Dépannage

### Problèmes Courants

#### "ADB not found" / "ADB introuvable"

```bash
# Vérifiez que ADB est dans le PATH
adb version

# Si non, ajoutez le chemin vers platform-tools dans les variables d'environnement
```

#### "No devices found" / "Aucun appareil"

1. Vérifiez que le câble USB fonctionne (données, pas charge seule)
2. Activez le débogage USB sur l'appareil
3. Acceptez la demande d'autorisation sur l'appareil
4. Exécutez `adb devices` pour vérifier

#### Transfert lent

- Augmentez le nombre de processus parallèles (4 → 8)
- Utilisez un câble USB 3.0 de qualité
- Évitez les hubs USB

#### Échec du réassemblage

- Vérifiez l'espace disponible sur l'appareil
- Augmentez le timeout dans les paramètres
- Activez le mode Termux si le mode ADB Shell échoue

#### Erreur de compilation PyInstaller

```bash
# Si erreur liée à NumPy avec Python 3.13
pip uninstall numpy
pyinstaller --onefile --windowed --name ADB_Transfer_Tool src/main.py
```

### Logs

Les logs sont affichés dans le journal de l'interface. Pour un débogage avancé, lancez depuis un terminal :

```bash
cd src
python main.py 2>&1 | tee debug.log
```

---

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 🙏 Remerciements

- **ADB** - Android Debug Bridge par Google
- **Termux** - Terminal émulateur pour Android
- **PyInstaller** - Création d'exécutables Python

---

## 📞 Support

Pour signaler un bug ou demander une fonctionnalité, ouvrez une [issue](https://github.com/FaideJaures/adb-transfer/issues).

---

**Made with ❤️ for fast Android file transfers**
