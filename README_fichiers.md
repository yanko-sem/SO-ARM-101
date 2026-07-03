# Fichiers de données du projet SO-ARM 101

## Inventaire des fichiers lus et écrits par le pipeline (hors scripts)

Service Écoles-Médias (SEM)

Ce document recense les principaux fichiers lus ou écrits par le pipeline — directement par les scripts SEM, par le module caméra qu'ils appellent, ou par LeRobot lorsqu'il est lancé depuis le script 10 : calibrations, masque, datasets, checkpoints et fichiers d'état. Il a été établi en analysant le code réel des **11 scripts numérotés** et du module caméra **`SEM_so101_camera_auto.py`** (réglage d'exposition et contrôle image). Ce module **n'écrit aucun fichier persistant** : il règle l'exposition via `v4l2-ctl` au moment de l'exécution (auto puis figée par session) et lit `camera_mask.json` pour mesurer la zone utile de la caméra globale.

### 🧭 Conventions

- **Écrit par** : script (ou module) qui crée ou met à jour le fichier.
- **Lu par** : script (ou module) qui le lit.
- **Écriture atomique** : la plupart des fichiers de configuration sont écrits via un fichier `*.tmp` puis renommés (`os.replace`), pour éviter un fichier corrompu en cas d'interruption. Les `*.tmp` sont **transitoires** (jamais persistants).
- Quatre racines de stockage : `~/lerobot/calibration/`, `~/.cache/huggingface/lerobot/local/`, `~/lerobot/outputs/train/` (un sous-dossier par **modèle nommé**), et le dossier des scripts.


### 📁 1. `~/lerobot/calibration/` — configuration persistante

| Fichier | Rôle | Écrit par | Lu par |
| :--- | :--- | :--- | :--- |
| `leader_calibration.json` | Limites min/max des servos du Leader | 2 | 2, 3, 4, 5, 6, 7, 8 |
| `follower_calibration.json` | Limites min/max des servos du Follower | 2 | 2, 3, 4, 5, 6, 7, 8, 11 |
| `repos_position.json` | Position de repos commune | 3 | 3, 4, 5, 6, 7, 8, 11 |
| `teleoperation_config_cote.json` | Config téléopération côte à côte (COPY/MIRROR par servo) | 5 | 5, 6, 7, 8 |
| `teleoperation_config_face.json` | Config téléopération face à face | 5 | 5, 6, 7, 8 |
| `camera_mask.json` | Masque de la zone utile (caméra globale) | 7 | 7, 8, 11, module `camera_auto` |

> **Note 1 — leader vs follower au déploiement :** le déploiement (script 11) ne charge **que** la calibration Follower (`charger_calibration('follower')`). La calibration Leader n'est pas requise pour le robot autonome.

> **Note 2 — fichiers transitoires :** `*_calibration.json.tmp`, `repos_position.json.tmp`, `teleoperation_config_*.json.tmp` et `camera_mask.json.tmp` sont des écritures atomiques (non persistantes).

> **Note 3 — réglages caméra non persistés :** l'exposition (et la balance des blancs) est réglée **à l'exécution** par `camera_auto` (via `v4l2-ctl`, auto puis figée par session) ; aucun fichier de réglages caméra n'est produit. Le **contrôle image** se fait aussi à l'exécution, sur l'image brute, sans fichier de sortie.


### 🎞️ 2. Dataset brut — `~/.cache/huggingface/lerobot/local/so101_pick_place/`

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

> **Note 4 :** `sem_state.json` (à la racine de `so101_pick_place/`) permet la reprise de l'enregistrement épisode par épisode. C'est un fichier propre au script 8, distinct du format LeRobot.


### 🧱 3. Dataset consolidé — `~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/`

Construit par le **script 9** (fusion des 5 positions), lu par le **script 10**.

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

> **Note 5 — bascule « tout ou rien » :** le script 9 construit d'abord dans `so101_pick_place_consolidated_tmp/`, puis renomme l'ancien dataset en `so101_pick_place_consolidated_old/`, installe le nouveau, et **annule (rollback)** si le renommage échoue. Les fichiers `*.tmp.mp4` sont des conversions vidéo temporaires. Ces dossiers/fichiers sont transitoires.


### 🧠 4. Sorties d'entraînement — `~/lerobot/outputs/train/<nom_du_modele>/`

Chaque entraînement crée ou reprend un **modèle nommé** : un dossier
`~/lerobot/outputs/train/<nom_du_modele>/` (le nom est celui saisi au script 10,
sans préfixe). Les chemins ci-dessous sont relatifs à ce dossier.

| Fichier / dossier | Rôle | Écrit par | Lu par |
| :--- | :--- | :--- | :--- |
| `sem_training_params.json` | Mémoire **informative** des paramètres SEM du lancement (entraînement neuf ou remplacement) — **non mise à jour** en reprise/prolongation, et **ne pilote pas** la reprise | 10 | 10 (affichage à la reprise) |
| `checkpoints/<step>/pretrained_model/` | Checkpoint ACT (modèle + config) | LeRobot (via 10) | 10, 11 |
| `checkpoints/<step>/pretrained_model/model.safetensors` | Poids du modèle ACT | LeRobot | 11 |
| `checkpoints/<step>/pretrained_model/config.json` | Configuration de la policy | LeRobot | 11 |
| `checkpoints/<step>/pretrained_model/train_config.json` | Config de reprise + traçabilité du dataset | LeRobot | 10 (reprise via `--config_path`) |
| `checkpoints/last/pretrained_model/` | Dernier checkpoint | LeRobot (via 10) | 10, 11 |

> **Note 6 — déploiement et checkpoint :** le script 11 charge le modèle depuis `pretrained_model/` (`model.safetensors` + `config.json`) et le place sur le périphérique disponible (GPU si présent, sinon CPU). Il ne lit pas `train_config.json` (utilisé uniquement par le script 10 pour la reprise).


### 📝 5. Dossier des scripts — `~/lerobot/Scripts_SEM/scripts/`

Le dossier des scripts ne contient **aucun fichier de données persistant** : il
n'héberge que les scripts eux-mêmes.

> **Note 7 — `sem_training_params.json` :** ce fichier est désormais écrit dans le
> dossier du **modèle** (`~/lerobot/outputs/train/<nom_du_modele>/`, voir section 4),
> **après** le lancement de l'entraînement — jamais avant, pour ne pas créer un
> `output_dir` non vide qui ferait échouer un entraînement neuf. Il est purement
> informatif : la reprise fiable s'appuie sur `train_config.json` du checkpoint,
> pas sur ce fichier.


### 📌 Notes finales

- **Le script 1** (configuration des IDs servo) n'écrit aucun fichier persistant.
- **Réglages caméra à l'exécution :** l'exposition est réglée par `camera_auto` (auto puis figée par session) et le contrôle image se fait sur l'image brute — sans fichier de sortie. Le seul fichier caméra persistant est `camera_mask.json` (créé au script 7).
- **Écriture atomique généralisée :** calibrations, repos, configs téléopération et masque sont écrits via `.tmp` puis renommés ; le dataset consolidé via une bascule `_tmp/` → `_old/` avec rollback.
- **Fail-closed :** un réglage d'exposition non appliqué (`camera_auto`), une calibration Follower illisible, un masque absent, ou une image non exploitable **bloquent** plutôt que de dégrader silencieusement.
