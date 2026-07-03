# Scripts SEM pour SO-ARM 101

Collection de scripts Python pour la configuration, la calibration, l'enregistrement, l'entraînement et le déploiement d'un robot SO-ARM 101 avec LeRobot.

Ce README décrit la chaîne actuelle validée des scripts SEM :

```text
1  Configuration des servos
2  Calibration
3  Monitoring
4  Contrôle manuel
5  Configuration téléopération
6  Téléopération pure
7  Téléopération + caméra / masque
8  Enregistrement du dataset
9  Préparation du dataset + visualisation
10 Entraînement ACT
11 Déploiement ACT
```

---

## 🔧 Prérequis

```bash
# Environnement conda activé
conda activate lerobot

# Permissions USB, configurées une fois pendant l'installation
groups | grep dialout
groups | grep video

# Outils vidéo nécessaires (v4l2-ctl pour l'exposition, ffmpeg pour la vidéo)
sudo apt update
sudo apt install v4l-utils ffmpeg
# guvcview est optionnel (inspection manuelle ponctuelle)
```

Prévoir également, dans l'environnement `lerobot` :

```bash
# Moteur Parquet pour pandas / LeRobot
pip install pyarrow

# Backend vidéo utilisé par l'entraînement
pip install av
```

Selon l'installation LeRobot, certaines dépendances peuvent déjà être présentes. Les scripts 9 et 10 effectuent maintenant des contrôles explicites pour éviter les erreurs tardives et difficiles à comprendre.

---

## 📋 Liste des scripts

### 1️⃣ `SEM_so101_1_configure.py`

Configuration initiale des servos avec leurs IDs pendant le montage.

- configure un servo à la fois ;
- teste le mouvement automatiquement ;
- centre et bloque le servo pour le montage ;
- propose les options de blocage et de libération du couple.

**Utilisation :**

```bash
python SEM_so101_1_configure.py
```

---

### 2️⃣ `SEM_so101_2_calibrate.py`

Calibration des limites de mouvement de chaque servo.

- enregistre les limites `min`, `max` et `center` ;
- sauvegarde automatiquement après chaque servo ;
- vérifie que l'amplitude de calibration est exploitable ;
- sert de base à tous les mouvements sûrs des scripts suivants ;
- les scripts récents refusent les calibrations absentes, incomplètes ou incohérentes.

**Utilisation :**

```bash
python SEM_so101_2_calibrate.py
# Choisir L pour Leader ou F pour Follower
# Utiliser l'option T pour calibrer tous les servos
```

---

### 3️⃣ `SEM_so101_3_monitor.py`

Monitoring temps réel des positions des servos.

- affiche les positions en tableau ;
- permet de manipuler le robot avec le couple désactivé ;
- utile pour vérifier la position de repos, les limites et les comportements mécaniques ;
- aide au diagnostic avant calibration, téléopération ou déploiement.

**Utilisation :**

```bash
python SEM_so101_3_monitor.py
```

---

### 4️⃣ `SEM_so101_4_control.py`

Contrôle manuel d'un robot au clavier.

- mode normal et mode précis ;
- mouvements interpolés pour éviter les à-coups ;
- contrôle servo par servo ;
- arrêt d'urgence ;
- utilise les calibrations pour éviter les mouvements incohérents.

**Utilisation :**

```bash
python SEM_so101_4_control.py
```

---

### 5️⃣ `SEM_so101_5_config_teleoperation.py`

Configuration du comportement Leader → Follower.

- définit, servo par servo, le mode copie ou miroir ;
- indispensable pour une installation face à face ;
- sauvegarde les profils de téléopération ;
- inclut des tests de centrage et de retour repos ;
- s'appuie sur les calibrations validées des deux bras.

**Utilisation :**

```bash
python SEM_so101_5_config_teleoperation.py
```

---

### 6️⃣ `SEM_so101_6_teleoperation.py`

Téléopération Leader → Follower pure.

- contrôle le Follower à partir du Leader ;
- applique le mappage copie/miroir ;
- respecte les calibrations des deux bras ;
- utilise des séquences sûres de positionnement initial et final ;
- sert de base comportementale aux scripts d'enregistrement.

**Utilisation :**

```bash
python SEM_so101_6_teleoperation.py
```

---

### 7️⃣ `SEM_so101_7_teleoperation_camera.py`

Téléopération avec affichage vidéo et création du masque de zone utile.

- affiche le flux caméra pendant la téléopération ;
- permet de cadrer la zone de travail ;
- permet de dessiner un polygone de masque pour la caméra globale ;
- sauvegarde `camera_mask.json` dans `~/lerobot/calibration/` ;
- ce masque est ensuite utilisé par les scripts 8 et 11 pour garantir la cohérence visuelle.

**Utilisation :**

```bash
python SEM_so101_7_teleoperation_camera.py
```

---

## 📷 Module utilitaire : `SEM_so101_camera_auto.py`

Module canonique de réglage caméra et de contrôle image.

Ce module n'est pas une étape numérotée. Il est utilisé par les scripts 8 et 11 pour régler l'exposition des caméras et vérifier que l'image est exploitable, à l'enregistrement comme au déploiement.

Fonctions principales :

- **exposition (et balance des blancs) auto puis figée** : le pilote laisse l'auto s'ajuster à la lumière réelle de la salle pendant quelques secondes (flux actif), puis fige la valeur trouvée pour la session (fréquence secteur 50 Hz, anti-scintillement) ;
- réglage appliqué via `v4l2-ctl` (paquet `v4l-utils`) ; `guvcview` n'est pas requis ;
- **contrôle image simple** sur l'image brute (avant masque) : plancher physique de lumière (luminosité, part de pixels très clairs / très sombres) ;
- mesure dans la **zone utile du masque** pour la caméra globale (le plateau), en **plein cadre** pour la caméra pince ;
- verdict gradué 🟢 (exploitable) / 🟠 (limite) / 🔴 (cramée ou écrasée) ;
- gestion fail-closed : un réglage non appliqué arrête le script appelant.

---

### 8️⃣ `SEM_so101_8_record_dataset.py`

Enregistrement du dataset d'apprentissage par imitation.

Ce script enregistre les démonstrations avec deux caméras :

- `cam_top` : caméra globale ;
- `cam_follower` : caméra pince / Follower.

Fonctions principales :

- identification explicite des deux caméras ;
- mise au repos des robots avant la préparation caméra ;
- réglage de l'exposition des caméras (auto puis figée) au démarrage de la session ;
- contrôle image des deux caméras avant chaque bloc ;
- application du masque de la caméra globale ;
- enregistrement synchronisé des images et des états/action servo ;
- rejet des frames si la lecture série ou vidéo n'est pas valide ;
- sauvegarde au format LeRobotDataset v2.1 ;
- action enregistrée dans le repère du Follower, c'est-à-dire la cible réellement envoyée ;
- positions d'enregistrement :
  - position 1 : Centre ;
  - position 2 : Libre ;
  - position 3 : Haut ;
  - position 4 : Gauche ;
  - position 5 : Droite.

Points de sécurité et de cohérence :

- le script est fail-closed sur les caméras ;
- aucune création de dataset ne doit se faire si les deux flux vidéo ou les lectures servo ne sont pas fiables ;
- le retour repos est utilisé pour conserver la cohérence entre les épisodes ;
- le clavier est suspendu pendant les confirmations `input()` pour éviter les interférences avec le thread clavier.

**Utilisation :**

```bash
python SEM_so101_8_record_dataset.py
```

---

### 9️⃣ `SEM_so101_9_dataset.py`

Préparation complète du dataset pour l'entraînement.

Ce script remplace l'ancienne séparation entre consolidation, finalisation et visualisation. Il prépare le dataset final en un seul passage.

Fonctions principales :

- analyse des dossiers source créés par le script 8 ;
- vérification des colonnes obligatoires `observation.state` et `action` ;
- vérification de la forme attendue des états et actions ;
- refus des parquets vides, illisibles, non numériques ou contenant `NaN` / `Inf` ;
- vérification de la présence des vidéos des deux caméras ;
- fusion des cinq positions dans un dataset consolidé ;
- génération de `info.json`, `tasks.jsonl`, `episodes.jsonl` et `episodes_stats.jsonl` ;
- conversion H.264 tout-ou-rien pour la visualisation navigateur ;
- vérification résolution vidéo `640×360` et cohérence frames vidéo / lignes parquet ;
- construction dans un dossier temporaire puis bascule finale seulement si les étapes critiques réussissent ;
- visualisation LeRobot intégrée en fin de script.

**Utilisation :**

```bash
python SEM_so101_9_dataset.py
```

---

### 🔟 `SEM_so101_10_train.py`

Entraînement de la politique ACT sur le dataset consolidé.

Fonctions principales :

- sélection ou création d'un **modèle nommé** (registre local sous `~/lerobot/outputs/train/`), nom libre validé par `^[a-z0-9][a-z0-9_-]*$` (= nom exact du dossier, sans préfixe) ;
- vérification des prérequis avant lancement ;
- détection du GPU / CUDA, avec bascule automatique sur CPU si absent (avertissement non bloquant) ;
- vérification PyAV, requis par `--dataset.video_backend=pyav` ;
- vérification de la présence du dataset consolidé ;
- vérification de `info.json`, `episodes_stats.jsonl`, parquets et dossiers vidéo ;
- quatre profils d'entraînement :
  - rapide ;
  - intermédiaire ;
  - standard ;
  - intensif ;
- protection contre la veille et l'extinction via `systemd-inhibit` ;
- sauvegarde des checkpoints ;
- reprise fiable avec `train_config.json` du checkpoint ;
- prolongation d'un entraînement existant vers un nombre de steps supérieur ;
- tri numérique des checkpoints, pour éviter de reprendre un checkpoint plus ancien par erreur ;
- **remplacement** d'un modèle existant uniquement après confirmation forte (saisie de `SUPPRIMER`), avec l'option « choisir un autre modèle » ; un dossier existant même partiel ne bloque pas le nom ;
- `sem_training_params.json` écrit dans le dossier du modèle, **après** le lancement.

**Utilisation :**

```bash
python SEM_so101_10_train.py
```

---

### 1️⃣1️⃣ `SEM_so101_11_deploy.py`

Déploiement autonome du modèle ACT entraîné.

Le modèle observe les deux caméras et l'état actuel du Follower, puis commande les servos en autonomie.

Fonctions principales :

- sélection **explicite du modèle nommé** (aucun défaut), puis du checkpoint **chargeable** — priorité à `last` s'il est chargeable, sinon le plus grand checkpoint numérique chargeable ; seuls les modèles et checkpoints réellement chargeables (`config.json` + `model.safetensors`) sont proposés ;
- chargement du modèle ACT avec `ACTPolicy.from_pretrained()` ;
- masque de caméra globale obligatoire ;
- calibration Follower chargée et validée avant ouverture du port et activation du couple ;
- retour repos avant réglage caméra et avant inférence ;
- identification explicite de `cam_top` et `cam_follower` ;
- réglage de l'exposition (auto puis figée) et contrôle image des deux caméras avant déploiement ;
- inférence à environ 30 Hz ;
- clipping calibré des actions du modèle dans les plages `[min, max]` de chaque servo ;
- vérification des écritures servo ;
- arrêt sûr après trois itérations consécutives avec échec d'écriture ;
- retour repos en fin d'essai ;
- relance impossible si le repos n'est pas confirmé ;
- arrêt d'urgence avec coupure immédiate du couple ;
- nettoyage final des caméras et du port série.

**Commandes pendant l'inférence :**

| Touche | Action |
| --- | --- |
| P | Pause / reprendre |
| R | Retour repos + désactivation du modèle |
| Entrée | Relancer un essai après retour repos confirmé |
| Q | Quitter proprement |
| Ctrl+C | Arrêt d'urgence : coupure immédiate du couple, sans retour repos |

**Utilisation :**

```bash
python SEM_so101_11_deploy.py
```

---

## ⌨️ Commandes utiles

### Identification des caméras, scripts 8 et 11

Touches lues **directement dans la fenêtre live** (pas de `Entrée`) :

| Touche | Action |
| --- | --- |
| G | Identifier la caméra comme globale, `cam_top` |
| P | Identifier la caméra comme pince, `cam_follower` |
| Q | Passer la caméra affichée |
| Échap | Annuler |

### Contrôle image caméra, scripts 8 et 11

| Verdict | Touches (dans la fenêtre) |
| --- | --- |
| 🟢 | continue automatiquement |
| 🟠 | `C` continuer / `R` re-régler / `Q` annuler |
| 🔴 | `R` re-régler / `Q` annuler — pas de `C` |

### Menu d'enregistrement, script 8

| Choix | Action |
| --- | --- |
| 1 | Afficher les instructions |
| 2 | Test rapide |
| 3 | Enregistrer une série d'épisodes pour une position |
| 4 | Visualiser / contrôler les données disponibles |
| 5 | Effacer des données |
| 6 | Repositionner au repos |
| Q | Quitter |

Un contrôle des deux caméras précède chaque bloc d'enregistrement.

### Pendant un épisode, script 8

| Touche | Action |
| --- | --- |
| T | Terminer l'épisode avec succès |
| A | Annuler l'épisode en cours |
| S | Stopper la session et revenir au menu |

---

## 📁 Fichiers de calibration et de configuration

Tous les fichiers globaux sont enregistrés dans :

```text
~/lerobot/calibration/
```

Fichiers principaux :

- `leader_calibration.json` : calibration du Leader ;
- `follower_calibration.json` : calibration du Follower ;
- `teleoperation_config_cote.json` : profil de téléopération côte à côte ;
- `teleoperation_config_face.json` : profil de téléopération face à face ;
- `repos_position.json` : position de repos partagée par les scripts ;
- `camera_mask.json` : masque de la zone utile de la caméra globale.

---

## 📁 Datasets et modèles

### Données brutes par position

```text
~/.cache/huggingface/lerobot/local/so101_pick_place/
```

Structure attendue :

```text
position_1_centre/
position_2_libre/
position_3_haut/
position_4_gauche/
position_5_droite/
```

### Dataset consolidé

```text
~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/
```

Ce dossier est produit par le script 9. Il contient les parquets, les vidéos et les métadonnées LeRobot.

### Modèles entraînés

Chaque entraînement crée un **modèle nommé** sous une racine commune (un
sous-dossier par modèle) :

```text
~/lerobot/outputs/train/                 # un sous-dossier par modèle
~/lerobot/outputs/train/<nom_du_modele>/
```

Les checkpoints d'un modèle sont stockés dans :

```text
~/lerobot/outputs/train/<nom_du_modele>/checkpoints/
```

---

## ⚠️ Notes importantes

1. Un seul robot doit être connecté pour les scripts qui travaillent sur un seul bras. Les scripts 5, 6, 7 et 8 nécessitent les deux bras.
2. Le script 11 ne nécessite que le Follower, mais il exige deux caméras fonctionnelles.
3. Le Follower doit être alimenté pour être détecté sur le port série.
4. Les conditions matérielles au déploiement (positions et cadrage des caméras) doivent correspondre à celles de l'enregistrement du dataset d'entraînement.
5. Les scripts récents privilégient le fail-closed : si la caméra, la calibration ou la communication servo sont douteuses, le script refuse de continuer plutôt que de créer ou utiliser un état ambigu.
6. Chaque entraînement est un **modèle nommé** ; vous pouvez en conserver plusieurs. Réutiliser un nom existant propose de reprendre, prolonger ou **remplacer** ce modèle ; le remplacement (suppression de l'existant) exige la saisie de `SUPPRIMER`.
7. Avant un déploiement réel, vérifier manuellement que la zone de travail est dégagée et que le bras peut revenir au repos sans obstacle.

---

## 🔁 Chaîne d'utilisation recommandée

```bash
python SEM_so101_2_calibrate.py
python SEM_so101_3_monitor.py
python SEM_so101_4_control.py
python SEM_so101_5_config_teleoperation.py
python SEM_so101_6_teleoperation.py
python SEM_so101_7_teleoperation_camera.py
python SEM_so101_8_record_dataset.py
python SEM_so101_9_dataset.py
python SEM_so101_10_train.py
python SEM_so101_11_deploy.py
```

Le script 1 est utilisé principalement pendant le montage initial des servos.
