# Guide Déploiement Autonome SO-ARM 101

## Phase 10 : Déploiement du modèle ACT (inférence autonome)

Service Écoles-Médias (SEM) — DIP Genève

### ✅ Prérequis

- Phases 1 à 9 complétées
- Un modèle ACT entraîné (checkpoint dans `~/lerobot/outputs/train/act_so101_pick_place/checkpoints/`)
- Bras **Follower** branché (le **Leader n'est pas nécessaire** — le modèle remplace l'opérateur)
- Les **deux caméras** (Globale + Pince) branchées, **aux mêmes positions** qu'à l'enregistrement
- Fichiers de calibration présents : `camera_mask.json`, `camera_settings.json`, `repos_position.json`
- Module `SEM_8_camera_config.py` dans le même dossier que le script (obligatoire)
- Environnement lerobot activé, GPU NVIDIA


### 🎯 Objectif de cette phase

**Pourquoi déployer ?** C'est l'aboutissement du projet : le modèle ACT entraîné prend la place de l'opérateur et exécute la tâche **de façon autonome**. Plus de téléopération — le robot observe et agit seul.

Cette phase permet de :

- Charger un modèle ACT entraîné (un checkpoint) et le faire piloter le bras Follower
- Exécuter la tâche en boucle, à ~30 images/seconde
- Enchaîner plusieurs essais (replacer la pièce, relancer)
- Arrêter le robot en sécurité à tout moment


### 🤖 Comment fonctionne l'inférence autonome

À chaque cycle (~30 Hz), le script :

1. lit les images des **deux caméras** (Globale + Pince) ;
2. lit les **positions actuelles** des 6 servos du Follower ;
3. construit l'observation et demande au modèle ACT l'**action suivante** ;
4. envoie les **positions cibles** aux servos.

Le modèle gère en interne l'*action chunking* (il prédit une séquence d'actions et les exécute, pour des mouvements plus fluides).

Deux points sont **critiques pour la cohérence entraînement ↔ déploiement** :

- **Le masque de la Globale est réappliqué** : si le dataset a été enregistré masqué (Phases 6-7), le modèle doit voir la même image masquée au déploiement.
- **Les réglages caméra sont verrouillés** (exposition, balance des blancs) via `SEM_8_camera_config.py`, comme à l'enregistrement. Au lancement, le script propose de les garder ou de les **refaire** (balance des blancs au papier blanc, utile si la lumière a changé — voir Étape 1). Sans ce verrouillage, l'auto-exposition ferait dériver l'image et tromperait le modèle. Si le module est absent, le script **refuse de démarrer** (sécurité).


### 🚀 Étape 1 : Lancement et préparation

**Lancement**

```bash
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_12_deploy.py
```

Le script enchaîne ensuite cinq préparations :

1. **Sélection du checkpoint** — la liste des checkpoints disponibles s'affiche ; `[Entrée]` utilise le dernier (`last`, recommandé), ou tapez un numéro pour en choisir un autre.
2. **Identification des caméras** — pour chaque caméra affichée, tapez **G** (Globale) ou **P** (Pince) (**Q** pour annuler). Les deux sont requises.
3. **Réglages caméra (balance des blancs)** — pour chaque caméra, les réglages enregistrés s'affichent : `[Entrée]` les garde (réglages du dataset), ou `[R]` les refait. Pour `[R]`, placez une feuille blanche devant les caméras et réglez le blanc dans guvcview sous la lumière du moment (pour que le blanc soit neutre), puis fermez guvcview. À faire si la lumière de la salle diffère de celle de l'enregistrement. *(guvcview requis seulement pour `[R]`.)*
4. **Vérifications automatiques** — résolution exacte (**640×360**, identique à l'entraînement) puis verrouillage des réglages caméra (gardés ou refaits). En cas d'échec, le script s'arrête (ou demande confirmation).
5. **Connexion du bras Follower** — « Branchez le bras FOLLOWER », puis `[Entrée]`. (Le Leader reste débranché.)

> **💡 Note :** Si le masque (`camera_mask.json`) est absent, le script prévient et continue avec l'image brute — mais la cohérence avec l'entraînement est rompue et le comportement risque d'être dégradé.


### ▶️ Étape 2 : L'inférence autonome

Le bras se met d'abord en **position repos** (sécurité), puis le script affiche :

```
🚀 DÉMARRAGE DE L'INFÉRENCE AUTONOME
   Le bras va bouger seul. Assurez-vous que la zone est dégagée.
```

Appuyez sur `[Entrée]` pour démarrer. Une fenêtre affiche les deux caméras (Globale | Pince) avec le numéro d'étape, l'état (pause) et la dernière action.

> **⚠️ Le bras bouge tout seul.** Dégagez la zone de travail et gardez une main prête à le retenir.

**Contrôles (au clavier, dans le terminal) :**

| Touche | Action |
| :--- | :--- |
| **P** | Pause / Reprendre |
| **R** | Retour repos + **désactivation du modèle** (fin d'essai) |
| **Entrée** | Relancer le modèle pour un **nouvel essai** |
| **Q** | Quitter (retour repos puis arrêt) |

**Enchaîner plusieurs essais :** appuyez sur **R** pour terminer un essai — le bras revient au repos et le modèle se désactive. Replacez la pièce, puis appuyez sur **Entrée** pour relancer un essai. (La première action de chaque essai est lissée sur 1 seconde pour éviter un à-coup.)


### 🛡️ Étape 3 : Arrêt et sécurité

Deux façons d'arrêter, au comportement **volontairement différent** :

- **Q (arrêt normal)** : le bras **revient au repos**, puis le script affiche « Tenez le bras — désactivation du couple dans 3 secondes » avant de couper le couple. **Tenez le bras** pendant ce compte à rebours.
- **CTRL+C (arrêt d'urgence)** : le couple est coupé **immédiatement**, **sans** retour au repos (le bras peut être en butée ou coincé). À utiliser si le robot fait un mouvement dangereux.

> **⚠️ Sécurité :** Une fois le couple coupé, le bras retombe sous son propre poids. Soyez prêt à le retenir, surtout lors d'un arrêt d'urgence.


### 📈 Étape 4 : Évaluer le comportement

Observez si le robot exécute correctement la tâche (prendre la pièce, la déposer).

> **⚠️ Rappel :** Une loss d'entraînement basse ne garantit pas un bon comportement réel — c'est ici, au déploiement, que se fait la vraie évaluation.

Si le comportement est mauvais :

- **Mouvements erratiques** → vérifiez la cohérence avec l'entraînement : masque appliqué, réglages caméra verrouillés, résolution 640×360, caméras aux **mêmes positions** qu'à l'enregistrement.
- **Tâche ratée ou robot hésitant** → le modèle manque probablement de données ou d'entraînement : enregistrez davantage d'épisodes (Phase 7), reconsolidez (Phase 8) et réentraînez plus longtemps (Phase 9).


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| Dossier de checkpoints introuvable | Entraînement non fait | Lancer le script 11 (Phase 9) |
| Résolution caméra incorrecte | Caméra ≠ 640×360 | La résolution doit être identique à l'entraînement (640×360) |
| `SEM_8_camera_config.py` indisponible | Module absent | Le placer dans le même dossier que le script (obligatoire) |
| Verrouillage caméra incomplet | v4l2 / caméra | Confirmer `[O]` pour continuer, ou vérifier les caméras |
| Aucun port USB détecté | Branchement / permissions | Vérifier le câble et le groupe `dialout` |
| Masque absent | `camera_mask.json` manquant | Le définir (script 7) pour respecter la cohérence avec l'entraînement |
| Le bras bouge de façon erratique | Incohérence entraînement↔déploiement | Vérifier masque, réglages caméra, résolution, positions des caméras |
| Le bras ne fait pas la tâche | Modèle insuffisant | Plus d'épisodes + réentraînement (Phases 7-9) |


### 💡 Conseils pratiques

1. **Dégagez la zone** et gardez une main prête à retenir le bras — il agit seul.
2. **Mêmes conditions qu'à l'enregistrement** : positions des caméras, éclairage, zone de travail.
3. **Commencez par une position connue** : placez la pièce comme lors des démonstrations.
4. **Utilisez R puis Entrée** pour enchaîner les essais proprement, sans relancer le script.
5. **CTRL+C** est l'arrêt d'urgence — gardez-le à l'esprit en cas de mouvement dangereux.
6. **Démarrez avec le checkpoint `last`** ; testez d'autres checkpoints si le comportement n'est pas satisfaisant.


### 🚀 Commandes de référence rapide

```bash
# Lancer le déploiement
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_12_deploy.py
```

| Action | Touche |
| :--- | :--- |
| Choisir le checkpoint | numéro ou Entrée (dernier) |
| Identifier les caméras | G (Globale) / P (Pince) |
| Pause / Reprendre | P |
| Fin d'essai (retour repos) | R |
| Nouvel essai | Entrée |
| Quitter (arrêt normal) | Q |
| Arrêt d'urgence | CTRL+C |


### ✅ Notes finales

**✅ Phase 10 terminée quand :**

- Le modèle ACT est chargé depuis un checkpoint
- Le bras Follower exécute la tâche **de façon autonome**
- Vous savez arrêter le robot en sécurité (Q et CTRL+C)
- Vous pouvez enchaîner plusieurs essais (R / Entrée)

> **🎉 Pipeline complet :** De la configuration matérielle (Phase 1) au robot autonome (Phase 10), votre chaîne d'apprentissage par imitation est opérationnelle. Le robot reproduit vos démonstrations sans opérateur.

Service Écoles-Médias — DIP Genève
Guide Phase 10 — Version 1.1
