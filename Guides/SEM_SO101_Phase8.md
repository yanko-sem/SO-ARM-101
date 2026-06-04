# Guide Consolidation et Visualisation SO-ARM 101

## Phase 8 : Préparation du dataset pour l'entraînement

Service Écoles-Médias (SEM) — DIP Genève

### ✅ Prérequis

- Phases 1 à 7 complétées
- ≥ 50 épisodes enregistrés (10 par position × 5 positions)
- Scripts SEM installés depuis GitHub
- Environnement lerobot activé


### 🎯 Objectif de cette phase

**Pourquoi consolider ?** Le script d'enregistrement (Phase 7) stocke les données dans 5 dossiers séparés (un par position). L'entraînement du modèle ACT nécessite un dataset unique et unifié. Cette phase fusionne les données et vérifie leur qualité avant de lancer l'entraînement.

Cette phase permet de :

- Fusionner les 5 positions en un seul dataset LeRobot v2.1
- Normaliser les timestamps pour une fréquence régulière
- Générer les statistiques nécessaires à l'entraînement
- Convertir les vidéos pour la visualisation dans le navigateur
- Valider visuellement la qualité des données


### 📁 Structure des données

**Avant consolidation (sortie du script 8) :**

```
~/.cache/huggingface/lerobot/local/so101_pick_place/
├── position_1_centre/    (10-11 épisodes)
├── position_2_bas/       (10 épisodes)
├── position_3_haut/      (10 épisodes)
├── position_4_gauche/    (10 épisodes)
└── position_5_droite/    (10 épisodes)
```

**Après consolidation (sortie du script 9) :**

```
~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/
├── data/chunk-000/
│   ├── episode_000000.parquet
│   ├── episode_000001.parquet
│   └── ...                        (51 fichiers)
├── videos/chunk-000/
│   ├── observation.images.cam_top/
│   │   ├── episode_000000.mp4
│   │   └── ...
│   └── observation.images.cam_follower/
│       ├── episode_000000.mp4
│       └── ...
└── meta/
    ├── info.json                  (métadonnées du dataset)
    ├── tasks.jsonl                (5 tâches, une par position)
    ├── episodes.jsonl             (index des épisodes)
    └── consolidation_trace.json   (traçabilité)
```


### 🔧 Étape 1 : Consolidation du dataset (Script 9)

**Lancement**

```bash
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_9_dataset.py
```

**Déroulement**

Le script procède automatiquement :

1. **Analyse** — inventorie les épisodes dans chaque dossier de position
2. **Vérification** — confirme que chaque épisode a ses 2 vidéos (cam_top + cam_follower)
3. **Confirmation** — affiche le résumé et attend votre validation (Entrée)
4. **Consolidation** — fusionne les données :
   - Renumérotation séquentielle des épisodes (0, 1, 2, ...)
   - Mise à jour des index globaux dans chaque fichier parquet
   - Normalisation des timestamps (exactement 1/30s entre chaque frame)
   - Copie des vidéos avec renommage
   - Attribution d'une tâche par position
5. **Métadonnées** — génère `info.json`, `tasks.jsonl`, `episodes.jsonl`
6. **Résumé** — affiche les statistiques du dataset consolidé

**Sortie attendue**

```
📊 INVENTAIRE DES DONNÉES SOURCE
=======================================================
  ✅ Position 1 (Centre  ) : 11 épisodes
  ✅ Position 2 (Bas     ) : 10 épisodes
  ✅ Position 3 (Haut    ) : 10 épisodes
  ✅ Position 4 (Gauche  ) : 10 épisodes
  ✅ Position 5 (Droite  ) : 10 épisodes
-------------------------------------------------------
  Total : 51 épisodes | 26579 frames
=======================================================

  ✅ Toutes les vidéos sont présentes
```

> **💡 Note :** Si le dossier consolidé existe déjà, le script vous demande de taper **E** pour écraser ou **A** pour annuler.

**Tâches générées**

Le script crée automatiquement 5 tâches distinctes :

| Index | Tâche |
| :--- | :--- |
| 0 | Prendre le cube à la position Centre et le déposer dans la boîte |
| 1 | Prendre le cube à la position Bas et le déposer dans la boîte |
| 2 | Prendre le cube à la position Haut et le déposer dans la boîte |
| 3 | Prendre le cube à la position Gauche et le déposer dans la boîte |
| 4 | Prendre le cube à la position Droite et le déposer dans la boîte |

> **💡 Note :** L'objet manipulé est un prisme hexagonal ; il est désigné « cube » dans ces libellés de tâches (hérités du script 8).


### 🔍 Étape 2 : Vérification et visualisation (Script 10)

**Lancement**

```bash
python SEM_so101_10_visualize_dataset.py
```

**Déroulement**

Le script procède en plusieurs étapes automatiques :

1. **Vérification d'intégrité** — contrôle la structure du dataset (dossiers, fichiers parquet, vidéos, métadonnées)

2. **Résumé** — affiche les statistiques du dataset :
   ```
   📊 Épisodes : 51
   🎬 Frames   : 26579
   📄 Parquet  : 51 fichiers
   💾 Taille   : ~523 MB
   🎯 Tâches   : 5
   ⚡ FPS      : 30
   ```

3. **Complétion info.json** — ajoute automatiquement les champs manquants si nécessaire

4. **Génération des statistiques** — crée `episodes_stats.jsonl` avec les statistiques (mean, std, min, max) de chaque épisode pour chaque feature (observation.state, action, caméras)

   > Si le fichier existe déjà, le script demande : **R** pour regénérer ou **G** pour garder.

5. **Conversion vidéo** — convertit les vidéos du format mp4v vers H.264 pour la compatibilité navigateur (une seule fois, marqueur de conversion)

6. **Vérification frames/parquet** — confirme que le nombre de frames vidéo correspond aux lignes parquet pour chaque épisode

7. **Menu** — propose de lancer la visualisation ou quitter

**Visualisation dans le navigateur**

En choisissant **V**, le script lance l'outil officiel LeRobot `visualize_dataset_html.py` et démarre un serveur web local dans le terminal.

> **⚠️ IMPORTANT — l'ouverture du navigateur n'est PAS automatique.**
>
> Firefox ne s'ouvre **pas** tout seul. **Ouvrez Firefox manuellement**, puis **copiez-collez** l'adresse `http://127.0.0.1:9090` dans la barre d'adresse.
>
> *(Possible bug du script, à corriger ultérieurement ; en attendant, l'ouverture manuelle est nécessaire.)*

Une fois la page ouverte, l'interface affiche pour chaque épisode :

- Les flux vidéo des deux caméras (cam_top et cam_follower)
- Les courbes des 6 positions moteurs (observation.state)
- Les courbes des 6 actions (action)
- Les contrôles de lecture (play, pause, navigation)
- La liste de tous les épisodes dans le panneau gauche
- Pour arrêter le serveur : **Ctrl+C** dans le terminal

> **💡 Conseil :** Vérifiez quelques épisodes de chaque position. Assurez-vous que les vidéos sont fluides et que les mouvements des courbes correspondent aux gestes visibles dans les vidéos.


### ✅ Étape 3 : Validation du dataset

Avant de passer à l'entraînement, vérifiez les points suivants :

**Checklist de validation**

| Critère | Comment vérifier |
| :--- | :--- |
| Nombre d'épisodes correct | Résumé du script 10 (≥ 50) |
| Toutes les vidéos présentes | Pas d'erreur à la vérification d'intégrité |
| Vidéos fluides et bien cadrées | Visualisation dans le navigateur |
| Mouvements cohérents | Courbes moteurs lisses, pas de sauts |
| Les 5 positions couvertes | Vérifier des épisodes de chaque position |
| Fichiers meta complets | 4 ✅ dans la section métadonnées |

> **⚠️ Important :** Si vous constatez des épisodes de mauvaise qualité (geste raté, prisme tombé, mouvement parasite), vous pouvez les supprimer manuellement dans les dossiers source (`position_X_*/`) puis relancer le script 9 pour reconsolider.


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| "Dataset consolidé introuvable" | Script 9 non exécuté | Lancer d'abord le script 9 |
| "Aucun épisode trouvé" | Dossiers de position vides | Vérifier le script 8 a bien enregistré |
| Vidéos manquantes | Enregistrement incomplet | Réenregistrer les épisodes manquants |
| Erreur timestamps | Données non normalisées | Relancer le script 9 (il normalise automatiquement) |
| Visualisation ne s'ouvre pas | Serveur non démarré | Vérifier le terminal, ouvrir `http://127.0.0.1:9090` manuellement |
| Vidéos noires dans le navigateur | Codec incompatible | Le script 10 convertit automatiquement en H.264 |
| "episodes_stats.jsonl" manquant | Stats non générées | Relancer le script 10 (il le génère automatiquement s'il manque) |


### 📝 Récapitulatif des fichiers

| Fichier | Description | Créé par |
| :--- | :--- | :--- |
| `SEM_so101_9_dataset.py` | Consolidation du dataset | Script 9 |
| `SEM_so101_10_visualize_dataset.py` | Vérification et visualisation | Script 10 |
| `so101_pick_place_consolidated/` | Dataset unifié prêt pour l'entraînement | Script 9 |
| `meta/episodes_stats.jsonl` | Statistiques par épisode | Script 10 |
| `meta/consolidation_trace.json` | Traçabilité de la consolidation | Script 9 |


### 🚀 Commandes de référence rapide

```bash
# Consolidation
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_9_dataset.py

# Visualisation
python SEM_so101_10_visualize_dataset.py
```


### ✅ Notes finales

**✅ Phase 8 terminée quand :**

- Le dataset consolidé contient ≥ 50 épisodes
- Toutes les vidéos sont présentes (cam_top + cam_follower)
- Les statistiques sont générées (episodes_stats.jsonl)
- La visualisation dans le navigateur fonctionne
- Les vidéos et courbes moteurs sont cohérentes
- Vous avez validé visuellement la qualité des données

> **🚀 Objectif atteint :** Votre dataset est consolidé, vérifié et prêt pour l'entraînement du modèle ACT ! Passez à la Phase 9 pour former votre robot à reproduire vos gestes de manière autonome.

Service Écoles-Médias — DIP Genève
Guide Phase 8 — Version 1.0
