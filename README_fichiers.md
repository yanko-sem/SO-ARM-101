# Fichiers de données du projet SO-ARM 101

## Inventaire des fichiers lus et écrits par le pipeline (hors scripts)

Service Écoles-Médias (SEM)

Ce document recense les principaux fichiers lus ou écrits par le pipeline — directement par les scripts SEM, par les modules caméra qu'ils appellent, ou par LeRobot lorsqu'il est lancé depuis le script 10 : calibrations, masque, réglages caméra, références visuelles, datasets, checkpoints, et fichiers d'état. Il a été établi en analysant le code réel des **11 scripts numérotés** et des **2 modules caméra** (`SEM_so101_camera_config.py`, `SEM_so101_camera_reference.py`) qui réalisent les E/S de configuration et de référence pour le compte des scripts.

### 🧭 Conventions

- **Écrit par** : script (ou module) qui crée ou met à jour le fichier.
- **Lu par** : script (ou module) qui le lit.
- **Écriture atomique** : la plupart des fichiers de configuration sont écrits via un fichier `*.tmp` puis renommés (`os.replace`), pour éviter un fichier corrompu en cas d'interruption. Les `*.tmp` sont **transitoires** (jamais persistants).
- Quatre racines de stockage : `~/lerobot/calibration/`, `~/.cache/huggingface/lerobot/local/`, `~/lerobot/outputs/train/act_so101_pick_place/`, et le dossier des scripts.


### 📁 1. `~/lerobot/calibration/` — configuration persistante

| Fichier | Rôle | Écrit par | Lu par |
| :--- | :--- | :--- | :--- |
| `leader_calibration.json` | Limites min/max des servos du Leader | 2 | 2, 3, 4, 5, 6, 7, 8 |
| `follower_calibration.json` | Limites min/max des servos du Follower | 2 | 2, 3, 4, 5, 6, 7, 8, 11 |
| `repos_position.json` | Position de repos commune | 3 | 3, 4, 5, 6, 7, 8, 11 |
| `teleoperation_config_cote.json` | Config téléopération côte à côte (COPY/MIRROR par servo) | 5 | 5, 6, 7, 8 |
| `teleoperation_config_face.json` | Config téléopération face à face | 5 | 5, 6, 7, 8 |
| `camera_mask.json` | Masque de la zone utile (caméra globale) | 7 | 7, 8, 11, module `camera_reference` |
| `camera_settings.json` | Réglages caméra verrouillés (exposition / WB / gain) | module `camera_config` *(déclenché par 8, ou par le recalibrage guidé du module `camera_reference`)* | 8, 11, modules `camera_config` et `camera_reference` |

> **Note 1 — leader vs follower au déploiement :** le déploiement (script 11) ne charge **que** la calibration Follower (`charger_calibration('follower')`). La calibration Leader n'est pas requise pour le robot autonome.

> **Note 2 — fichiers transitoires et de secours :**
> - `*_calibration.json.tmp`, `repos_position.json.tmp`, `teleoperation_config_*.json.tmp`, `camera_mask.json.tmp` : écritures atomiques (non persistantes).
> - `camera_settings.json.corrupt.AAAAMMJJ_HHMMSS` : sauvegarde horodatée créée par `camera_config` si `camera_settings.json` est détecté corrompu, **avant** régénération (fail-closed — jamais d'écrasement silencieux).


### 📷 2. Références visuelles caméra (dans `~/lerobot/calibration/`)

Sous-système géré par le module `SEM_so101_camera_reference.py`, **déclenché par le script 8** (menus de référence et contrôle de conformité) ou utilisé en autonome. Relu au déploiement par le script 11, et **copié dans le `meta/` du dataset par le script 9**.

| Fichier | Rôle |
| :--- | :--- |
| `camera_reference_cam_top.json` | Référence chiffrée de la caméra globale (zones, statistiques, infos de masque) |
| `camera_reference_cam_follower.json` | Référence chiffrée de la caméra pince |
| `camera_reference_zones_cam_top.json` | Définition locale des zones de mesure (globale) |
| `camera_reference_zones_cam_follower.json` | Définition locale des zones de mesure (pince) |
| `camera_reference_cam_top_raw.png` | Image témoin brute (globale) |
| `camera_reference_cam_top_masked.png` | Image témoin masquée (globale) |
| `camera_reference_cam_follower_raw.png` | Image témoin brute (pince) |
| `camera_reference_log.jsonl` | Journal des contrôles de conformité (notamment passages 🟠 confirmés) |

> **Note 3 — référence autosuffisante :** les zones de mesure sont **intégrées** dans `camera_reference_<cam>.json` (champ `zones`), en plus du fichier de travail `camera_reference_zones_*.json`. C'est ce qui permet au déploiement d'utiliser les références **copiées dans le `meta/`** du dataset comme vérité de comparaison, sans dépendre des fichiers locaux.

> **Note 4 — temporaires de validation :** `camera_reference_<cam>_tmp.json`, `camera_reference_<cam>_raw_tmp.png`, `camera_reference_<cam>_masked_tmp.png` sont écrits avant validation finale puis nettoyés (`_nettoyer_tmp`). La caméra pince n'a pas de version masquée (profil sans masque).


### 🎞️ 3. Dataset brut — `~/.cache/huggingface/lerobot/local/so101_pick_place/`

Créé par le **script 8**. Une sous-arborescence par position :

```
so101_pick_place/
├── sem_state.json                 # état de reprise (épisodes enregistrés par position)
├── position_1_centre/
├── position_2_libre/
├── position_3_haut/
├── position_4_gauche/
└── position_5_droite/
```

Contenu de chaque dossier de position (format LeRobotDataset v2.1) :

| Fichier / dossier | Rôle | Écrit par | Lu par |
| :--- | :--- | :--- | :--- |
| `meta/info.json` | Métadonnées du dataset | 8 | 8, 9 |
| `meta/tasks.jsonl` | Description de la tâche | 8 | 9 |
| `meta/episodes.jsonl` | Index des épisodes | 8 | 9 |
| `data/chunk-000/episode_XXXXXX.parquet` | États / actions / timestamps | 8 | 9 |
| `data/chunk-000/episode_XXXXXX.json` | **Fallback** si Parquet/Pandas indisponible (hors chemin normal) | 8 | 9 |
| `videos/chunk-000/observation.images.cam_top/episode_XXXXXX.mp4` | Vidéo caméra globale | 8 | 9 |
| `videos/chunk-000/observation.images.cam_follower/episode_XXXXXX.mp4` | Vidéo caméra pince | 8 | 9 |

> **Note 5 :** `sem_state.json` (à la racine de `so101_pick_place/`) permet la reprise de l'enregistrement épisode par épisode. C'est un fichier propre au script 8, distinct du format LeRobot.


### 🧱 4. Dataset consolidé — `~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/`

Construit par le **script 9** (fusion des 5 positions), lu par le **script 10**, et utilisé indirectement par le **script 11** via `train_config.json`.

| Fichier / dossier | Rôle | Écrit par | Lu par |
| :--- | :--- | :--- | :--- |
| `data/chunk-000/episode_XXXXXX.parquet` | Épisodes consolidés | 9 | 10 / LeRobot |
| `videos/chunk-000/observation.images.cam_top/episode_XXXXXX.mp4` | Vidéos globales consolidées (H.264) | 9 | 10 / LeRobot |
| `videos/chunk-000/observation.images.cam_follower/episode_XXXXXX.mp4` | Vidéos pince consolidées (H.264) | 9 | 10 / LeRobot |
| `meta/info.json` | Métadonnées consolidées | 9 | 10 / LeRobot |
| `meta/tasks.jsonl` | Tâches consolidées | 9 | LeRobot via 10 |
| `meta/episodes.jsonl` | Index consolidé | 9 | LeRobot via 10 |
| `meta/episodes_stats.jsonl` | Statistiques par épisode (requises à l'entraînement) | 9 | 10 / LeRobot |
| `meta/consolidation_trace.json` | Traçabilité de la consolidation | 9 | — |
| `meta/.h264_converted` | Marqueur de conversion H.264 réussie | 9 | 9 |
| `meta/camera_reference_cam_top.json` | Référence globale copiée (vérité de comparaison au déploiement) | 9 | 11 |
| `meta/camera_reference_cam_follower.json` | Référence pince copiée | 9 | 11 |
| `meta/camera_reference_cam_top_raw.png` | Image témoin globale copiée | 9 | — |
| `meta/camera_reference_cam_top_masked.png` | Image témoin globale masquée copiée | 9 | — |
| `meta/camera_reference_cam_follower_raw.png` | Image témoin pince copiée | 9 | — |
| `meta/camera_reference_log.jsonl` | Journal copié (si présent) | 9 | — |

> **Note 6 — bascule « tout ou rien » :** le script 9 construit d'abord dans `so101_pick_place_consolidated_tmp/`, puis renomme l'ancien dataset en `so101_pick_place_consolidated_old/`, installe le nouveau, et **annule (rollback)** si le renommage échoue. Les fichiers `*.tmp.mp4` sont des conversions vidéo temporaires. Ces dossiers/fichiers sont transitoires.


### 🧠 5. Sorties d'entraînement — `~/lerobot/outputs/train/act_so101_pick_place/`

| Fichier / dossier | Rôle | Écrit par | Lu par |
| :--- | :--- | :--- | :--- |
| `checkpoints/<step>/pretrained_model/` | Checkpoint ACT (modèle + config) | LeRobot (via 10) | 10, 11 |
| `checkpoints/<step>/pretrained_model/model.safetensors` | Poids du modèle ACT | LeRobot | 11 |
| `checkpoints/<step>/pretrained_model/config.json` | Configuration de la policy | LeRobot | 11 |
| `checkpoints/<step>/pretrained_model/train_config.json` | Config de reprise + traçabilité du dataset | LeRobot | 10 (reprise via `--config_path`), 11 (remontée vers le `meta/` d'entraînement) |
| `checkpoints/last/pretrained_model/` | Dernier checkpoint | LeRobot (via 10) | 10, 11 |


### 📝 6. Dossier des scripts — `~/lerobot/Scripts_SEM/scripts/`

| Fichier | Rôle |
| :--- | :--- |
| `sem_training_params.json` | Mémoire **informative** des derniers paramètres d'entraînement SEM |

> **Note 7 — exception notable :** ce fichier est écrit **à côté du script 10** (`Path(__file__).parent`), et non dans `outputs/train/`. Il est purement informatif : la reprise fiable s'appuie sur `train_config.json` du checkpoint, pas sur ce fichier.


### 📌 Notes finales

- **Le script 1** (configuration des IDs servo) n'écrit aucun fichier persistant.
- **Écriture atomique généralisée** : calibrations, repos, configs téléopération, masque et références sont écrits via `.tmp` puis renommés ; le dataset consolidé via une bascule `_tmp/` → `_old/` avec rollback.
- **Fail-closed** : références manquantes, fichier de réglages corrompu (sauvegarde `.corrupt.*`), ou non-conformité bloquent plutôt que de dégrader silencieusement.
- **Pivot pour la correction automatique (projet 2.0)** : les références caméra sont figées à l'entraînement dans `calibration/`, **copiées dans le `meta/` du dataset par le script 9** (JSON + images témoins), puis relues par le script 11 qui compare l'image live à *ces* références. Comme les zones sont intégrées au JSON, ces copies sont autosuffisantes.
