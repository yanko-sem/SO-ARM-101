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


### 📗 Phase 3 — Calibration

Définition des limites de mouvement pour chaque servo.

- Calibration manuelle des positions min/max
- Sauvegarde automatique après chaque servo
- Centrage en douceur (courbe sinusoïdale)
- Validation des amplitudes

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
- Téléopération avec retour caméra en temps réel

**Script utilisé :**
- `SEM_so101_7_teleoperation_camera.py`


### 📗 Phase 7 — Enregistrement de Dataset

Capture de démonstrations pour l'apprentissage par imitation.

- 2 caméras simultanées (cam_top + cam_follower)
- Identification caméras par touches G (Globale) et P (Pince)
- Format LeRobotDataset v2.1
- 5 positions × 10 épisodes = 50 démonstrations
- Tâche : prendre un cube et le déposer dans une boîte

**Script utilisé :**
- `SEM_so101_8_record_dataset.py`


## 🚀 Guides à Venir

- **📕 Phase 8 — Configuration IA** : Mise en place du système ACT (Action Chunking Transformers)
- **📘 Phase 9 — Entraînement** : Formation du modèle d'IA sur les démonstrations
- **📙 Phase 10 — Autonomie** : Déploiement du robot en mode autonome


## 🔧 Matériel Requis

- 2× Bras SO-ARM 101 (Leader + Follower)
- 2× Adaptateurs USB Feetech
- 2× Alimentations (5V ou 12V selon kit)
- 1× PC Ubuntu 22.04+
- 2× Caméras USB (à partir de la Phase 6)


## 📋 Workflow Recommandé

```
Phase 1 (Installation)
  ↓
Phase 2 (Configuration servos)
  ↓
Phase 3 (Calibration)
  ↓
Phase 4 (Tests et contrôle)
  ↓
Phase 5 (Téléopération)
  ↓
Phase 6 (Caméras)
  ↓
Phase 7 (Enregistrement dataset)
  ↓
Phase 8+ (IA / Entraînement / Autonomie)
```


## 📌 Notes Importantes

1. **Suivre l'ordre :** Les phases sont séquentielles
2. **Permissions USB :** Chaque utilisateur doit être dans les groupes `dialout` et `video` (voir Phase 1, Étape 6)
3. **Environnement :** Toujours activer avec `conda activate lerobot`
4. **Sauvegardes :** Garder les fichiers de calibration et de configuration
5. **Un robot à la fois :** Pour les phases 2-3
6. **Alimentation :** Vérifier les LEDs avant utilisation
7. **Caméras :** Brancher sur des ports USB différents pour éviter les conflits de bande passante

---

Service Écoles-Médias — DIP Genève
Dernière mise à jour : 12.03.2026
