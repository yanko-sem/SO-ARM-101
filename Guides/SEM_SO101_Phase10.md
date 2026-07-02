# Guide Déploiement Autonome SO-ARM 101

## Phase 10 : Déploiement du modèle ACT (inférence autonome)

Service Écoles-Médias (SEM)

### 🧩 Scripts utilisés

- `SEM_so101_11_deploy.py` — déploiement autonome du modèle ACT : **sélection du modèle nommé, puis du checkpoint**, chargement du modèle, contrôle du Follower, lecture des deux caméras, inférence et sécurité.
- `SEM_so101_camera_auto.py` — réglage caméra en **exposition (et balance des blancs) auto puis figée** (via `v4l2-ctl`) et **contrôle image simple** (plancher physique de lumière sur l'image brute).

### 📋 Prérequis

- Phases 1 à 9 complétées
- Au moins un modèle ACT entraîné et **chargeable** : un dossier `~/lerobot/outputs/train/<nom>/checkpoints/<step>/pretrained_model/` contenant `config.json` et `model.safetensors`
- Bras **Follower** branché (le **Leader n'est pas nécessaire** — le modèle remplace l'opérateur)
- Les **deux caméras** (Globale + Pince) branchées, **aux mêmes positions** qu'à l'enregistrement
- Fichiers de calibration présents : `follower_calibration.json` et
  `repos_position.json` (Phase 3), et `camera_mask.json` (**obligatoire** —
  le déploiement s'arrête sans lui)
- Module dans le même dossier que le script (obligatoire) :
  `SEM_so101_camera_auto.py` (réglage exposition auto puis figée + contrôle image)
- Environnement lerobot activé ; GPU NVIDIA recommandé, CPU possible mais plus lent


### 🎯 Objectif de cette phase

**Pourquoi déployer ?** C'est l'aboutissement du projet : le modèle ACT entraîné prend la place de l'opérateur et exécute la tâche **de façon autonome**. Plus de téléopération — le robot observe et agit seul.

Cette phase permet de :

- Choisir un modèle ACT entraîné (parmi ceux disponibles) et l'un de ses checkpoints, puis le faire piloter le bras Follower
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

Deux points sont **importants pour la cohérence entraînement ↔ déploiement** :

- **Le masque de la Globale est réappliqué** : le dataset ayant été enregistré masqué (Phases 6-7), le modèle voit la même image masquée au déploiement. Le masque est **obligatoire** ; sans lui, le script s'arrête.
- **L'exposition des deux caméras est réglée (auto puis figée), puis l'image est contrôlée.** Comme à l'enregistrement, chaque caméra laisse son exposition (et sa balance des blancs) s'ajuster à la lumière réelle de la salle pendant quelques secondes, puis la **fige** pour la session. Le script contrôle ensuite l'image **brute** (plancher physique de lumière) et n'autorise l'inférence que si les deux caméras sont exploitables. Si un réglage ne peut pas être appliqué, le script s'arrête (*fail-closed*) ; si le module caméra est absent, il **refuse de démarrer**. Ce qui doit rester identique à l'enregistrement, c'est la **position** des caméras et le **cadrage** (le masque), pas les conditions d'éclairage : l'exposition se ré-adapte à la salle.


### 🚀 Étape 1 : Lancement et préparation

**Lancement**

```bash
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_11_deploy.py
```

> **🔑 Ordre du démarrage (important).** Comme à l'enregistrement, la vue de
> la caméra **pince** dépend de la position du bras. Le bras Follower est
> donc **mis au repos AVANT** la préparation des caméras, et y reste maintenu
> pendant le réglage et le contrôle. Déroulé : **modèle → checkpoint → module
> caméra → chargement du modèle → masque → Follower au repos → identification
> caméras → connexion des caméras → réglage exposition (auto puis figée) →
> contrôle image → inférence.**

Le script enchaîne :

1. **Sélection du modèle** — la liste des modèles disponibles s'affiche. Le
   choix est **explicite** (tapez un numéro) : il n'y a **aucun modèle par
   défaut**. Vous pouvez aussi taper **N** pour saisir un nom manuellement, ou
   **Q** pour quitter. Seuls les modèles possédant au moins un checkpoint
   **réellement chargeable** sont proposés.
2. **Sélection du checkpoint** — la liste s'affiche ; `[Entrée]` utilise le
   checkpoint recommandé — `last` s'il est chargeable, sinon le plus grand
   checkpoint numérique chargeable —, ou tapez un numéro. Seuls les checkpoints
   chargeables (`config.json` + `model.safetensors`) sont listés.
3. **Vérification du module caméra** — le module `SEM_so101_camera_auto` est
   obligatoire ; le script s'arrête s'il manque.
4. **Chargement du modèle ACT** — le checkpoint sélectionné est chargé sur le
   périphérique disponible (GPU si présent, sinon CPU).
5. **Masque de la Globale** — chargé depuis `camera_mask.json`. **Absent →
   le script s'arrête** (lancer le script 7 pour le créer).
6. **Connexion du bras Follower et mise au repos** — « Branchez le bras
   FOLLOWER », puis `[Entrée]` (le Leader reste débranché). Le bras est mis
   **au repos** et y reste maintenu pendant tout le réglage et le contrôle
   caméra.
7. **Identification des caméras** — pour chaque caméra affichée (fenêtre live),
   tapez **G** (Globale), **P** (Pince), **Q** pour passer cette caméra ou
   **Échap** pour tout annuler. Les deux caméras doivent être identifiées ;
   sinon le déploiement s'arrête.
8. **Réglage de l'exposition (auto puis figée) et contrôle image** des deux
   caméras (voir Étape 1 bis).

### 📷 Étape 1 bis : Réglage et contrôle des deux caméras

Le bras Follower reste **au repos**. Pour chaque caméra (la Globale puis la
Pince), le script :

- **règle l'exposition — auto puis figée** : l'exposition (et la balance des
  blancs) s'ajuste à la lumière réelle de la salle pendant quelques secondes,
  flux actif, puis est **figée** pour la session (50 Hz anti-scintillement). Si
  un réglage échoue, le déploiement **s'arrête** (*fail-closed*) ;
- **contrôle l'image brute** (plancher physique de lumière) et rend un verdict :

| Verdict | Signification | Choix proposés (dans la fenêtre) |
| :--- | :--- | :--- |
| 🟢 | Lumière exploitable | continue automatiquement |
| 🟠 | Lumière limite (image un peu sombre ou un peu claire) | `C` continuer / `R` re-régler / `Q` quitter |
| 🔴 | Image inexploitable (cramée ou écrasée) | `R` re-régler / `Q` quitter (pas de `C`) |

La mesure porte sur la **zone utile du masque** pour la Globale (le plateau) et
sur le **plein cadre** pour la Pince. La touche `R` relance le réglage
« exposition auto puis figée » (après, par exemple, avoir ajusté la lumière de
la salle). **L'inférence ne démarre que si les deux caméras sont autorisées**
(🟢, ou 🟠 accepté avec `C`).

> **💡 L'éclairage n'a pas à être identique à l'entraînement.** Le modèle apprend
> à généraliser à partir de démonstrations enregistrées sous des lumières variées
> mais exploitables — une augmentation d'éclairage à l'entraînement pourra renforcer
> cette tolérance lorsqu'elle sera activée dans le script 10. Au déploiement,
> l'exposition se ré-adapte à la lumière de la salle puis se fige. Ce qui doit rester
> identique à l'enregistrement, c'est la **position des caméras** et le **cadrage**
> (le masque), pas la lumière.


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

- **Q (arrêt normal)** : le bras **revient au repos**, puis le script affiche « Tenez le bras — désactivation du couple dans 3 secondes » avant de couper le couple. **Tenez le bras** pendant ce délai de 3 secondes.
- **CTRL+C (arrêt d'urgence)** : le couple est coupé **immédiatement**, **sans** retour au repos (le bras peut être en butée ou coincé). À utiliser si le robot fait un mouvement dangereux.

> **⚠️ Sécurité :** Une fois le couple coupé, le bras retombe sous son propre poids. Soyez prêt à le retenir, surtout lors d'un arrêt d'urgence.


### 📈 Étape 4 : Évaluer le comportement

Observez si le robot exécute correctement la tâche (prendre la pièce, la déposer).

> **⚠️ Rappel :** Une loss d'entraînement basse ne garantit pas un bon comportement réel — c'est ici, au déploiement, que se fait la vraie évaluation.

Si le comportement est mauvais :

- **Mouvements erratiques** → vérifiez la cohérence avec l'entraînement : masque appliqué, exposition réglée (auto puis figée), résolution 640×360, caméras aux **mêmes positions** et **mêmes cadrages** qu'à l'enregistrement.
- **Tâche ratée ou robot hésitant** → le modèle manque probablement de données ou d'entraînement : enregistrez davantage d'épisodes (Phase 7), reconsolidez (Phase 8) et réentraînez plus longtemps (Phase 9).


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| Aucun modèle proposé (« aucun modèle trouvé ») | Aucun entraînement, ou aucun checkpoint chargeable | Lancer le script 10 (Phase 9) et laisser au moins un checkpoint se sauvegarder |
| Un modèle attendu n'apparaît pas dans la liste | Ses checkpoints sont incomplets (`config.json`/`model.safetensors` absents) | Réentraîner ou prolonger ce modèle jusqu'à un checkpoint complet |
| Résolution caméra incorrecte | Caméra ≠ 640×360 | La résolution doit être identique à l'entraînement (640×360) |
| Module caméra indisponible | `SEM_so101_camera_auto.py` absent | Le placer dans le dossier des scripts (obligatoire) |
| « réglage d'exposition non appliqué » → arrêt | `v4l2-ctl` absent, ou contrôle refusé par le pilote | Installer `v4l-utils` ; vérifier les caméras ; relancer |
| Aucun port USB détecté | Branchement / permissions | Vérifier le câble et le groupe `dialout` |
| « Masque globale introuvable » → arrêt | `camera_mask.json` manquant | Le créer (script 7, Phase 6) ; il est obligatoire au déploiement |
| Image 🔴 inexploitable (cramée ou écrasée) | Lumière trop forte / trop faible | Ajuster la lumière de la salle, puis `R` pour re-régler (**pas de `C` en 🔴**) |
| Image 🟠 limite | Lumière un peu sombre ou un peu claire | `C` pour continuer, ou `R` pour re-régler |
| Le bras bouge de façon erratique | Incohérence entraînement↔déploiement | Vérifier masque, cadrage, résolution, **positions** des caméras |
| Le bras ne fait pas la tâche | Modèle insuffisant | Plus d'épisodes + réentraînement (Phases 7-9) |


### 💡 Conseils pratiques

1. **Dégagez la zone** et gardez une main prête à retenir le bras — il agit seul.
2. **Mêmes cadrages qu'à l'enregistrement** : positions des caméras et zone de travail. L'**éclairage peut varier** (l'exposition se ré-adapte puis se fige) ; évitez seulement les extrêmes (image cramée ou écrasée).
3. **Commencez par une position connue** : placez la pièce comme lors des démonstrations.
4. **Utilisez R puis Entrée** pour enchaîner les essais proprement, sans relancer le script.
5. **CTRL+C** est l'arrêt d'urgence — gardez-le à l'esprit en cas de mouvement dangereux.
6. **Choisissez le modèle voulu, puis démarrez avec le checkpoint recommandé** (`last` s'il est chargeable) ; testez d'autres checkpoints (ou un autre modèle) si le comportement n'est pas satisfaisant.


### 🚀 Commandes de référence rapide

```bash
# Lancer le déploiement
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_11_deploy.py
```

| Action | Touche |
| :--- | :--- |
| Choisir le modèle | numéro, ou N pour saisir un nom |
| Choisir le checkpoint | numéro ou Entrée (dernier) |
| Identifier les caméras | G (Globale) / P (Pince) / Q (passer) / Échap (annuler) |
| Contrôle image caméra (🟠/🔴) | C (continuer si 🟠) / R (re-régler l'exposition) / Q |
| Pause / Reprendre | P |
| Fin d'essai (retour repos) | R |
| Nouvel essai | Entrée |
| Quitter (arrêt normal) | Q |
| Arrêt d'urgence | CTRL+C |


### 📝 Notes finales

**✅ Phase 10 terminée quand :**

- Le modèle nommé et son checkpoint ont été choisis, et le modèle ACT est chargé
- Le bras Follower exécute la tâche **de façon autonome**
- Vous savez arrêter le robot en sécurité (Q et CTRL+C)
- Vous pouvez enchaîner plusieurs essais (R / Entrée)

> **🎉 Pipeline complet :** De la configuration matérielle (Phase 1) au robot autonome (Phase 10), votre chaîne d'apprentissage par imitation est opérationnelle. Le robot reproduit vos démonstrations sans opérateur.
