# Guide Calibration SO-ARM 101

## Phase 3 : Calibration et position de repos

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
cd ~/lerobot/Scripts_SEM/scripts
# Vérifier que le script est présent
ls SEM_so101_2_calibrate.py
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
python SEM_so101_2_calibrate.py
```

**Sélection du bras**

```
╔══════════════════════════════════════════════════════════╗
║     CALIBRATION SO-ARM 101                              ║
║     Service Ecoles Médias                               ║
╚══════════════════════════════════════════════════════════╝

✅ Port détecté: /dev/ttyACM0

🤖 Quel robot calibrer ?
  [L] LEADER
  [F] FOLLOWER

Votre choix : _
```

Tapez `L` pour le Leader ou `F` pour le Follower (une entrée vide équivaut à Leader).

**Menu principal**

```
============================================================
MENU PRINCIPAL
============================================================
1-6 → Calibrer un servo spécifique
  T → Calibrer TOUS les servos
  V → Voir calibration actuelle
  Q → Quitter
============================================================

Votre choix: _
```

> **💡 Conseil :** Pour une première calibration, utilisez T pour calibrer tous les servos d'un coup. Pour des ajustements, utilisez les numéros 1-6.


### 🔧 Étape 3 : Procédure de calibration

**Principe de la calibration**

Pour chaque servo, vous devez :

1. Bouger manuellement le servo jusqu'à sa position MINIMALE
2. Valider avec ENTRÉE (le script lit la position MIN)
3. Bouger jusqu'à sa position MAXIMALE
4. Valider avec ENTRÉE (le script lit la position MAX)
5. Le script calcule automatiquement le centre et l'amplitude
6. Le servo se recentre automatiquement en douceur, puis est libéré

**Exemple pratique : Calibration du servo 3 (Coude)**

```
============================================================
CALIBRATION DU SERVO 3 - COUDE
============================================================
Position actuelle: 1800

⚠️  Le servo est maintenant LIBRE

📋 Instructions:
1. Bougez MANUELLEMENT le servo à sa position MINIMALE
2. Maintenez la position et appuyez sur ENTRÉE

➡️  Position MIN prête? [ENTRÉE]
✅ Position MIN enregistrée: 512

3. Bougez MANUELLEMENT le servo à sa position MAXIMALE
4. Maintenez la position et appuyez sur ENTRÉE

➡️  Position MAX prête? [ENTRÉE]
✅ Position MAX enregistrée: 3584

📊 Résumé calibration:
  • MIN: 512
  • MAX: 3584
  • CENTRE: 2048
  • Amplitude: 3072
  🔄 Centrage fluide vers 2048...
✅ Servo 3 centré
💾 Calibration du servo 3 sauvegardée!
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
================================================================================
TABLEAU RÉCAPITULATIF DE CALIBRATION
================================================================================
ID   Nom             MIN      CENTRE   MAX      Amplitude
--------------------------------------------------------------------------------
1    BASE            1024     2048     3072     2048
2    ÉPAULE          768      2304     3840     3072
3    COUDE           512      2048     3584     3072
4    POIGNET-F       1280     2176     3072     1792
5    POIGNET-R       1024     2048     3072     2048
6    PINCE/POIGNÉE   1536     2560     3584     2048
================================================================================
```

> **Note :** Les valeurs ci-dessus sont des exemples. Vos valeurs seront différentes selon votre montage mécanique.


### 🔍 Étape 5 : Vérification et ajustements

**Visualiser la calibration actuelle**

Utilisez l'option V pour voir les valeurs enregistrées :

```
Votre choix: V
```

`V` réaffiche le **tableau récapitulatif** (identique à celui de l'option `T`, voir Étape 4) avec les valeurs actuellement enregistrées pour le robot sélectionné.

**Recalibrer un servo spécifique**

Si un servo nécessite un ajustement :

1. Tapez son numéro (1-6) dans le menu
2. Refaites la procédure de calibration
3. Les nouvelles valeurs remplacent automatiquement les anciennes

> **💡 Centrage doux :** Le script utilise une courbe sinusoïdale pour recentrer les servos en douceur. Cela évite les mouvements brusques qui pourraient stresser les mécaniques.

**Sauvegarde finale**

Utilisez Q pour quitter et confirmer la sauvegarde :

```
Votre choix: Q

🏁 Libération des servos...

✅ Calibration terminée
📁 Fichier: ~/lerobot/calibration/follower_calibration.json
```


### 📡 Étape 6 : Définir la position de repos (script 3)

**Pourquoi cette étape ?** Une fois la calibration faite, il reste à définir la **position de repos** : le point de départ et de retour commun à *tous* les scripts (contrôle, téléopération, enregistrement, déploiement). Elle est enregistrée dans un fichier partagé, `~/lerobot/calibration/repos_position.json`, et stockée en **pourcentages** relatifs à la calibration de chaque servo — elle reste donc cohérente même après une recalibration.

Le script `SEM_so101_3_monitor.py` sert à cela. Il affiche aussi en temps réel les positions des servos, utile pour diagnostiquer le montage.

> **⚠️ Prérequis :** la calibration du robot doit être faite (Étapes 1 à 5), car le script s'en sert pour convertir les positions en pourcentages.

**Lancement**

```bash
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_3_monitor.py
```

Le script détecte le port, puis demande le robot :

```
🤖 Quel robot monitorer ?
  [L] LEADER
  [F] FOLLOWER

Votre choix : _
```

Tapez `L` ou `F`. Les servos sont alors **libérés** (vous pouvez bouger le bras à la main) et le monitoring démarre :

```
╔═══════════╦═══════╦═══════╦═══════╦═══════╦═══════╦══════════════════════╗
║ SERVO     ║  POS  ║   %   ║  MIN  ║ CENTRE║  MAX  ║     GRAPHIQUE        ║
╠═══════════╬═══════╬═══════╬═══════╬═══════╬═══════╬══════════════════════╣
║ 1:BASE    ║  2048 ║  50.0 ║  1024 ║  2048 ║  3072 ║ ██████████░░░░░░░░░░ ║
...
╚═══════════╩═══════╩═══════╩═══════╩═══════╩═══════╩══════════════════════╝
```

**Définir la position de repos**

Sous le tableau, deux touches permettent de créer ou modifier le repos :

- **`C`** — **capture** la position physique actuelle du bras. Placez le bras à la main dans la pose de repos souhaitée, pressez `C`, vérifiez le récapitulatif (ticks, %, contrôle des limites), puis confirmez par `O`.
- **`M`** — **saisie manuelle** des 6 valeurs en ticks (le script vérifie que chaque valeur est dans les limites de calibration).

Dans les deux cas, un récapitulatif s'affiche avant la confirmation, puis la position est enregistrée dans `repos_position.json`.

> **💡 Recommandation :** capturez la position de repos depuis le **FOLLOWER** — c'est lui qui sert de référence au déploiement. Le script le rappelle si vous monitorez le Leader.

**Quitter**

Pressez `Ctrl+C` : le script libère tous les servos et ferme proprement le port.


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
~/lerobot/calibration/leader_calibration.json
~/lerobot/calibration/follower_calibration.json
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
# Les scripts sont installés en Phase 1 (dépôt SEM cloné dans ~/lerobot/Scripts_SEM)
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_2_calibrate.py
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
