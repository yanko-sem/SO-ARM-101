# Guide Enregistrement de Dataset SO-ARM 101

## Phase 7 : Capture de démonstrations pour l'apprentissage par imitation

Service Écoles-Médias (SEM) — DIP Genève

### ✅ Prérequis

- Phases 1 à 6 complétées
- Téléopération avec caméra fonctionnelle (Phase 6 validée)
- 2 caméras USB disponibles (cam_top + cam_follower)
- Supports de fixation stables pour les 2 caméras
- Environnement lerobot activé
- Objet de manipulation : un cube et une boîte (ou récipient)


### 🎯 Objectif de cette phase

**Pourquoi enregistrer un dataset ?** L'apprentissage par imitation nécessite des démonstrations humaines. En téléopérant le robot (le Leader guide le Follower), on enregistre simultanément les positions des moteurs et les images des caméras. Ces données serviront à entraîner un modèle d'IA qui reproduira les gestes de manière autonome.

L'enregistrement permet de :

- Capturer des démonstrations de la tâche "pick and place"
- Enregistrer 2 flux vidéo simultanés (vue d'ensemble + vue pince)
- Varier les positions de départ du cube pour la généralisation
- Produire un dataset au format LeRobotDataset v2.1


### 📷 Étape 1 : Installation des 2 caméras

**Positionnement des caméras**

| Caméra | Nom | Position | Rôle |
| :--- | :--- | :--- | :--- |
| Caméra Globale | cam_top | Au-dessus de l'espace de travail, 40-60cm, angle 45-60° | Vue d'ensemble de la scène |
| Caméra Pince | cam_follower | Montée sur le Follower (servo 5 ou support pince) | Vue rapprochée de la manipulation |

> **💡 Conseil :** Fixez solidement les caméras. Elles ne doivent pas bouger pendant toute la session d'enregistrement. La position des caméras devra être identique lors du déploiement autonome (Phase 10).

**Vérification des connexions**

```bash
# Vérifier que les 2 caméras sont détectées
ls /dev/video*

# Résultat attendu : au moins 2 devices vidéo
# /dev/video0 /dev/video1 /dev/video2 /dev/video3
# Note : chaque caméra crée souvent 2 devices
```

> **⚠️ Important :** Branchez chaque caméra sur un port USB différent pour éviter les conflits de bande passante.


### 🎯 Étape 2 : Préparation de la scène

**Espace de travail**

1. Placez le Follower au centre de l'espace de travail
2. Placez la boîte (récipient) à portée du bras
3. Marquez 5 positions pour le cube :

| Position | Emplacement | Description |
| :--- | :--- | :--- |
| 1 - Centre | Devant le robot | Position de référence |
| 2 - Bas | Plus près du robot | Accès facile |
| 3 - Haut | Plus loin du robot | Extension du bras |
| 4 - Gauche | Côté gauche | Rotation latérale |
| 5 - Droite | Côté droit | Rotation latérale |

> **💡 Astuce :** Marquez les 5 positions au feutre ou avec du ruban adhésif. Vous devrez replacer le cube exactement au même endroit pour chaque épisode d'une position.

**Éclairage**

- Éclairage constant et diffus
- Pas d'ombres dures ni de reflets
- Pas de contre-jour
- Reproductible (même éclairage à chaque session)

**Arrière-plan**

- Fixe et contrasté
- Pas d'éléments mobiles dans le champ
- Simple (pas de motifs complexes)


### 🎮 Étape 3 : Lancement du script d'enregistrement (Script 8)

**Lancement**

```bash
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_8_record_dataset.py
```

**Phase d'identification des caméras**

Au lancement, le script affiche une fenêtre vidéo pour chaque caméra détectée. Pour chacune, vous devez indiquer quel rôle elle joue :

```
╔══════════════════════════════════════════════════════════╗
║     IDENTIFICATION DES CAMÉRAS                           ║
╚══════════════════════════════════════════════════════════╝

Camera 0 :
Répondez dans le TERMINAL
```

| Touche | Action |
| :--- | :--- |
| G + Entrée | Cette caméra est la vue **G**lobale (cam_top) |
| P + Entrée | Cette caméra est la vue **P**ince (cam_follower) |
| Q + Entrée | Passer cette caméra (ce n'est ni l'une ni l'autre) |

> **💡 Conseil :** Regardez la fenêtre vidéo qui s'affiche et identifiez ce qu'elle montre. Si vous voyez la vue d'ensemble, tapez G. Si vous voyez la pince de près, tapez P.

**Phase d'identification des robots**

Le script identifie ensuite le Leader et le Follower avec le même processus que les scripts 5 et 6 (débrancher, brancher, valider par test de la pince).

**Phase de positionnement**

Le script positionne automatiquement les robots (centrage puis repos).


### 🎬 Étape 4 : Enregistrement des épisodes

**Choix de la position**

Le script vous demande de choisir la position du cube :

```
╔══════════════════════════════════════════════════════════╗
║     CHOIX DE LA POSITION                                 ║
╠══════════════════════════════════════════════════════════╣
║  1. Centre                                               ║
║  2. Bas                                                  ║
║  3. Haut                                                 ║
║  4. Gauche                                               ║
║  5. Droite                                               ║
╚══════════════════════════════════════════════════════════╝
```

**Processus d'enregistrement**

Pour chaque épisode :

1. Placez le cube sur la position choisie
2. Appuyez sur **D** pour démarrer l'enregistrement
3. Téléopérez : guidez le Leader pour que le Follower saisisse le cube et le dépose dans la boîte
4. Appuyez sur **T** pour terminer l'épisode (succès)

| Touche | Action |
| :--- | :--- |
| D | **D**émarrer l'enregistrement |
| T | **T**erminer l'épisode (succès, les données sont sauvegardées) |
| A | **A**nnuler l'épisode en cours (données supprimées, recommencer) |
| S | **S**topper la session (passer à une autre position ou quitter) |
| Q | **Q**uitter le programme |

**Pendant l'enregistrement :**

- Les 2 fenêtres vidéo affichent les flux en temps réel
- Les positions des 6 moteurs sont enregistrées à 30 FPS
- Les 2 flux vidéo sont enregistrés simultanément

> **⚠️ Important :** Si vous ratez un geste (cube tombé, mouvement parasité), appuyez sur **A** pour annuler. Mieux vaut un épisode annulé qu'un épisode de mauvaise qualité dans le dataset.

**Plan d'enregistrement recommandé**

| Position | Épisodes | Objectif |
| :--- | :--- | :--- |
| 1 - Centre | 10 épisodes | Position de référence |
| 2 - Bas | 10 épisodes | Varier l'approche |
| 3 - Haut | 10 épisodes | Tester l'extension |
| 4 - Gauche | 10 épisodes | Rotation latérale |
| 5 - Droite | 10 épisodes | Rotation latérale |
| **Total** | **50 épisodes** | **Dataset complet** |

> **💡 Conseil :** Faites les 10 épisodes d'une position avant de passer à la suivante. Essayez de varier légèrement vos gestes (vitesse, trajectoire) pour que le modèle apprenne à généraliser.


### ✅ Étape 5 : Vérification des données

**Vérification rapide après chaque position**

```bash
# Compter les épisodes par position
for i in 1 2 3 4 5; do
    count=$(find ~/.cache/huggingface/lerobot/local/so101_pick_place/position_${i}_* -name "*.parquet" 2>/dev/null | wc -l)
    echo "Position $i : $count épisodes"
done
```

Résultat attendu :

```
Position 1 : 10 épisodes
Position 2 : 10 épisodes
Position 3 : 10 épisodes
Position 4 : 10 épisodes
Position 5 : 10 épisodes
```

**Vérification de la résolution vidéo**

```bash
conda activate lerobot
python3 -c "
import cv2, os
v = cv2.VideoCapture(os.path.expanduser('~/.cache/huggingface/lerobot/local/so101_pick_place/position_1_centre/videos/chunk-000/observation.images.cam_top/episode_000000.mp4'))
w = int(v.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(v.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f'Resolution: {w}x{h}')
v.release()
"
```

Résultat attendu : `Resolution: 640x360`

**Données enregistrées par épisode**

Chaque épisode produit :

| Fichier | Contenu |
| :--- | :--- |
| `episode_NNNNNN.parquet` | Positions moteurs (observation.state) + actions, 30 FPS |
| `observation.images.cam_top/episode_NNNNNN.mp4` | Vidéo de la vue d'ensemble |
| `observation.images.cam_follower/episode_NNNNNN.mp4` | Vidéo de la vue pince |


### 📁 Structure des données enregistrées

```
~/.cache/huggingface/lerobot/local/so101_pick_place/
├── position_1_centre/
│   ├── data/chunk-000/
│   │   ├── episode_000000.parquet
│   │   └── ...
│   └── videos/chunk-000/
│       ├── observation.images.cam_top/
│       │   ├── episode_000000.mp4
│       │   └── ...
│       └── observation.images.cam_follower/
│           ├── episode_000000.mp4
│           └── ...
├── position_2_bas/
│   └── ...
├── position_3_haut/
│   └── ...
├── position_4_gauche/
│   └── ...
└── position_5_droite/
    └── ...
```


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| Caméra non détectée | Pas dans le groupe `video` | `sudo usermod -a -G video $USER` puis déconnexion/reconnexion |
| Image rognée (pas de bords) | Mauvaise résolution | Vérifier `camera_height: 360` dans le script |
| Fenêtre vidéo noire | Mauvais index caméra | Passer la caméra avec Q et identifier la suivante |
| Touche D ne réagit pas | Focus sur la mauvaise fenêtre | Cliquer dans le terminal avant de taper |
| Épisode très court | T appuyé trop tôt | Annuler avec A, recommencer |
| Vidéos vides | ffmpeg manquant | `ffmpeg -version`, installer si absent |
| Robots ne s'identifient pas | Branchement incorrect | Suivre l'ordre : débrancher tout, brancher Leader d'abord |
| Erreur "import cv2" | Mauvais environnement | `conda activate lerobot` |
| Fenêtre vidéo ne s'ouvre pas | opencv-python-headless | Voir Phase 6, Étape 2 |


### 💡 Conseils pour des enregistrements de qualité

1. **Régularité :** Essayez d'avoir des gestes similaires en durée (8-15 secondes par épisode)
2. **Fluidité :** Mouvements continus, pas de pauses ni de saccades
3. **Variabilité :** Variez légèrement la trajectoire entre chaque épisode d'une même position
4. **Début et fin clairs :** Partez toujours de la position repos et terminez avec le cube dans la boîte
5. **Pas de précipitation :** Un geste calme et maîtrisé vaut mieux qu'un geste rapide et imprécis
6. **Annuler plutôt que garder :** Si le geste est raté (cube tombé, mauvaise saisie), appuyez sur A
7. **Pauses :** Faites des pauses entre les positions pour éviter la fatigue


### 🚀 Commandes de référence rapide

```bash
# Lancement
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_8_record_dataset.py

# Vérification après enregistrement
for i in 1 2 3 4 5; do
    count=$(find ~/.cache/huggingface/lerobot/local/so101_pick_place/position_${i}_* -name "*.parquet" 2>/dev/null | wc -l)
    echo "Position $i : $count épisodes"
done
```


### ✅ Notes finales

**✅ Phase 7 terminée quand :**

- Les 50 épisodes sont enregistrés (10 par position)
- Les 2 caméras ont fonctionné pour chaque épisode
- Les vidéos sont en résolution 640×360 (16:9)
- Les données parquet sont cohérentes
- Vous avez vérifié visuellement quelques vidéos

> **🚀 Objectif atteint :** Votre dataset de démonstrations est complet ! 50 épisodes de la tâche "pick and place" sont prêts à être consolidés et utilisés pour l'entraînement. Passez à la Phase 8 pour fusionner les données et préparer l'entraînement.

**📝 Récapitulatif des fichiers**

| Fichier | Description | Créé par |
| :--- | :--- | :--- |
| `SEM_so101_8_record_dataset.py` | Script d'enregistrement | Phase 7 |
| `position_X_*/` | Dossiers de données par position | Script 8 |
| Fichiers Phase 6 inchangés | Configuration caméra et calibration | Phases 3-6 |

Service Écoles-Médias — DIP Genève
Guide Phase 7 — Version 1.0
