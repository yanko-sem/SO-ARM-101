# SO-ARM 101 - Projet Robotique Éducative

Système complet pour l'apprentissage de la robotique avec les bras SO-ARM 101. Développé par le Service Écoles-Médias (SEM) du Département de l'Instruction Publique (DIP) de Genève en Suisse.

## 🎯 Objectif du Projet

Former un robot à effectuer des tâches de manipulation d'objets par apprentissage par démonstration (Imitation Learning) en utilisant le système LeRobot et les bras robotiques SO-ARM 101.

## 📋 Vue d'Ensemble des Phases

### ✅ Phases Complétées (Guides disponibles)
- **Phase 1** : Installation de l'environnement LeRobot
- **Phase 2** : Configuration des servos (IDs et ratios)
- **Phase 3** : Calibration des limites de mouvement
- **Phase 4** : Tests et contrôle manuel
- **Phase 5** : Téléopération (Leader contrôle Follower)
- **Phase 6** : Installation et configuration des caméras
- **Phase 7** : Enregistrement de dataset pour l'apprentissage par imitation (2 caméras)
- **Phase 8** : Consolidation du dataset et visualisation
- **Phase 9** : Entraînement du modèle ACT (Action Chunking Transformers)

### 🚀 Phases à Venir
- Phase 10 : Déploiement et test autonome

## 🔧 Configuration Matérielle

### Matériel Requis
- 2× Bras SO-ARM 101 (Leader + Follower)
- 2× Adaptateurs USB Feetech
- 2× Alimentations (5V ou 12V selon kit)
- 2× Caméras USB (cam_top + cam_follower)
- 1× PC avec Ubuntu 22.04+ et GPU NVIDIA (recommandé pour l'entraînement)

### Configuration des Servos
**Leader** (Bras de contrôle)
- Servos 1,3 : Ratio 1:191 (C044)
- Servo 2 : Ratio 1:345 (C001)
- Servos 4,5,6 : Ratio 1:147 (C046)

**Follower** (Bras suiveur)
- Tous les servos : Ratio 1:345 (identiques)

## 📚 Guide d'Utilisation par Phase

### Phase 1 : Installation LeRobot
```bash
# Suivre le guide complet SEM_SO101_Phase1.md
# Points clés : Python 3.10, PyTorch, Dynamixel SDK
# Permissions USB : sudo usermod -a -G dialout $USER
# Permissions caméras : sudo usermod -a -G video $USER
```

### Phase 2 : Configuration des Servos
```bash
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_1_configure.py

# Configure chaque servo avec son ID (1-6)
# Un servo à la fois, test de mouvement inclus
```

### Phase 3 : Calibration
```bash
python SEM_so101_2_calibrate.py

# Définit les limites min/max de chaque servo
# Sauvegarde automatique dans ~/lerobot/calibration/
```

### Phase 4 : Test et Contrôle Manuel
```bash
# Monitoring temps réel
python SEM_so101_3_monitor.py

# Contrôle manuel (script unifié Leader/Follower)
python SEM_so101_4_control.py
```

### Phase 5 : Téléopération
```bash
# Configuration COPIE/MIROIR par servo
python SEM_so101_5_config_teleoperation.py

# Contrôle simultané Leader → Follower
python SEM_so101_6_teleoperation.py
```

### Phase 6 : Caméras
```bash
# Téléopération avec retour vidéo
python SEM_so101_7_teleoperation_camera.py
```

### Phase 7 : Enregistrement de Dataset
```bash
# Enregistrement avec 2 caméras (cam_top + cam_follower)
python SEM_so101_8_record_dataset.py

# Tâche : Prendre un cube et le déposer dans une boîte
# 5 positions × 10 épisodes = 50 démonstrations
# Format de sortie : LeRobotDataset v2.1
```

### Phase 8 : Consolidation et Visualisation
```bash
# Fusionner les 5 positions en un dataset unifié
python SEM_so101_9_consolidate_dataset.py

# Vérifier et visualiser le dataset
python SEM_so101_10_visualize_dataset.py
```

### Phase 9 : Entraînement du modèle ACT
```bash
# Lancer l'entraînement (3 profils disponibles)
python SEM_so101_11_train.py

# Profils : Rapide (30min), Standard (4-6h), Intensif (8-12h)
# GPU NVIDIA requis (Quadro RTX 4000 ou équivalent)
```

## 📁 Structure Complète des Fichiers

```
~/lerobot/Scripts_SEM/                 (après git clone)
├── scripts/
│   ├── SEM_so101_1_configure.py
│   ├── SEM_so101_2_calibrate.py
│   ├── SEM_so101_3_monitor.py
│   ├── SEM_so101_4_control.py
│   ├── SEM_so101_5_config_teleoperation.py
│   ├── SEM_so101_6_teleoperation.py
│   ├── SEM_so101_7_teleoperation_camera.py
│   ├── SEM_so101_8_record_dataset.py
│   ├── SEM_so101_9_dataset.py
│   ├── SEM_so101_10_visualize_dataset.py
│   ├── SEM_so101_11_train.py
│   └── README.md
├── docs/
│   ├── SEM_SO101_Phase1.md
│   ├── SEM_SO101_Phase2.md
│   ├── SEM_SO101_Phase3.md
│   ├── SEM_SO101_Phase4.md
│   ├── SEM_SO101_Phase5.md
│   ├── SEM_SO101_Phase6.md
│   ├── SEM_SO101_Phase7.md
│   └── README.md
└── README.md
```

**Note :** Le dossier `~/lerobot/calibration/` sera créé automatiquement lors de l'utilisation du script 2 avec les fichiers `leader_calibration.json` et `follower_calibration.json`.

## 🔧 Dépannage

| Problème | Solution |
|----------|----------|
| Port USB non détecté | Vérifier le groupe `dialout` (voir Phase 1) |
| Servo ne répond pas | Vérifier alimentation |
| Calibration perdue | Relancer script 2 |
| Mouvement brusque | Activer mode précis (P) |
| Import error | `conda activate lerobot` |
| Script ne démarre pas | Vérifier environnement Python 3.10 |
| Caméra non détectée | `sudo usermod -a -G video $USER` |
| Vidéos vides | Vérifier `ffmpeg -version` |

## 📊 Spécifications Techniques

### Servos STS3215
- Protocole : Dynamixel v1.0
- Baudrate : 1,000,000 bps
- Plage : 0-4095 (0°-360°)
- Centre : 2048
- Couple : 15 kg.cm

### Performances
- Fréquence contrôle : 30-50 Hz
- Mouvements fluides : 100 steps
- Latence téléopération : < 50ms

### Caméras (Phase 7)
- Résolution : 640 × 360 pixels (16:9)
- FPS : 30 images/seconde
- Format vidéo : MP4

## 🌐 Ressources

### Documentation
- [LeRobot GitHub](https://github.com/huggingface/lerobot)
- [SO-ARM Wiki](https://wiki.seeedstudio.com/guide_so-arm_100)
- [Feetech Robotics](https://www.feetechrc.com/)

## 👥 Contributeurs

- **Yanko Michel** - Service Écoles-Médias (SEM) - Genève
- **Claude AI Opus 4.6** - Assistant développement

## 📝 Licence

![Licence Creative Commons](https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png)

Cette œuvre est mise à disposition selon les termes de la Licence Creative Commons Attribution - Pas d'Utilisation Commerciale - Partage dans les Mêmes Conditions 4.0 International.

**Vous êtes autorisé à :**
- Partager — copier, distribuer et communiquer le matériel
- Adapter — remixer, transformer et créer à partir du matériel

**Selon les conditions suivantes :**
- Attribution — Créditer l'œuvre et indiquer les modifications
- Pas d'Utilisation Commerciale
- Partage dans les Mêmes Conditions

---

*Note : Ce projet est en développement actif. La phase 10 sera documentée lors de sa finalisation.*

**Dernière mise à jour : 24.04.2026**
