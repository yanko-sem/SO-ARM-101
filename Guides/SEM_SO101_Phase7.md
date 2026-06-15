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
- **Masque de la caméra globale** créé en Phase 6 (`camera_mask.json`) —
  obligatoire : l'enregistrement s'arrête sans lui
- **Module de référence visuelle** `SEM_so101_camera_reference.py` présent
  dans le dossier des scripts (contrôle des deux caméras)


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

> **🔑 Ordre du démarrage (important).** La vue de la caméra **pince**
> dépend de la position du bras. Pour que la référence de la pince
> corresponde à la scène réelle, **les robots sont mis au repos AVANT** la
> préparation des caméras, et ils y restent maintenus (rigides) pendant
> toute cette préparation. Le déroulé est donc :
>
> **robots → repos → caméras → menus de référence → récapitulatif →
> téléopération.**

**1. Identification des robots**

Le script identifie d'abord le Leader et le Follower (même processus que les
scripts 5 et 6 : débrancher, brancher, valider par test de la pince), puis
demande la disposition :

| Touche | Disposition |
| :--- | :--- |
| C + Entrée | Robots **C**ôte à côte |
| F + Entrée | Robots en **F**ace à face |

**2. Position de repos**

Le script place automatiquement les deux robots en position de repos. À
partir d'ici, **les deux bras restent rigides** jusqu'au menu de
téléopération — ne les forcez pas à la main.

**3. Identification des caméras**

Le script affiche une fenêtre vidéo pour chaque caméra détectée. Pour
chacune, indiquez son rôle **dans le terminal** :

| Touche | Action |
| :--- | :--- |
| G + Entrée | Cette caméra est la vue **G**lobale (cam_top) |
| P + Entrée | Cette caméra est la vue **P**ince (cam_follower) |
| Q + Entrée | Passer cette caméra (ce n'est ni l'une ni l'autre) |

> **💡 Conseil :** Regardez la fenêtre vidéo. Vue d'ensemble → G ; pince de
> près → P. Les numéros `/dev/videoX` changent d'un branchement à l'autre,
> c'est pourquoi cette identification manuelle est nécessaire à chaque fois.

> **📷 Premier lancement d'une caméra :** si une caméra n'a encore aucun
> réglage enregistré, le script propose une seule fois un réglage initial
> avec guvcview (papier blanc). Ensuite, le réglage « à l'œil » n'est plus
> proposé : tout passe par les menus de référence ci-dessous.

### 🎯 Étape 3 bis : Menus de référence des deux caméras

Une fois les caméras identifiées, le script ouvre **successivement le menu
de référence de chaque caméra** (d'abord la GLOBALE, puis la PINCE). Ce menu
remplace le réglage « à l'œil » : il mesure les conditions visuelles et les
compare à une **référence chiffrée**, pour que tous les épisodes du dataset
soient visuellement cohérents (condition importante pour que le modèle
apprenne bien).

Pour chaque caméra, le menu propose :

| Option | Rôle |
| :--- | :--- |
| 1 | Définir / redessiner les zones de mesure |
| 2 | Visualiser les zones actuelles |
| 3 | Mesurer en direct |
| 4 | Créer / remplacer la référence (scène standard requise) |
| 5 | Afficher la référence active |
| 6 | Diagnostic de conformité (vs référence active) |
| 7 | Recalibrer pour revenir à la référence (ajuster jusqu'à 🟢) |
| **S** | **Étape suivante** — passer à la caméra suivante, puis aux robots |

**Usage typique :**

- **Tout premier dataset** (aucune référence) : pour chaque caméra, dessinez
  les zones (option 1), puis créez la référence (option 4) avec la scène
  standard en place (robots au repos, bol vide, **pas de cube**). Puis `S`.
- **Sessions suivantes** (référence déjà créée) : faites un diagnostic
  (option 6). Si l'éclairage a changé (🟠 ou 🔴), recalibrez (option 7)
  jusqu'au 🟢. Puis `S`.

> **💡 La scène de référence est la même pour les deux caméras** : robots au
> repos, bol vide, **pas de cube** sur le plateau. La caméra globale utilise
> le masque ; la caméra pince mesure sur toute l'image (sa sentinelle de
> couleur est la pince verte, toujours visible).

> **⚠️ Ne réglez pas les caméras « à la main » après avoir créé la
> référence.** Si vous changez l'exposition ou la balance des blancs ensuite,
> l'image ne correspondra plus à la référence et le contrôle bloquera. Les
> réglages se décident **une fois**, au moment de créer la référence.

**Récapitulatif avant / après**

Après les deux menus, le script affiche un **récapitulatif** des deux
caméras : date de leur référence et réglages, avec mention « ← modifié » sur
ce qui a changé pendant les menus. Appuyez sur Entrée pour **libérer le
Leader** et démarrer la téléopération.


### 🎬 Étape 4 : Enregistrement des épisodes

La téléopération est maintenant active (le Follower suit le Leader). Le menu
principal propose :

```
║  1. 📖 Lire les instructions                          ║
║  2. 🧪 Test rapide (2 épisodes)                       ║
║  3. 📹 Enregistrer 10 épisodes pour une position      ║
║  4. 👁️  Visualiser vos datasets                       ║
║  5. 🗑️  Effacer des données                           ║
║  6. 🏁 Repositionner le robot à repos                 ║
║  Q. 🚪 Quitter (affiche le résumé)                    ║
```

- **Option 2 — Test rapide** : enregistre 2 épisodes (pour se familiariser
  ou vérifier la chaîne complète).
- **Option 3 — Enregistrer 10 épisodes** : le bloc normal d'une position. Le
  script demande ensuite **quelle position** (Centre, Bas, Haut, Gauche,
  Droite).

> **📷 Contrôle caméra avant chaque bloc.** Que vous lanciez un test rapide
> (2 épisodes) ou un bloc de 10, le script contrôle d'abord **les deux
> caméras** (globale puis pince) par rapport à leur référence. Les robots
> sont remis au repos le temps du contrôle. **L'enregistrement ne démarre
> que si les deux caméras sont conformes.** Si une caméra n'est pas conforme,
> l'option **[M]** ouvre son menu de référence pour recalibrer, puis le
> contrôle est refait.

**Processus d'un épisode**

1. Placez le cube sur la position demandée
2. L'enregistrement démarre (les robots reviennent d'abord au repos)
3. Téléopérez : guidez le Leader pour que le Follower saisisse le cube et le
   dépose dans la boîte
4. Terminez avec **T** (succès, données sauvegardées)

Pendant un épisode :

| Touche | Action |
| :--- | :--- |
| T | **T**erminer + sauvegarder (les robots reviennent au repos, hors enregistrement) |
| A | **A**nnuler l'épisode en cours (données supprimées, on recommence) |
| S | **S**topper la session (revenir au menu) |

> **⚠️ Important :** Si vous ratez un geste (cube tombé, mouvement parasite),
> appuyez sur **A** pour annuler. Mieux vaut un épisode annulé qu'un épisode
> de mauvaise qualité dans le dataset.

> **💡 À la fin d'un épisode (T), les deux bras restent rigides au repos et
> la téléopération ne reprend pas tout de suite** : vous pouvez replacer le
> cube tranquillement avant l'épisode suivant.

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
| « Masque globale introuvable » au lancement | `camera_mask.json` absent | Lancer le script 7 (Phase 6) pour créer le masque |
| Bloc refusé : contrôle caméra non conforme | Éclairage différent de la référence | Option [M] → recalibrer (option 7) jusqu'au 🟢 |
| « Réglages non verrouillés » dans un menu de référence | Caméra sans réglages valides | Option [R] dans le menu pour (re)faire les réglages |


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
| `SEM_so101_camera_reference.py` | Module de référence visuelle (contrôle des 2 caméras) | Sous-projet caméra |
| `position_X_*/` | Dossiers de données par position | Script 8 |
| `~/lerobot/calibration/camera_reference_*` | Références visuelles actives des 2 caméras | Menus de référence |
| Fichiers Phase 6 inchangés | Configuration caméra et calibration | Phases 3-6 |

Service Écoles-Médias — DIP Genève
Guide Phase 7 — Version 1.1 (enregistrement bi-caméra + référence visuelle)
