# Guide Enregistrement de Dataset SO-ARM 101

## Phase 7 : Capture de démonstrations pour l'apprentissage par imitation

Service Écoles-Médias (SEM)

### 🧩 Scripts utilisés

- `SEM_so101_8_record_dataset.py` — enregistrement du dataset bi-caméra avec téléopération Leader → Follower, contrôle qualité caméra et sauvegarde au format LeRobotDataset v2.1.
- `SEM_so101_camera_config.py` — verrouillage matériel des réglages caméra (exposition, balance des blancs, gain) via `v4l2-ctl` et `guvcview`.
- `SEM_so101_camera_reference.py` — création et contrôle des références visuelles des deux caméras : zones, référence active, diagnostic, recalibrage et contrôle avant enregistrement.

### 📋 Prérequis

- Phases 1 à 6 complétées
- Téléopération avec caméra fonctionnelle (Phase 6 validée)
- 2 caméras USB disponibles (cam_top + cam_follower)
- Supports de fixation stables pour les 2 caméras
- Environnement lerobot activé
- Objet de manipulation : un cube et une boîte (ou récipient)
- **Masque de la caméra globale** créé en Phase 6 (`camera_mask.json`) —
  obligatoire : l'enregistrement s'arrête sans lui
- **Modules caméra** `SEM_so101_camera_config.py` (réglage et verrouillage) et
  `SEM_so101_camera_reference.py` (références visuelles et contrôle qualité)
  présents dans le dossier des scripts
- Outils système `v4l-utils` (commande `v4l2-ctl`) et `guvcview` installés
  (`sudo apt install v4l-utils guvcview`)


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

> **🔑 Ordre du démarrage (important).** Contrairement à une intuition
> « caméras d'abord », le script suit cet ordre précis :
>
> **calibrations → vérification des modules caméra → masque globale →
> identification des robots → choix du mode + configuration → mise au repos →
> identification des deux caméras → menus de référence caméra → libération du
> Leader → connexion + verrouillage des caméras → téléopération.**
>
> L'**identification des caméras et leurs menus de référence arrivent _après_
> la mise au repos des robots** : la vue de la caméra Pince dépend de la pose
> du bras, donc la scène doit être dans sa posture standard (repos) pour
> préparer des références fiables.

**1. Calibrations et modules caméra**

Au lancement, le script vérifie d'abord les **calibrations** Leader et Follower
(Phase 3) et refuse de démarrer si elles sont absentes ou invalides. Il vérifie
ensuite que les **deux modules caméra** sont présents et s'arrête sinon
(*fail-closed*) :

- `SEM_so101_camera_config.py` — pour figer puis verrouiller les réglages
  caméra (sans lui, on enregistrerait en auto-exposition, incohérent avec le
  déploiement) ;
- `SEM_so101_camera_reference.py` — pour contrôler la conformité visuelle des
  images (sans lui, impossible de garantir que les images correspondent à la
  référence du dataset).

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

Le script affiche une fenêtre vidéo pour chaque caméra détectée. Pour chacune,
indiquez son rôle **dans le terminal** :

| Touche | Action |
| :--- | :--- |
| G + Entrée | Vue **G**lobale (cam_top) |
| P + Entrée | Vue **P**ince (cam_follower) |
| Q + Entrée | Passer cette caméra (ni l'une ni l'autre) |

> **💡 Conseil :** Les numéros `/dev/videoX` changent d'un branchement à
> l'autre, d'où cette identification manuelle à chaque session. Les **deux**
> caméras (globale + pince) sont obligatoires : sans les deux, le script
> s'arrête.

**6. Menus de référence caméra (cam_top, puis cam_follower)**

Les robots **restent au repos** pendant que le script ouvre un **menu de
référence pour chaque caméra**, l'une après l'autre. C'est ici qu'on prépare ce
qui permettra, plus tard, de vérifier que chaque enregistrement est conforme aux
conditions du dataset.

Pour chaque caméra, le menu affiche son état (réglages verrouillés ou non, zones
définies, référence active) et propose :

| Option | Rôle |
| :--- | :--- |
| `[1]` | Définir / redessiner les **zones** de mesure |
| `[2]` | Visualiser les zones actuelles |
| `[3]` | Mesurer en direct (luminosité, couleurs, contraste, stabilité) |
| `[4]` | Créer / remplacer la **référence** active (scène standard requise) |
| `[5]` | Afficher la référence active |
| `[6]` | **Diagnostic** de conformité (vs référence active) |
| `[7]` | **Recalibrer** vers la référence (validation verte ou orange confirmée) |
| `[R]` | Régler la caméra avec **guvcview** (exposition / balance des blancs / gain) puis verrouiller — **toujours disponible** : avant verrouillage pour définir les réglages, après pour les refaire (ce qui **invalide la référence**, à recréer avec `[4]`) |
| `[S]` | Étape suivante (poursuivre l'enregistrement) |

Concrètement, pour chaque caméra : si ses réglages ne sont pas encore figés,
utilisez `[R]` (guvcview) pour les définir ; définissez ses **zones** `[1]` ;
créez sa **référence** `[4]` ; vérifiez avec le **diagnostic** `[6]`. Si vous
refaites les réglages plus tard avec `[R]`, **recréez ensuite la référence**
avec `[4]`. Quand la caméra est prête, `[S]` passe à la suivante (puis à la
suite du script).

> **⚠️ Conditions d'accès.** Les options `[4]`, `[6]` et `[7]` exigent des
> réglages **verrouillés** : tant qu'ils ne le sont pas, commencez par `[R]`.
> `[R]` reste **toujours disponible**, y compris une fois les réglages figés
> (il sert alors à les refaire, ce qui invalide la référence). De même, `[2]`,
> `[3]`, `[4]`, `[6]` et `[7]` exigent d'avoir d'abord défini les **zones** `[1]`.

> **🛡️ Référence protégée contre la surexposition.** À la création `[4]`, le
> script **refuse** d'enregistrer une référence saturée. Une **zone pilote
> obligatoire** est refusée dès qu'elle dépasse **~1 % de pixels saturés**
> (même sans être visuellement « cramée »), et le **bol** est refusé s'il
> devient une **sentinelle morte** (uniformément blanc). Si `[4]` refuse,
> réduisez l'exposition via `[R]` (guvcview, désactivez l'auto-exposition),
> limitez les reflets si besoin, puis relancez `[4]`.

> **🟠 Valider un écart non bloquant dans `[7]`.** Le recalibrage guidé vous
> fait ajuster les réglages jusqu'au verdict 🟢. Mais si le seul écart restant
> est **orange et non bloquant** (typiquement la *sentinelle couleur* — la pince
> verte ou la pièce rose —, souvent décalée pour une raison **géométrique**, pas
> de balance des blancs), `[V]` permet de **valider explicitement cet orange**
> (après confirmation). Inutile alors de continuer à modifier la balance des
> blancs : vous tourneriez en rond.

> **💡 Pourquoi figer l'exposition et la balance des blancs ?** Pour que
> **tous** les épisodes soient visuellement cohérents — condition importante
> pour que le modèle apprenne correctement. Réglez chaque caméra pour obtenir
> une image stable, puis gardez les mêmes réglages tant que la référence reste
> valable. Si vous les changez avec `[R]`, recréez la référence avec `[4]`.

**7. Récapitulatif, libération du Leader, connexion et verrouillage des caméras**

Une fois les deux menus de référence terminés, le script affiche un
**récapitulatif** de l'état des caméras, puis demande d'appuyer sur **Entrée**
pour libérer le Leader et lancer la suite. Le Leader est alors **libéré** (le
Follower reste actif) ; le script **connecte** les deux caméras, vérifie la
résolution **640×360** (il s'arrête si elle est incorrecte) et **verrouille**
leurs réglages via `v4l2-ctl`. Si le verrouillage est incomplet, il demande s'il
faut continuer malgré tout.

**8. Téléopération**

La téléopération démarre : le script affiche **« Tenez le LEADER »**, laisse 2
secondes pour saisir le Leader, puis ouvre le menu d'enregistrement (Étape 4).

> **🛡️ À retenir :** avant **chaque** série d'épisodes, le script revérifiera
> automatiquement la conformité des deux caméras (voir Étape 4). L'enregistrement
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

> **🛡️ Contrôle qualité avant chaque série (important).** Avant le **Test
> rapide** comme avant un **bloc de 10 épisodes**, le script ramène les robots
> au repos et **contrôle les deux caméras** (la Globale puis la Pince) par
> rapport à leur référence visuelle. Le verdict est gradué : 🟢 conforme →
> enregistrement autorisé ; 🟠 léger écart → autorisé après confirmation (écart
> journalisé) ; 🔴 écart important ou mesure instable → **bloqué**, avec
> recalibrage guidé proposé. Si le contrôle est impossible (zones ou référence
> manquantes), `[M]` ouvre le menu de référence pour réparer, `[Q]` annule.
> **L'enregistrement n'est jamais autorisé à l'aveugle** : si une caméra n'est
> pas conforme, le bloc est annulé. C'est un verrou de qualité du dataset, pas
> un simple confort.

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
| Image trop claire/sombre ou couleurs fausses | Exposition/balance des blancs mal réglées | Choisir `[R]` (guvcview) et réajuster ; si `[4]` **refuse** la référence (image saturée), réduire l'exposition via `[R]` puis recréer `[4]` |
| « Verrouillage caméra incomplet » | `v4l2-ctl` absent ou contrôle non appliqué | Installer `v4l-utils` ; vérifier la caméra ; relancer |
| Module `SEM_so101_camera_reference.py` absent | Module manquant dans le dossier | Le script s'arrête au démarrage : placer le module dans le dossier des scripts |
| « Zones absentes » ou zones caduques | Zones non définies, ou masque/référence modifié | Menu de référence → `[1]` (re)définir les zones |
| « Aucune référence active » | Référence non créée pour la caméra | Menu de référence → `[1]` zones, puis `[4]` créer la référence |
| Diagnostic 🔴 ou contrôle avant bloc refusé | Image non conforme à la référence (lumière, cadrage, couleurs) | Suivre l'action recommandée : `[7]`/`[R]` recalibrage, ou `[M]` menu de référence |
| Recalibrage `[7]` qui « boucle » (orange persistant) | Un critère non bloquant reste orange (ex. sentinelle couleur, souvent géométrique) ; la balance des blancs ne le corrigera pas | Dans `[7]`, valider avec `[V]` au lieu d'ajuster sans fin ; ou accepter l'orange au contrôle avant bloc |
| Réglages caméra incompatibles avec la référence | Exposition / balance des blancs changées depuis la référence | Menu de référence → `[R]` régler puis verrouiller, ou recalibrer `[7]` |


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
- Les références visuelles des deux caméras sont créées et les contrôles avant bloc ont autorisé les enregistrements
- Les vidéos sont en résolution 640×360 (16:9)
- Les données parquet sont cohérentes
- Vous avez vérifié visuellement quelques vidéos

> **🚀 Objectif atteint :** Votre dataset de démonstrations est complet ! 50 épisodes de la tâche "pick and place" sont prêts à être consolidés et utilisés pour l'entraînement. Passez à la Phase 8 pour fusionner les données et préparer l'entraînement.

**📝 Récapitulatif des fichiers**

| Fichier | Description | Créé / utilisé par |
| :--- | :--- | :--- |
| `SEM_so101_8_record_dataset.py` | Script d'enregistrement bi-caméra | Phase 7 |
| `SEM_so101_camera_config.py` | Module : réglage + verrouillage des caméras (exposition / balance des blancs / gain) | Scripts 8 et 11 |
| `SEM_so101_camera_reference.py` | Module : références visuelles (zones, référence, diagnostic, recalibrage, contrôle avant enregistrement) | Scripts 8, 9 et 11 |
| `position_X_*/` | Dossiers de données par position | Script 8 |
| `~/lerobot/calibration/camera_mask.json` | Masque de la zone utile (caméra globale) | Script 7 (Phase 6) |
| `~/lerobot/calibration/camera_settings.json` | Réglages des 2 caméras (exposition / balance des blancs / gain) | Module `camera_config` |
| `~/lerobot/calibration/camera_reference_cam_top.json` / `..._cam_follower.json` | Référence visuelle active de chaque caméra | Module `camera_reference` |
| `~/lerobot/calibration/camera_reference_zones_cam_top.json` / `..._cam_follower.json` | Zones de mesure de chaque caméra | Module `camera_reference` |
| `~/lerobot/calibration/camera_reference_log.jsonl` | Journal des écarts 🟠 confirmés | Module `camera_reference` |
| Fichiers Phases 3-6 inchangés | Calibration, repos, configuration téléop, masque | Phases 3-6 |
