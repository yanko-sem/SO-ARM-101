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
- **Module de configuration caméra** `SEM_8_camera_config.py` présent dans le
  dossier des scripts (réglage et verrouillage des caméras)
- Outils système `v4l-utils` (commande `v4l2-ctl`) et `guvcview` installés
  (`sudo apt install v4l-utils guvcview`)

> **Note :** Cette phase utilise le script `SEM_so101_8_record_dataset.py`
> (enregistrement bi-caméra du dataset), qui s'appuie sur le module
> `SEM_8_camera_config.py` pour régler et verrouiller les caméras.


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
| 2 - Libre | Au choix | Position libre |
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

> **🔑 Ordre du démarrage (important).** Les caméras sont **identifiées et
> réglées d'abord** (avant les robots), puis le masque globale est chargé ;
> ensuite seulement les robots sont identifiés et mis au repos, et les
> caméras sont connectées puis verrouillées juste avant la téléopération. Le
> déroulé est donc :
>
> **caméras (identification + réglages) → masque globale → robots
> (identification) → disposition → repos → connexion + verrouillage des
> caméras → téléopération.**

Au lancement, le script vérifie d'abord les **calibrations** Leader et
Follower (Phase 3) et refuse de démarrer si elles sont absentes ou invalides.
Le déroulement est ensuite le suivant.

**1. Identification des caméras**

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
> Les **deux** caméras (globale + pince) sont obligatoires : sans les deux,
> le script s'arrête.

**2. Réglage des deux caméras**

Une fois les caméras identifiées, le script règle **chaque caméra** (d'abord
la GLOBALE `[1/2]`, puis la PINCE `[2/2]`) via le module
`SEM_8_camera_config.py`. Pour chacune :

- Il affiche les réglages déjà enregistrés (`camera_settings.json`).
- Si des réglages existent : `[Entrée]` pour les garder, `[R]` pour les
  refaire.
- Refaire ouvre **guvcview** : décochez « Auto » pour l'exposition, ajustez
  l'exposition et la balance des blancs, puis fermez guvcview. Le script
  relit les valeurs (via `v4l2-ctl`), vous les confirmez, et elles sont
  enregistrées.

Le but est de **figer l'exposition et la balance des blancs** pour que tous
les épisodes soient visuellement cohérents (condition importante pour que le
modèle apprenne bien). Ces réglages seront **verrouillés** sur les caméras
plus loin, juste avant la téléopération.

> **⚠️ Réglez les caméras une seule fois, puis gardez les mêmes réglages.**
> Si vous changez l'exposition ou la balance des blancs entre deux sessions,
> les images ne seront plus cohérentes avec le reste du dataset.

**3. Masque de zone utile (globale)**

Le script charge le masque de la caméra globale (`camera_mask.json`, créé en
Phase 6). Il est **obligatoire** : sans masque valide, l'enregistrement
s'arrête (relancez le script 7, Phase 6, pour le créer). Le masque est
appliqué à la vue globale — seule la zone utile (le plateau) est enregistrée.

**4. Identification des robots**

Le script identifie ensuite le Leader et le Follower (même processus que les
scripts 5 et 6 : débrancher, brancher, valider par test de la pince), puis
demande la disposition :

| Touche | Disposition |
| :--- | :--- |
| C + Entrée | Robots **C**ôte à côte |
| F + Entrée | Robots en **F**ace à face |

La configuration du mode choisi (créée en Phase 5) est **obligatoire** : si
elle est absente ou invalide, le script s'arrête.

**5. Repos, puis connexion et verrouillage des caméras**

Le script place automatiquement les deux robots en position de repos, puis
**libère le Leader** (le Follower reste actif). Il connecte ensuite les deux
caméras (en vérifiant la résolution 640×360) et **verrouille** leurs réglages
(via `v4l2-ctl`). La téléopération démarre alors : le script affiche **« Tenez
le LEADER »** et laisse 2 secondes pour saisir le Leader avant d'ouvrir le
menu d'enregistrement.


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
  script demande ensuite **quelle position** (Centre, Libre, Haut, Gauche,
  Droite).

**Processus d'un épisode**

À l'entrée d'un bloc, les deux bras sont **rigides au repos** et la
téléopération est en pause (mains libres pour placer le cube). L'écran
d'attente propose :

| Touche | Action |
| :--- | :--- |
| D | **D**émarrer l'enregistrement (cube placé, Leader en main) |
| R | **R**epositionner les robots au repos |
| S | **S**topper la session (revenir au menu) |

1. Placez le cube sur la position demandée
2. Prenez le Leader en main, puis appuyez sur **D** pour démarrer
3. Téléopérez : guidez le Leader pour que le Follower saisisse le cube et le
   dépose dans la boîte
4. Terminez avec **T** (succès, données sauvegardées)

Pendant l'enregistrement :

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
| 2 - Libre | 10 épisodes | Varier l'approche |
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
├── position_2_libre/
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
| Vidéos vides | Flux caméra absent, ou écriture OpenCV (`VideoWriter`, codec `mp4v`) en échec | Vérifier que les deux caméras fournissent des images et qu'OpenCV peut écrire un `.mp4` |
| Robots ne s'identifient pas | Branchement incorrect | Suivre l'ordre : débrancher tout, brancher Leader d'abord |
| Erreur "import cv2" | Mauvais environnement | `conda activate lerobot` |
| Fenêtre vidéo ne s'ouvre pas | opencv-python-headless | Voir Phase 6, Étape 2 |
| « Masque globale introuvable » au lancement | `camera_mask.json` absent | Lancer le script 7 (Phase 6) pour créer le masque |
| Image trop claire/sombre ou couleurs fausses | Exposition/balance des blancs mal réglées | Au réglage de la caméra, choisir `[R]` (guvcview) et réajuster |
| « Verrouillage caméra incomplet » | `v4l2-ctl` absent ou contrôle non appliqué | Installer `v4l-utils` ; vérifier la caméra ; relancer |


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
| `SEM_8_camera_config.py` | Module de configuration caméra (réglage + verrouillage) | Sous-projet caméra |
| `position_X_*/` | Dossiers de données par position | Script 8 |
| `~/lerobot/calibration/camera_settings.json` | Réglages des 2 caméras (exposition / balance des blancs) | Réglage caméra |
| Fichiers Phase 6 inchangés | Configuration caméra et calibration | Phases 3-6 |

Service Écoles-Médias — DIP Genève
Guide Phase 7 — Version 1.2 (enregistrement bi-caméra ; réglage + verrouillage caméra)
