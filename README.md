# 🤖 SO-ARM 101 — Robotique éducative, IA & apprentissage par imitation

<p align="center">
  <strong>Construisez, téléopérez, entraînez et déployez un robot capable d’apprendre un geste par démonstration.</strong>
</p>

<p align="center">
  <a href="#-parcours-des-scripts-principaux">Parcours des scripts principaux</a> •
  <a href="#-guide-dutilisation-par-phase">Phases du projet</a> •
  <a href="#-structure-complète-des-fichiers">Structure</a> •
  <a href="#-ressources">Ressources</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10-blue">
  <img alt="Ubuntu" src="https://img.shields.io/badge/Ubuntu-22.04%20%7C%2024.04-orange">
  <img alt="LeRobot" src="https://img.shields.io/badge/LeRobot-Imitation%20Learning-purple">
  <img alt="License" src="https://img.shields.io/badge/Licence-CC%20BY--NC--SA%204.0-lightgrey">
</p>

> 🇫🇷 **Français** | 🇬🇧 [English](README_EN.md)

---

## 🎯 Objectif du Projet

**SO-ARM 101 - Projet Robotique Éducative** est une chaîne complète, reproductible et pédagogique pour explorer la robotique moderne avec l’IA.

Le projet permet de former un bras robotique à réaliser une tâche de manipulation d’objet par **apprentissage par démonstration** (*Imitation Learning*) : un humain guide un bras **Leader**, un bras **Follower** reproduit le geste, les démonstrations sont enregistrées avec deux caméras, puis un modèle ACT (*Action Chunking Transformers*) apprend à exécuter la tâche de manière autonome.

Développé par le **Service Écoles-Médias (SEM)** du **Département de l’Instruction Publique (DIP) de Genève**, ce projet vise à rendre l’IA robotique concrète, observable et expérimentable dans un cadre éducatif.

### Pourquoi ce projet est intéressant ?

- 🎓 **Pensé pour l’éducation** : une progression claire, phase par phase, adaptée à l’enseignement.
- 🛠️ **DIY et clé en main** : du montage logiciel au déploiement autonome.
- 🤖 **IA concrète** : imitation learning, dataset, entraînement et inférence sur un vrai robot.
- 📷 **Deux caméras** : vision globale + vision embarquée sur la pince.
- 🔁 **Reproductible** : scripts, guides, calibration, masques, **référence visuelle des caméras** et checkpoints.
- 🚀 **Moderne** : basé sur LeRobot, PyTorch, Dynamixel SDK et ACT.

---

## 👥 À qui s’adresse ce projet ?

| Public | Ce que le projet apporte |
| :--- | :--- |
| **Enseignants** | Une séquence complète pour enseigner robotique, programmation, IA et démarche expérimentale. |
| **Étudiants / élèves avancés** | Un projet concret pour comprendre la chaîne complète : capteurs → données → modèle → action. |
| **Institutions éducatives** | Une base structurée pour créer des ateliers, démonstrateurs, formations ou projets interdisciplinaires. |
| **Makers / développeurs** | Un pipeline robotique open source à adapter, améliorer ou étendre. |

---

## 🧠 Ce que vous allez construire

À la fin du parcours, vous disposez d’un système capable de :

1. configurer et tester les servomoteurs ;
2. calibrer les limites mécaniques des deux bras ;
3. téléopérer un bras Follower avec un bras Leader ;
4. filmer la scène avec deux caméras ;
5. enregistrer un dataset de démonstrations ;
6. consolider et vérifier les données ;
7. entraîner un modèle ACT ;
8. déployer le modèle pour que le robot agisse seul.

La tâche de référence est volontairement simple et pédagogique : **prendre un prisme hexagonal (désigné « cube » dans le dataset) à l’une de cinq positions et le déposer dans une boîte**.

---

## 📋 Vue d'Ensemble des Phases

### ✅ Pipeline complet disponible

- **Phase 1** : Installation complète de l'environnement LeRobot
- **Phase 2** : Configuration des servos (IDs, test, centrage et montage)
- **Phase 3** : Calibration des limites de mouvement
- **Phase 4** : Tests et contrôle manuel
- **Phase 5** : Téléopération Leader → Follower (configuration + téléopération temps réel)
- **Phase 6** : Téléopération avec caméras et définition du masque de zone utile
- **Phase 7** : Enregistrement de dataset pour l'apprentissage par imitation (2 caméras)
- **Phase 8** : Consolidation et vérification du dataset (statistiques, conversion vidéo, visualisation)
- **Phase 9** : Entraînement du modèle ACT (*Action Chunking Transformers*)
- **Phase 10** : Déploiement autonome du modèle entraîné

### 🚀 Extensions possibles

- scénarios pédagogiques en classe ;
- nouvelles tâches de manipulation ;
- amélioration du dataset ;
- comparaison de modèles ;
- interface web de pilotage ou de visualisation ;
- version anglaise du projet.

---

## 🔧 Configuration Matérielle

### Matériel Requis

- 2× Bras SO-ARM 101 (**Leader** + **Follower**)
- 2× Adaptateurs USB Feetech ou Waveshare
- 2× Alimentations selon le kit utilisé
- 12× Servos Feetech STS3215
- 2× Caméras USB (`cam_top` + `cam_follower`)
- 1× PC avec Ubuntu 22.04 ou 24.04
- (Optionnel) GPU NVIDIA pour accélérer l'entraînement

### Configuration des Servos

**Leader** — bras de contrôle humain

- Servos 1,3 : Ratio 1:191 (C044)
- Servo 2 : Ratio 1:345 (C001)
- Servos 4,5,6 : Ratio 1:147 (C046)

**Follower** — bras qui apprend et agit

- Tous les servos : Ratio 1:345 (identiques)

---

## ⚡ Parcours des scripts principaux

Cette section donne une vue synthétique de l'ordre général des scripts. Elle ne remplace pas les guides détaillés : chaque phase demande des vérifications matérielles, des choix opérateur et des étapes de sécurité.

```bash
# Activer l'environnement
conda activate lerobot

# Aller dans les scripts SEM
cd ~/lerobot/Scripts_SEM/scripts

# Configurer les servos
python SEM_so101_1_configure.py

# Calibrer les bras
python SEM_so101_2_calibrate.py

# Téléopération avec caméras
python SEM_so101_7_teleoperation_camera.py

# Enregistrer le dataset
python SEM_so101_8_record_dataset.py

# Consolider, vérifier, entraîner, déployer
python SEM_so101_9_dataset.py
python SEM_so101_10_visualize_dataset.py
python SEM_so101_11_train.py
python SEM_so101_12_deploy.py
```

Pour une installation complète et sûre, suivez les guides détaillés dans le dossier `Guides/`.

---

## 📚 Guide d'Utilisation par Phase

> **Note :** les phases pédagogiques regroupent parfois plusieurs scripts. Les numéros de phase ne correspondent donc pas toujours aux numéros des fichiers Python (par exemple, la Phase 8 utilise les scripts 9 et 10).

### Phase 1 : Installation LeRobot

```bash
# Suivre le guide complet : Guides/SEM_SO101_Phase1.md
# Points clés : Python 3.10, PyTorch, Dynamixel SDK, ffmpeg
# Permissions USB : sudo usermod -a -G dialout $USER
# Permissions caméras : sudo usermod -a -G video $USER
# Outils caméra : v4l-utils et guvcview
```

### Phase 2 : Configuration des Servos

```bash
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_1_configure.py

# Configure chaque servo avec son ID (1-6)
# Un servo à la fois, test de mouvement inclus
# Options : T = configurer les 6 servos, B = bloquer, L = libérer, D = détecter le port
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
# Téléopération avec retour vidéo et création du masque de zone utile
python SEM_so101_7_teleoperation_camera.py

# Le masque est partagé avec les phases 7 et 10
# Fichier : ~/lerobot/calibration/camera_mask.json
```

### Phase 7 : Enregistrement de Dataset

```bash
# Enregistrement avec 2 caméras (cam_top + cam_follower)
python SEM_so101_8_record_dataset.py

# Tâche : Prendre un prisme hexagonal (désigné « cube » dans le dataset) et le déposer dans une boîte
# 5 positions × 10 épisodes = 50 démonstrations
# Format de sortie : LeRobotDataset v2.1
# Référence visuelle des deux caméras : menus de référence au démarrage (globale
# puis pince) et contrôle de conformité avant chaque bloc, pour garantir la
# cohérence visuelle du dataset (et avec le déploiement)
```

### Phase 8 : Consolidation et Visualisation

```bash
# Script 9 — fusionner les 5 positions en un dataset unifié
python SEM_so101_9_dataset.py

# Script 10 — vérifier le dataset, générer les statistiques,
# convertir les vidéos en H.264 et visualiser dans le navigateur
python SEM_so101_10_visualize_dataset.py

# Dataset consolidé et vérifié, prêt pour l'entraînement
```

### Phase 9 : Entraînement du modèle ACT

```bash
# Lancer l'entraînement
python SEM_so101_11_train.py

# Le script utilise le dataset consolidé
# Reprise d'entraînement possible depuis un checkpoint existant
# Entraînement CPU possible, GPU NVIDIA recommandé
```

### Phase 10 : Déploiement autonome

```bash
# Déployer le modèle ACT entraîné
python SEM_so101_12_deploy.py

# Le Follower agit de manière autonome à partir des deux caméras
# Masque réappliqué + contrôle des deux caméras vs les références du dataset
# d'entraînement (recalibrage guidé si l'éclairage a dérivé)
# Contrôles : P = pause, R = retour repos + arrêt modèle, Entrée = relance, Q = quitter
```

---

## 📁 Structure Complète des Fichiers

```
/home/prof/lerobot/Scripts_SEM
├── Guides
│   ├── README.md
│   ├── SEM_SO101_Phase1.md
│   ├── SEM_SO101_Phase2.md
│   ├── SEM_SO101_Phase3.md
│   ├── SEM_SO101_Phase4.md
│   ├── SEM_SO101_Phase5.md
│   ├── SEM_SO101_Phase6.md
│   ├── SEM_SO101_Phase7.md
│   ├── SEM_SO101_Phase8.md
│   ├── SEM_SO101_Phase9.md
│   └── SEM_SO101_Phase10.md
├── Hardware
│   └── Modèles 3D (STL) et fichiers matériels
├── README.md
└── scripts
    ├── __pycache__
    ├── SEM_so101_8_camera_config.py
    ├── SEM_so101_camera_reference.py
    ├── SEM_so101_10_visualize_dataset.py
    ├── SEM_so101_11_train.py
    ├── SEM_so101_12_deploy.py
    ├── SEM_so101_1_configure.py
    ├── SEM_so101_2_calibrate.py
    ├── SEM_so101_3_monitor.py
    ├── SEM_so101_4_control.py
    ├── SEM_so101_5_config_teleoperation.py
    ├── SEM_so101_6_teleoperation.py
    ├── SEM_so101_7_teleoperation_camera.py
    ├── SEM_so101_8_record_dataset.py
    ├── SEM_so101_9_dataset.py
    └── Version_26_05_26
```

**Note :** Le dossier `~/lerobot/calibration/` est créé automatiquement par les scripts. Il contient notamment `leader_calibration.json`, `follower_calibration.json`, `repos_position.json`, `camera_mask.json`, `camera_settings.json` et les **références visuelles des caméras** (`camera_reference_cam_top.json`, `camera_reference_cam_follower.json` et leurs fichiers associés).

---

## 🧪 Qualité des données et sécurité

Ce projet ne se limite pas à “faire bouger un robot”. Il met l’accent sur la **qualité du dataset**, car un modèle d’imitation apprend directement à partir des démonstrations.

Les scripts SEM intègrent plusieurs garde-fous :

- cohérence stricte entre enregistrement et déploiement ;
- masque partagé pour la caméra globale ;
- **référence visuelle chiffrée par caméra** : contrôle de conformité avant chaque bloc d'enregistrement et au déploiement (image cohérente avec le dataset, recalibrage guidé si besoin) ;
- verrouillage exposition / balance des blancs / gain ;
- vérification des deux flux caméra ;
- contrôle des lectures et écritures série pendant l’enregistrement ;
- retour repos sécurisé ;
- arrêt d’urgence sans mouvement de retour automatique.

---

## 🔧 Dépannage

| Problème | Solution |
|----------|----------|
| Port USB non détecté | Vérifier le groupe `dialout` (voir Phase 1) |
| Servo ne répond pas | Vérifier alimentation et câbles 3-pins |
| Calibration perdue | Relancer script 2 |
| Mouvement brusque | Vérifier calibration, repos et mode de téléopération |
| Import error | `conda activate lerobot` |
| Script ne démarre pas | Vérifier environnement Python 3.10 |
| Caméra non détectée | Vérifier le groupe `video` et tester avec `v4l2-ctl --list-devices` |
| Réglages caméra impossibles | Vérifier `v4l2-ctl --version` et `guvcview --version` |
| Vidéos vides | Vérifier `ffmpeg -version` et la connexion des deux caméras |
| Dataset incohérent | Vérifier masque, réglages caméra, résolution 640×360 et synchronisation des deux caméras |
| Messages “instant ignoré” fréquents | Vérifier câbles, alimentation et stabilité du bus série |

---

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
- Déploiement autonome : environ 30 Hz

### Caméras (Phases 6, 7 et 10)

- Résolution : 640 × 360 pixels (16:9)
- FPS : 30 images/seconde
- Format vidéo : MP4 puis conversion H.264 si nécessaire
- Caméra globale : `cam_top`
- Caméra pince : `cam_follower`
- Réglages verrouillés : exposition, balance des blancs, gain
- Masque de zone utile appliqué à la caméra globale
- Référence visuelle chiffrée par caméra (contrôle de conformité enregistrement ↔ déploiement, module `SEM_so101_camera_reference.py`)

---

## 🌐 Ressources

### Documentation

- [LeRobot GitHub](https://github.com/huggingface/lerobot)
- [SO-ARM Wiki](https://wiki.seeedstudio.com/guide_so-arm_100)
- [Feetech Robotics](https://www.feetechrc.com/)

### Mots-clés utiles

`SO-ARM 101` · `LeRobot` · `Imitation Learning` · `Action Chunking Transformers` · `ACT` · `Robotique éducative` · `Dataset robotique` · `PyTorch` · `Dynamixel SDK` · `Feetech STS3215`

---

## 🤝 Contribuer

Les contributions sont les bienvenues :

- amélioration des guides ;
- correction de bugs ;
- nouveaux scénarios pédagogiques ;
- amélioration des scripts ;
- traduction anglaise ;
- ajout de visuels, schémas ou vidéos ;
- adaptation à d’autres tâches robotiques.

---

## 👥 Contributeurs

- Yanko Michel — Service Écoles-Médias (SEM), Genève
- Claude AI — Assistant développement
- ChatGPT — Assistance à l’audit, à la documentation et à la structuration


---

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

<p align="center">
  <strong>Un projet pour rendre la robotique intelligente visible, manipulable et enseignable.</strong>
</p>

<p align="center">
  Service Écoles-Médias (SEM) — Département de l’Instruction Publique (DIP), Genève
</p>

**Dernière mise à jour : 15.06.2026**
