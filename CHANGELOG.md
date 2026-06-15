# Changelog

Toutes les modifications importantes du projet seront documentées dans ce fichier.

Le format s’inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le projet utilise une logique de versionnement stable à partir de la version `v1.0.0`.

## [1.1] - 2026-06-15

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

## [1.0] - 2026-06-04

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
