# Guide Tests et Contrôle SO-ARM 101

## Phase 4 : Test et contrôle manuel des robots

Service Écoles-Médias (SEM)

### 📋 Prérequis

- Phase 1 complétée (LeRobot installé)
- Phase 2 complétée (Servos configurés avec IDs 1-6)
- Phase 3 complétée (Calibration effectuée)
- Scripts SEM installés depuis GitHub
- Environnement lerobot activé


### 🎯 Objectif des tests

**Pourquoi tester ?** Le script de contrôle permet de vérifier que tous les servos fonctionnent correctement et respectent les limites de calibration. C'est l'étape finale avant la téléopération.

Les tests permettent de :

- Vérifier le bon fonctionnement de chaque servo
- Valider les limites définies lors de la calibration
- S'habituer au contrôle du robot
- Identifier les problèmes avant la téléopération


### 🛠️ Étape 1 : Préparation

**Activation de l'environnement**

```bash
# Activer l'environnement conda
conda activate lerobot
# Se placer dans le dossier des scripts
cd ~/lerobot/Scripts_SEM/scripts
# Vérifier que le script est présent
ls SEM_so101_4_control.py
```

**Configuration matérielle**

| Élément | Vérification |
| :--- | :--- |
| Adaptateur USB | Branché sur le port USB du robot à tester |
| Alimentation | Active (LED allumée) |
| Espace de travail | Dégagé pour permettre les mouvements |
| Calibration | Fichier de calibration présent (Phase 3 complétée) |

> **⚠️ Important :** Un seul robot à la fois ! Branchez uniquement l'adaptateur USB du robot que vous voulez tester.


### 🚀 Étape 2 : Lancement du contrôle

**Lancement du script unifié**

```bash
python SEM_so101_4_control.py
```

Le script vous demande d'abord quel robot tester :

```
╔══════════════════════════════════════════════════════════╗
║     CONTRÔLE MANUEL SO-ARM 101                          ║
╚══════════════════════════════════════════════════════════╝

Contrôler [L]eader ou [F]ollower?
Choix: _
```

Tapez `L` ou `F` puis Entrée. Le script se connecte, charge la calibration et place le bras en position INITIALE sécurisée.

**Menu des contrôles**

```
╔════════════════════════════════════════════════════════╗
║                    CONTRÔLES                           ║
╠════════════════════════════════════════════════════════╣
║  ↑/↓       : Augmenter/Diminuer position              ║
║  ←/→       : Changer de servo (1-6)                   ║
║  ESPACE    : Centrer le servo actif                   ║
║  I         : Position INITIALE                        ║
║  C         : Centrer TOUS les servos                  ║
║  P         : Mode précis ON/OFF (pas 10 vs 50)        ║
║  S         : Afficher tableau positions               ║
║  A         : Position ATTRAPER                        ║
║  R         : Position REPOS                           ║
║  Q         : Quitter                                  ║
║  X         : ARRÊT D'URGENCE                          ║
╚════════════════════════════════════════════════════════╝
```

> **Note :** Au démarrage, tous les servos sont automatiquement placés en position INITIALE.


### 🎮 Étape 3 : Commandes de contrôle

**Contrôles de base**

| Touche | Action |
| :--- | :--- |
| ↑ Flèche HAUT | Augmente la position du servo actif |
| ↓ Flèche BAS | Diminue la position du servo actif |
| ← Flèche GAUCHE | Sélectionne le servo précédent |
| → Flèche DROITE | Sélectionne le servo suivant |

**Commandes spéciales**

| Touche | Action |
| :--- | :--- |
| ESPACE | Centre le servo actif à sa position de calibration |
| I | Position INITIALE (séquence sécurisée) |
| C | Centre TOUS les servos simultanément |
| P | Active/désactive le mode précis (pas de 10 au lieu de 50) |
| S | Affiche le tableau détaillé des positions et limites |
| A | Position ATTRAPER (prêt pour la manipulation) |
| R | Position REPOS (bras replié pour le rangement) |
| Q | Quitte proprement et remet le bras en position repos |
| X | ARRÊT D'URGENCE (libère tous les moteurs immédiatement) |

**Mode précis**

- Mode normal : Pas de mouvement = 50 unités
- Mode précis : Pas de mouvement = 10 unités (pour ajustements fins)

L'affichage indique le mode actif en temps réel :

```
Servo actif: 3 (COUDE)
Mode: PRÉCIS (pas=10) [CHANGÉ]
Position: 2048
```

**Positions prédéfinies**

| Position | Description | Usage |
| :--- | :--- | :--- |
| INITIALE | Position de départ sécurisée | Lancement du script |
| ATTRAPER | Bras prêt pour saisir un objet | Tests de manipulation |
| REPOS | Bras replié compact | Rangement, fin de session |

> **Note :** La position REPOS (touche `R`, ainsi que le retour automatique lors de `Q`) utilise la position de repos définie en Phase 3 (`repos_position.json`). Si ce fichier n'existe pas encore, le script applique une position par défaut.


### 🧪 Étape 4 : Tests systématiques

**Test 1 : Vérification individuelle de chaque servo**

1. Utilisez → pour sélectionner chaque servo (1 à 6)
2. Pour chaque servo :
   - Testez le mouvement vers le MAX avec ↑
   - Testez le mouvement vers le MIN avec ↓
   - Recentrez avec ESPACE
3. Vérifiez que le servo s'arrête aux limites de calibration

**Test 2 : Centrage global**

1. Bougez plusieurs servos de leur position centrale
2. Appuyez sur C
3. Vérifiez que tous les servos reviennent au centre simultanément

**Test 3 : Mode précis**

1. Sélectionnez un servo sensible (ex: servo 6 — Pince)
2. Activez le mode précis avec P
3. Testez les mouvements fins avec les flèches
4. Désactivez avec P pour revenir au mode normal

**Test 4 : Positions prédéfinies**

1. Appuyez sur I → le bras se place en position initiale
2. Appuyez sur A → le bras se prépare à attraper
3. Appuyez sur R → le bras se replie en position repos
4. Vérifiez que chaque transition est fluide et sans à-coups

**Test 5 : Affichage des positions**

Appuyez sur S pour voir le tableau détaillé des positions et limites de tous les servos.

**Test 6 : Arrêt d'urgence**

1. Appuyez sur X
2. Vérifiez que tous les servos se libèrent immédiatement
3. Le bras doit devenir "mou" (plus de résistance moteur)

> **⚠️ Note :** L'arrêt d'urgence libère les moteurs sans repositionnement. Tenez le bras pour éviter qu'il ne tombe.


### 🤖 Étape 5 : Tests de coordination

**Mouvement de préhension (Follower)**

1. Servo 2 (Épaule) : Lever le bras
2. Servo 3 (Coude) : Plier pour approcher
3. Servo 4 (Poignet) : Ajuster l'angle
4. Servo 6 (Pince) : Ouvrir puis fermer

**Rotation complète (Leader ou Follower)**

1. Servo 1 (Base) : Rotation gauche maximum
2. Servo 5 (Poignet rotation) : Rotation opposée
3. Recentrer avec C
4. Répéter dans l'autre sens

**Position de repos**

Pour mettre le robot en position de repos sécurisée :

1. Appuyez sur R pour la position repos
2. Puis Q pour quitter et libérer les moteurs

> **✅ Tests réussis si :**
> - Tous les servos répondent aux commandes
> - Les limites de calibration sont respectées
> - Le centrage et les positions prédéfinies fonctionnent
> - Les transitions sont fluides (mouvements sinusoïdaux)
> - Pas de bruits anormaux ou de résistance


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| Script ne démarre pas | Port USB non détecté | Vérifier branchement et groupe `dialout` (voir Phase 1, Étape 6) |
| "Pas de calibration" | Phase 3 non complétée | Lancer d'abord `SEM_so101_2_calibrate.py` |
| Servo ne bouge pas | Alimentation coupée | Vérifier alimentation (LED) |
| Mouvement saccadé | Pas trop grand | Activer mode précis avec P |
| Servo force en butée | Calibration incorrecte | Refaire calibration Phase 3 |
| Flèches ne fonctionnent pas | Terminal incompatible | Utiliser un terminal standard Linux |
| Position affichée incorrecte | Décalage mécanique | Recentrer avec ESPACE |


### 💡 Conseils d'utilisation

1. **Commencez lentement :** Testez d'abord en mode normal avant le mode précis
2. **Surveillez les limites :** Le script empêche de dépasser les valeurs calibrées
3. **Libérez après usage :** Toujours quitter avec Q pour libérer les servos proprement
4. **Un robot à la fois :** Ne branchez qu'un seul adaptateur USB
5. **Position de sécurité :** Utilisez R (repos) ou X (urgence) en cas de doute


### 📖 Comprendre l'affichage

**Ligne d'état**

```
Servo actif: 3 (COUDE)
Mode: NORMAL (pas=50)
Position: 2048
```

| Élément | Signification |
| :--- | :--- |
| Servo actif: 3 | Numéro du servo sélectionné (1-6) |
| (COUDE) | Nom du servo |
| Mode: NORMAL | Mode de déplacement actif (NORMAL ou PRÉCIS) |
| Position: 2048 | Position actuelle (0-4095) |

**Correspondance servos**

| ID | Nom | Fonction | Mouvement |
| :--- | :--- | :--- | :--- |
| 1 | BASE | Rotation horizontale | Gauche ↔ Droite |
| 2 | ÉPAULE | Lever le bras | Haut ↔ Bas |
| 3 | COUDE | Plier l'avant-bras | Plié ↔ Tendu |
| 4 | POIGNET-F | Flexion du poignet | Haut ↔ Bas |
| 5 | POIGNET-R | Rotation du poignet | Gauche ↔ Droite |
| 6 | PINCE/POIGNÉE | Préhension | Ouvert ↔ Fermé |


### 🚀 Commandes de référence rapide

```bash
# Lancement
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_4_control.py
```

**Contrôles clavier :**
- `↑↓←→` — Navigation et mouvement
- `ESPACE` — Centre servo actif
- `I` — Position initiale
- `C` — Centre tous les servos
- `P` — Mode précis
- `S` — Afficher positions
- `A` — Position attraper
- `R` — Position repos
- `Q` — Quitter
- `X` — Arrêt d'urgence


### 📝 Notes finales

> **🎯 Validation complète :** Si tous les tests passent avec succès, votre robot est prêt pour la téléopération (Leader contrôle Follower), l'enregistrement de trajectoires et l'apprentissage par démonstration.

**✅ Phase 4 terminée quand :**

- Les 6 servos du Leader répondent correctement
- Les 6 servos du Follower répondent correctement
- Les limites de calibration sont respectées
- Les positions prédéfinies (I, A, R) fonctionnent
- Vous maîtrisez les commandes de contrôle
