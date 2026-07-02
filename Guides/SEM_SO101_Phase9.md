--- ORIG_P9.md	2026-07-02 14:19:05.793151498 +0000
+++ SEM_SO101_Phase9.md	2026-07-02 14:28:24.997446642 +0000
@@ -6,7 +6,7 @@
 
 ### 🧩 Scripts utilisés
 
-`SEM_so101_10_train.py` — lanceur d'entraînement ACT autour du script officiel `lerobot/scripts/train.py` : vérification du GPU et du dataset, choix du profil d'entraînement, lancement, reprise, prolongation, gestion des checkpoints et protection contre la veille.
+`SEM_so101_10_train.py` — lanceur d'entraînement ACT autour du script officiel `lerobot/scripts/train.py` : **création ou sélection d'un modèle nommé**, vérification du GPU et du dataset, choix du profil d'entraînement, lancement, reprise, prolongation, remplacement, gestion des checkpoints et protection contre la veille.
 
 ### 📋 Prérequis
 
@@ -27,6 +27,11 @@
 - Généraliser à partir des 5 positions différentes
 - Produire des checkpoints sauvegardés régulièrement
 
+> **💡 Plusieurs modèles nommés.** Chaque entraînement produit un **modèle nommé**
+> (un dossier sous `~/lerobot/outputs/train/`). Vous pouvez ainsi entraîner et
+> conserver plusieurs modèles issus de démonstrations différentes, et choisir
+> lequel déployer en Phase 10 — sans réentraîner entre deux démonstrations.
+
 
 ### 🧠 Comprendre le modèle ACT
 
@@ -96,6 +101,41 @@
 > (« Pas de GPU CUDA détecté — l'entraînement utilisera le CPU… ») et
 > l'entraînement se poursuit sur CPU.
 
+**Choix ou création du modèle**
+
+Le script gère un **registre local de modèles nommés** : chaque modèle est un
+dossier sous `~/lerobot/outputs/train/`. Le menu propose de reprendre un modèle
+existant ou d'en créer un nouveau :
+
+```
+📂 MODÈLE À ENTRAÎNER
+
+📋 Modèles existants (2) :
+   [ 1]  cube_centre                      (3 checkpoint(s))
+   [ 2]  cube_gauche_droite               (1 checkpoint(s))
+
+   [C] Créer un nouveau modèle
+   [Q] Quitter
+```
+
+- Un **numéro** sélectionne un modèle existant (pour le reprendre, le prolonger
+  ou le remplacer — voir Étape 3).
+- **C** crée un nouveau modèle : vous saisissez un **nom libre**, composé
+  uniquement de minuscules, chiffres, tiret et souligné (`a`–`z`, `0`–`9`, `-`,
+  `_`), et **commençant par une lettre ou un chiffre**. Un nom hors de ces
+  règles est **refusé** (jamais corrigé automatiquement) : vous ressaisissez.
+- Le nombre entre parenthèses est le nombre de checkpoints **réellement
+  chargeables** du modèle.
+
+> **📁 Le nom saisi est le nom exact du dossier.** Un modèle nommé `cube_centre`
+> est stocké dans `~/lerobot/outputs/train/cube_centre/`. Aucun préfixe n'est
+> ajouté automatiquement.
+
+> **⚠️ Ne renommez jamais un dossier de modèle à la main** après sa création.
+> La reprise d'entraînement relit le chemin de sortie enregistré à l'intérieur
+> du checkpoint (`train_config.json`) : renommer le dossier romprait cette
+> correspondance. Pour un autre nom, créez simplement un nouveau modèle.
+
 **Choix du profil d'entraînement**
 
 Quatre profils sont proposés. Les durées indiquées sont des **estimations sur le GPU de référence** (Quadro RTX 4000) ; sur CPU, elles sont **bien plus longues** :
@@ -167,12 +207,20 @@
 
 **Reprise automatique**
 
-Si vous relancez le script 10 après une interruption :
+Si vous sélectionnez un modèle **existant** (ou relancez le script après une
+interruption) :
 
-1. Le script détecte l'entraînement précédent
-2. Il propose : **R** (Reprendre), **P** (Prolonger), **N** (Nouveau), **V** (Voir checkpoints), **Q** (Quitter)
+1. Le script détecte l'entraînement précédent du modèle choisi
+2. Il propose : **R** (Reprendre), **P** (Prolonger), **N** (Remplacer ce
+   modèle), **A** (Choisir un autre modèle), **V** (Voir checkpoints),
+   **Q** (Quitter)
 3. En choisissant **R**, l'entraînement reprend depuis le dernier checkpoint
 
+> **🗑️ Remplacer un modèle (N)** supprime définitivement le modèle existant et
+> tous ses checkpoints, puis relance un entraînement neuf sous le même nom. Par
+> sécurité, la suppression n'a lieu qu'après la saisie explicite du mot
+> **`SUPPRIMER`** ; toute autre saisie annule et conserve le modèle.
+
 > **💡 Note :** La reprise s'appuie sur deux paramètres : `--config_path` (vers le `train_config.json` du dernier checkpoint) et `--resume=true`. LeRobot recharge ainsi le modèle, l'optimiseur et le compteur de steps à partir du dernier checkpoint sauvegardé.
 
 **Prolonger un entraînement (option P)**
@@ -188,7 +236,7 @@
 | 100 000 (Standard) | 200 000 (Intensif) |
 | 200 000 (Intensif) | Aucune (maximum atteint) |
 
-> **💡 Équivalence :** Un entraînement de 100k prolongé depuis 10k est **équivalent** à un entraînement de 100k lancé depuis zéro. ACT n'utilise aucun planificateur de learning-rate (LR constant à 1.0e-05) et LeRobot recharge l'état de l'optimiseur : la prolongation continue exactement la même trajectoire d'optimisation. On ne perd pas en qualité — on économise les steps déjà calculés.
+> **💡 Prolonger sans repartir de zéro :** L'option **P** reprend l'entraînement depuis le dernier checkpoint via `--config_path` et `--resume=true`, puis augmente la cible de steps. LeRobot enregistre l'état complet de l'entraînement (poids, optimiseur, générateur aléatoire, compteur de steps) et le recharge à la reprise ; comme ACT utilise un learning-rate constant (1.0e-05, sans planificateur), la prolongation vise à **continuer la même trajectoire d'optimisation** au lieu de recommencer, en conservant les steps déjà calculés. Ce comportement doit être **confirmé sur le `train.py` installé** avant d'être considéré comme définitif.
 
 Concrètement, la prolongation reprend la commande de reprise en y ajoutant la nouvelle cible (`--steps`) et la fréquence de sauvegarde du profil cible (`--save_freq`).
 
@@ -203,17 +251,20 @@
 | Standard | 10 000 steps | 10 checkpoints |
 | Intensif | 20 000 steps | 10 checkpoints |
 
-Les checkpoints sont stockés dans :
+Le dossier du modèle nommé contient les paramètres SEM et les checkpoints :
 
 ```
-~/lerobot/outputs/train/act_so101_pick_place/checkpoints/
-├── 002000/
-│   └── pretrained_model/
-├── 004000/
-│   └── pretrained_model/
-├── ...
-└── last/
-    └── pretrained_model/
+~/lerobot/outputs/train/<nom_du_modele>/
+├── sem_training_params.json        (métadonnées SEM, écrites après le lancement)
+└── checkpoints/
+    ├── 002000/
+    │   └── pretrained_model/
+    │       ├── config.json
+    │       ├── model.safetensors
+    │       └── train_config.json
+    ├── ...
+    └── last/
+        └── pretrained_model/
 ```
 
 
@@ -242,7 +293,8 @@
 | "CUDA out of memory" | VRAM insuffisante | Fermer les applications lourdes (Chrome, etc.) |
 | "Dataset introuvable" | Script 9 non exécuté | Lancer d'abord le script 9 |
 | "episodes_stats.jsonl manquant" | Script 9 non exécuté ou préparation incomplète | Relancer la Phase 8 : `python SEM_so101_9_dataset.py` |
-| Dossier d'entraînement déjà présent | Entraînement précédent | Le script propose Reprendre / Nouveau / Voir ; l'ancien n'est supprimé qu'après confirmation finale |
+| Dossier de modèle déjà présent | Modèle existant, ou dossier partiel après un entraînement interrompu/échoué | Le script propose Reprendre / Prolonger / Remplacer / Autre modèle ; le remplacement exige la saisie de `SUPPRIMER` |
+| Nom de modèle refusé | Caractères non autorisés, ou ne commence pas par une lettre/un chiffre | Utiliser uniquement `a-z`, `0-9`, `-`, `_`, en commençant par une lettre ou un chiffre |
 | Loss ne descend pas | Données de mauvaise qualité | Vérifier les épisodes, réenregistrer si nécessaire |
 | Entraînement très lent | GPU non utilisé | Vérifier `nvidia-smi`, GPU-Util doit être > 90% |
 | Erreur torchcodec | Backend vidéo incompatible | Le script utilise `pyav` automatiquement |
@@ -270,8 +322,11 @@
 # Surveiller le GPU (dans un autre terminal)
 nvidia-smi -l 5
 
-# Voir les checkpoints sauvegardés
-ls ~/lerobot/outputs/train/act_so101_pick_place/checkpoints/
+# Lister les modèles entraînés
+ls ~/lerobot/outputs/train/
+
+# Voir les checkpoints d'un modèle (remplacez <nom_du_modele>)
+ls ~/lerobot/outputs/train/<nom_du_modele>/checkpoints/
 ```
