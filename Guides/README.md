# Guides SO-ARM 101

Documentation complète pour l'installation, configuration et utilisation des robots SO-ARM 101.

## 📚 Guides Disponibles

### 📘 Phase 1 — Installation LeRobot

Installation complète de l'environnement de développement.

- Installation Miniconda
- Configuration Python 3.10
- Installation LeRobot et Dynamixel SDK
- Installation ffmpeg (conda + système)
- Permissions USB et caméras (groupes `dialout` et `video`)
- Configuration PyTorch (CPU ou GPU)
- Tests et vérifications

**Points clés :**
- Environnement conda `lerobot`
- Support servos Feetech STS3215
- Compatible Ubuntu 22.04+

**Scripts utilisés :**
- Aucun (phase d'installation)


### 📙 Phase 2 — Configuration des Servos

Configuration individuelle de chaque servo avec son ID.

- Attribution des IDs (1-6)
- Configuration des ratios spécifiques
- Tests de mouvement
- Un servo à la fois

**Ratios Leader :**
- Servos 1, 3 : 1:191 (C044)
- Servo 2 : 1:345 (C001)
- Servos 4, 5, 6 : 1:147 (C046)

**Ratios Follower :**
- Tous : 1:345

**Script utilisé :**
- `SEM_so101_1_configure.py`


### 📗 Phase 3 — Calibration

Définition des limites de mouvement pour chaque servo.

- Calibration manuelle des positions min/max
- Sauvegarde automatique après chaque servo
- Centrage en douceur (courbe sinusoïdale)
- Validation des amplitudes

**Scripts utilisés :**
- `SEM_so101_2_calibrate.py`
- `SEM_so101_3_monitor.py`

**Fichiers générés :**
- `~/lerobot/calibration/leader_calibration.json`
- `~/lerobot/calibration/follower_calibration.json`


### 📕 Phase 4 — Tests et Contrôle

Validation et contrôle manuel des robots avec un script unifié.

- Choix Leader ou Follower au lancement
- Contrôle par clavier (flèches + touches)
- Positions prédéfinies : Initiale (I), Attraper (A), Repos (R)
- Mode précis pour ajustements fins (P)
- Arrêt d'urgence (X)

**Script utilisé :**
- `SEM_so101_4_control.py`


### 📘 Phase 5 — Téléopération

Contrôle du Follower par le Leader en temps réel.

- Configuration COPIE/MIROIR par servo (script 5)
- Test interactif de chaque mode avant validation
- Téléopération temps réel (script 6)
- Basculement côte à côte ↔ face à face en temps réel

**Scripts utilisés :**
- `SEM_so101_5_config_teleoperation.py` — Configuration par servo
- `SEM_so101_6_teleoperation.py` — Téléopération temps réel

**Fichiers générés :**
- `~/lerobot/calibration/teleoperation_config_cote.json`
- `~/lerobot/calibration/teleoperation_config_face.json`


### 📙 Phase 6 — Caméras

Installation et configuration du système de vision.

- Installation physique des caméras USB
- Correction OpenCV (headless → GUI)
- Test de capture avec LeRobot
- Création du masque de zone utile de la caméra globale (`camera_mask.json`), réutilisé aux Phases 7 et 10
- Téléopération avec retour caméra en temps réel

**Script utilisé :**
- `SEM_so101_7_teleoperation_camera.py`


### 📗 Phase 7 — Enregistrement de Dataset

Capture de démonstrations pour l'apprentissage par imitation.

- 2 caméras simultanées (cam_top + cam_follower)
- Identification caméras par touches G (Globale) et P (Pince)
- **Contrôle image des deux caméras** : exposition (et balance des blancs) réglée automatiquement puis figée au démarrage, puis contrôle de l'image (lumière) avant chaque bloc
- Format LeRobotDataset v2.1
- 5 positions × 10 épisodes = 50 démonstrations
- Tâche : prendre un prisme hexagonal (désigné « cube » dans le dataset) et le déposer dans une boîte

**Scripts utilisés :**
- `SEM_so101_8_record_dataset.py` — Enregistrement
- `SEM_so101_camera_auto.py` — Réglage caméra (exposition auto puis figée) et contrôle image


### 📕 Phase 8 — Consolidation et Visualisation

Préparation du dataset pour l'entraînement.

- Fusion des 5 dossiers de positions en un dataset unifié
- Normalisation des timestamps (fréquence régulière à 30 FPS)
- Génération des statistiques par épisode
- Conversion des vidéos en H.264 (compatibilité navigateur)
- Visualisation interactive dans le navigateur via l'outil LeRobot

**Scripts utilisés :**
- `SEM_so101_9_dataset.py` — Préparation complète (consolidation, métadonnées, conversion H.264, vérification, visualisation)

**Fichiers générés :**
- `~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/`


### 📘 Phase 9 — Entraînement du modèle ACT

Formation du modèle d'intelligence artificielle sur les démonstrations.

- Modèle ACT (Action Chunking with Transformers), entre 50 et 80 millions de paramètres selon la configuration
- 4 profils d'entraînement : Rapide (~30min), Intermédiaire (~2-3h), Standard (~4-6h), Intensif (~8-12h)
- Optimisé pour GPU NVIDIA (Quadro RTX 4000, batch size 4)
- Sauvegarde de checkpoints régulière
- Reprise d'entraînement interrompu

**Script utilisé :**
- `SEM_so101_10_train.py`

**Fichiers générés :**
- `~/lerobot/outputs/train/act_so101_pick_place/checkpoints/`


### 📙 Phase 10 — Déploiement Autonome

Inférence autonome : le modèle ACT pilote le robot sans opérateur.

- Sélection d'un checkpoint entraîné
- Inférence en boucle à ~30 images/seconde
- Bras Follower seul (le Leader n'est pas nécessaire — le modèle remplace l'opérateur)
- Masque réappliqué + **contrôle image des deux caméras** (exposition auto puis figée, adaptée à la lumière de la salle, puis contrôle de l'image)
- Contrôles : Pause (P), fin d'essai (R), nouvel essai (Entrée), quitter (Q)
- Arrêt d'urgence (CTRL+C)

**Scripts utilisés :**
- `SEM_so101_11_deploy.py` — Déploiement
- `SEM_so101_camera_auto.py` — Réglage caméra (exposition auto puis figée) et contrôle image


## 🔧 Matériel Requis

- 2× Bras SO-ARM 101 (Leader + Follower)
- 2× Adaptateurs USB Feetech
- 2× Alimentations (5V ou 12V selon kit)
- 1× PC Ubuntu 22.04+ ; GPU NVIDIA fortement recommandé pour l'entraînement, CPU possible mais beaucoup plus lent
- 2× Caméras USB (à partir de la Phase 6)


## 📌 Notes Importantes

1. **Suivre l'ordre :** Les phases sont séquentielles
2. **Permissions USB :** Chaque utilisateur doit être dans les groupes `dialout` et `video` (voir Phase 1, Étape 6)
3. **Environnement :** Toujours activer avec `conda activate lerobot`
4. **Sauvegardes :** Garder les fichiers de calibration et de configuration
5. **Un robot à la fois :** Pour les phases 2-3
6. **Alimentation :** Vérifier les LEDs avant utilisation
7. **Caméras :** Brancher sur des ports USB différents pour éviter les conflits de bande passante
8. **GPU :** fortement recommandé pour la Phase 9 (entraînement) ; CPU possible mais beaucoup plus lent

---

Service Écoles-Médias — DIP Genève
Dernière mise à jour : 01.07.2026
