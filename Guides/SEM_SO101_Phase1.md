# Guide d'Installation LeRobot SO-ARM 101

## Phase 1 : Installation Complète de l'Environnement

### 🧩 Scripts utilisés

*Aucun script SEM.* Cette phase installe et configure l'environnement : conda, fork LeRobot, dépôt SEM, pilotes, permissions USB/caméra et outils vidéo. Les scripts SEM interviennent à partir des phases suivantes.

### 📋 Prérequis

- Ubuntu 22.04 ou 24.04
- Connexion Internet stable
- Droits sudo
- Au moins 20 GB d'espace disque libre
- (Optionnel) GPU NVIDIA pour l'entraînement


### 🧹 Étape 0 : Désinstallation (si installation précédente)

**Suppression de l'environnement conda existant**

```bash
# Désactiver l'environnement
conda deactivate
# Supprimer l'environnement lerobot
conda remove --name lerobot --all -y
```

**Nettoyage des dossiers**

> ⚠️ **Opération destructive — irréversible.** Cette étape supprime définitivement :
> - le dépôt cloné `~/lerobot`, **y compris `~/lerobot/calibration/`** : calibrations des bras, `camera_settings.json`, `repos_position.json`, `camera_mask.json` et les certificats VR ;
> - le cache `~/.cache/huggingface/lerobot`, **y compris les datasets enregistrés** (ex. `local/so101_pick_place/`).
>
> À n'utiliser que pour une réinstallation complète, sur un poste ne contenant aucune donnée à conserver. **Sauvegardez `~/lerobot/calibration/` et vos datasets avant de continuer.**

```bash
# Supprimer le dépôt cloné (inclut ~/lerobot/calibration/ : calibrations, réglages caméra, certificats VR)
rm -rf ~/lerobot
# Supprimer le cache HuggingFace/LeRobot (inclut les datasets enregistrés)
rm -rf ~/.cache/huggingface/lerobot
```

**Vérification**

```bash
# Vérifier que l'environnement est supprimé
conda env list | grep lerobot
# Vérifier que les dossiers sont supprimés (ne doit rien retourner)
ls ~/lerobot 2>/dev/null
```


### 📦 Étape 1 : Installation de Miniconda

**Outils de base requis par la suite du guide**

```bash
# git (Étape 3) et wget (téléchargement de Miniconda) ne sont pas toujours présents sur une Ubuntu fraîche
sudo apt update
sudo apt install git wget -y
```

**Vérifier si Miniconda est déjà présent**

```bash
conda --version
```

> **Note :** Si la commande renvoie « command not found », c'est normal : Miniconda n'est pas encore installé. Passez directement à l'installation ci-dessous.

**Installation pour système x86/x64 (PC standard)**

```bash
mkdir -p ~/miniconda3
cd ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm ~/miniconda3/miniconda.sh
source ~/miniconda3/bin/activate
conda init --all
source ~/.bashrc
```

**Installation pour système ARM (Jetson)**

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
chmod +x Miniconda3-latest-Linux-aarch64.sh
./Miniconda3-latest-Linux-aarch64.sh
source ~/.bashrc
```

> **Note :** Cette variante ARM/Jetson n'est **pas** le chemin validé pour le projet SEM. Le chemin validé est l'installation x86/x64 sur PC Ubuntu 22.04 ou 24.04. Les étapes suivantes (pilotes NVIDIA, PyTorch `cu121`) supposent ce chemin x86 et ne s'appliquent pas telles quelles à un Jetson (JetPack/L4T).


### 🐍 Étape 2 : Création de l'environnement Python

```bash
# Créer un environnement Python 3.10
conda create -y -n lerobot python=3.10
# Activer l'environnement
conda activate lerobot
# Vérifier l'activation
which python
# Devrait afficher : /home/<user>/miniconda3/envs/lerobot/bin/python
```


### 📁 Étape 3 : Clonage des dépôts (LeRobot + scripts SEM)

**Dépôt LeRobot (fork validé pour le projet SEM)**

```bash
# Cloner le fork validé pour le pipeline SEM
git clone https://github.com/ZhuYaoHui1998/lerobot.git ~/lerobot
# Se placer dans le dossier
cd ~/lerobot
# Vérifier la branche
git branch
```

> **Note :** Il s'agit d'un **fork** de LeRobot (et non du dépôt officiel `huggingface/lerobot`), figé sur l'ancienne structure de l'API : `lerobot.common.*` et les scripts exécutables `lerobot/scripts/*.py`. Cette structure est **requise** par les scripts SEM 9, 10 et 11. Le dépôt officiel actuel a refactorisé cette API (`lerobot.*` + commandes CLI) ; l'utiliser nécessiterait de réécrire ces scripts.

**Dépôt SEM (scripts + guides)**

```bash
# Cloner le dépôt SEM dans un dossier nommé Scripts_SEM, à l'intérieur de ~/lerobot
cd ~/lerobot
git clone https://github.com/yanko-sem/SO-ARM-101.git Scripts_SEM
```

> **Note :** Le dépôt s'appelle `SO-ARM-101` mais on le clone dans un dossier `Scripts_SEM` (la cible explicite à la fin de la commande). Les scripts se trouvent alors dans `~/lerobot/Scripts_SEM/scripts`.


### 🎬 Étape 4 : Installation de ffmpeg

**Installation via conda (bibliothèques d'encodage vidéo)**

```bash
# S'assurer d'être dans l'environnement lerobot
conda activate lerobot
# Installer ffmpeg via conda (IMPORTANT : faire avant pip)
conda install ffmpeg -c conda-forge -y
# Vérifier l'installation
ffmpeg -version
```

**Installation des outils ffmpeg système (optionnel mais recommandé)**

Pourquoi cette installation ? Les outils ffplay et ffprobe permettent de lire et vérifier les vidéos enregistrées lors de la création de datasets. Ils sont utiles pour visualiser les enregistrements et diagnostiquer d'éventuels problèmes.

```bash
# Mettre à jour la liste des paquets avant installation
sudo apt update
# Installer les outils ffmpeg système
sudo apt install ffmpeg -y
# Vérifier l'installation
ffplay -version
ffprobe -version
```


### ⚙️ Étape 5 : Installation de LeRobot avec support Feetech

```bash
# S'assurer d'être dans le bon dossier
cd ~/lerobot
# Installer LeRobot avec support pour les servos Feetech
pip install -e ".[feetech]"
# Installer le SDK Dynamixel, utilisé par les scripts SEM pour piloter les servos
pip install dynamixel-sdk
```

> **Note :** L'installation peut prendre 5-10 minutes selon votre connexion

> **Pourquoi `dynamixel-sdk` ?** Les servos sont des Feetech STS3215, mais les scripts SEM (1 à 8 et 11) communiquent avec eux via le SDK Dynamixel (`from dynamixel_sdk import *`). L'extra `[feetech]` n'installe que le SDK Feetech ; le SDK Dynamixel doit donc être ajouté séparément, sinon les scripts échouent à l'import.


### 🔌 Étape 6 : Permissions USB et caméras

Les robots communiquent via les ports USB (`/dev/ttyACM*`) et les caméras via `/dev/video*`. Pour y accéder sans mot de passe administrateur, ajoutez votre utilisateur aux groupes `dialout` et `video` :

```bash
sudo usermod -a -G dialout $USER
sudo usermod -a -G video $USER
```

**Déconnectez-vous puis reconnectez-vous** pour appliquer le changement.

**Vérification :**

```bash
groups | grep dialout
groups | grep video
```

Les mots `dialout` et `video` doivent apparaître dans la liste.

> **Note :** Cette étape est indispensable. Sans elle, les scripts des phases suivantes ne pourront pas communiquer avec les robots ni accéder aux caméras. Répétez cette opération pour chaque compte utilisateur (enseignant, élèves).


### 📷 Étape 7 : Installation des outils caméra (v4l-utils + guvcview)

Pourquoi cette installation ? Les scripts SEM des phases suivantes verrouillent l'exposition, la balance des blancs et le gain des caméras, afin que les images soient identiques entre l'enregistrement du dataset (script 8) et le déploiement du modèle (script 11). Ce verrouillage s'appuie sur `v4l2-ctl` (paquet `v4l-utils`), et le réglage de l'image en direct se fait avec `guvcview`. Sans ces outils, le script 8 ne pourra ni régler ni verrouiller les caméras.

```bash
sudo apt update
sudo apt install v4l-utils guvcview -y
```

**Vérification :**

```bash
v4l2-ctl --version
guvcview --version
```


### 🎮 Étape 8 : Installation des drivers NVIDIA (Optionnel)

**Vérifier la présence d'un GPU NVIDIA**

```bash
lspci | grep -i nvidia
```

**Si un GPU est détecté - Nettoyer les anciennes installations (réinstallation propre uniquement)**

> ⚠️ Ces commandes désinstallent **tous** les pilotes NVIDIA et CUDA présents. Ne les exécuter **que** si vous repartez d'une installation propre. Sur un poste dont les pilotes NVIDIA fonctionnent déjà (`nvidia-smi` répond), **sautez ce bloc** et passez directement à l'installation.

```bash
sudo apt remove --purge nvidia-* -y
sudo apt remove --purge cuda-* -y
sudo apt autoremove -y
```

**Installer les drivers**

> **Note :** Si `add-apt-repository` est introuvable (Ubuntu minimale) : `sudo apt install software-properties-common -y`.

```bash
# Ajouter le PPA officiel
sudo add-apt-repository ppa:graphics-drivers/ppa -y
sudo apt update
# Voir les drivers disponibles
ubuntu-drivers devices
# Installer automatiquement le pilote recommandé (voie principale)
sudo ubuntu-drivers autoinstall
```

> **Note :** N'installez une version précise (`sudo apt install nvidia-driver-XXX -y`) que si elle est explicitement recommandée par `ubuntu-drivers devices` ou par l'administrateur du poste.

> **Important :** Redémarrage nécessaire après l'installation des drivers

```bash
sudo reboot
```

**Après redémarrage - Vérification**

```bash
# Vérifier les drivers
nvidia-smi
```


### 🔥 Étape 9 : Configuration de PyTorch

**Configuration CPU (sans GPU)**

```bash
# Activer l'environnement
conda activate lerobot
cd ~/lerobot
# Installer PyTorch CPU
pip uninstall torch torchvision torchaudio -y
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

**Configuration GPU NVIDIA**

```bash
# Activer l'environnement
conda activate lerobot
cd ~/lerobot
# Désinstaller les versions existantes
pip uninstall torch torchvision torchaudio -y
# Installer avec support CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```


### ✅ Étape 10 : Vérifications finales

**Test PyTorch**

```bash
python -c "import torch; \
    print(f'PyTorch version: {torch.__version__}'); \
    print(f'CUDA disponible: {torch.cuda.is_available()}'); \
    print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"Aucun\"}')"
```

**Test des dépendances du projet**

```bash
# Bibliothèques de base (torch déjà vérifié ci-dessus)
python -c "import cv2; print('cv2', cv2.__version__)"
python -c "import numpy; print('numpy', numpy.__version__)"
# SDK des servos (détection/configuration des moteurs — script 1)
python -c "from dynamixel_sdk import *; print('dynamixel_sdk OK')"
# Politique ACT (importée par le script 11 de déploiement)
python -c "from lerobot.common.policies.act.modeling_act import ACTPolicy; print('ACTPolicy OK')"
```

**Tableau de vérification**

| Composant | Version attendue | Commande de vérification |
| :--- | :--- | :--- |
| Conda | Latest | `conda --version` |
| Python | 3.10.x | `python --version` |
| PyTorch | version installée par l'Étape 9 | `python -c "import torch; print(torch.__version__)"` |
| CUDA (roue PyTorch, si GPU) | 12.1 (roues `cu121`) | `python -c "import torch; print(torch.version.cuda)"` |
| Pilote NVIDIA (si GPU) | ≥ supportant CUDA 12.1 | `nvidia-smi` |
| ffmpeg | 6.x ou 7.x | `ffmpeg -version` |
| LeRobot (fork) | — | `python -c "from lerobot.common.policies.act.modeling_act import ACTPolicy"` |
| dynamixel-sdk | — | `python -c "from dynamixel_sdk import *; print('OK')"` |
| Groupe dialout | — | `groups \| grep dialout` |
| Groupe video | — | `groups \| grep video` |
| v4l-utils | — | `v4l2-ctl --version` |
| guvcview | — | `guvcview --version` |


### 🔧 Dépannage

**Problème : nvidia-smi ne fonctionne pas**

```bash
# Vérifier Secure Boot
mokutil --sb-state
# Vérifier les modules
lsmod | grep nvidia
# Voir les logs
sudo dmesg | grep nvidia
```

**Problème : PyTorch ne détecte pas le GPU**

```bash
# Réinstaller PyTorch avec CUDA
pip uninstall torch torchvision torchaudio -y
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```


### 📝 Notes importantes

1. **Environnement :** activez `conda activate lerobot` à chaque nouvelle session de terminal.
2. **Ordre d'installation :** installez toujours ffmpeg via conda **avant** le `pip install`.
3. **Permissions :** les groupes `dialout` et `video` sont à refaire **pour chaque compte utilisateur** (enseignant, élèves).
4. **Dépôt LeRobot :** utilisez le fork validé (`ZhuYaoHui1998/lerobot`), **jamais** le dépôt officiel `huggingface/lerobot` — son API refactorisée casserait les scripts SEM 9, 10 et 11.
