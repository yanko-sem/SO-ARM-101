# Guide Calibration SO-ARM 101

## Phase 3 : Calibration et position de repos

Service Écoles-Médias (SEM)

### 🧩 Scripts utilisés

- `SEM_so101_2_calibrate.py` — calibration des limites MIN/MAX de chaque servo (un fichier de calibration par bras).
- `SEM_so101_3_monitor.py` — monitoring temps réel des positions et définition de la position de repos partagée.

### 📋 Prérequis

- Phase 1 complétée (LeRobot et `dynamixel-sdk` installés)
- Phase 2 complétée (Servos configurés avec IDs 1-6)
- Bras monté mécaniquement
- Scripts SEM installés depuis GitHub
- Environnement lerobot activé


### 🎯 Objectif de la calibration

**Pourquoi calibrer ?** La calibration définit les limites de mouvement sécurisées pour chaque servo. Sans calibration, les servos pourraient forcer contre les butées mécaniques et s'endommager.

La calibration permet de :

- Définir les limites MIN et MAX de chaque servo
- Calculer automatiquement le centre mécanique (médiane MIN/MAX, distinct de la position de repos définie au script 3)
- Protéger le matériel contre les mouvements hors limites
- Optimiser l'amplitude de mouvement disponible


### 🛠️ Étape 1 : Préparation

**Activation de l'environnement**

```bash
# Activer l'environnement conda
conda activate lerobot
# Se placer dans le dossier des scripts
cd ~/lerobot/Scripts_SEM/scripts
# Vérifier que les deux scripts de la phase sont présents
ls SEM_so101_2_calibrate.py SEM_so101_3_monitor.py
```

**Vérification du matériel**

| Élément | Leader | Follower |
| :--- | :--- | :--- |
| Adaptateur USB | Branché et détecté | Branché et détecté |
| Alimentation | 5V 3A active | 5V ou 12V active |
| Servos | Tous configurés (ID 1-6) | Tous configurés (ID 1-6) |
| Montage | Bras assemblé | Bras assemblé |

> **⚠️ Attention :** Avant de calibrer, assurez-vous que le bras peut bouger librement sans obstruction. Éloignez tout objet qui pourrait gêner le mouvement.

> **⚠️ Un seul adaptateur à la fois :** ne branchez que l'adaptateur USB du bras en cours de calibration. Si les deux adaptateurs (Leader et Follower) sont connectés en même temps, le script **refuse de démarrer** (il détecte plusieurs robots) pour éviter de calibrer le mauvais bras. Calibrez donc un bras, débranchez-le, puis l'autre. Le tableau ci-dessus liste les prérequis **par bras**, à vérifier l'un après l'autre.


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

Votre choix [L/F] : _
```

Tapez `L` pour le Leader ou `F` pour le Follower. Le script attend un choix **explicite** : une entrée vide ou invalide est refusée et redemandée (il n'y a plus de bascule silencieuse vers Leader).

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

> **✅ Important :** La sauvegarde est automatique après chaque servo **validé**. Si une calibration est annulée ou échoue (lecture invalide, amplitude trop faible), elle n'est **pas** sauvegardée, afin de ne pas corrompre le fichier de calibration.

> **⚠️ Recentrage non confirmé :** si le script affiche « recentrage non confirmé » ou « couple non réactivé, recentrage ignoré », la calibration (MIN/MAX) reste **valide et sauvegardée** — mais le servo n'a pas rejoint son centre. Replacez alors le bras à la main dans une **position sûre** avant de continuer.

> ### ℹ️ Message « statut interne non nul » — faut-il s'inquiéter ?
>
> Certains servos (le **servo 2 / ÉPAULE** surtout) peuvent renvoyer un statut interne non nul pendant la **calibration** ou la **capture du repos**, par exemple :
> `⚠️ Servo 2 : statut interne non nul (code 1) — position conservée, à identifier`
>
> Ce n'est **pas une panne de communication** : le servo répond, mais signale un **drapeau interne**. Ce drapeau peut tenir à l'alimentation, à la charge mécanique, à la température ou à un autre état interne du servo — la **cause exacte reste à identifier** si le message revient régulièrement. En conséquence :
> - la **lecture de position reste valide** et l'opération **continue** — seul un véritable échec de communication bloque ;
> - ce n'est pas anodin pour autant : c'est un **signal de surveillance**, à examiner si le message est récurrent.
>
> Cette tolérance ne vaut que pour les **lectures de position** de la Phase 3 (calibration et capture du repos) ; elle ne garantit pas le bon fonctionnement du servo en mouvement.


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
ID   Nom               MIN      CENTRE   MAX      Amplitude
--------------------------------------------------------------------------------
1    BASE              1024     2048     3072     2048
2    ÉPAULE            768      2304     3840     3072
3    COUDE             512      2048     3584     3072
4    POIGNET-FLEXION   1280     2176     3072     1792
5    POIGNET-ROTATION  1024     2048     3072     2048
6    PINCE/POIGNÉE     1536     2560     3584     2048
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

**Quitter proprement**

Utilisez `Q` pour quitter le script. Les calibrations déjà validées ont été sauvegardées automatiquement après chaque servo ; en quittant, le script libère les servos et ferme le port :

```
Votre choix: Q

🏁 Libération des servos...

✅ Calibration terminée
📁 Fichier: ~/lerobot/calibration/follower_calibration.json
```


### 📡 Étape 6 : Définir la position de repos (script 3)

**Pourquoi cette étape ?** Une fois la calibration faite, il reste à définir la **position de repos** : le point de départ et de retour commun à *tous* les scripts (contrôle, téléopération, enregistrement, déploiement). Elle est enregistrée dans un fichier partagé, `~/lerobot/calibration/repos_position.json`, et stockée en **pourcentages** relatifs à la calibration de chaque servo — elle reste donc cohérente même après une recalibration.

Le script `SEM_so101_3_monitor.py` sert à cela. Il affiche aussi en temps réel les positions des servos, utile pour diagnostiquer le montage.

> **⚠️ Prérequis :** la calibration du robot doit être **complète et valide** (les 6 servos calibrés, amplitude ≥ 500), car le script s'en sert pour convertir les positions en pourcentages. Si la calibration est absente, incomplète ou invalide, les modes `C` et `M` **refusent** d'enregistrer un repos.

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

Votre choix [L/F] : _
```

Tapez `L` ou `F` (choix explicite : une entrée vide ou invalide est redemandée). Les servos sont alors **libérés** (vous pouvez bouger le bras à la main) et le monitoring démarre :

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

Dans les deux cas, un récapitulatif s'affiche avant la confirmation, puis la position est enregistrée dans `repos_position.json` (écriture atomique).

> **🔒 Sécurités à l'enregistrement :** une position **hors des limites** de calibration est refusée (repositionnez le bras et recommencez) ; et si vous n'êtes **pas sur le FOLLOWER**, le script demande de taper `OUI` en toutes lettres pour confirmer. En mode `C`, si la **communication** avec un servo échoue, la capture est annulée ; un statut interne non nul est, lui, **signalé sans bloquer** (voir l'encadré en Étape 3).

> **💡 Recommandation :** capturez la position de repos depuis le **FOLLOWER** — c'est lui qui sert de référence au déploiement. Le script le rappelle si vous monitorez le Leader.

**Quitter**

Pressez `Ctrl+C` : le script libère tous les servos et ferme proprement le port.


### 📖 Comprendre les valeurs de calibration

**Signification des valeurs**

| Paramètre | Description | Utilisation |
| :--- | :--- | :--- |
| MIN | Position minimale sûre | Limite basse du mouvement |
| MAX | Position maximale sûre | Limite haute du mouvement |
| CENTRE | Position médiane calculée entre MIN et MAX | Point de recentrage mécanique, distinct de la position de repos (définie au script 3) |
| Amplitude | MAX - MIN | Plage totale de mouvement |

**Différences d'amplitude (Leader vs Follower)**

Les différences d'amplitude observées (en ticks) viennent surtout du **montage mécanique, des butées physiques et de la plage sûre choisie** pendant la calibration — l'encodeur lit 0-4096 sur la course de sortie de chaque joint, indépendamment du ratio de réduction. Les ratios des servos (Leader : servos 1 et 3 en 1:191, servo 2 en 1:345, servos 4-6 en 1:147 ; Follower : tous en 1:345) comptent pour le choix et le montage des servos, mais **ne doivent pas servir d'explication directe** aux valeurs MIN/MAX/amplitude.

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
| Plusieurs robots détectés (script refuse) | Leader ET Follower branchés en même temps | Ne garder branché que l'adaptateur du bras à calibrer |
| Servo ne bouge pas manuellement | Couple moteur actif | Normal au début, le script libère les servos |
| « Statut interne non nul (code X) » sur un servo | Drapeau interne du servo, communication OK ; cause à vérifier (alimentation, câblage, charge mécanique, température) | Non bloquant pour la lecture : l'opération continue. Vérifier le servo si le message est récurrent |
| Amplitude trop faible (< 500) | MIN/MAX trop proches (servo peu/pas bougé, butées trop proches) | Le script **refuse** la sauvegarde ; recommencez avec des limites MIN/MAX bien distinctes |
| Amplitude très élevée (> 3800) | Plage presque complète de l'encodeur, ou limites trop larges | Vérifier que MIN/MAX ne forcent pas contre les butées mécaniques |
| Le servo force après calibration | Limites mal définies | Recalibrer ce servo spécifiquement |
| Calibration perdue | Fichier supprimé | Refaire la calibration (option T) |


### 💡 Conseils pratiques

1. **Calibrez après chaque remontage :** Si vous démontez/remontez des servos, recalibrez-les
2. **Testez les limites :** Utilisez le script de contrôle (Phase 4) pour vérifier que les limites sont bien respectées
3. **Soyez doux :** Ne forcez jamais les servos contre les butées
4. **Amplitude normale :** Entre 1500 et 3500 pour la plupart des servos


### 🚀 Commandes de référence

```bash
# Les scripts sont installés en Phase 1 (dépôt SEM cloné dans ~/lerobot/Scripts_SEM)
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts

# Calibration des limites MIN/MAX (un fichier par bras)
python SEM_so101_2_calibrate.py

# Monitoring temps réel + définition de la position de repos
python SEM_so101_3_monitor.py
```

**Options du menu (calibration, script 2) :**
- `T` — Calibrer tous les servos
- `V` — Voir la calibration actuelle
- `1-6` — Calibrer un servo spécifique
- `Q` — Quitter (libère les servos et ferme le port)

**Touches (monitoring/repos, script 3) :**
- `C` — Capturer la position de repos (position physique actuelle)
- `M` — Saisie manuelle des 6 valeurs (ticks)
- `Ctrl+C` — Quitter (libère les servos et ferme le port)


### 📝 Notes finales

**✅ Calibration réussie quand :**

- Tous les servos bougent librement dans leurs limites
- Aucun servo ne force en position extrême
- Les amplitudes sont cohérentes (ni trop faibles, ni excessives)
- Le centrage automatique fonctionne pour tous les servos

> **🎯 Objectif atteint :** Votre robot est maintenant calibré, sa position de repos peut être définie, et il est prêt pour les tests de contrôle (Phase 4) puis la téléopération. Les scripts de contrôle, téléopération, enregistrement et déploiement utiliseront automatiquement ces valeurs de calibration pour protéger votre matériel.
