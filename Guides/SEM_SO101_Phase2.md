# Guide Configuration Servos SO-ARM 101

## Phase 2 : Attribution des IDs et Tests des Servomoteurs

Développé par : Service Écoles-Médias (SEM)

### 📋 Prérequis

- Phase 1 complétée (LeRobot installé, permissions USB configurées)
- Environnement lerobot activé
- 2 adaptateurs USB-Serial (Waveshare ou Feetech)
- Alimentations :
  - Kit Standard : 2×5V 3A
  - Kit Pro : 1×5V 3A + 1×12V 2A
- 12 servos Feetech STS3215
- Câbles 3-pins fournis

> **Note :** Cette phase utilise le script `SEM_so101_1_configure.py` développé par le Service Écoles-Médias, optimisé pour l'éducation et la formation.


### 🔍 Vue d'ensemble de la Phase 2

Cette phase consiste à :

1. Attribuer un ID unique à chaque servo (1 à 6)
2. Tester le mouvement de chaque servo
3. Centrer chaque servo en position 2048
4. Monter les servos sur la structure
5. Reconfigurer si nécessaire après montage


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


### 📝 Étape 2 : Le script de configuration

**Que fait le script `SEM_so101_1_configure.py` ?**

Le script effectue automatiquement les opérations suivantes :

1. **Détection du port USB** — il trouve automatiquement l'adaptateur branché
2. **Attribution de l'ID** — il assigne un numéro unique (1 à 6) au servo connecté
3. **Test de mouvement** — il fait bouger le servo vers trois positions (MIN → MAX → CENTRE) pour vérifier son bon fonctionnement
4. **Centrage** — il positionne le servo à 2048 (position neutre) pour le montage
5. **Mode détection** — il permet d'identifier un servo déjà configuré

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

Le script affiche un menu qui vous guide : choisissez le numéro du servo (1 à 6) ou `D` pour détecter un servo existant.


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
   - Si la position bouge pendant le montage, relancer le script

**B. Configuration du bras FOLLOWER**

Rappel Follower : Tous les servos du Follower sont identiques (ratio 1:345)

Répéter la même procédure avec l'adaptateur USB du Follower.

> **💡 Astuce :** Après avoir monté chaque servo, il est normal que la position centrale soit perdue. N'hésitez pas à relancer le script pour recentrer le servo après montage. C'est pourquoi nous configurons AVANT le montage (pour avoir l'ID) puis APRÈS si nécessaire (pour recentrer).


### 🔍 Étape 4 : Vérification et dépannage

**Utilisation du mode Détection**

Pour identifier un servo déjà configuré :

```bash
python SEM_so101_1_configure.py
# Choisir 'D' pour détecter
```

Le script affichera l'ID et la position actuelle du servo connecté.

**Tableau de dépannage**

| Problème | Causes possibles | Solutions |
| :--- | :--- | :--- |
| Port USB non détecté | Adaptateur non branché, mauvais port USB, permissions insuffisantes | Vérifier le branchement, essayer un autre port USB, vérifier le groupe `dialout` (voir Phase 1, Étape 6) |
| Servo ne bouge pas | Alimentation non connectée, câble 3-pins mal branché, servo défectueux | Vérifier l'alimentation (LED allumée), reconnecter le câble 3-pins, tester avec un autre servo |
| Position incorrecte après montage | Normal — le montage fait bouger le servo, palonnier mal positionné | Relancer le script pour recentrer, démonter et remonter le palonnier |
| Plusieurs servos détectés | Plusieurs servos connectés en chaîne | Débrancher tous sauf un, configurer un par un |
| ID déjà utilisé | Servo déjà configuré, mauvais servo branché | Utiliser mode 'D' pour identifier, brancher le bon servo |


### 📝 Notes importantes

> **⚠️ Règles essentielles :**

1. **Un servo à la fois :** Ne JAMAIS connecter plusieurs servos non configurés
2. **Position 2048 :** Toujours configurer avant montage
3. **Reconfiguration :** Normal et recommandé après montage
4. **Alimentation :**
   - Leader : TOUJOURS 5V
   - Follower : 5V (Standard) ou 12V (Pro)
5. **Ordre :** Configurer → Tester → Monter → (Reconfigurer si besoin)


### 🚀 Commandes rapides de référence

```bash
# Activer l'environnement
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts

# Configurer un servo
python SEM_so101_1_configure.py

# Détecter un servo existant
python SEM_so101_1_configure.py
# Puis choisir 'D'
```

> **Note :** Si vous obtenez une erreur de permission sur les ports USB, vérifiez que votre utilisateur est bien dans le groupe `dialout` (voir Phase 1, Étape 6).
