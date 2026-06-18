# Guide Téléopération avec Caméra SO-ARM 101

## Phase 6 : Visualisation temps réel

Service Écoles-Médias (SEM) — DIP Genève

### ✅ Prérequis

- Phases 1 à 5 complétées
- Calibrations Leader et Follower **complètes et valides** (Phase 3)
- Configuration de téléopération du mode choisi **créée en Phase 5** (script 5)
- Support de la caméra Globale installé
- Caméra Globale branchée

> **Note :** Cette phase utilise le script `SEM_so101_7_teleoperation_camera.py`, qui ajoute la caméra Globale et le masque de zone utile à la téléopération validée en Phase 5.

> **⚠️ Important :** le script 7 **refuse de démarrer** si une calibration est absente/invalide, si aucune caméra n'est détectée, ou si la configuration du mode choisi n'existe pas.


### 🎯 Objectif de cette phase

**Pourquoi ajouter une caméra ?** La visualisation en temps réel permet de voir ce que "voit" le robot pendant la téléopération. C'est l'étape préparatoire avant l'enregistrement de trajectoires pour l'apprentissage par imitation, où la caméra capturera les démonstrations visuelles.

L'ajout de la caméra permet de :

- Visualiser l'espace de travail pendant la téléopération
- Préparer l'enregistrement visuel des démonstrations
- Valider le positionnement optimal de la caméra
- Tester la qualité d'image et la latence

**Pourquoi définir un masque ?** Cette phase introduit aussi une étape déterminante : la définition d'un **masque de zone utile**. La caméra Globale voit plus que le plateau (bords, arrière-plan, environnement) ; en traçant la zone utile, on ne conserve que le plateau et on noircit le reste. Ce masque n'est pas un simple confort d'affichage : le fichier produit ici est **réutilisé lors de l'enregistrement (Phase 7)** et appliqué à la caméra Globale. Autrement dit, la zone délimitée maintenant est exactement celle que le modèle apprendra à voir — un cadrage soigné conditionne la qualité de l'apprentissage.


### 📋 Étape 1 : Installation physique de la caméra

**Matériel nécessaire**

| Élément | Description | Alternative |
| :--- | :--- | :--- |
| Caméra USB | Webcam standard (720p minimum) | Webcam intégrée PC portable |
| Support | Pièce imprimée 3D | Trépied, pince, bricolage |
| Fixation | Vis M3 ou M4 | Colle forte, ruban adhésif double face |
| Position | Globale : coin opposé du plateau ; Pince : vissée sur la pince | — |

**Les deux caméras du projet :**

- **Caméra Globale :** posée dans le coin opposé du plateau, orientée vers l'espace de travail — elle donne la vue d'ensemble de la scène.
- **Caméra Pince :** vissée sur la pince via le support imprimé en 3D fourni (fichier STL), orientée vers les doigts — elle donne la vue rapprochée de la préhension.

> **⚠️ En Phase 6, le script 7 n'utilise QUE la Caméra Globale.** La Caméra Pince fait partie du projet global mais n'est pas pilotée par ce script. **Les deux caméras du projet étant identiques**, le script ne devine pas laquelle est la Globale : il vous la fait **identifier visuellement** au lancement — une seule caméra branchée : aperçu + confirmation ; plusieurs caméras : il les montre tour à tour et vous tapez `G` (Globale), `P` (Pince) ou `Q` (passer). Pour simplifier, vous pouvez ne laisser branchée que la Caméra Globale.


### 🔧 Étape 2 : Résolution du problème OpenCV

> **⚠️ Erreur fréquente lors du premier lancement :**
> ```
> cv2.error: The function is not implemented. Rebuild the library with
> Windows, GTK+ 2.x or Cocoa support
> ```

Cette erreur apparaît car LeRobot a installé `opencv-python-headless` (version sans interface graphique) au lieu de `opencv-python` (version avec fenêtres).

**Solution validée**

```bash
# Activer l'environnement
conda activate lerobot

# Vérifier ce qui est installé
pip list | grep opencv

# Si vous voyez "opencv-python-headless", le remplacer :
pip uninstall opencv-python-headless -y
pip install opencv-python

# Vérifier la correction
python -c "import cv2; print('OpenCV version:', cv2.__version__)"
```

> **✅ Après cette correction :** Les fenêtres OpenCV pourront s'afficher normalement pour visualiser le flux vidéo de la caméra.


### 📷 Étape 3 : Détection et test de la caméra

> **💡 Note :** Le script 7 vous fait **identifier la caméra Globale** et en affiche un aperçu au lancement (résolution réelle + image figée). Cette étape est donc une **vérification optionnelle** : confirmer que la caméra est branchée et, si vous en avez plusieurs, repérer son index.

**Vérification de la connexion USB**

```bash
# Vérifier les périphériques vidéo disponibles
ls /dev/video*

# Résultat attendu :
# /dev/video0 /dev/video1
# Note : Certaines caméras créent 2 devices :
# video0 pour la vidéo, video1 pour les métadonnées
```

**Test de capture avec LeRobot**

Utilisez la commande officielle LeRobot pour détecter et tester la caméra :

```bash
# Activer l'environnement
conda activate lerobot

# Se placer dans le dossier LeRobot
cd ~/lerobot

# Lancer la détection et capture d'images test
python lerobot/common/robot_devices/cameras/opencv.py \
    --images-dir outputs/images_from_opencv_cameras
```

Sortie attendue :

```
Linux detected.
Finding available camera indices through scanning '/dev/video*' ports
Camera found at index /dev/video0
Connecting cameras
OpenCVCamera(0, fps=30, width=640, height=480, color_mode=rgb)
Saving images to outputs/images_from_opencv_cameras
Frame: 0000 Latency (ms): 822.57
Frame: 0001 Latency (ms): 55.93
...
Frame: 0091 Latency (ms): 32.00
Images have been saved to outputs/images_from_opencv_cameras
```

**Vérification des images capturées**

> **⚠️ Étape importante :** Vérifiez quelle caméra correspond à quel index !

```bash
# Lister les images capturées
ls outputs/images_from_opencv_cameras/

# Ouvrir une image pour vérifier visuellement
xdg-open outputs/images_from_opencv_cameras/camera_00_frame_000000.png
```

Vérifications à effectuer :

1. Ouvrez l'image `camera_00_frame_000000.png`
2. Confirmez que c'est bien la vue souhaitée (pince, dessus, côté)
3. Notez l'index correspondant : `camera_00` = index 0 = `/dev/video0`
4. Si ce n'est pas la bonne caméra, c'est peut-être votre webcam intégrée

> **💡 Conseil :** Si `/dev/video0` est votre webcam intégrée, votre caméra USB sera probablement sur `/dev/video2`.


### 🎮 Étape 4 : Lancement du script de téléopération avec caméra

Le script `SEM_so101_7_teleoperation_camera.py` reprend la téléopération du script 6 (Phase 5) et y ajoute la **caméra** : détection et aperçu automatiques, **masque de zone utile obligatoire**, affichage temps réel pendant la téléopération, et une commande `M` pour refaire le masque sans tout relancer.

**Lancement du script**

```bash
# Activer l'environnement
conda activate lerobot
# Se placer dans le dossier des scripts
cd ~/lerobot/Scripts_SEM/scripts
# Lancer le script 7
python SEM_so101_7_teleoperation_camera.py
```

**Déroulement de l'exécution**

Le script suit ce déroulement :

1. **Vérification des calibrations** — au tout début, le script vérifie que les calibrations Leader et Follower sont complètes et valides, et **refuse de démarrer** sinon (avant toute interaction caméra ou robot).

2. **Sélection et aperçu de la caméra Globale** — le script sonde les caméras disponibles. Les deux caméras du projet étant identiques, il vous fait **identifier la Globale** : s'il n'y en a qu'une, il affiche un aperçu et demande **confirmation** ; s'il y en a plusieurs, il les montre tour à tour pour que vous désigniez la Globale (`G`), la Pince (`P`) ou que vous passiez (`Q`). Il affiche ensuite un bref aperçu (résolution réelle + image figée) ; appuyez sur ENTRÉE pour continuer. Si **aucune caméra** n'est détectée — ou si la Globale n'est pas confirmée/identifiée — le script s'arrête.

3. **Définition du masque de zone utile (obligatoire)** — étape déterminante, détaillée juste après. Si la création est **abandonnée**, le script **s'arrête** (aucun robot n'est encore branché).

4. **Identification des robots** — débrancher tout, brancher Leader, valider, brancher Follower, valider (test de la pince pour chaque). La détection est **stricte** : exactement 1 robot après le Leader, exactement 2 après le Follower.

5. **Choix de la disposition** (choix explicite, redemandé si invalide)
   ```
   [C]ôte à côte ou [F]ace à face ?
   Choix [C/F] : _
   ```

6. **Chargement de la configuration du mode** — le script charge la config COPIE/MIROIR du mode choisi (créée en Phase 5) et **refuse de démarrer** si elle est absente, illisible ou mal formée.

7. **Positionnement automatique** — centrage parallèle puis position repos.

8. **Téléopération avec caméra** — la fenêtre `Camera SO-ARM 101` s'ouvre en plus de l'interface terminal (voir « Interface de téléopération » plus bas). Si la caméra **ne peut pas s'ouvrir** à ce moment, le script s'arrête proprement.

**Définition du masque de zone utile (obligatoire)**

> **⚠️ Rappel — étape déterminante.** Le masque tracé ici est réutilisé tel quel lors de l'enregistrement (Phase 7), appliqué à la caméra Globale : c'est la zone exacte qui entrera dans le jeu de données d'apprentissage. Soignez le cadrage du plateau — un masque mal placé fausse tout l'apprentissage.

Le script applique un **masque** sur l'image : seule la zone utile (le plateau) reste visible, tout le reste est noirci. Ce sont les pixels hors du plateau qui sont mis à zéro : il ne s'agit **pas** d'un recadrage. Le script demande une résolution de 640×360, mais si la caméra en renvoie une autre, le masque est **reconstruit à la taille réelle de l'image** (les points sont mis à l'échelle automatiquement) — il reste donc correct.

Au lancement, après l'aperçu caméra :

- Si un masque existe déjà **et est valide** : `[Entrée]` pour le garder, `[M]` pour en refaire un, `[Q]` pour quitter (aucun robot n'est encore engagé).
- Si le fichier `camera_mask.json` existant est **corrompu ou invalide** (il doit contenir exactement 5 points avec des coordonnées numériques), il est **rejeté** et la recréation est lancée automatiquement.
- Sinon, la création est lancée automatiquement (elle est **obligatoire** : un abandon arrête le script).

Création interactive : une image figée de la caméra s'ouvre. Cliquez **5 points** délimitant le plateau, **dans le sens horaire en partant du haut-gauche**. Un aperçu masqué s'affiche, puis le terminal demande `[V]` valider / `[R]` recommencer / `[A]` abandonner. Le masque est enregistré (de façon atomique) dans :

```
~/lerobot/calibration/camera_mask.json
```

Pour forcer la recréation au lancement : `python SEM_so101_7_teleoperation_camera.py --refaire-masque`. Pendant la téléopération, la touche `M` permet aussi de le refaire (les robots reviennent au repos, puis la téléopération reprend). **Si le retour repos ou la réouverture de la caméra échoue pendant `M`**, la recréation est annulée et la téléopération **s'arrête proprement** (l'état des bras est alors incertain).

**Interface de téléopération**

Une fois le masque défini et les robots positionnés, la fenêtre vidéo s'ouvre et le terminal affiche :

```
╔══════════════════════════════════════════════════════════╗
║     TÉLÉOPÉRATION - CÔTÉ À CÔTÉ                         ║
║     Servos miroir: []                                   ║
╚══════════════════════════════════════════════════════════╝

🎮 Commandes:
  [Q] + Enter : Quitter
  [F] + Enter : Flip mode (côté ↔ face)
  [M] + Enter : Refaire le masque caméra (téléop en pause)
  [q] (fenêtre vidéo) : Quitter
----------------------------------------

✅ Téléopération active!
🤖 Bougez le LEADER, le FOLLOWER suit
```

**Commandes disponibles**

| Commande | Action |
| :--- | :--- |
| Q + Entrée | Quitter proprement (terminal) : retour repos **puis** libération |
| F + Entrée | Basculer côté à côte ↔ face à face — uniquement si la config du mode cible est valide ; sinon mode conservé (terminal) |
| M + Entrée | Refaire le masque caméra (téléop en pause → retour repos → reprise ; **arrêt propre** si le repos ou la réouverture caméra échoue) |
| q (fenêtre vidéo) | Quitter proprement, **comme `Q`** (retour repos puis libération) |
| CTRL+C | Interruption immédiate : libération des servos, **sans** retour repos |

**Fenêtre vidéo :**
- Résolution demandée : 640×360 pixels ; si la caméra renvoie une autre taille, le masque est ajusté à la taille réelle de l'image. La fenêtre est affichée en 1280×720.
- La fenêtre affiche le flux en temps réel de la caméra, masqué selon la zone définie
- La caméra Globale est celle que vous avez **identifiée au lancement** (confirmation, ou choix `G`/`P`) ; l'aperçu permet de vérifier le cadrage

> **💡 Note :** Comme les deux caméras du projet sont identiques, le script ne choisit pas tout seul : il vous fait **identifier la Globale** au lancement (confirmation si une seule caméra, sinon choix `G`/`P`/`Q` en regardant chaque flux). En cas d'erreur, relancez le script et reprenez l'identification. Pour simplifier, ne laissez branchée que la Caméra Globale.


### 📊 Étape 5 : Tests de validation

**Test 1 : Masque de zone utile**

1. Vérifiez que le plateau est entièrement visible dans la fenêtre
2. Vérifiez que tout ce qui est hors plateau est bien noirci
3. Assurez-vous qu'aucune zone utile (objets, espace de manipulation) n'est coupée par le masque
4. Si le cadrage n'est pas bon, refaites le masque avec la touche `M`

**Test 2 : Qualité d'image**

1. Vérifiez que l'image dans la fenêtre est nette
2. Ajustez la mise au point si nécessaire (molette sur la caméra)
3. Assurez-vous que toute la zone de travail est visible
4. Évitez les contre-jours et reflets

**Test 3 : Synchronisation téléopération + vidéo**

1. Bougez le Leader pour déplacer le Follower
2. Vérifiez que le mouvement est visible dans la fenêtre vidéo
3. La vidéo ne doit pas ralentir la téléopération

**Test 4 : Changement de mode avec vidéo active**

1. Appuyez sur F + Entrée pour changer de mode
2. La vidéo doit continuer sans interruption
3. Si la config du mode cible est **valide** : le mode bascule et les mouvements miroir/copie restent synchronisés. Si elle est **absente/invalide** : la bascule est refusée, le mode courant est conservé, et la téléop continue.

**Test 5 : Stabilité sur 5 minutes**

1. Laissez le système tourner avec vidéo active
2. Effectuez des mouvements réguliers
3. Vérifiez qu'il n'y a pas de gel d'image
4. La fenêtre vidéo ne doit pas se fermer seule

> **✅ Tests réussis si :**
> - Le masque cadre correctement le plateau
> - La fenêtre vidéo s'affiche correctement
> - Image nette et stable
> - Pas de ralentissement de la téléopération
> - Système stable pendant 5 minutes
> - `Q` (terminal) et `q` (fenêtre vidéo) ramènent au repos puis libèrent ; `CTRL+C` libère immédiatement, **sans** retour repos


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| Erreur "function not implemented" | `opencv-python-headless` installé | Voir Étape 2 : remplacer par `opencv-python` |
| Le script s'arrête : « Aucune caméra globale utilisable » | Caméra débranchée / non reconnue / non confirmée | Brancher la Caméra Globale, vérifier `ls /dev/video*`, relancer |
| Le script s'arrête : « Caméra indisponible » (au lancement ou après `M`) | Caméra occupée par une autre application, ou déconnectée | Fermer l'autre application, vérifier le câble USB, relancer |
| Le script s'arrête : masque abandonné | Création du masque interrompue (`A` ou ESC) | Relancer et définir le masque (obligatoire en Phase 6) |
| Le script s'arrête : calibration ou configuration manquante | Phase 3 ou Phase 5 non faite pour ce mode | Refaire la calibration (Phase 3) / créer la config (script 5, Phase 5) |
| Image noire / mauvaise caméra | Caméra Pince identifiée à la place de la Globale | Relancer et identifier la Globale (`G`) ; ou ne laisser branchée que la Caméra Globale |
| Téléopération ralentie | Charge CPU trop élevée | Fermer autres applications |
| Permission denied /dev/video* | Droits insuffisants | Vérifier le groupe `video` (voir Phase 1, Étape 6) |
| Caméra se déconnecte | Câble USB instable | Changer de port USB, éviter les hubs |
| Image floue | Mise au point incorrecte | Ajuster la molette de focus sur la caméra |
| Robots ne bougent pas | Problème d'identification | Relancer le script, suivre l'ordre de branchement |
| Module cv2 not found | Mauvais environnement | `conda activate lerobot` |


### 💡 Conseils pour l'enregistrement futur

Cette phase prépare l'enregistrement de trajectoires (Phase 7). Quelques points à valider maintenant :

- **Caméra Globale figée après le masque :** une fois le masque défini, ne déplacez plus la caméra Globale. Le masque est lié à sa position — si la caméra bouge, la zone masquée ne correspond plus au plateau et il faut tout refaire.
- **Position :** toute la zone de manipulation visible, caméra stable (aucune vibration), distance et angle fixes après validation.
- **Éclairage :** constant et diffus, sans reflets sur les surfaces brillantes, sans variation (fenêtres, néons).
- **Arrière-plan :** fixe, contrasté et simple, pour bien distinguer les objets.
- **Reproductibilité :** les conditions validées ici (position caméra, éclairage, arrière-plan) devront être **identiques** lors de l'enregistrement (Phase 7) et de l'utilisation du modèle.

> **💡 Astuce :** Prenez une photo de votre configuration finale (caméra, éclairage, plateau). Vous devrez la reproduire à l'identique pour que le modèle fonctionne après l'entraînement.


### ✅ Notes finales

**✅ Phase 6 terminée quand :**

- Les calibrations Leader/Follower et la configuration du mode (Phase 5) sont valides (sinon le script refuse de démarrer)
- La caméra Globale est montée, branchée et **identifiée** au lancement (confirmation si une seule caméra, sinon choix `G`/`P`)
- OpenCV avec support GUI est installé
- Le masque de zone utile est défini (5 points du plateau)
- La fenêtre vidéo s'affiche pendant la téléopération
- Pas de ralentissement de la téléopération
- Le système reste stable pendant 5 minutes
- Vous maîtrisez la sortie normale (`Q` ou `q`, retour repos) et l'interruption immédiate (`CTRL+C`, sans repos)

> **🚀 Objectif atteint :** Votre système de téléopération dispose maintenant d'une visualisation en temps réel ! La caméra est prête pour l'enregistrement de trajectoires et l'apprentissage par imitation qui seront couverts dans la Phase 7.

**📝 Récapitulatif des fichiers**

| Fichier | Description | Créé par |
| :--- | :--- | :--- |
| `~/lerobot/Scripts_SEM/scripts/SEM_so101_7_teleoperation_camera.py` | Script de téléopération avec visualisation caméra | Phase 6 |
| `~/lerobot/calibration/camera_mask.json` | Masque de zone utile (polygone 5 points du plateau) | Phase 6 / script 7 |
| `~/lerobot/outputs/images_from_opencv_cameras/` | Dossier contenant les images test de la caméra | Test caméra (optionnel) |

Service Écoles-Médias — DIP Genève
Guide Phase 6 — Version 2.1
