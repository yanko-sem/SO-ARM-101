# SO-ARM 101 - Projet Robotique Éducative

Système complet pour l'apprentissage de la robotique avec les bras SO-ARM 101. Développé par le Service Ecoles Médias (SEM) du Département de l'Instruction Publique (DIP) de Genève en Suisse.

## 🎯 Objectif du Projet

Former un robot à effectuer des tâches de manipulation d'objets par apprentissage par démonstration (Imitation Learning) en utilisant le système LeRobot et les bras robotiques SO-ARM 101.

## 📋 Vue d'Ensemble des Phases

### ✅ Phases Complétées (Guides disponibles)
- **Phase 1** : Installation de l'environnement LeRobot
- **Phase 2** : Configuration des servos (IDs et ratios)
- **Phase 3** : Calibration des limites de mouvement
- **Phase 4** : Tests et contrôle manuel
- **Phase 5** : Téléopération (Leader contrôle Follower) - Scripts 5 et 6 disponibles
- **Phase 6** : Installation et configuration des caméras
- **Phase 7** : Enregistrement de dataset pour l'apprentissage par imitation (2 caméras)

### 🚀 Phases à Venir
- Phase 8 : Configuration du système d'IA (ACT - Action Chunking Transformers)
- Phase 9 : Entraînement du modèle
- Phase 10 : Déploiement et test autonome

## 🔧 Configuration Matérielle

### Matériel Requis
- 2x Bras SO-ARM 101 (Leader + Follower)
- 2x Adaptateurs USB Feetech
- 2x Alimentations 12V 3A
- 2x Caméras USB (cam_top + cam_follower)
- 1x PC avec Ubuntu 22.04+

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
# Suivre le guide complet SEM_SOARM_101_Phase1.pdf
# Points clés : Python 3.10, PyTorch, Dynamixel SDK
```

### Phase 2 : Configuration des Servos
```bash
cd ~/lerobot/Docs_SEM/scripts
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

# Contrôle manuel
python SEM_so101_4_control.py
...

### Phase 5 : Téléopération
```bash
# Configuration de la téléopération
python SEM_so101_5_config_teleoperation.py

# Contrôle simultané Leader → Follower
python SEM_so101_6_teleoperation.py

# Modes disponibles :
# MIROIR : Mouvement inversé
# COPIE : Mouvement identique
```

### Phase 7 : Enregistrement de Dataset
```bash
# Enregistrement avec 2 caméras (cam_top + cam_follower)
python SEM_so101_8_record_dataset.py

# Tâche : Prendre un cube et le déposer dans une boîte
# 5 positions × 10 épisodes = 50 démonstrations
# Format de sortie : LeRobotDataset v2.1
```

## 📁 Structure Complète des Fichiers

```
~/lerobot/Docs_SEM/                    (après git clone)
├── scripts/
│   ├── SEM_so101_1_configure.py
│   ├── SEM_so101_2_calibrate.py
│   ├── SEM_so101_3_monitor.py
│   ├── SEM_so101_4_control.py
│   ├── SEM_so101_5_config_teleoperation.py
│   ├── SEM_so101_6_teleoperation.py
│   ├── SEM_so101_7_teleoperation_camera.py
│   ├── SEM_so101_8_record_dataset.py
│   └── README.md
├── docs/
│   ├── SEM_SOARM_101_Phase1.pdf
│   ├── SEM_SOARM_101_Phase2.pdf
│   ├── SEM_SOARM_101_Phase3.pdf
│   ├── SEM_SOARM_101_Phase4.pdf
│   ├── SEM_SOARM_101_Phase5.pdf
│   ├── SEM_SOARM_101_Phase6.pdf
│   ├── SEM_SOARM_101_Phase7.pdf
│   └── README.md
└── README.md
```

**Note :** Le dossier `~/lerobot/calibration/` sera créé automatiquement lors de l'utilisation du script 2 avec les fichiers `leader_calibration.json` et `follower_calibration.json`.

## 🔧 Dépannage

| Problème | Solution |
|----------|----------|
| Port USB non détecté | `sudo chmod 666 /dev/ttyACM*` |
| Servo ne répond pas | Vérifier alimentation 12V |
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
- Résolution : 640 × 480 pixels
- FPS : 30 images/seconde
- Format vidéo : MP4 (H.264)

## 🌐 Ressources

### Documentation
- [LeRobot GitHub](https://github.com/huggingface/lerobot)
- [SO-ARM Wiki](https://wiki.seeedstudio.com/guide_so-arm_100)
- [Feetech Robotics](https://www.feetechrc.com/)

## 👥 Contributeurs

- **Yanko Michel** - Service Ecoles Médias (SEM) - Genève
- **Claude AI Opus 4.5** - Assistant développement

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

*Note : Ce projet est en développement actif. Les phases 8-10 seront documentées au fur et à mesure de leur finalisation.*

**Dernière mise à jour : 09.01.2026**
