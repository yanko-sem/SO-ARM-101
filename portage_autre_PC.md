# Portage du projet SO-ARM 101 vers un autre PC

## Transférer le pipeline complet (calibration, datasets, modèles) d'un poste à un autre

Service Écoles-Médias (SEM)

### 🎯 Objectif

Utiliser l'ensemble des scripts (1 à 11) sur un second PC (p. ex. un portable de démonstration), avec la bonne configuration, sans tout refaire. Principe : le **code se réinstalle**, les **données se copient**.

### 🧭 Principe

- Le **code** (fork LeRobot + `Scripts_SEM`, dont `camera_auto`) ne se copie pas : il se réinstalle via la **Phase 1** sur le nouveau poste.
- Les **données** (calibration, datasets, modèles) se copient depuis le poste d'origine.
- La calibration suit le **matériel** (les bras), pas le PC : la copier est valide **tant que ce sont les mêmes bras physiques**. C'est une mesure physique qui peut dériver au transport → Étape 4.

### 📋 Étape 1 — Environnement sur le nouveau PC

Dérouler la **Phase 1** (`SEM_SO101_Phase1.md`) : environnement conda `lerobot`, clonage du fork LeRobot et du dépôt `Scripts_SEM`, `v4l-utils`, groupes `dialout` et `video`.

> Copier le dossier des scripts seulement si vous avez des modifications locales non poussées sur GitHub.

### 📦 Étape 2 — Fichiers à copier

| Élément | Chemin | Utile pour | Quand |
| :--- | :--- | :--- | :--- |
| Configuration / calibration | `~/lerobot/calibration/` *(dossier entier)* | scripts 3 → 11 | toujours |
| Dataset brut | `~/.cache/huggingface/lerobot/local/so101_pick_place/` | 8 (poursuite), 9 | si travail sur dataset |
| Dataset consolidé | `~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/` | 10, visualisation | si entraînement / visu |
| Sorties d'entraînement | `~/lerobot/outputs/train/act_so101_pick_place/` *(dossier entier)* | 10 (reprise), 11 (déploiement) | si déploiement / reprise |

`~/lerobot/calibration/` contient : `leader_calibration.json`, `follower_calibration.json`, `repos_position.json`, `teleoperation_config_cote.json` (+ `_face.json` si utilisé), `camera_mask.json`.

> **À ne pas copier :** rien d'autre n'est requis. Le script 11 ne lit pas le dataset ; `sem_training_params.json` est purement informatif.

### 🚚 Étape 3 — Commandes de transfert

Vérifier d'abord quels dossiers existent (retirer de la commande ceux qui sont absents, sinon `tar` échoue) :

```bash
ls ~/lerobot/calibration
ls ~/.cache/huggingface/lerobot/local/
ls ~/lerobot/outputs/train/act_so101_pick_place/
```

Sur le PC d'origine — créer l'archive (le `h` de `czhf` déréférence le lien `checkpoints/last`) :

```bash
tar czhf portage_so101.tgz -C ~ \
  lerobot/calibration \
  lerobot/outputs/train/act_so101_pick_place \
  .cache/huggingface/lerobot/local/so101_pick_place \
  .cache/huggingface/lerobot/local/so101_pick_place_consolidated
```

Sur le nouveau PC (après Phase 1) — **si le poste contient déjà une configuration SO-ARM 101**, la sauvegarder d'abord (l'extraction écrase les fichiers existants) :

```bash
mkdir -p ~/backup_so101_avant_portage
cp -a ~/lerobot/calibration                        ~/backup_so101_avant_portage/ 2>/dev/null
cp -a ~/lerobot/outputs/train/act_so101_pick_place ~/backup_so101_avant_portage/ 2>/dev/null
cp -a ~/.cache/huggingface/lerobot/local           ~/backup_so101_avant_portage/ 2>/dev/null
```

Puis extraire :

```bash
tar xzf portage_so101.tgz -C ~
```

Alternative réseau (déréférence aussi les liens symboliques) :

```bash
rsync -aL ORIGINE:lerobot/calibration/ ~/lerobot/calibration/
rsync -aL ORIGINE:lerobot/outputs/train/act_so101_pick_place/ ~/lerobot/outputs/train/act_so101_pick_place/
rsync -a  ORIGINE:.cache/huggingface/lerobot/local/so101_pick_place/ ~/.cache/huggingface/lerobot/local/so101_pick_place/
rsync -a  ORIGINE:.cache/huggingface/lerobot/local/so101_pick_place_consolidated/ ~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/
```

Après copie, vérifier que le **modèle** est bien présent. Avec `tar -h` / `rsync -aL`, `last` devient un vrai dossier — `readlink` n'est donc pas un test fiable ; on teste le contenu réel (les deux fichiers lus par le script 11) :

```bash
ls -l ~/lerobot/outputs/train/act_so101_pick_place/checkpoints/last
test -f ~/lerobot/outputs/train/act_so101_pick_place/checkpoints/last/pretrained_model/model.safetensors && echo "modele OK"
test -f ~/lerobot/outputs/train/act_so101_pick_place/checkpoints/last/pretrained_model/config.json       && echo "config OK"
```

> **Note `checkpoints/last` :** souvent un lien symbolique à l'origine. Si vous ne le déréférencez pas, déployez plutôt depuis un checkpoint numérique (ex. `checkpoints/100000/`) qu'un lien éventuellement cassé. `readlink -f .../last` reste utile à titre purement informatif.

### 🛠️ Étape 4 — Après le transport

La calibration (MIN/MAX des servos) est une mesure physique qui peut **dériver** au transport (chocs, jeu mécanique, remontage d'un palonnier, température). Avant une démo :

1. **Vérifier** le comportement (script 4). Si un bras force ou se décale, **recalibrer** (script 2).
2. On ne refait **que** la calibration : `repos_position.json` (stocké en %) et les configs de téléopération (mapping logique) restent valides après recalibration.
3. **Masque caméra** : valide seulement si la géométrie caméra ↔ plateau est reproduite. Sinon, le refaire :

```bash
python SEM_so101_7_teleoperation_camera.py --refaire-masque
```

(ou la touche `[M]` pendant la téléopération). Pour le script 11, reproduire autant que possible le **cadrage** d'entraînement : l'exposition se réadapte automatiquement, pas le cadrage.

### ⚠️ Notes

- **Entraînement (script 10) sur un portable sans GPU** : bascule automatique sur **CPU**, beaucoup plus lent — utilisable pour un test léger, pas pour un entraînement complet.
- **Mêmes bras physiques** requis pour que la calibration copiée ait un sens.

### 📝 Récapitulatif

- **Réinstaller** : l'environnement (Phase 1).
- **Copier** : `~/lerobot/calibration/`, les datasets voulus, `~/lerobot/outputs/train/act_so101_pick_place/`.
- **Vérifier sur place** : calibration (recalibrer si dérive), masque (si la caméra a bougé).
