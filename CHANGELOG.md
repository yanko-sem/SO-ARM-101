# Changelog

Toutes les modifications importantes du projet seront documentées dans ce fichier.

Le format s’inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le projet utilise une logique de versionnement stable à partir de la version `v1.0.0`.

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
