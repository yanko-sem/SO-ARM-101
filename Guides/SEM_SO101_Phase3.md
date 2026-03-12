# Guide Calibration SO-ARM 101

## Phase 3 : Calibration des limites de mouvement

Service Écoles-Médias (SEM)

### 📋 Prérequis

- Phase 1 complétée (LeRobot installé)
- Phase 2 complétée (Servos configurés avec IDs 1-6)
- Bras monté mécaniquement
- Scripts SEM installés depuis GitHub
- Environnement lerobot activé


### 🎯 Objectif de la calibration

**Pourquoi calibrer ?** La calibration définit les limites de mouvement sécurisées pour chaque servo. Sans calibration, les servos pourraient forcer contre les butées mécaniques et s'endommager.

La calibration permet de :

- Définir les limites MIN et MAX de chaque servo
- Calculer automatiquement le centre (position de repos)
- Protéger le matériel contre les mouvements hors limites
- Optimiser l'amplitude de mouvement disponible


### 🛠️ Étape 1 : Préparation

**Activation de l'environnement**

```bash
# Activer l'environnement conda
conda activate lerobot
# Se placer dans le dossier des scripts
cd ~/lerobot/SO-ARM-101/scripts
# Vérifier que le script est présent
ls SEM_so101_calibrate.py
```

**Vérification du matériel**

| Élément | Leader | Follower |
| :--- | :--- | :--- |
| Adaptateur USB | Branché et détecté | Branché et détecté |
| Alimentation | 5V 3A active | 5V ou 12V active |
| Servos | Tous configurés (ID 1-6) | Tous configurés (ID 1-6) |
| Montage | Bras assemblé | Bras assemblé |

> **⚠️ Attention :** Avant de calibrer, assurez-vous que le bras peut bouger librement sans obstruction. Éloignez tout objet qui pourrait gêner le mouvement.


### 🚀 Étape 2 : Lancement du script de calibration

**Démarrage**

```bash
python SEM_so101_calibrate.py
```

**Sélection du bras**

```
==================================================
        CALIBRATION SO-ARM-101
        Service Écoles-Médias (SEM)
==================================================

Quel bras ?
  1 - LEADER (avec poignée)
  2 - FOLLOWER (avec pince)

Choix (1 ou 2) : _
```

Entrez 1 pour le Leader ou 2 pour le Follower.

**Menu principal**

```
[ROBOT: FOLLOWER]
==================================================
MENU PRINCIPAL:
  1-6 : Calibrer UN servo spécifique
  T   : Calibrer TOUS les servos
  V   : Voir calibration actuelle
  Q   : QUITTER et sauvegarder
==================================================
follower> _
```

> **💡 Conseil :** Pour une première calibration, utilisez T pour calibrer tous les servos d'un coup. Pour des ajustements, utilisez les numéros 1-6.


### 🔧 Étape 3 : Procédure de calibration

**Principe de la calibration**

Pour chaque servo, vous devez :

1. Bouger manuellement le servo jusqu'à une butée (extrême 1)
2. Valider cette position avec ENTRÉE
3. Bouger jusqu'à l'autre butée (extrême 2)
4. Valider cette seconde position
5. Le script calcule automatiquement le centre et les limites
6. Le servo se recentre automatiquement en douceur

**Exemple pratique : Calibration du servo 3 (Coude)**

```
========================================
  SERVO 3 : COUDE
========================================

-> Bougez le servo a une BUTEE (extreme 1)
   Appuyez ENTREE...

Position 1 = 512

-> Bougez le servo a l'AUTRE BUTEE (extreme 2)
   Appuyez ENTREE...

Position 2 = 3584

NOUVELLE CALIBRATION:
  MIN    : 512
  CENTRE : 2048
  MAX    : 3584
  Amplitude : 3072

-> Centrage dans 2 secondes...
-> Centrage en douceur...
OK: Servo recentré et libéré

[Sauvegarde automatique effectuée]
```

> **✅ Important :** La sauvegarde est automatique après chaque servo. Vous ne perdrez jamais votre travail !


### 📊 Étape 4 : Calibration complète (option T)

L'option T permet de calibrer les 6 servos à la suite :

**Ordre de calibration**

1. **BASE** — Rotation horizontale du bras complet
2. **ÉPAULE** — Lève/baisse le bras entier
3. **COUDE** — Plie/déplie l'avant-bras
4. **POIGNET FLEXION** — Incline la pince vers le haut/bas
5. **POIGNET ROTATION** — Tourne la pince gauche/droite
6. **PINCE/POIGNÉE** — Ouvre/ferme la prise

**Tableau récapitulatif**

À la fin de la calibration complète, un tableau s'affiche :

```
============================================================
                  TABLEAU RECAPITULATIF
============================================================
ID  Nom                  MIN    CENTRE  MAX    Amplitude
------------------------------------------------------------
1   BASE                 1024   2048    3072   2048
2   EPAULE               768    2304    3840   3072
3   COUDE                512    2048    3584   3072
4   POIGNET FLEXION      1280   2176    3072   1792
5   POIGNET ROTATION     1024   2048    3072   2048
6   PINCE/POIGNEE        1536   2560    3584   2048
============================================================
```

> **Note :** Les valeurs ci-dessus sont des exemples. Vos valeurs seront différentes selon votre montage mécanique.


### 🔍 Étape 5 : Vérification et ajustements

**Visualiser la calibration actuelle**

Utilisez l'option V pour voir les valeurs enregistrées :

```
follower> V

CALIBRATION ACTUELLE (FOLLOWER):
  Servo 1: MIN=1024, CENTRE=2048, MAX=3072
  Servo 2: MIN=768,  CENTRE=2304, MAX=3840
  Servo 3: MIN=512,  CENTRE=2048, MAX=3584
  Servo 4: MIN=1280, CENTRE=2176, MAX=3072
  Servo 5: MIN=1024, CENTRE=2048, MAX=3072
  Servo 6: MIN=1536, CENTRE=2560, MAX=3584
```

**Recalibrer un servo spécifique**

Si un servo nécessite un ajustement :

1. Tapez son numéro (1-6) dans le menu
2. Refaites la procédure de calibration
3. Les nouvelles valeurs remplacent automatiquement les anciennes

> **💡 Centrage doux :** Le script utilise une courbe sinusoïdale pour recentrer les servos en douceur. Cela évite les mouvements brusques qui pourraient stresser les mécaniques.

**Sauvegarde finale**

Utilisez Q pour quitter et confirmer la sauvegarde :

```
follower> Q
Calibration finale sauvegardée pour FOLLOWER
Fichier: ~/.cache/calibration/so101/follower_calibration.json
```


### 📖 Comprendre les valeurs de calibration

**Signification des valeurs**

| Paramètre | Description | Utilisation |
| :--- | :--- | :--- |
| MIN | Position minimale sûre | Limite basse du mouvement |
| MAX | Position maximale sûre | Limite haute du mouvement |
| CENTRE | Position médiane calculée | Position de repos/départ |
| Amplitude | MAX - MIN | Plage totale de mouvement |

**Différences Leader vs Follower**

**Leader :** Les servos ont des ratios de réduction différents, ce qui peut donner des amplitudes variées :
- Servo 3 (Coude) : Amplitude souvent plus élevée (ratio 1:191)
- Servos 4-6 : Amplitudes plus faibles (ratio 1:147)

**Follower :** Tous les servos sont identiques (ratio 1:345), les amplitudes sont généralement plus uniformes.

**Fichiers de calibration**

Les calibrations sont stockées dans :

```
~/.cache/calibration/so101/leader_calibration.json
~/.cache/calibration/so101/follower_calibration.json
```


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| Port USB non détecté | Adaptateur débranché ou permissions | Vérifier le groupe `dialout` (voir Phase 1, Étape 6) |
| Servo ne bouge pas manuellement | Couple moteur actif | Normal au début, le script libère les servos |
| Amplitude très faible (< 500) | Butées mécaniques trop proches | Vérifier le montage mécanique |
| Amplitude très élevée (> 4000) | Normal pour certains servos | Particulièrement le servo 3 du Leader |
| Le servo force après calibration | Limites mal définies | Recalibrer ce servo spécifiquement |
| Calibration perdue | Fichier supprimé | Refaire la calibration (option T) |


### 💡 Conseils pratiques

1. **Calibrez après chaque remontage :** Si vous démontez/remontez des servos, recalibrez-les
2. **Testez les limites :** Utilisez le script de contrôle (Phase 4) pour vérifier que les limites sont bien respectées
3. **Soyez doux :** Ne forcez jamais les servos contre les butées
4. **Amplitude normale :** Entre 1500 et 3500 pour la plupart des servos
5. **Sauvegarde automatique :** Pas besoin de sauvegarder manuellement, c'est fait après chaque servo


### 🚀 Commandes de référence

```bash
# Installation des scripts (si pas déjà fait)
cd ~/lerobot
git clone https://github.com/yanko-sem/SO-ARM-101.git

# Utilisation
conda activate lerobot
cd ~/lerobot/SO-ARM-101/scripts
python SEM_so101_calibrate.py
```

**Options du menu :**
- `T` — Calibrer tous les servos
- `V` — Voir la calibration actuelle
- `1-6` — Calibrer un servo spécifique
- `Q` — Quitter et sauvegarder


### 📝 Notes finales

**✅ Calibration réussie quand :**

- Tous les servos bougent librement dans leurs limites
- Aucun servo ne force en position extrême
- Les amplitudes sont cohérentes (ni trop faibles, ni excessives)
- Le centrage automatique fonctionne pour tous les servos

> **🎯 Objectif atteint :** Votre robot est maintenant calibré et prêt pour la téléopération ! Les scripts de contrôle et d'entraînement utiliseront automatiquement ces valeurs de calibration pour protéger votre matériel.
