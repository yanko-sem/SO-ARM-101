# Guide Préparation du dataset SO-ARM 101

## Phase 8 : Préparation du dataset pour l'entraînement

Service Écoles-Médias (SEM)

### 🧩 Scripts utilisés

- `SEM_so101_9_dataset.py` — préparation complète du dataset : validation des sources, consolidation, métadonnées, statistiques, conversion H.264, vérification frames/parquet, visualisation et rapport final.

### 📋 Prérequis

- Phases 1 à 7 complétées
- Dataset complet recommandé : ≥ 50 épisodes (10 par position × 5 positions)
- Un dataset réduit est aussi accepté (test pédagogique ou technique) : le script
  ne bloque pas sur le total, il signale seulement les positions à 0 épisode et
  demande confirmation
- Scripts SEM installés depuis GitHub
- Environnement lerobot activé
- Outils `ffmpeg` et `ffprobe` installés (`sudo apt install ffmpeg`) —
  nécessaires pour la conversion vidéo H.264 (visualisation navigateur) et la
  vérification des frames


### 🎯 Objectif de cette phase

**Pourquoi préparer le dataset ?** Le script d'enregistrement (Phase 7) stocke
les données dans 5 dossiers séparés (un par position). L'entraînement du modèle
ACT a besoin d'un dataset **unique et unifié**, avec des métadonnées complètes.
Cette phase fusionne les données, génère ces métadonnées et vérifie la qualité
avant de lancer l'entraînement. Le script 9 réunit la consolidation et la
visualisation, auparavant réparties dans deux scripts séparés.

Cette phase permet de :

- Fusionner les 5 positions en un seul dataset LeRobot v2.1
- Normaliser les timestamps (fréquence régulière de 30 images/seconde)
- Générer les statistiques nécessaires à l'entraînement (`episodes_stats.jsonl`)
- Convertir les vidéos en H.264 pour la visualisation dans le navigateur
- Vérifier la cohérence frames vidéo ↔ lignes parquet
- Valider visuellement la qualité des données


### 📁 Structure des données

**Avant préparation (sortie du script 8) :**

```
~/.cache/huggingface/lerobot/local/so101_pick_place/
├── position_1_centre/    (10-11 épisodes)
├── position_2_libre/     (10 épisodes)
├── position_3_haut/      (10 épisodes)
├── position_4_gauche/    (10 épisodes)
└── position_5_droite/    (10 épisodes)
```

**Après préparation (sortie du script 9) :**

```
~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/
├── data/chunk-000/
│   ├── episode_000000.parquet
│   ├── episode_000001.parquet
│   └── ...                        (un fichier par épisode)
├── videos/chunk-000/
│   ├── observation.images.cam_top/
│   │   ├── episode_000000.mp4
│   │   └── ...
│   └── observation.images.cam_follower/
│       ├── episode_000000.mp4
│       └── ...
└── meta/
    ├── info.json                  (métadonnées du dataset, v2.1)
    ├── tasks.jsonl                (une tâche par position)
    ├── episodes.jsonl             (index des épisodes)
    ├── episodes_stats.jsonl       (statistiques par épisode)
    ├── consolidation_trace.json   (traçabilité de la préparation)
    └── .h264_converted            (présent seulement si la conversion H.264 a réussi)
```

> **🔒 Préparation atomique.** Le script construit l'intégralité du dataset dans
> un dossier **temporaire** (`..._consolidated_tmp`), puis ne bascule vers le
> dossier final qu'une fois **toutes les étapes critiques réussies**. Un échec en
> cours de route ne détruit donc jamais un dataset final existant.


### 🔧 Étape 1 : Préparation du dataset (Script 9)

**Lancement**

```bash
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_9_dataset.py
```

**Si un dataset préparé existe déjà**

Au démarrage, si un dataset final est déjà présent, le script propose un menu :

| Touche | Action |
| :--- | :--- |
| P | **P**réparer à nouveau (reconsolider depuis les données du script 8) |
| V | **V**isualiser directement le dataset existant |
| Q | **Q**uitter |

**Déroulement de la préparation**

Le script enchaîne automatiquement :

1. **Analyse** — inventorie les épisodes de chaque position et lit chaque parquet
2. **Validation des sources** (*fail-closed*) — refuse de continuer si un parquet
   est invalide (colonne manquante, vide, mauvaise forme, valeurs NaN/Inf) ou si
   une vidéo manque pour un épisode existant
3. **Confirmation** — affiche l'inventaire. Si une position est à 0 épisode, il le
   signale et demande **[O/N]** avant de continuer ; sinon, appuyez sur **Entrée**
   pour lancer la préparation
4. **Consolidation** (dans le dossier temporaire) :
   - Renumérotation séquentielle des épisodes (0, 1, 2, …)
   - Mise à jour des index globaux dans chaque parquet
   - Normalisation des timestamps (1/30 s entre chaque frame)
   - Copie des vidéos avec renommage
   - Attribution d'une tâche par position
5. **Métadonnées** — génère `info.json`, `tasks.jsonl`, `episodes.jsonl`,
   `consolidation_trace.json`
6. **Statistiques** — génère `episodes_stats.jsonl` (mean, std, min, max par
   épisode et par feature). Refuse si une colonne obligatoire manque
7. **Conversion H.264** — convertit les vidéos pour le navigateur (*tout-ou-rien* :
   les originaux ne sont remplacés que si toutes les conversions réussissent).
   Sans `ffmpeg`, l'étape est sautée (vidéos en mp4v, visualisation navigateur
   indisponible)
8. **Vérification frames ↔ parquet** — confirme que chaque vidéo a autant de
   frames que son parquet (via `ffprobe`)
9. **Bascule atomique** vers le dataset final
10. **Rapport** — résumé du dataset + rapport à **états distincts** (conversion
    H.264, vérification frames), pour ne jamais déclarer « tout prêt » d'un bloc

**Sortie attendue (extrait)**

```
📊 INVENTAIRE DES DONNÉES SOURCE
=======================================================
  ✅ Position 1 (Centre  ) : 11 épisodes
  ✅ Position 2 (Libre   ) : 10 épisodes
  ✅ Position 3 (Haut    ) : 10 épisodes
  ✅ Position 4 (Gauche  ) : 10 épisodes
  ✅ Position 5 (Droite  ) : 10 épisodes
-------------------------------------------------------
  Total : 51 épisodes | 26579 frames
=======================================================

  ✅ Toutes les vidéos sont présentes
```

**Tâches générées**

Le script crée une tâche par position (l'ordre des index suit l'ordre des
positions ayant des épisodes) :

| Index | Tâche |
| :--- | :--- |
| 0 | Prendre le cube à la position Centre et le déposer dans la boîte |
| 1 | Prendre le cube à la position Libre et le déposer dans la boîte |
| 2 | Prendre le cube à la position Haut et le déposer dans la boîte |
| 3 | Prendre le cube à la position Gauche et le déposer dans la boîte |
| 4 | Prendre le cube à la position Droite et le déposer dans la boîte |

> **💡 Note :** L'objet manipulé est un prisme hexagonal ; il est désigné
> « cube » dans ces libellés (hérités du script 8).


### 🔍 Étape 2 : Visualisation dans le navigateur

À la fin de la préparation (ou via l'option **[V]** au démarrage sur un dataset
déjà préparé), le script lance l'outil officiel LeRobot
`visualize_dataset_html.py` et démarre un serveur web local.

**Ouverture du navigateur**

Le script attend que le serveur réponde, puis **ouvre automatiquement votre
navigateur par défaut** sur `http://127.0.0.1:9090`. Si le serveur n'est pas
joignable dans le délai imparti, le script affiche l'adresse à ouvrir
manuellement.

Une fois la page ouverte, l'interface affiche pour chaque épisode :

- Les flux vidéo des deux caméras (cam_top et cam_follower)
- Les courbes des 6 positions moteurs (observation.state)
- Les courbes des 6 actions (action)
- Les contrôles de lecture (play, pause, navigation)
- La liste de tous les épisodes dans le panneau de gauche

Pour arrêter le serveur : **Ctrl+C** dans le terminal.

> **💡 Conseil :** Vérifiez quelques épisodes de chaque position. Les vidéos
> doivent être fluides, et les courbes moteurs doivent correspondre aux gestes
> visibles dans les vidéos.

> **⚠️ La visualisation navigateur exige des vidéos en H.264.** Si `ffmpeg` était
> absent au moment de la préparation, les vidéos sont restées en mp4v et ne
> s'afficheront pas dans le navigateur : installez `ffmpeg`, puis relancez la
> préparation (option **[P]**).


### 🧪 Étape 3 : Validation du dataset

Avant de passer à l'entraînement, vérifiez les points suivants.

| Critère | Comment vérifier |
| :--- | :--- |
| Nombre d'épisodes correct | Résumé du script 9 (≥ 50) |
| Toutes les vidéos présentes | Aucune erreur à la validation des sources |
| Métadonnées complètes | 4 ✅ dans la section métadonnées (info.json, tasks, episodes, episodes_stats) |
| Conversion H.264 réussie | Rapport final : « vidéos en H.264 » |
| Frames = lignes parquet | Rapport final : « frames vidéo = lignes parquet » |
| Vidéos fluides et bien cadrées | Visualisation dans le navigateur |
| Mouvements cohérents | Courbes moteurs lisses, sans sauts |
| Positions couvertes | Vérifier des épisodes de chaque position |

> **⚠️ Important :** Si vous repérez des épisodes de mauvaise qualité (geste raté,
> prisme tombé, mouvement parasite), supprimez-les dans les dossiers source
> (`position_X_*/`), puis relancez le script 9 (option **[P]**) pour reconstruire
> le dataset.


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| « Dossier source introuvable » | Script 8 non exécuté | Enregistrer d'abord des épisodes (Phase 7) |
| « Aucun épisode trouvé » | Dossiers de position vides | Vérifier que le script 8 a bien enregistré |
| « parquet(s) source invalide(s) » | Données corrompues ou incomplètes | Réenregistrer les épisodes concernés |
| « vidéo(s) manquante(s) » | Enregistrement incomplet | Réenregistrer les épisodes manquants |
| Conversion H.264 « non faite » | `ffmpeg` absent | `sudo apt install ffmpeg`, puis relancer (option [P]) |
| Vérification frames « non vérifiée » | `ffprobe` absent | Installer `ffmpeg` (fournit `ffprobe`), puis relancer |
| Vidéos noires dans le navigateur | Vidéos encore en mp4v | Installer `ffmpeg` et relancer la préparation |
| Le navigateur ne s'ouvre pas | Serveur lent à répondre | Ouvrir `http://127.0.0.1:9090` manuellement |
| « Incohérences frames/parquet » | Vidéos/parquets désynchronisés | Réenregistrer les épisodes signalés, puis relancer |


### 📝 Récapitulatif des fichiers

| Fichier | Description | Créé par |
| :--- | :--- | :--- |
| `SEM_so101_9_dataset.py` | Préparation complète (consolidation, métadonnées, conversion, vérification, visualisation) | Script 9 |
| `so101_pick_place_consolidated/` | Dataset unifié prêt pour l'entraînement | Script 9 |
| `meta/info.json` | Métadonnées du dataset (v2.1) | Script 9 |
| `meta/episodes_stats.jsonl` | Statistiques par épisode | Script 9 |
| `meta/consolidation_trace.json` | Traçabilité de la préparation | Script 9 |


### 🚀 Commandes de référence rapide

```bash
# Préparation complète du dataset (+ visualisation optionnelle)
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_9_dataset.py
```


### 📝 Notes finales

**✅ Phase 8 terminée quand :**

- Le dataset consolidé contient le nombre d'épisodes prévu (≥ 50 pour un dataset complet)
- Les 4 fichiers de métadonnées sont présents (`info.json`, `tasks.jsonl`,
  `episodes.jsonl`, `episodes_stats.jsonl`)
- Les vidéos sont converties en H.264
- La vérification frames ↔ parquet est passée
- La visualisation dans le navigateur fonctionne et les données sont cohérentes

> **🚀 Objectif atteint :** Votre dataset est préparé, vérifié et prêt pour
> l'entraînement du modèle ACT ! Passez à la Phase 9 pour entraîner le robot à
> reproduire vos gestes de manière autonome.
