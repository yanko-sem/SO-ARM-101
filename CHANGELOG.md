# Changelog

Toutes les modifications importantes du projet seront documentées dans ce fichier.

Le format s’inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le projet utilise une logique de versionnement stable à partir de la version `v1.0.0`.

## [1.4.0] - 2026-06-24

Refonte de la calibration (script 2) en parcours guidé Follower → Leader, et inventaire de référence des fichiers de données du pipeline.

### Modifié

- **Refonte du script de calibration** (script 2) : architecture à deux niveaux. Menu principal affichant l'état des calibrations (Follower / Leader) et proposant `[1]` calibration complète guidée — **Follower d'abord (obligatoire, 6 servos), puis Leader (optionnel, recommandé)** — ou `[2]` recalibration d'un seul bras (maintenance, granularité libre). Confirmation de rôle explicite avant chaque bras (les deux SO-ARM 101 étant électriquement indiscernables). Un seul bras branché à la fois ; libération des 6 servos avant tout débranchement ; récapitulatif final à la sortie. Dans le sous-menu servo, l'option de sortie passe de `[Q]` à `[R] Retour au menu principal`.
- **Maintien des servos au centre** (script 2) : après un recentrage **confirmé**, le servo reste bloqué au centre (facilite l'alignement des servos suivants) au lieu d'être libéré. Fail-closed : recentrage non confirmé → servo libéré (jamais bloqué dans une pose non maîtrisée). Libération de tous les servos garantie à la sortie.

### Corrigé

- **Message du flux « T »** (script 2) : en cas d'échec d'un servo pendant la calibration des six, le message précise désormais que seul *ce* servo n'est pas sauvegardé, et une ligne d'information rappelle que les servos déjà validés restent enregistrés.

### Documentation

- **Nouveau `README_fichiers.md`** : inventaire de référence des principaux fichiers lus/écrits par le pipeline hors scripts (calibrations, masque, réglages et références caméra, datasets bruts et consolidés, checkpoints, fichiers d'état), avec rôle, écrivain et lecteurs, établi à partir du code réel.
- **Guide Phase 3 mis à jour** : nouveau menu de calibration (Follower d'abord, sous-menu servo `[R]`), confirmation de rôle, maintien des servos au centre, récapitulatif final, et clarification du comportement en cas d'échec partiel du Follower.

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
