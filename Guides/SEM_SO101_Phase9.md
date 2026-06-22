# Guide Entraînement ACT SO-ARM 101

## Phase 9 : Entraînement du modèle d'apprentissage par imitation

Service Écoles-Médias (SEM)

### 🧩 Scripts utilisés

`SEM_so101_10_train.py` — lanceur d'entraînement ACT autour du script officiel `lerobot/scripts/train.py` : vérification du GPU et du dataset, choix du profil d'entraînement, lancement, reprise, prolongation, gestion des checkpoints et protection contre la veille.

### 📋 Prérequis

- Phases 1 à 8 complétées
- Dataset consolidé et validé : ≥ 50 épisodes recommandé pour un entraînement complet ; un dataset réduit est possible pour un test technique
- GPU NVIDIA avec au moins 8 Go de VRAM
- Environnement lerobot activé


### 🎯 Objectif de cette phase

**Pourquoi entraîner un modèle ?** L'entraînement transforme vos démonstrations (les 50 épisodes enregistrés) en un modèle d'intelligence artificielle capable de reproduire la tâche de manière autonome. Le modèle ACT (Action Chunking with Transformers) apprend à prédire les actions du robot en observant les images des caméras et les positions des moteurs.

L'entraînement permet de :

- Créer un modèle ACT à partir de vos démonstrations
- Apprendre la correspondance entre images et actions
- Généraliser à partir des 5 positions différentes
- Produire des checkpoints sauvegardés régulièrement


### 🧠 Comprendre le modèle ACT

**ACT (Action Chunking with Transformers)** est une architecture de réseau de neurones conçue pour l'apprentissage par imitation en robotique.

**Principe de fonctionnement :**

1. Le modèle reçoit en entrée les images des 2 caméras et les positions des 6 moteurs
2. Un backbone ResNet18 extrait les caractéristiques visuelles des images
3. Un Transformer prédit les prochaines actions du robot (chunk de 50 pas)
4. Le robot exécute les 15 premières actions prédites, puis recalcule

**Paramètres du modèle :**

| Paramètre | Valeur | Description |
| :--- | :--- | :--- |
| Paramètres totaux | Entre 50 et 80 millions | Taille du réseau, selon la configuration |
| Vision backbone | ResNet18 | Extracteur de caractéristiques visuelles |
| Chunk size | 50 | Nombre de pas d'action prédits |
| Action steps | 15 | Nombre de pas exécutés avant recalcul |
| Encodeur | 4 couches Transformer | Traitement des observations |
| Décodeur | 1 couche Transformer | Génération des actions |
| VAE | Activé | Gère la variabilité des démonstrations |


### 🖥️ Configuration matérielle

**Machine de référence :**

| Composant | Spécification | Rôle |
| :--- | :--- | :--- |
| GPU | NVIDIA Quadro RTX 4000 | Calcul des entraînements |
| VRAM | 8 Go | Stockage du modèle et des batches |
| CPU | Intel Core i9 | Chargement des données |
| RAM | 32 Go | Mémoire système |
| Stockage | ≥ 5 Go libres | Checkpoints et logs |

> **💡 Note :** L'entraînement nécessite un GPU NVIDIA. Sans GPU, l'entraînement serait des dizaines de fois plus lent et n'est pas recommandé.


### 🚀 Étape 1 : Lancement de l'entraînement (Script 10)

**Lancement**

```bash
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_10_train.py
```

**Vérification des prérequis**

Le script vérifie automatiquement :

```
🔍 Vérification des prérequis...
  ✅ GPU : Quadro RTX 4000 (7.6 Go VRAM)
  ✅ Dataset : 50 épisodes, 26579 frames
  ✅ Statistiques : episodes_stats.jsonl présent
  ✅ Script LeRobot : train.py trouvé
  ✅ PyTorch : 2.5.1+cu121
  ✅ CUDA : 12.1
  ✅ Espace disque : 111 Go disponibles
```

**Choix du profil d'entraînement**

Quatre profils sont proposés, adaptés au GPU Quadro RTX 4000 :

| Profil | Steps | Batch size | Durée estimée | Usage |
| :--- | :--- | :--- | :--- | :--- |
| 1. Rapide | 10 000 | 4 | ~30 minutes | Vérifier que tout fonctionne |
| 2. Intermédiaire | 50 000 | 4 | ~2-3 heures | Souvent suffisant pour un petit dataset |
| 3. Standard | 100 000 | 4 | ~4-6 heures | Entraînement recommandé |
| 4. Intensif | 200 000 | 4 | ~8-12 heures | Seulement si 100k est insuffisant |

> **💡 Recommandation :** Commencez toujours par le profil **Rapide** pour valider la chaîne. Si tout se passe bien, relancez en **Standard** pour un vrai entraînement.


### 📊 Étape 2 : Suivi de l'entraînement

**Lecture des logs**

Pendant l'entraînement, le terminal affiche des logs toutes les 100 steps :

```
INFO step:100 smpl:400 ep:1 epch:0.02 loss:10.902 grdn:286.095 lr:1.0e-05 updt_s:0.217 data_s:0.028
INFO step:200 smpl:800 ep:2 epch:0.03 loss:4.341 grdn:159.633 lr:1.0e-05 updt_s:0.161 data_s:0.024
INFO step:300 smpl:1K ep:2 epch:0.05 loss:3.536 grdn:135.938 lr:1.0e-05 updt_s:0.166 data_s:0.024
```

**Comprendre les métriques :**

| Métrique | Signification | Valeurs attendues |
| :--- | :--- | :--- |
| step | Numéro de l'itération | 0 → steps max |
| smpl | Nombre d'échantillons traités | step × batch_size |
| loss | Erreur du modèle (doit diminuer) | Commence ~10, descend vers ~0.5-1.0 |
| grdn | Norme du gradient | Diminue progressivement |
| lr | Taux d'apprentissage | 1.0e-05 (constant) |
| updt_s | Temps par step (secondes) | ~0.15-0.20s |
| data_s | Temps de chargement des données | ~0.02-0.03s |

**Indicateurs de bon fonctionnement :**

- La **loss** diminue régulièrement au fil des steps
- Le **gradient** se stabilise
- Le temps par step (**updt_s**) est constant
- Pas de messages d'erreur

> **⚠️ Important :** Il est normal que la loss descende rapidement au début puis ralentisse. Ne vous inquiétez pas si elle stagne après quelques milliers de steps — c'est le comportement attendu.

**Surveillance du GPU**

Dans un second terminal, surveillez l'utilisation du GPU :

```bash
nvidia-smi -l 5
```

| Métrique | Valeur attendue | Alerte si |
| :--- | :--- | :--- |
| GPU-Util | 90-100% | < 50% (problème de chargement données) |
| Memory-Usage | 2-4 Go / 8 Go | > 7.5 Go (risque de saturation) |
| Temperature | 70-85°C | > 90°C (surchauffe, vérifier ventilation) |
| Power | 100-125W | — |


### ⏸️ Étape 3 : Interruption et reprise

**Interruption propre**

L'entraînement peut être interrompu à tout moment avec **Ctrl+C**. Les checkpoints déjà sauvegardés sont préservés.

**Reprise automatique**

Si vous relancez le script 10 après une interruption :

1. Le script détecte l'entraînement précédent
2. Il propose : **R** (Reprendre), **P** (Prolonger), **N** (Nouveau), **V** (Voir checkpoints), **Q** (Quitter)
3. En choisissant **R**, l'entraînement reprend depuis le dernier checkpoint

> **💡 Note :** La reprise s'appuie sur deux paramètres : `--config_path` (vers le `train_config.json` du dernier checkpoint) et `--resume=true`. LeRobot recharge ainsi le modèle, l'optimiseur et le compteur de steps à partir du dernier checkpoint sauvegardé.

**Prolonger un entraînement (option P)**

L'option **P** reprend un entraînement existant **et augmente le nombre de steps cible**. Elle permet de réutiliser un entraînement court — par exemple un profil **Rapide** (10k) validé — pour le pousser en **Standard** (100k) ou **Intensif** (200k) sans repartir de zéro.

Le script ne propose que les profils **supérieurs** au nombre de steps déjà atteint :

| Steps déjà atteints | Cibles proposées |
| :--- | :--- |
| 10 000 (Rapide) | 50 000 (Intermédiaire), 100 000 (Standard) ou 200 000 (Intensif) |
| 50 000 (Intermédiaire) | 100 000 (Standard) ou 200 000 (Intensif) |
| 100 000 (Standard) | 200 000 (Intensif) |
| 200 000 (Intensif) | Aucune (maximum atteint) |

> **💡 Équivalence :** Un entraînement de 100k prolongé depuis 10k est **équivalent** à un entraînement de 100k lancé depuis zéro. ACT n'utilise aucun planificateur de learning-rate (LR constant à 1.0e-05) et LeRobot recharge l'état de l'optimiseur : la prolongation continue exactement la même trajectoire d'optimisation. On ne perd pas en qualité — on économise les steps déjà calculés.

Concrètement, la prolongation reprend la commande de reprise en y ajoutant la nouvelle cible (`--steps`) et la fréquence de sauvegarde du profil cible (`--save_freq`).

**Sauvegarde des checkpoints**

Les checkpoints sont sauvegardés automatiquement selon le profil :

| Profil | Sauvegarde tous les | Checkpoints attendus |
| :--- | :--- | :--- |
| Rapide | 2 000 steps | 5 checkpoints |
| Intermédiaire | 5 000 steps | 10 checkpoints |
| Standard | 10 000 steps | 10 checkpoints |
| Intensif | 20 000 steps | 10 checkpoints |

Les checkpoints sont stockés dans :

```
~/lerobot/outputs/train/act_so101_pick_place/checkpoints/
├── 002000/
│   └── pretrained_model/
├── 004000/
│   └── pretrained_model/
├── ...
└── last/
    └── pretrained_model/
```


> **💡 Tirer parti des checkpoints intermédiaires :** Tous les checkpoints sont conservés (par exemple 10k, 50k, 100k pour un profil Standard). Vous pouvez en déployer plusieurs en Phase 10 — par exemple 10k, 50k et 100k — pour observer concrètement la progression de l'apprentissage : un modèle peu entraîné (10k) est souvent saccadé ou incomplet, alors qu'un modèle plus entraîné (100k) est plus fluide. Le choix du checkpoint à déployer se fait dans le script 11.


### 📈 Étape 4 : Évaluation de la qualité

**Critères de réussite de l'entraînement**

| Critère | Profil Rapide (10k) | Profil Standard (100k) |
| :--- | :--- | :--- |
| Loss finale | < 3.0 | < 1.0 |
| Pas d'erreur CUDA OOM | ✅ | ✅ |
| Checkpoints sauvegardés | ≥ 3 | ≥ 8 |
| Durée cohérente | ~30 min | ~4-6h |

> **⚠️ Attention :** Une loss basse ne garantit pas un bon comportement du robot. La validation réelle se fait en Phase 10 (déploiement). Le profil Rapide sert uniquement à valider que la chaîne technique fonctionne.


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| "CUDA non disponible" | Driver NVIDIA non chargé | `nvidia-smi`, réinstaller le driver si nécessaire |
| "CUDA out of memory" | VRAM insuffisante | Fermer les applications lourdes (Chrome, etc.) |
| "Dataset introuvable" | Script 9 non exécuté | Lancer d'abord le script 9 |
| "episodes_stats.jsonl manquant" | Script 9 non exécuté ou préparation incomplète | Relancer la Phase 8 : `python SEM_so101_9_dataset.py` |
| Dossier d'entraînement déjà présent | Entraînement précédent | Le script propose Reprendre / Nouveau / Voir ; l'ancien n'est supprimé qu'après confirmation finale |
| Loss ne descend pas | Données de mauvaise qualité | Vérifier les épisodes, réenregistrer si nécessaire |
| Entraînement très lent | GPU non utilisé | Vérifier `nvidia-smi`, GPU-Util doit être > 90% |
| Erreur torchcodec | Backend vidéo incompatible | Le script utilise `pyav` automatiquement |
| Température GPU > 90°C | Mauvaise ventilation | Vérifier que le PC est bien ventilé, faire une pause |


### 💡 Conseils pratiques

1. **Commencez par le Rapide :** Validez que tout fonctionne avant un entraînement long
2. **Fermez les applications :** Chrome et Firefox consomment de la VRAM GPU — fermez-les pendant l'entraînement
3. **Planifiez l'entraînement Standard :** Lancez-le en fin de journée et laissez tourner la nuit
4. **Surveillez la température :** Gardez `nvidia-smi -l 5` ouvert dans un second terminal
5. **N'interrompez pas inutilement :** Les checkpoints sont réguliers, mais chaque interruption fait perdre le travail depuis le dernier checkpoint
6. **Gardez le PC branché :** Une coupure de courant pendant l'entraînement n'est pas dramatique (les checkpoints sont sauvegardés), mais elle fait perdre du temps


### 🚀 Commandes de référence rapide

```bash
# Lancer l'entraînement
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_10_train.py

# Surveiller le GPU (dans un autre terminal)
nvidia-smi -l 5

# Voir les checkpoints sauvegardés
ls ~/lerobot/outputs/train/act_so101_pick_place/checkpoints/
```


### 📝 Notes finales

**✅ Phase 9 terminée quand :**

- L'entraînement Rapide (10k steps) se termine sans erreur
- L'entraînement Standard (100k steps) est complété
- La loss finale est inférieure à 1.0
- Les checkpoints sont sauvegardés dans le dossier de sortie
- Le GPU a fonctionné à > 90% d'utilisation pendant l'entraînement

> **🚀 Objectif atteint :** Votre modèle ACT est entraîné ! Il a appris à associer les images des caméras aux mouvements des moteurs. Passez à la Phase 10 pour déployer le modèle et voir votre robot agir de manière autonome.
