# Guide Enregistrement de Dataset SO-ARM 101

## Phase 7 : Capture de démonstrations pour l'apprentissage par imitation

Service Écoles-Médias (SEM)

### 🧩 Scripts utilisés

- `SEM_so101_8_record_dataset.py` — enregistrement du dataset bi-caméra avec téléopération Leader → Follower, réglage et contrôle image des caméras, et sauvegarde au format LeRobotDataset v2.1.
- `SEM_so101_camera_auto.py` — réglage caméra en **exposition (et balance des blancs) auto puis figée** (via `v4l2-ctl`) et **contrôle image simple** (plancher physique de lumière sur l'image brute).

### 📋 Prérequis

- Phases 1 à 6 complétées
- Téléopération avec caméra fonctionnelle (Phase 6 validée)
- 2 caméras USB disponibles (cam_top + cam_follower)
- Supports de fixation stables pour les 2 caméras
- Environnement lerobot activé
- Objet de manipulation : un prisme hexagonal (désigné « cube » dans le dataset) et une boîte (ou récipient)
- **Masque de la caméra globale** créé en Phase 6 (`camera_mask.json`) —
  obligatoire : l'enregistrement s'arrête sans lui
- **Module caméra** `SEM_so101_camera_auto.py` (réglage exposition auto puis
  figée + contrôle image) présent dans le dossier des scripts
- Outil système `v4l-utils` (commande `v4l2-ctl`) installé
  (`sudo apt install v4l-utils`)


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

- Diffus, sans ombres dures ni reflets marqués, sans contre-jour
- **Stable pendant une session** : au démarrage, l'exposition de chaque caméra
  s'ajuste automatiquement à la lumière ambiante puis est **figée** — évitez donc
  de changer l'éclairage en cours de session
- **Pas besoin d'un éclairage identique d'une session à l'autre** : au contraire,
  enregistrer sous des lumières variées (selon l'heure, la saison, la salle) aide
  le modèle à **généraliser**. La seule exigence est de rester dans des conditions
  exploitables (ni image cramée, ni image écrasée), ce que le contrôle image
  vérifie au démarrage et avant chaque bloc

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

> **🔑 Ordre du démarrage (important).** Contrairement à une intuition
> « caméras d'abord », le script suit cet ordre précis :
>
> **calibrations → vérification du module caméra → masque globale →
> identification des robots → choix du mode + configuration → mise au repos →
> identification des deux caméras → connexion des caméras → réglage exposition
> (auto puis figée) → contrôle image → libération du Leader → téléopération.**
>
> L'**identification des caméras et leur réglage arrivent _après_ la mise au
> repos des robots** : la vue de la caméra Pince dépend de la pose du bras, donc
> la scène doit être dans sa posture standard (repos) pour régler et contrôler
> l'image.

**1. Calibrations et module caméra**

Au lancement, le script vérifie d'abord les **calibrations** Leader et Follower
(Phase 3) et refuse de démarrer si elles sont absentes ou invalides. Il vérifie
ensuite que le **module caméra** est présent et s'arrête sinon (*fail-closed*) :

- `SEM_so101_camera_auto.py` — pour régler l'exposition (auto puis figée) et
  contrôler l'image de chaque caméra. Sans lui, le script ne peut ni régler ni
  contrôler les caméras, et s'arrête.

**2. Masque de zone utile (globale)**

Le script charge le masque de la caméra globale (`camera_mask.json`, créé en
Phase 6). Il est **obligatoire** : sans masque valide, l'enregistrement s'arrête
(relancez le script 7, Phase 6). Seule la zone utile (le plateau) sera
enregistrée et mesurée.

**3. Identification des robots, mode et configuration**

Le script identifie le Leader et le Follower (même processus que les scripts 5
et 6 : débrancher, brancher, valider par le test de la pince), puis demande la
disposition :

| Touche | Disposition |
| :--- | :--- |
| C + Entrée | Robots **C**ôte à côte |
| F + Entrée | Robots en **F**ace à face |

La configuration du mode choisi (créée en Phase 5) est **obligatoire** : si elle
est absente ou invalide, le script s'arrête (relancez le script 5).

**4. Mise au repos**

Le script place automatiquement les deux robots en **position de repos**
(séquence sûre). Cette posture standard sert de référence pour les caméras à
l'étape suivante.

**5. Identification des deux caméras (après le repos)**

Le script affiche une fenêtre vidéo **live** pour chaque caméra détectée, l'une
après l'autre. Pour chacune, indiquez son rôle **directement dans la fenêtre**
(pas au terminal) :

| Touche (dans la fenêtre) | Action |
| :--- | :--- |
| G | Vue **G**lobale (cam_top) |
| P | Vue **P**ince (cam_follower) |
| Q | Passer cette caméra (ni l'une ni l'autre) |
| Échap | Tout annuler |

> **💡 Conseil :** Les numéros `/dev/videoX` changent d'un branchement à
> l'autre, d'où cette identification manuelle à chaque session. Les **deux**
> caméras (globale + pince) sont obligatoires : sans les deux, le script
> s'arrête.

**6. Connexion des caméras, réglage de l'exposition et contrôle image**

Les robots **restent au repos**. Le script **connecte** les deux caméras et
vérifie leur résolution **640×360** (il s'arrête si elle est incorrecte). Puis,
pour chaque caméra (Globale puis Pince) :

- **Réglage de l'exposition — auto puis figée.** Le pilote laisse l'exposition
  (et la balance des blancs) s'ajuster automatiquement à la lumière réelle de la
  salle pendant quelques secondes, flux actif, puis **fige** la valeur trouvée
  pour toute la session (fréquence secteur réglée sur 50 Hz, anti-scintillement).
  Si un réglage ne peut pas être appliqué, l'enregistrement **s'arrête**
  (*fail-closed*).
- **Contrôle image (plancher physique).** Le script mesure l'image **brute**
  (avant masque) et rend un verdict de lumière :

| Verdict | Signification | Choix proposés (dans la fenêtre) |
| :--- | :--- | :--- |
| 🟢 | Lumière exploitable | continue automatiquement |
| 🟠 | Lumière limite (image un peu sombre ou un peu claire) | `C` continuer / `R` re-régler / `Q` annuler |
| 🔴 | Image inexploitable (cramée ou écrasée) | `R` re-régler / `Q` annuler (pas de `C`) |

La mesure porte sur la **zone utile du masque** pour la Globale (le plateau) et
sur le **plein cadre** pour la Pince. La touche `R` relance le réglage
« exposition auto puis figée » (après, par exemple, avoir ajusté la lumière de
la salle). L'**enregistrement ne démarre que si les deux caméras sont
autorisées** (🟢, ou 🟠 accepté avec `C`).

> **💡 Pourquoi « auto puis figée » plutôt qu'un réglage fixe ?** L'éclairage
> d'une salle de classe ne se contrôle pas (heure, saison, emplacement). Plutôt
> que d'imposer des réglages fixes, chaque caméra s'adapte à la lumière du moment
> puis **fige** son exposition pour que **tous les épisodes d'une même session**
> soient cohérents. La robustesse à la variété d'éclairage vient d'enregistrer des
> démonstrations sous des lumières **variées mais exploitables** — une augmentation
> d'éclairage à l'entraînement pourra la renforcer lorsqu'elle sera activée dans le
> script 10.

**7. Caméras prêtes, libération du Leader**

Une fois les deux caméras réglées et contrôlées, le script affiche
**« Caméras prêtes (exposition réglée) »** et demande d'appuyer sur **Entrée**
pour libérer le Leader et lancer la téléopération. Le Leader est alors
**libéré** (le Follower reste actif), puis la téléopération démarre.

**8. Téléopération**

La téléopération démarre : le script affiche **« Tenez le LEADER »**, laisse 2
secondes pour saisir le Leader, puis ouvre le menu d'enregistrement (Étape 4).

> **🛡️ À retenir :** avant **chaque** série d'épisodes, le script recontrôlera
> automatiquement l'image des deux caméras (voir Étape 4). L'enregistrement
> n'est pas un simple « appuyer pour filmer » : c'est un processus qui protège la
> qualité du dataset.


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

> **🛡️ Contrôle image avant chaque série (important).** Avant le **Test
> rapide** comme avant un **bloc de 10 épisodes**, le script ramène les robots
> au repos et **contrôle l'image des deux caméras** (la Globale puis la Pince).
> Le verdict est gradué : 🟢 lumière exploitable → enregistrement autorisé ;
> 🟠 lumière limite → autorisé après confirmation (`C`) ou re-réglage (`R`) ;
> 🔴 image inexploitable (cramée ou écrasée) → **bloqué**, avec re-réglage `R`
> proposé (pas de passage en force). **L'enregistrement n'est jamais autorisé à
> l'aveugle** : si une caméra n'est pas exploitable, le bloc est annulé. C'est un
> verrou de qualité du dataset, pas un simple confort.

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


### 🔍 Étape 5 : Vérification des données

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
| Image trop claire (🔴 cramée) ou trop sombre (🔴 écrasée) | Lumière trop forte / trop faible dans la salle | Ajuster la lumière de la salle, puis `R` pour relancer le réglage « exposition auto puis figée » |
| Contrôle image 🟠 persistant | Lumière limite (un peu sombre ou un peu claire) | `C` pour continuer, ou ajuster la lumière puis `R` pour re-régler |
| « réglage d'exposition non appliqué » → arrêt | `v4l2-ctl` absent, ou contrôle refusé par le pilote | Installer `v4l-utils` ; vérifier la caméra ; relancer |
| Module `SEM_so101_camera_auto.py` absent | Module manquant dans le dossier | Le script s'arrête au démarrage : placer le module dans le dossier des scripts |


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


### 📝 Notes finales

**✅ Phase 7 terminée quand :**

- Les 50 épisodes sont enregistrés (10 par position)
- Les 2 caméras ont fonctionné pour chaque épisode
- L'exposition des deux caméras a été réglée et les contrôles image avant bloc ont autorisé les enregistrements
- Les vidéos sont en résolution 640×360 (16:9)
- Les données parquet sont cohérentes
- Vous avez vérifié visuellement quelques vidéos

> **🚀 Objectif atteint :** Votre dataset de démonstrations est complet ! 50 épisodes de la tâche "pick and place" sont prêts à être consolidés et utilisés pour l'entraînement. Passez à la Phase 8 pour fusionner les données et préparer l'entraînement.

**📝 Récapitulatif des fichiers**

| Fichier | Description | Créé / utilisé par |
| :--- | :--- | :--- |
| `SEM_so101_8_record_dataset.py` | Script d'enregistrement bi-caméra | Phase 7 |
| `SEM_so101_camera_auto.py` | Module : réglage exposition (auto puis figée) + contrôle image | Scripts 8 et 11 |
| `position_X_*/` | Dossiers de données par position | Script 8 |
| `~/lerobot/calibration/camera_mask.json` | Masque de la zone utile (caméra globale) | Script 7 (Phase 6) |
| Fichiers Phases 3-6 inchangés | Calibration, repos, configuration téléop, masque | Phases 3-6 |
