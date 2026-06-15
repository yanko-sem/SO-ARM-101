# Guide Déploiement Autonome SO-ARM 101

## Phase 10 : Déploiement du modèle ACT (inférence autonome)

Service Écoles-Médias (SEM) — DIP Genève

### ✅ Prérequis

- Phases 1 à 9 complétées
- Un modèle ACT entraîné (checkpoint dans `~/lerobot/outputs/train/act_so101_pick_place/checkpoints/`)
- Bras **Follower** branché (le **Leader n'est pas nécessaire** — le modèle remplace l'opérateur)
- Les **deux caméras** (Globale + Pince) branchées, **aux mêmes positions** qu'à l'enregistrement
- Fichiers de calibration présents : `camera_mask.json` (**obligatoire** —
  le déploiement s'arrête sans lui), `camera_settings.json`, `repos_position.json`
- Modules dans le même dossier que le script (obligatoires) :
  `SEM_so101_8_camera_config.py` (repli `SEM_8_camera_config.py`) et
  `SEM_so101_camera_reference.py` (contrôle des deux caméras)
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

- **Le masque de la Globale est réappliqué** : le dataset ayant été enregistré masqué (Phases 6-7), le modèle voit la même image masquée au déploiement. Le masque est **obligatoire** ; sans lui, le script s'arrête.
- **Les deux caméras sont contrôlées vs les références du DATASET d'entraînement.** Au lieu d'un réglage « à l'œil », le script compare au démarrage ce que voient la Globale et la Pince aux **références copiées dans le dataset** qui a servi à entraîner le modèle (retrouvées automatiquement via le checkpoint). Si l'éclairage a dérivé, un **recalibrage guidé** ramène l'image vers la référence. Les réglages caméra sont ensuite **verrouillés** ; si le verrouillage échoue, le script s'arrête (fail-closed). Si un module caméra est absent, le script **refuse de démarrer**.


### 🚀 Étape 1 : Lancement et préparation

**Lancement**

```bash
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_12_deploy.py
```

> **🔑 Ordre du démarrage (important).** Comme à l'enregistrement, la vue de
> la caméra **pince** dépend de la position du bras. Le bras Follower est
> donc **mis au repos AVANT** la préparation des caméras, et y reste maintenu
> pendant le contrôle. Déroulé : **checkpoint → références du dataset →
> masque → Follower au repos → caméras → contrôle des deux caméras →
> inférence.**

Le script enchaîne :

1. **Sélection du checkpoint** — la liste s'affiche ; `[Entrée]` utilise le
   dernier (`last`, recommandé), ou tapez un numéro.
2. **Références du dataset** — le script remonte du checkpoint au dataset qui
   a servi à l'entraînement et y cherche les références caméra (voir l'encadré
   « mode LEGACY » ci-dessous).
3. **Masque de la Globale** — chargé depuis `camera_mask.json`. **Absent →
   le script s'arrête** (lancer le script 7 pour le créer).
4. **Connexion du bras Follower** — « Branchez le bras FOLLOWER », puis
   `[Entrée]` (le Leader reste débranché). Le bras est mis **au repos** et y
   reste maintenu pendant tout le contrôle caméra.
5. **Identification des caméras** — pour chaque caméra affichée, tapez **G**
   (Globale) ou **P** (Pince) (**Q** pour annuler). Les deux sont requises.
6. **Contrôle des deux caméras** (voir Étape 1 bis).

> **📂 Mode LEGACY (datasets anciens).** Si le dataset du modèle ne contient
> pas de références caméra (modèle entraîné avant le système de référence
> visuelle), le script propose :
>
> ```
> ⚠️  Le dataset de ce checkpoint ne contient pas de références caméra.
>   [L] utiliser les références LOCALES actives — mode LEGACY, moins traçable
>   [Q] quitter
> ```
>
> En mode LEGACY, le contrôle se fait contre les références **locales** de la
> machine (moins fiable, mais permet de déployer un ancien modèle). Si le
> dataset contient **une seule** des deux références (état incohérent), le
> script s'arrête : reconsolidez le dataset (Phase 8) ou choisissez un autre
> modèle.

### 📷 Étape 1 bis : Contrôle des deux caméras

Le script contrôle **la Globale puis la Pince**, en comparant ce qu'elles
voient aux références **du dataset d'entraînement**. Pour chaque caméra, un
verdict s'affiche avec les chiffres :

| Verdict | Signification | Choix proposés |
| :--- | :--- | :--- |
| 🟢 | Conforme au dataset | continue automatiquement |
| 🟠 | Écart modéré | `[Entrée]` continuer (journalisé) / `[R]` recalibrer / `[Q]` |
| 🔴 | Trop éloigné du dataset | `[R]` recalibrer / `[Q]` (pas de passage en force) |

Le recalibrage `[R]` vous guide (guvcview) pour ramener l'image vers la
référence du dataset, jusqu'au 🟢. **L'inférence ne démarre que si les deux
caméras sont autorisées.**

> **💡 Pourquoi contre le dataset et pas en local ?** Le modèle a appris dans
> les conditions visuelles du dataset. La référence qui fait foi est donc
> celle **du dataset d'entraînement**, copiée dans ses métadonnées (Phase 8),
> pas une référence locale qui aurait pu changer.

> **🔒 Création de référence impossible au déploiement.** Le script peut
> **recalibrer** (revenir vers la référence) mais jamais **créer** une
> nouvelle référence : cela masquerait une dérive vis-à-vis de
> l'entraînement. La création de référence se fait uniquement à
> l'enregistrement (Phase 7).


### ▶️ Étape 2 : L'inférence autonome

Le bras (déjà au repos depuis le contrôle caméra) reste en sécurité, puis le
script affiche :

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
| Module caméra indisponible | `SEM_so101_8_camera_config.py` ou `SEM_so101_camera_reference.py` absent | Le placer dans le dossier des scripts (obligatoire) |
| Verrouillage caméra incomplet | v4l2 / caméra | Le script s'arrête (fail-closed) ; vérifier les caméras puis relancer |
| Aucun port USB détecté | Branchement / permissions | Vérifier le câble et le groupe `dialout` |
| « Masque globale introuvable » → arrêt | `camera_mask.json` manquant | Le créer (script 7, Phase 6) ; il est obligatoire au déploiement |
| Déploiement annulé : contrôle caméra non concluant | Éclairage ≠ dataset | Au verdict 🟠/🔴, utiliser `[R]` pour recalibrer jusqu'au 🟢 |
| « références partielles » → arrêt | Une seule des 2 références dans le dataset | Reconsolider le dataset (Phase 8) ou choisir un autre modèle |
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
| Mode LEGACY (dataset ancien) | L (références locales) / Q |
| Identifier les caméras | G (Globale) / P (Pince) |
| Recalibrer une caméra (🟠/🔴) | R (guidé jusqu'au 🟢) |
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
Guide Phase 10 — Version 1.2 (déploiement bi-caméra + contrôle vs dataset)
