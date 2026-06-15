# Scripts SEM pour SO-ARM 101

Collection de scripts Python pour la configuration, calibration et contrôle des robots SO-ARM 101.

## 🔧 Prérequis

```bash
# Environnement conda activé
conda activate lerobot

# Permissions USB (configuré une fois en Phase 1, Étape 6)
# L'utilisateur doit être dans les groupes dialout et video
groups | grep dialout
groups | grep video

# Outils vidéo nécessaires pour le verrouillage matériel des caméras (installé en Phase 1, Étape 7)
sudo apt update && sudo apt install v4l-utils guvcview

```

## 📋 Liste des Scripts

### 1️⃣ SEM_so101_1_configure.py

Configuration initiale des servos avec leurs IDs (1-6) pendant le montage.

* Configure un servo à la fois
* Test de mouvement automatique
* Centre et bloque pour le montage
* Options B (bloquer) et L (libérer) dans le menu

**Utilisation :**

```bash
python SEM_so101_1_configure.py

```

### 2️⃣ SEM_so101_2_calibrate.py

Calibration des limites de mouvement (min/max) pour chaque servo.

* Sauvegarde automatique après chaque servo
* Mode manuel : bougez le bras aux limites physiques
* Mouvement fluide de centrage (courbe sinusoïdale)

**Utilisation :**

```bash
python SEM_so101_2_calibrate.py
# Choisir L (Leader) ou F (Follower)
# Option T pour calibrer tous les servos

```

### 3️⃣ SEM_so101_3_monitor.py

Monitoring temps réel des positions des servos.

* Affichage en tableau avec barres graphiques
* Servos libres (torque off) pour manipulation
* Utile pour vérifier la position de repos ou débugger

**Utilisation :**

```bash
python SEM_so101_3_monitor.py

```

### 4️⃣ SEM_so101_4_control.py

Contrôle manuel (clavier) d'un robot.

* Mode normal (pas de 50) ou précis (pas de 10)
* Mouvements fluides interpolés
* Arrêt d'urgence (touche X)

**Utilisation :**

```bash
python SEM_so101_4_control.py

```

### 5️⃣ SEM_so101_5_config_teleoperation.py

Configuration du comportement de chaque servo (Copie ou Miroir).

* Indispensable pour l'installation "Face à face" (miroir sur la base)
* Sauvegarde la configuration pour la téléopération
* Inclut un test de centrage parallèle et un retour à la position de repos

**Utilisation :**

```bash
python SEM_so101_5_config_teleoperation.py

```

### 6️⃣ SEM_so101_6_teleoperation.py

Téléopération maître-esclave (Leader → Follower) pure.

* Mouvement fluide et synchronisé à haute fréquence
* Mappage intelligent respectant les calibrations de chaque robot
* Gestion propre du positionnement initial et final (séquences sûres)

**Utilisation :**

```bash
python SEM_so101_6_teleoperation.py

```

### 7️⃣ SEM_so101_7_teleoperation_camera.py

Téléopération maître-esclave avec affichage vidéo (1 caméra).

* Permet de vérifier le flux vidéo et de cadrer la zone de travail
* Dessin interactif (souris) pour créer un masque de la zone utile (polygone)
* Masque sauvegardé pour isoler la zone d'intérêt lors de l'enregistrement

**Utilisation :**

```bash
python SEM_so101_7_teleoperation_camera.py

```

### 📸 Module Utilitaire : SEM_so101_8_camera_config.py

*Ce module n'est pas une étape numérotée, mais une dépendance critique des scripts 8 et 12* (repli sur l'ancien nom `SEM_8_camera_config.py` s'il est présent).
Fige les réglages matériels (Exposition, Balance des blancs, Gain) via `v4l2-ctl` et `guvcview`.

* Garantit la cohérence visuelle stricte entre l'enregistrement (dataset) et le déploiement (inférence).
* Tolérant aux pannes (ignore les paramètres illisibles, évite les valeurs par défaut destructrices).

**Utilisation autonome (Optionnel) :**

```bash
python SEM_so101_8_camera_config.py --show
python SEM_so101_8_camera_config.py --capture cam_top /dev/video0

```

### 📷 Module Utilitaire : SEM_so101_camera_reference.py

*Dépendance critique des scripts 8, 9 et 12.* Remplace le réglage caméra « à l'œil » par une **référence visuelle chiffrée** par caméra (zones de mesure, score de conformité 🟢/🟠/🔴, recalibrage guidé), pour que l'image reste cohérente entre l'enregistrement et le déploiement.

* **Multi-caméra** : un profil par caméra (globale et pince), fichiers de référence séparés.
* Lançable **seul** pour préparer/vérifier une référence (menu : zones, mesure, création de référence, diagnostic, recalibrage) ; intégré aux scripts 8 et 12 pour le contrôle automatique.

**Utilisation autonome (Optionnel) :**

```bash
python SEM_so101_camera_reference.py
# Choisir G (globale) ou P (pince), puis suivre le menu

```

### 8️⃣ SEM_so101_8_record_dataset.py

Enregistrement du dataset (2 caméras : *cam_top* et *cam_follower*) pour l'apprentissage par imitation.

* **Référence visuelle des deux caméras** (via `SEM_so101_camera_reference`) : menus de référence au démarrage (globale puis pince) et contrôle de conformité avant chaque bloc — l'enregistrement n'est autorisé que si les deux caméras sont conformes.
* Verrouillage matériel des caméras (via `SEM_so101_8_camera_config`) ; applique le masque vidéo généré au script 7.
* Flux réordonné : robots identifiés et mis au repos **avant** la préparation des caméras (la vue de la pince dépend de la pose du bras).
* Architecture robuste contre les micro-coupures USB (cache des positions) et la saturation CPU.
* Sauvegarde au format LeRobotDataset v2.1.

**Utilisation :**

```bash
python SEM_so101_8_record_dataset.py

```

### 9️⃣ SEM_so101_9_dataset.py

Consolidation des données enregistrées.

* Fusionne les dossiers des différentes positions (1 à 5) en un seul dataset unifié.
* Vérifie l'intégrité globale et l'inventaire des frames/vidéos.
* Copie les **références visuelles des deux caméras** et le journal dans le `meta/` du dataset (traçabilité : le déploiement s'y rattache).

**Utilisation :**

```bash
python SEM_so101_9_dataset.py

```

### 🔟 SEM_so101_10_visualize_dataset.py

Vérification technique et visualisation du dataset consolidé.

* Génère les statistiques (`episodes_stats.jsonl`) requises par LeRobot.
* Lance l'outil officiel LeRobot dans le navigateur pour rejouer les épisodes.

**Utilisation :**

```bash
python SEM_so101_10_visualize_dataset.py

```

### 1️⃣1️⃣ SEM_so101_11_train.py

Entraînement de la politique ACT sur le dataset consolidé (optimisé Quadro RTX 4000).

* 3 profils d'entraînement : Rapide (test), Standard (recommandé), Intensif.
* Protège la session contre la mise en veille de l'OS (`systemd-inhibit`).
* Gestion sécurisée de la reprise d'entraînement basée sur le fichier `train_config.json` du checkpoint.

**Utilisation :**

```bash
python SEM_so101_11_train.py

```

### 1️⃣2️⃣ SEM_so101_12_deploy.py

Déploiement du modèle (Inférence autonome).

* Le robot agit seul basé sur le flux des 2 caméras à ~30 Hz.
* **Contrôle des deux caméras vs les références du dataset d'entraînement** (retrouvées via le checkpoint) au démarrage : recalibrage guidé si l'éclairage a dérivé, fail-closed si le verrouillage échoue — évite le "Distribution Shift". Mode LEGACY si le dataset est antérieur au système.
* Robot Follower mis au repos **avant** le contrôle caméra ; masque réappliqué.
* Architecture défensive : tolérance aux pertes de paquets série (maintien de la dernière position connue).

**Utilisation :**

```bash
python SEM_so101_12_deploy.py

```

## ⌨️ Commandes Utiles

**Pendant l'identification des caméras (Scripts 8 & 12) :**

| Touche | Action |
| --- | --- |
| G + Entrée | Identifier la caméra comme GLOBALE (*cam_top*) |
| P + Entrée | Identifier la caméra comme PINCE (*cam_follower*) |
| Q + Entrée | Passer la caméra |

**Menu d'enregistrement (Script 8) :** 1 = instructions, 2 = test rapide (2 épisodes), 3 = enregistrer 10 épisodes pour une position, 4 = visualiser, 5 = effacer, 6 = repositionner au repos, Q = quitter. Un **contrôle des deux caméras** précède chaque bloc (test rapide inclus).

**Pendant un épisode (Script 8) :**

| Touche | Action |
| --- | --- |
| T | Terminer l'épisode avec succès (fige le robot, sauvegarde, retour repos) |
| A | Annuler l'épisode en cours |
| S | Stopper la session (retour au menu) |

## 📁 Fichiers de Calibration & Configuration

Les paramètres globaux sont automatiquement sauvegardés dans `~/lerobot/calibration/` :

* `leader_calibration.json` / `follower_calibration.json` : Limites min/max.
* `teleoperation_config_cote.json` / `teleoperation_config_face.json` : Profils de mappage.
* `repos_position.json` : Position de repos universelle (partagée par tous les scripts).
* `camera_mask.json` : Polygone de la zone utile (généré par le script 7, utilisé par les scripts 8 et 12).
* `camera_settings.json` : Valeurs d'exposition et WB verrouillées (générées et utilisées par `SEM_so101_8_camera_config.py`).
* `camera_reference_cam_top.json` / `camera_reference_cam_follower.json` (+ images témoins, zones, `camera_reference_log.jsonl`) : Références visuelles des deux caméras (générées par `SEM_so101_camera_reference.py`, copiées dans le `meta/` du dataset par le script 9).

## 📁 Datasets & Modèles

**Données :**

* Brutes (par position) : `~/.cache/huggingface/lerobot/local/so101_pick_place/`
* Consolidées : `~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/`

**Modèles entraînés :**

* Dossier d'export : `~/lerobot/outputs/train/act_so101_pick_place/`

## ⚠️ Notes Importantes

1. **Un seul robot connecté à la fois** (sauf scripts 5, 6, 7, 8 et 12).
2. **Alimentation :** Toujours vérifier que l'alimentation (5V ou 12V) est active pour détecter les ports série.
3. **Sauvegardes des modèles :** Pensez à renommer le dossier d'export `act_so101_pick_place` pour archiver vos modèles avant de lancer un nouvel entraînement avec le script 11.
