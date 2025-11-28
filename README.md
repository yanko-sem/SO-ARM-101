[README.md](https://github.com/user-attachments/files/23821020/README.md)
# SO-ARM 101 - Projet Robotique Éducative

Système complet pour l'apprentissage de la robotique avec les bras SO-ARM 101.
Développé par le Service Ecoles Médias (SEM) du Département de l'Instruction Publique (DIP) de Genève en Suisse.

## 🎯 Objectif du Projet

Former un robot à effectuer des tâches de manipulation d'objets par apprentissage par démonstration (Imitation Learning) en utilisant le système LeRobot et les bras robotiques SO-ARM 101.

## 📋 Vue d'Ensemble des Phases

### ✅ Phases Complétées (Guides disponibles)
- **Phase 1** : Installation de l'environnement LeRobot
- **Phase 2** : Configuration des servos (IDs et ratios)
- **Phase 3** : Calibration des limites de mouvement
- **Phase 4** : Tests et contrôle manuel

### 🚀 Phases à Venir
- **Phase 5** : Téléopération (Leader contrôle Follower)
- **Phase 6** : Installation et configuration des caméras
- **Phase 7** : Enregistrement de trajectoires
- **Phase 8** : Configuration du système d'IA (ACT - Action Chunking Transformers)
- **Phase 9** : Entraînement du modèle
- **Phase 10** : Déploiement et test autonome

## 📦 Installation

```bash
# 1. Installer LeRobot (voir Phase 1 pour détails complets)
conda create -n lerobot python=3.10 -y
conda activate lerobot
git clone https://github.com/ZhuYaoHui1998/lerobot.git ~/lerobot
cd ~/lerobot
pip install -e ".[feetech]"

# 2. Installer les scripts SEM
cd ~/lerobot
git clone https://github.com/yanko-sem/SO-ARM-101.git Docs_SEM

# Structure créée :
# ~/lerobot/Docs_SEM/
#   ├── scripts_SEM/     (scripts Python)
#   └── guides/          (guides PDF)
```

## 🔧 Configuration Matérielle

### Matériel Requis
- 2x Bras SO-ARM 101 (Leader + Follower)
- 2x Adaptateurs USB Feetech
- 2x Alimentations (5V 3A minimum)
- 2x Caméras USB (pour les phases avancées)
- 1x PC avec Ubuntu 20.04+ (GPU recommandé pour l'IA)

### Configuration des Servos

#### Leader (Bras de contrôle)
- Servos 1,3 : Ratio 1:191 (C044)
- Servo 2 : Ratio 1:345 (C001)
- Servos 4,5,6 : Ratio 1:147 (C046)

#### Follower (Bras suiveur)
- Tous les servos : Ratio 1:345 (identiques)

## 📚 Guide d'Utilisation par Phase

### Phase 1 : Installation LeRobot
```bash
# Suivre le guide complet Phase1.pdf
# Points clés : Python 3.10, PyTorch, Dynamixel SDK
```

### Phase 2 : Configuration des Servos
```bash
cd ~/lerobot/Docs_SEM/scripts_SEM
python SEM_so101_config_servo.py

# Configure chaque servo avec son ID (1-6)
# Un servo à la fois, test de mouvement inclus
```

### Phase 3 : Calibration
```bash
python SEM_so101_calibrate.py

# Définit les limites min/max de chaque servo
# Sauvegarde automatique dans ~/.cache/calibration/so101/
```

### Phase 4 : Test et Contrôle Manuel
```bash
# Pour le Follower
python SEM_so101_control_follower.py

# Pour le Leader
python SEM_so101_control_leader.py

# Contrôles clavier disponibles :
# ↑/↓ : Augmenter/Diminuer position
# ←/→ : Changer de servo
# ESPACE : Centrer le servo actif
# C : Centrer tous les servos
# P : Mode précis ON/OFF
# S : Afficher positions
# A : Position ATTRAPER
# R : Position REPOS
# Q : Quitter (repos sécurisé)
# X : Arrêt d'urgence
```

### Phase 5 : Téléopération (À venir)
```bash
# Contrôle simultané Leader → Follower
cd ~/lerobot
python lerobot/scripts/control_robot.py teleoperate \
    --robot-path lerobot/configs/robot/so_arm_100.yaml
```

### Phase 6 : Configuration Caméras (À venir)
- Installation de 2 caméras USB
- Configuration dans LeRobot
- Calibration de la vision

### Phase 7 : Enregistrement de Données (À venir)
```bash
# Enregistrer des démonstrations
python lerobot/scripts/control_robot.py record \
    --robot-path lerobot/configs/robot/so_arm_100.yaml \
    --fps 30 \
    --episode-time-s 60 \
    --repo-id ${HF_USER}/so_arm_pick_place \
    --num-episodes 50
```

### Phase 8 : Configuration IA (À venir)
- Installation des modèles ACT (Action Chunking Transformers)
- Configuration des hyperparamètres
- Préparation du dataset

### Phase 9 : Entraînement (À venir)
```bash
# Entraîner le modèle sur les démonstrations
python lerobot/scripts/train.py \
    --config-path lerobot/configs/policy/act_so_arm_real.yaml \
    --dataset-repo-id ${HF_USER}/so_arm_pick_place
```

### Phase 10 : Déploiement Autonome (À venir)
```bash
# Exécuter le robot en mode autonome
python lerobot/scripts/control_robot.py replay \
    --robot-path lerobot/configs/robot/so_arm_100.yaml \
    --policy-path outputs/train/act_so_arm_real/checkpoints/last.ckpt
```

## 📁 Structure Complète des Fichiers

```
~/lerobot/
├── Docs_SEM/
│   ├── scripts_SEM/
│   │   ├── SEM_so101_config_servo.py
│   │   ├── SEM_so101_calibrate.py
│   │   ├── SEM_so101_control_follower.py
│   │   └── SEM_so101_control_leader.py
│   ├── guides/
│   │   ├── Phase1_Installation.pdf
│   │   ├── Phase2_Configuration.pdf
│   │   ├── Phase3_Calibration.pdf
│   │   └── Phase4_Tests.pdf
│   └── README.md
├── lerobot/
│   ├── configs/
│   │   ├── policy/
│   │   │   └── act_so_arm_real.yaml
│   │   └── robot/
│   │       ├── so_arm_100.yaml
│   │       └── feetech.yaml
│   ├── scripts/
│   │   ├── configure_motor.py
│   │   ├── control_robot.py
│   │   ├── train.py
│   │   ├── eval.py
│   │   └── visualize_dataset.py
│   ├── common/
│   │   ├── datasets/
│   │   ├── envs/
│   │   ├── policies/
│   │   └── utils/
│   └── __init__.py
├── dynamixel_sdk/
│   ├── port_handler.py
│   ├── packet_handler.py
│   └── __init__.py
├── outputs/
│   └── train/
│       └── act_so_arm_real/
│           └── checkpoints/
└── setup.py

~/.cache/
├── calibration/
│   └── so101/
│       ├── leader_calibration.json
│       └── follower_calibration.json
├── huggingface/
│   └── hub/
│       └── datasets/
└── torch/
```

## 🔧 Dépannage

| Problème | Solution |
|----------|----------|
| Port USB non détecté | `sudo chmod 666 /dev/ttyACM*` |
| Servo ne répond pas | Vérifier alimentation (LED allumée) |
| Calibration perdue | Refaire Phase 3 |
| Mouvement brusque | Activer mode précis (P) |
| Import error Python | Vérifier `conda activate lerobot` |
| Caméra non détectée | `ls /dev/video*` et vérifier USB |
| GPU non utilisé | Vérifier CUDA : `nvidia-smi` |

## 📊 Spécifications Techniques

### Servos STS3215
- Protocole : Dynamixel v1.0
- Baudrate : 1,000,000 bps
- Plage : 0-4095 (0°-360°)
- Centre : 2048
- Couple : 15 kg.cm

### Performances Attendues
- Fréquence contrôle : 30-50 Hz
- Latence téléopération : < 50ms
- Temps entraînement : 2-4h (50 épisodes)
- Précision finale : ~90% sur tâche pick & place

## 🌐 Ressources

### Documentation source
- [LeRobot GitHub](https://github.com/huggingface/lerobot)
- [SO-ARM Wiki Seeed](https://wiki.seeedstudio.com/so_arm_100/)
- [Feetech Robotics](https://www.feetechrc.com/)

### Tutoriels Vidéo
- [Installation LeRobot](https://www.youtube.com/watch?v=...)
- [Calibration SO-ARM](https://www.youtube.com/watch?v=...)
- [Imitation Learning Demo](https://www.youtube.com/watch?v=...)

### Communauté
- [Discord LeRobot](https://discord.gg/lerobot)
- [Forum HuggingFace](https://discuss.huggingface.co/c/lerobot)

## 👥 Contributeurs

- **Yanko Michel pour le Service Ecoles Médias (SEM)** - Genève
- **Opus 4.1 de Claude AI** - Développement et tests

## 📝 Licence

![Licence Creative Commons](https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png)

Cette œuvre est mise à disposition selon les termes de la [Licence Creative Commons Attribution - Pas d'Utilisation Commerciale - Partage dans les Mêmes Conditions 4.0 International](http://creativecommons.org/licenses/by-nc-sa/4.0/).

### Vous êtes autorisé à :
- **Partager** — copier, distribuer et communiquer le matériel par tous moyens et sous tous formats
- **Adapter** — remixer, transformer et créer à partir du matériel

### Selon les conditions suivantes :
- **Attribution** — Vous devez créditer l'Œuvre, intégrer un lien vers la licence et indiquer si des modifications ont été effectuées
- **Pas d'Utilisation Commerciale** — Vous n'êtes pas autorisé à faire un usage commercial de cette Œuvre
- **Partage dans les Mêmes Conditions** — Si vous transformez ou créez à partir du matériel, vous devez diffuser vos contributions sous la même licence

---

**Note :** Ce projet est en développement actif. Les phases 5-10 seront documentées au fur et à mesure de leur finalisation.

**28.11.2024**
