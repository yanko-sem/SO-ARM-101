# Guide Configuration Servos SO-ARM 101

## Phase 2 : Attribution des IDs et Tests des Servomoteurs

Développé par : Service Écoles-Médias (SEM)

### 🧩 Scripts utilisés

`SEM_so101_1_configure.py` — attribution des IDs (1 à 6), test de mouvement, centrage à 2048 et blocage des servos pour le montage.

### 📋 Prérequis

- Phase 1 complétée (LeRobot et `dynamixel-sdk` installés, permissions USB configurées)
- Environnement lerobot activé
- 2 adaptateurs USB-Serial (Waveshare ou Feetech)
- Alimentations :
  - Kit Standard : 2×5V 3A
  - Kit Pro : 1×5V 3A + 1×12V 2A
- 12 servos Feetech STS3215
- Câbles 3-pins fournis


### 🔍 Vue d'ensemble de la Phase 2

Cette phase consiste à :

1. Attribuer les IDs 1 à 6 aux servos de **chaque bras** (le Leader et le Follower ont chacun leurs propres IDs 1 à 6, car ils sont sur deux bus séparés)
2. Tester le mouvement de chaque servo
3. Centrer chaque servo en position 2048
4. Monter les servos sur la structure
5. Recentrer si nécessaire après montage avec l'option `B`


### 🛠️ Étape 1 : Préparation de l'environnement

**Activation de l'environnement LeRobot**

```bash
# Activer l'environnement conda
conda activate lerobot
# Se placer dans le dossier des scripts
cd ~/lerobot/Scripts_SEM/scripts
```

> Vous devez voir `(lerobot)` au début de votre ligne de commande.

**Configuration matérielle**

| Composant | Leader | Follower |
| :--- | :--- | :--- |
| Adaptateur USB | 1 adaptateur dédié | 1 adaptateur dédié |
| Alimentation | 5V 3A (toujours) | 5V ou 12V selon kit |
| Servos | 3 types (ratios différents) | Tous identiques (1:345) |

> **⚠️ Important :** Ne JAMAIS connecter plusieurs servos non configurés simultanément ! Configurez-les un par un.

> **⚠️ Un seul adaptateur à la fois :** ne branchez que l'adaptateur USB du bras en cours de configuration. Si les adaptateurs Leader et Follower sont connectés en même temps, le script prend le premier port détecté et peut cibler le mauvais bras.


### 📝 Étape 2 : Le script de configuration

**Que fait le script `SEM_so101_1_configure.py` ?**

Le script effectue automatiquement les opérations suivantes :

1. **Détection du port USB** — il sélectionne le **premier port USB disponible** (l'option `D` permet de relancer cette détection). Cela suppose qu'un seul adaptateur est branché à la fois (voir Étape 1)
2. **Attribution de l'ID** — il lit d'abord l'ID actuel du servo connecté, puis écrit le numéro voulu (1 à 6) dans l'EEPROM du servo ; l'ID y est conservé même après coupure d'alimentation
3. **Test de mouvement** — il fait bouger le servo vers trois positions (MIN → MAX → CENTRE) pour vérifier son bon fonctionnement
4. **Centrage et blocage** — il positionne le servo à 2048 (position neutre) et l'y maintient bloqué, couple actif, pour le montage
5. **Configuration groupée** — l'option `T` guide la configuration des six servos l'un après l'autre, avec une invite avant chaque branchement
6. **Blocage / libération** — les options `B` et `L` bloquent ou libèrent le servo connecté (utiliser `L` pour relâcher le couple après le montage)

> **Note technique (Feetech STS3215) :** l'ID est stocké dans le registre EEPROM **5** (et non au registre 3 des conventions AX/MX). L'EEPROM étant verrouillée, le script la déverrouille, écrit l'ID, la reverrouille, puis vérifie que le servo répond à son nouvel ID — automatiquement, sans action manuelle.

**Correspondance des servos :**

| ID | Nom | Fonction |
| :--- | :--- | :--- |
| 1 | Base | Rotation horizontale |
| 2 | Épaule | Monte/descend le bras |
| 3 | Coude | Plie/déplie |
| 4 | Poignet flexion | Haut/bas |
| 5 | Poignet rotation | Gauche/droite |
| 6 | Pince/Poignée | Ouvre/ferme |

**Lancement du script**

```bash
python SEM_so101_1_configure.py
```

Le script affiche un menu interactif : les numéros 1 à 6 configurent chaque servo ; les options `T`, `B`, `L`, `D` et `Q` sont détaillées à l'**Étape 4**.

> ### ℹ️ Messages affichés pendant l'attribution d'un ID — faut-il s'inquiéter ?
>
> Quand le script change l'ID d'un servo, il déverrouille la mémoire EEPROM, écrit le nouvel ID, la reverrouille, puis **vérifie que le servo répond à son nouvel ID**. Selon le résultat, vous verrez l'un de ces messages :
>
> - ✅ **« ID changé : le servo répond maintenant à l'ID X »** — tout est correct ; l'ID est sauvegardé dans l'EEPROM, de façon permanente (même après coupure de courant).
> - ✅ **« Le servo a déjà l'ID X »** — rien à faire, il était déjà au bon ID.
> - ❌ **« L'ID n'a pas changé… Débranchez/rebranchez le servo et réessayez »** — **ce n'est pas une panne.** L'écriture n'a pas été confirmée. Débranchez puis rebranchez le servo, vérifiez l'alimentation, et relancez la configuration. Aucun risque pour le matériel.
> - ⚠️ **« Baudrate non relu correctement »** — **avertissement sans conséquence** : l'ID a déjà été configuré ; seule la relecture du débit a échoué. Si l'ID s'affiche **[SAUVEGARDÉ]**, la configuration est valide.
>
> En résumé : un ❌ sur l'ID se règle en rebranchant le servo ; un ⚠️ sur le baudrate est inoffensif.


### ⚙️ Étape 3 : Procédure de configuration

**A. Configuration du bras LEADER**

Rappel Leader : Les servos du Leader ont des ratios différents :
- Servos 1 et 3 : Ratio 1:191 (marquage C044)
- Servo 2 : Ratio 1:345 (marquage C001)
- Servos 4, 5, 6 : Ratio 1:147 (marquage C046)

Procédure pour chaque servo :

1. **Préparation matérielle :**
   - Brancher l'adaptateur USB du Leader
   - Connecter l'alimentation 5V 3A
   - Ne brancher qu'UN SEUL servo à la fois

2. **Lancement du script :**
   ```bash
   python SEM_so101_1_configure.py
   ```

3. **Configuration :**
   - Choisir le numéro du servo (1 à 6)
   - Observer le test de mouvement (MIN → MAX → CENTRE)
   - Vérifier que le servo finit bien à la position 2048

4. **Montage sur la structure :**
   - Monter le palonnier en position alignée
   - Fixer le servo sur le bras
   - Si la position bouge pendant le montage, utilisez l'option `B` pour recentrer le servo

**B. Configuration du bras FOLLOWER**

Rappel Follower : Tous les servos du Follower sont identiques (ratio 1:345)

Répéter la même procédure avec l'adaptateur USB du Follower.

> **💡 Astuce :** Après avoir monté chaque servo, il est normal que la position centrale puisse bouger. Pour recentrer un servo **déjà configuré**, utilisez l'option `B` du menu : elle place le servo à 2048 et le bloque, sans rejouer le balayage MIN → MAX → CENTRE. Évitez une configuration complète (1–6) sur un servo déjà monté : ce balayage peut être trop ample une fois le servo fixé à la structure. C'est aussi pourquoi nous configurons AVANT le montage (pour avoir l'ID) puis recentrons APRÈS si nécessaire.

> **⚠️ Servo 6 (pince) :** le script centre le servo à 2048 et affiche un rappel (il n'ouvre pas la pince lui-même). Lors du montage mécanique, fixez la pince en position **OUVERTE** autour de cette position centrale.


### 🔍 Étape 4 : Vérification et dépannage

**Options de gestion du menu**

Au-delà de la configuration d'un servo (touches 1 à 6), le menu propose :

- `T` — configure les six servos l'un après l'autre, avec une invite avant chaque branchement
- `B` — bloque au centre (2048) le servo actuellement connecté
- `L` — libère le servo connecté (relâche le couple), à utiliser après le montage
- `D` — relance la détection du port USB (utile si l'adaptateur a été rebranché)

> **Note :** Les options `B` et `L` recherchent le servo branché et affichent son ID — c'est le moyen le plus simple de vérifier quel servo est connecté. Elles ne scrutent que les ID 1 à 6 : un servo neuf (livré en ID 1) ou déjà configuré est détecté ; un servo dont l'ID est hors de cette plage ne le sera pas. Si aucune confirmation n'apparaît après `B` ou `L`, c'est qu'aucun servo n'a répondu sur les IDs 1 à 6 : vérifiez le branchement et l'alimentation du servo.

**Tableau de dépannage**

| Problème | Causes possibles | Solutions |
| :--- | :--- | :--- |
| Port USB non détecté | Adaptateur non branché, mauvais port USB, permissions insuffisantes | Vérifier le branchement, essayer un autre port USB, vérifier le groupe `dialout` (voir Phase 1, Étape 6) |
| Servo ne bouge pas | Alimentation non connectée, câble 3-pins mal branché, servo défectueux | Vérifier l'alimentation (LED allumée), reconnecter le câble 3-pins, tester avec un autre servo |
| Position incorrecte après montage | Normal — le montage fait bouger le servo, palonnier mal positionné | Utiliser l'option `B` pour recentrer ; démonter/remonter le palonnier si besoin |
| Mauvais servo configuré | Plusieurs servos branchés en même temps — le script configure le premier qui répond | Débrancher tous les servos sauf celui à configurer, puis relancer |
| ID déjà utilisé | Servo déjà configuré, mauvais servo branché | Utiliser `B` ou `L` pour afficher l'ID du servo branché, brancher le bon servo |
| L'ID n'a pas changé après tentative | Écriture EEPROM non confirmée, coupure pendant l'écriture, alimentation instable | Débrancher/rebrancher le servo, vérifier l'alimentation, relancer la configuration |


### 📝 Notes importantes

> **⚠️ Règles essentielles :**

1. **Un seul servo et un seul adaptateur à la fois** — ne jamais connecter plusieurs servos non configurés.
2. **Alimentation :** Leader toujours 5V ; Follower 5V (Standard) ou 12V (Pro).
3. **Ordre de travail :** Configurer → Tester → Monter → Recentrer avec `B` si nécessaire.


### 🚀 Commandes rapides de référence

```bash
# Activer l'environnement
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts

# Configurer un servo
python SEM_so101_1_configure.py

# Options du menu après lancement :
#   T = configurer les six servos       B / L = bloquer / libérer (affiche l'ID)
#   D = relancer la détection du port    Q = quitter
```

> **Note :** Si vous obtenez une erreur de permission sur les ports USB, vérifiez que votre utilisateur est bien dans le groupe `dialout` (voir Phase 1, Étape 6).
