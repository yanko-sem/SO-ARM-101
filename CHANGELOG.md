# Changelog

Toutes les modifications importantes du projet seront documentées dans ce fichier.

Le format s’inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le projet utilise une logique de versionnement stable à partir de la version `v1.0.0`.

## [1.6.0] - 2026-07-03

**Registre local de modèles nommés** (scripts 10 et 11). Le pipeline passe d'un
**modèle unique** à un emplacement fixe (`~/lerobot/outputs/train/act_so101_pick_place/`)
à **plusieurs modèles nommés** sous `~/lerobot/outputs/train/<nom>/`. On peut ainsi
entraîner et conserver plusieurs modèles issus de démonstrations différentes, puis
**choisir explicitement** lequel déployer — sans réentraîner entre deux démonstrations.

### Ajouté

- **Modèles nommés (scripts 10 et 11).** Chaque entraînement crée ou reprend un modèle nommé sous `~/lerobot/outputs/train/<nom>/`. Le nom est **libre** (validé par `^[a-z0-9][a-z0-9_-]*$`, il commence par une lettre ou un chiffre) et devient le **nom exact du dossier**, sans préfixe ajouté. Fonction partagée **`checkpoint_chargeable()`** : un checkpoint n'est considéré valide que si son `pretrained_model/` contient `config.json` **et** `model.safetensors` (les deux fichiers chargés par `ACTPolicy.from_pretrained()`).
- **Script 10 :** menu de **sélection ou création de modèle** en tête de l'entraînement (nouvelles fonctions `checkpoint_chargeable`, `lister_modeles`, `nom_modele_valide`, `selectionner_ou_creer_modele`).
- **Script 11 :** **sélection explicite du modèle** (aucun modèle par défaut) **avant** la sélection du checkpoint (nouvelle fonction `selectionner_modele`) ; le résumé de fin d'exécution affiche le **modèle utilisé** en plus du checkpoint.

### Modifié

- **Script 10 :** `OUTPUT_DIR` **dynamique** (base commune `TRAIN_BASE = ~/lerobot/outputs/train`). Le fichier **`sem_training_params.json` est désormais écrit dans le dossier du modèle**, **après** le lancement (et non plus « à côté du script »), afin de ne pas créer un `output_dir` non vide qui ferait échouer un entraînement neuf. Menu de reprise : l'ancien « Nouveau » devient **« Remplacer ce modèle »** (suppression gardée par la saisie de `SUPPRIMER`), avec une nouvelle option **« Choisir un autre modèle »**. Un dossier existant **même partiel** (entraînement interrompu/échoué) ne bloque plus le nom : il est routé vers la reprise/le remplacement.
- **Script 11 :** `selectionner_checkpoint()` ne **liste et ne recommande** que des checkpoints **chargeables** (`config.json` + `model.safetensors`) ; sans `last` chargeable, la recommandation retombe sur le plus grand checkpoint numérique chargeable. Le **comptage des checkpoints** affiché dans les menus repose lui aussi sur `checkpoint_chargeable`.

### Sécurité

- **Remplacement d'un modèle** (script 10) gardé par une **confirmation forte** : saisie explicite du mot `SUPPRIMER`. Fail-closed — aucune suppression silencieuse ; toute autre saisie conserve le modèle.

### Documentation

- **Guides Phase 9 (entraînement) et Phase 10 (déploiement)** réalignés : sélection/création de modèle nommé, convention de nommage sans préfixe, règle **« ne pas renommer un dossier de modèle »**, menu de reprise (Remplacer/`SUPPRIMER`, Autre modèle), **sélection du modèle avant le checkpoint**, chemin exact `checkpoints/<step>/pretrained_model/`, et formulation du **checkpoint recommandé** (`last` s'il est chargeable, sinon le plus grand checkpoint numérique chargeable). Atténuation du paragraphe sur l'« équivalence » de la prolongation (comportement de reprise à confirmer sur le `train.py` installé).
- **READMEs et documents annexes** réalignés : `README_fichiers.md` (`sem_training_params.json` désormais dans le dossier du modèle ; racine `outputs/train/` par modèle nommé), `README_scripts.md` (descriptions des scripts 10/11, stockage par modèle nommé, filtre « chargeable »), `README_guides.md` (registre de modèles, sélection du modèle), et `portage_autre_PC.md` (copie de l'ensemble `~/lerobot/outputs/train/` — tous les modèles nommés — et note sur déploiement vs reprise d'un modèle porté).

## [1.5.0] - 2026-07-02

**Changement de direction sur la gestion de la lumière**, validé par les tests machine réels de la chaîne complète (scripts 8 → 11 : enregistrement → consolidation → entraînement → déploiement).

Les versions précédentes cherchaient à rendre chaque session visuellement **identique à une référence fixe** enregistrée : verrouillage matériel de l'exposition, de la balance des blancs et du gain (`camera_settings.json`, module `camera_config`), et **référence visuelle chiffrée** par caméra avec contrôle de conformité et recalibrage vers cette référence (module `camera_reference`), plus un mode `LEGACY` pour les datasets antérieurs. Cette approche supposait un éclairage reproductible.

Or, en salle de classe, l'éclairage **ne se contrôle pas** (emplacement, heure, saison) : exiger la convergence de chaque session vers une référence fixe unique est physiquement intenable. Le nouveau principe inverse la logique : chaque caméra laisse son exposition (et sa balance des blancs) **s'ajuster automatiquement à la lumière réelle de la salle**, puis la **fige** pour la durée de la session (cohérence intra-session, sans exiger d'identité inter-session). La robustesse à la variété d'éclairage est **recherchée** en enregistrant des démonstrations sous des conditions lumineuses variées mais exploitables — une augmentation d'éclairage à l'entraînement pourra la renforcer ultérieurement. Un **contrôle image simple** sur l'image brute (plancher physique de lumière) remplace la comparaison à une référence.

### Ajouté

- Module **`SEM_so101_camera_auto.py`** : réglage de l'exposition (et de la balance des blancs) **auto puis figée** par session (via `v4l2-ctl` ; secteur 50 Hz anti-scintillement ; convergence courte flux actif, puis figeage), et **contrôle image simple** sur l'image brute (avant masque) — luminosité et part de pixels très clairs / très sombres. La caméra globale est mesurée dans la **zone utile du masque**, la caméra pince en **plein cadre**. Verdict gradué 🟢 (exploitable) / 🟠 (limite) / 🔴 (cramée ou écrasée), *fail-closed* (un réglage non appliqué arrête le script appelant).

### Modifié

- **Script 8 (enregistrement)** migré vers `camera_auto` : identification des caméras en **fenêtre live** (touches directes G / P / Q / Échap), réglage exposition auto puis figée au démarrage de session, puis **contrôle image avant chaque bloc**. Suppression du verrouillage matériel et des menus de référence.
- **Script 11 (déploiement)** migré vers `camera_auto` : réglage exposition auto puis figée et contrôle image **avant l'inférence** ; modèle chargé sur le **périphérique disponible** (GPU si présent, sinon CPU). Suppression du contrôle contre les références du dataset, du verrouillage matériel, de la résolution de la traçabilité méta (`resoudre_meta_dataset`) et du mode `LEGACY`.
- **Script 9 (consolidation)** : suppression de la copie des **références caméra** dans le `meta/` du dataset et des états de traçabilité associés (copiée / partielle / absente / échec).

### Retiré

- Du workflow courant : modules **`SEM_so101_camera_config.py`** (verrouillage matériel) et **`SEM_so101_camera_reference.py`** (référence visuelle : zones, diagnostic de conformité, recalibrage), fichier **`camera_settings.json`**, copie des **références caméra** dans le `meta/`, et mode **`LEGACY`** au déploiement.
- **`guvcview`** n'est plus un outil requis (optionnel, inspection manuelle uniquement) ; `v4l-utils` (commande `v4l2-ctl`) reste requis.

### Documentation

- **Guides de phase** réalignés sur le nouveau paradigme : **Phase 1** (outils caméra : `v4l-utils` requis, `guvcview` optionnel), **Phase 7** (enregistrement : exposition auto puis figée + contrôle image, philosophie d'éclairage réécrite), **Phase 8** (retrait de la traçabilité « référence visuelle »), **Phase 10** (déploiement : contrôle image, GPU/CPU, prérequis calibration Follower). Guides des phases 2, 3, 4, 5, 6 et 9 inchangés (non concernés).
- **READMEs** réalignés : `README_guides.md`, `README.md`, `README_EN.md` et `README_scripts.md` — retrait des modules et fichiers de l'ancien paradigme, section unique `camera_auto`, harmonisation GPU/CPU (« fortement recommandé ; CPU possible mais beaucoup plus lent »), tables d'identification et de contrôle image.

## [1.4.0] - 2026-06-26

Fiabilisation de la définition de la **position de repos** (script 3) et de la chaîne de **référence visuelle des caméras** (module `SEM_so101_camera_reference.py`, version interne `8.2`), avec alignement des guides correspondants (phases 3, 7, 10).

### Modifié

- **Refonte du flux de calibration** (script 2) : le mode `[1]` calibre le **Follower en premier** (bras critique), puis enchaîne automatiquement le Leader. Les 6 servos d'un bras sont mesurés **en mémoire** ; le fichier de calibration n'est écrit qu'**après validation** du tableau **ancien → nouveau** (`[O]` valider, `[N]` recommencer les 6, `[A]` abandonner). Une interruption ou un abandon **conserve l'ancienne calibration**. Après un Follower validé, un Leader non finalisé devient un **avertissement non bloquant** (le bras critique reste enregistré).
- **Mode maintenance ciblé** (script 2) : le mode `[2]` recalibre explicitement **un seul bras** (Follower ou Leader) et **sauvegarde immédiatement** chaque servo validé — distinct du mode complet `[1]` à écriture différée.
- **Position de repos = Follower uniquement** (script 3) : la capture (`C`) et la saisie manuelle (`M`) ne sont proposées que lorsque le **Follower** est monitoré ; sur le Leader, le monitoring reste disponible mais ces touches sont refusées. Suppression du contournement « taper OUI » qui permettait d'enregistrer un repos depuis le Leader. Le repos est désormais affiché comme « référence Follower ». (`repos_position.json` est unique et partagé par les scripts 4, 5, 6, 7, 8 et 11 ; le Follower est le bras de référence du déploiement.)
- **Marge de tolérance et bornage du repos** (script 3) : une position est acceptée dans `[min − 2 %, max + 2 %]` de l'amplitude calibrée (jeu mécanique en butée), mais le **pourcentage enregistré reste borné à `[0, 100]`** — cohérent avec les consommateurs (scripts 11 et 4) qui rejettent toute valeur hors `[0, 100]` et bornent les cibles de déploiement à `[min, max]`.
- **Récapitulatifs du repos** (script 3) : affichage distinct du **% brut** (position physique, non borné, informatif) et du **% enregistré** (borné, réellement stocké) ; en saisie manuelle (`M`), une **table de référence** (position actuelle, %, MIN/CENTRE/MAX, repos déjà enregistré) précède la saisie.
- **Réglages caméra `[R]` toujours accessibles** (module de référence caméra) : le (re)réglage via guvcview est désormais disponible **même lorsque les réglages sont verrouillés** ; refaire les réglages **invalide la référence**, qui doit alors être recréée avec `[4]`.
- **Validation d'un écart orange `[V]` dans le recalibrage guidé `[7]`** (module de référence caméra) : lorsque le verdict global est 🟠 (jamais 🔴), une option `[V]` permet d'**accepter explicitement** l'écart non bloquant (typiquement la *sentinelle couleur*, souvent d'origine géométrique) après confirmation forte. Supprime la boucle de réglage sans issue lorsque seul un critère plafonné-orange subsiste. En déploiement (script 11), la validation se fait **sans modifier** la référence du dataset (lecture seule). Libellé de `[7]` ajusté : « Recalibrer vers la référence (validation verte ou orange confirmée) ».

### Sécurité

- **Sécurisation de la calibration** (script 2) : **détection fail-closed** d'un mauvais nombre d'adaptateurs branchés (refus de la session), **confirmation explicite du rôle** du bras (Leader/Follower indiscernables électriquement), **refus des amplitudes trop faibles** (`< 500` ticks), **conservation de l'ancienne calibration** en cas d'échec ou d'abandon, et **avertissement anti-chute** avant le relâchement du couple. Un statut interne non nul en lecture est **signalé sans bloquer** tant que la communication reste valide.
- **Porte qualité anti-saturation à la création de référence `[4]`** (module de référence caméra) : la capture est **refusée** si une **zone pilote obligatoire** dépasse ~1 % de pixels saturés, ou si le **bol** devient une **sentinelle morte** (`Y ≥ 254.5` et `sigma_Y < 0.5`, ou > 30 % de pixels saturés). Empêche d'enregistrer une référence surexposée, inexploitable pour le diagnostic ultérieur.

### Documentation

- **Guide Phase 3** aligné sur la refonte de la **calibration** et du **repos** : parcours Follower puis Leader, écriture différée en mode `[1]`, mode maintenance `[2]`, confirmation de rôle, avertissement anti-chute, gestion des statuts internes ; puis repos Follower-uniquement (sécurités, marge 2 % et bornage, modes `C`/`M`, table de référence, récapitulatif des touches).
- **Guide Phase 7** aligné sur le module caméra `8.2` : `[R]` toujours disponible et son effet sur la référence, porte qualité anti-saturation, validation orange `[V]` dans `[7]`, entrées de dépannage correspondantes ; suppression des formulations « une seule fois » devenues fausses.
- **Guide Phase 10** : le recalibrage de déploiement peut se valider en 🟢 **ou** sur un 🟠 confirmé via `[V]` (sans modifier la référence du dataset).

## [1.3.0] - 2026-06-22

Compatibilité CPU de l'entraînement et réalignement complet de la documentation sur la nouvelle numérotation des scripts (**8** enregistrement → **9** consolidation + visualisation → **10** entraînement → **11** déploiement).

### Modifié

- **Entraînement compatible CPU** (script 10) : en l'absence de GPU CUDA, le script n'échoue plus — il affiche un avertissement non bloquant et bascule automatiquement sur le **CPU** (`--policy.device=cpu`, `--policy.use_amp=false`). Sur GPU, le comportement est inchangé (`cuda` + AMP). L'entraînement reste possible sur une machine sans GPU, au prix d'une lenteur nettement accrue.
- **Commentaires internes** (script 7) réalignés sur la nouvelle numérotation : références neutres aux scripts d'enregistrement et de déploiement, à la place des anciennes mentions « scripts 8 et 12 ».

### Corrigé

- **Message d'import du module caméra** (scripts 8 et 11) : en cas d'absence du module de configuration caméra, l'erreur affiche désormais le **nom canonique** `SEM_so101_camera_config.py`, et non l'exception du dernier repli de la cascade d'imports.

### Documentation

- **Réalignement complet sur la numérotation 8 → 11** des guides des phases 7 à 10, de `README_guides.md`, `README_scripts.md` et du `README.md` global : suppression des références aux scripts périmés (`SEM_so101_10_visualize_dataset.py`, `SEM_so101_11_train.py`, `SEM_so101_12_deploy.py`, `SEM_so101_8_camera_config.py`) et harmonisation de la formulation GPU/CPU (« GPU fortement recommandé — CPU possible mais beaucoup plus lent »). Ceci clôt le point « à réaligner — en cours » de la version 1.2.

## [1.2.0] - 2026-06-19

Durcissement de sécurité et de robustesse de la chaîne enregistrement → entraînement → déploiement, et renumérotation des scripts. Les versions internes passent à : script 9 `2.1`, script 10 `1.1`, script 11 `1.1`, module de configuration caméra `5.1`.

### Modifié

- **Renumérotation des scripts.** La visualisation du dataset est intégrée au script 9 (l’ancienne étape de visualisation séparée disparaît) ; l’entraînement passe de `11` à `10` (`SEM_so101_10_train.py`) et le déploiement de `12` à `11` (`SEM_so101_11_deploy.py`). Le pipeline opérateur devient : **8** (enregistrement) → **9** (consolidation + visualisation) → **10** (entraînement) → **11** (déploiement). Les mentions de « script 12 » de la version 1.1 correspondent désormais au script 11.
- **Module de configuration caméra** renommé au nom canonique `SEM_so101_camera_config.py`, avec cascade de repli `SEM_so101_8_camera_config.py` → `SEM_8_camera_config.py` pour les anciens dépôts. Tous les consommateurs (scripts 8, 9, 11 et module de référence) sont alignés sur cet import.
- **Téléopération avec caméra** (script 7) : aperçu du masque existant avant la décision « conserver / refaire », validation stricte des 5 points du masque, correction de l’annonce d’étape, garde sur l’ouverture de la fenêtre d’affichage.
- **Enregistrement** (script 8) : identification des caméras placée **après** la mise au repos des bras (la vue de la caméra pince dépend de la pose du bras) ; `ThreadedCamera` aligné sur le déploiement (codec MJPG forcé) ; gestion d’un échec de retour repos dans le contrôle pré-bloc, avec restauration de l’état de téléopération.

### Corrigé

- **Sélection de checkpoint** (scripts 10 et 11) : tri par **valeur entière** au lieu d’un tri alphabétique. Sans dossier `last`, le script recommandait `50000` au lieu de `200000`, soit un modèle moins entraîné. Le repli privilégie le plus grand checkpoint numérique avant un éventuel dossier non numérique.
- **Reprise d’entraînement** (script 10) : `steps_du_checkpoint` retombe sur le plus grand checkpoint numérique voisin lorsque `last` est un vrai dossier et non un lien symbolique — l’option « Prolonger » ne se bloque plus à tort.
- **Préparation du dataset** (script 9) : vérification du moteur Parquet et de la résolution vidéo (640×360) avant traitement ; distinction propre des états de référence caméra (échec / absente / partielle) selon la présence réelle des sources locales.
- Numérotation interne et messages des scripts 9 à 11 alignés sur la nouvelle numérotation.

### Sécurité

- **Calibration chargée avant le couple** (script 11) : la calibration Follower est chargée et **validée avant toute activation du couple**. Une calibration absente, incomplète ou **corrompue** est refusée alors qu’aucun servo n’est sous tension — plus de bras laissé rigide sur un fichier illisible. `charger_calibration` est rendu fail-closed (jamais d’exception qui remonterait).
- **Écritures servo contrôlées** (script 11) : `ecrire_position` vérifie la communication (`COMM_SUCCESS`) et **borne chaque cible à la plage calibrée `[min, max]`** du servo — barrière contre une prédiction aberrante du modèle. La boucle d’inférence déclenche un **arrêt sûr** (coupure du couple) après 3 itérations d’inférence consécutives comportant une écriture en échec.
- **Retour repos fiable** (script 11) : `mouvement_servos` et la phase de levée d’épaule écrivent désormais de façon contrôlée ; `aller_position_repos` ne peut plus annoncer « Position repos atteinte » alors qu’une écriture a échoué. La relance d’un essai (`Entrée`) est **refusée tant que le retour repos n’est pas confirmé**, conformément à l’invariant « nouvel essai = départ du repos ».
- **Traçabilité du modèle** (script 11) : `resoudre_meta_dataset` est plus strict. Un checkpoint **non traçable** (`train_config.json` absent ou illisible, `repo_id` manquant, `meta/` introuvable) est **bloquant**. Le mode LEGACY reste réservé aux datasets identifiés mais antérieurs au système de références caméra (un seul cas : `meta/` présent, aucune référence).
- **OpenCV et caméras** (script 11) : sortie propre en tête de `main()` si OpenCV est indisponible, **avant tout engagement servo** ; stabilisation déterministe des caméras après le verrouillage des réglages, pour que la première action du modèle lise des images post-verrouillage.
- **Prérequis d’entraînement fail-closed** (script 10) : un `info.json` illisible et un dossier `~/lerobot` absent produisent une erreur claire au lieu d’un plantage ; vérification de **PyAV** (requis par `--dataset.video_backend=pyav`) ; préflight du dataset (épisodes et frames > 0, présence d’au moins un Parquet et des deux dossiers vidéo `cam_top` / `cam_follower`).
- **Identification active des caméras** (scripts 7 et 8) : les deux caméras identiques sont identifiées une par une (touches G / P / Q) au lieu de prendre `cameras[0]`, peu fiable ; refus si aucune image n’est lisible.
- **Configuration caméra fail-closed** (module `SEM_so101_camera_config.py`) : lecture des réglages distinguant fichier absent / valide / corrompu ; un `camera_settings.json` corrompu n’est plus réécrit silencieusement (sauvegarde horodatée avant toute action) ; verrouillage matériel fail-closed.

### Documentation

- CHANGELOG mis à jour (présente entrée).
- Guides de phase et README à réaligner sur la nouvelle numérotation (scripts 10 et 11) — en cours.

## [1.1.0] - 2026-06-15

### Ajouté

- Système de **référence visuelle des caméras** (`SEM_so101_camera_reference.py`) : référence chiffrée par caméra (zones de mesure, score de conformité 🟢/🟠/🔴), en remplacement du réglage caméra « à l'œil ».
- Architecture **multi-caméra** : un profil par caméra (globale et pince), avec ses propres zones, critères et fichiers de référence.
- **Contrôle de conformité des deux caméras** intégré au script 8 (avant chaque bloc d'enregistrement) et au script 12 (au démarrage du déploiement, contre les références du dataset d'entraînement).
- **Recalibrage guidé** vers la référence lorsque l'éclairage a dérivé.
- Mode **LEGACY** au déploiement pour les modèles entraînés avant ce système (références locales, après confirmation explicite).
- **Traçabilité** : copie des références des deux caméras et du journal dans le `meta/` du dataset à la consolidation (script 9).

### Modifié

- Flux d'enregistrement (script 8) et de déploiement (script 12) **réordonné** : les robots sont identifiés et mis au repos **avant** la préparation des caméras (la vue de la caméra pince dépend de la pose du bras).
- Module de configuration caméra renommé `SEM_so101_8_camera_config.py` (repli sur l'ancien `SEM_8_camera_config.py`).
- Réglage caméra « à l'œil » remplacé par le contrôle mesuré dans les scripts 8 et 12.

### Sécurité

- Politique **fail-closed** : suppression des options « continuer sans contrôle » et « continuer quand même » (verrouillage caméra). Un contrôle indisponible se répare ou s'annule ; à l'enregistrement, l'autorisation exige les deux caméras conformes.
- Masque de la caméra globale rendu **obligatoire** à l'enregistrement et au déploiement.

### Documentation

- Guides des phases 7, 8 et 10 mis à jour (flux bi-caméra, référence visuelle, traçabilité).
- README mis à jour : global (FR/EN), guides et scripts.

## [1.0.0] - 2026-06-04

### Ajouté

- Pipeline complet pour le projet éducatif SO-ARM 101.
- Guides d’installation et d’utilisation par phases.
- Scripts SEM pour la configuration, la calibration, la téléopération, l’enregistrement de dataset, l’entraînement et le déploiement.
- Support de deux bras SO-ARM 101 : Leader et Follower.
- Support de deux caméras : `cam_top` et `cam_follower`.
- Enregistrement de datasets pour l’apprentissage par imitation.
- Consolidation et vérification du dataset.
- Conversion vidéo H.264 si nécessaire.
- Entraînement d’un modèle ACT avec LeRobot.
- Déploiement autonome du modèle entraîné.
- Masque partagé de zone utile pour la caméra globale.
- Verrouillage des réglages caméra : exposition, balance des blancs et gain.
- Sécurités opérateur : retour repos, arrêt d’urgence, contrôle caméra et contrôle série.

### Stabilisé

- Script 8 : protection contre la corruption du dataset en cas de lecture ou écriture série invalide.
- Script 12 : déploiement autonome avec retour repos, pause, relance explicite et verrouillage caméra.
- Documentation racine du projet.
- Structure du dépôt `Scripts_SEM`.

### Licence

- Licence Creative Commons BY-NC-SA 4.0.
