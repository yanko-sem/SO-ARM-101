# Guide d'Installation LeRobot SO-ARM 101

## Phase 1 : Installation Complète de l'Environnement

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

```bash
# Supprimer le dépôt cloné
rm -rf ~/lerobot
# Supprimer les caches de calibration
rm -rf ~/.cache/calibration/so101
rm -rf ~/.cache/calibration/so100
# Supprimer le cache HuggingFace/LeRobot
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

**Vérification de Miniconda**

```bash
conda --version
```

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


### 📁 Étape 3 : Clonage du dépôt LeRobot

```bash
# Cloner la version stable recommandée par Seeed Studio
git clone https://github.com/ZhuYaoHui1998/lerobot.git ~/lerobot
# Se placer dans le dossier
cd ~/lerobot
# Vérifier la branche
git branch
```

> **Note :** Cette version est maintenue stable et vérifiée compatible avec le matériel SO-ARM 101


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
```

> **Note :** L'installation peut prendre 5-10 minutes selon votre connexion


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


### 🎮 Étape 7 : Installation des drivers NVIDIA (Optionnel)

**Vérifier la présence d'un GPU NVIDIA**

```bash
lspci | grep -i nvidia
```

**Si un GPU est détecté - Nettoyer les anciennes installations**

```bash
sudo apt remove --purge nvidia-* -y
sudo apt remove --purge cuda-* -y
sudo apt autoremove -y
```

**Installer les drivers**

```bash
# Ajouter le PPA officiel
sudo add-apt-repository ppa:graphics-drivers/ppa -y
sudo apt update
# Voir les drivers disponibles
ubuntu-drivers devices
# Installer automatiquement le driver recommandé
sudo ubuntu-drivers autoinstall
# OU installer une version spécifique
sudo apt install nvidia-driver-550 -y
```

> **Important :** Redémarrage nécessaire après l'installation des drivers

```bash
sudo reboot
```

**Après redémarrage - Vérification**

```bash
# Vérifier les drivers
nvidia-smi
```


### 🔥 Étape 8 : Configuration de PyTorch

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


### ✅ Étape 9 : Vérifications finales

**Test PyTorch**

```bash
python -c "import torch; \
    print(f'PyTorch version: {torch.__version__}'); \
    print(f'CUDA disponible: {torch.cuda.is_available()}'); \
    print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"Aucun\"}')"
```

**Test LeRobot**

```bash
# Vérifier l'import
python -c "from lerobot import available_tasks; print('LeRobot installé avec succès')"
# Vérifier les scripts disponibles
python lerobot/scripts/find_motors_bus_port.py --help
# Vérifier les commandes
which lerobot-find-port
which lerobot-setup-motors
which lerobot-calibrate
```

**Tableau de vérification**

| Composant | Version attendue | Commande de vérification |
| :--- | :--- | :--- |
| Conda | Latest | `conda --version` |
| Python | 3.10.x | `python --version` |
| PyTorch | 2.5.x | `python -c "import torch; print(torch.__version__)"` |
| CUDA (si GPU) | 11.8+ | `nvidia-smi` |
| ffmpeg | 6.x ou 7.x | `ffmpeg -version` |
| LeRobot | Latest | `python -c "from lerobot import available_tasks"` |
| Groupe dialout | — | `groups \| grep dialout` |
| Groupe video | — | `groups \| grep video` |


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

1. **Version du dépôt :** Utiliser https://github.com/ZhuYaoHui1998/lerobot.git
2. **Ordre d'installation :** Toujours installer ffmpeg AVANT pip install
3. **GPU :** Non obligatoire sauf pour l'entraînement
4. **Environnement :** Toujours activer avec `conda activate lerobot`
5. **Permissions USB :** Chaque utilisateur doit être dans les groupes `dialout` et `video`
