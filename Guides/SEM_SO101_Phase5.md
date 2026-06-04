# Guide Téléopération SO-ARM 101

## Phase 5 : Téléopération Leader-Follower

Service Écoles-Médias (SEM) — DIP Genève

### ✅ Prérequis

- Phase 1 complétée (LeRobot installé)
- Phase 2 complétée (Servos configurés avec IDs 1-6)
- Phase 3 complétée (Calibration effectuée)
- Phase 4 complétée (Tests de contrôle validés)
- Scripts SEM installés depuis GitHub
- Environnement lerobot activé


### 🎯 Objectif de la téléopération

**Pourquoi la téléopération ?** La téléopération permet au robot Follower de reproduire en temps réel les mouvements du robot Leader. C'est l'étape préparatoire essentielle avant l'enregistrement de trajectoires et l'apprentissage par imitation.

La téléopération permet de :

- Contrôler à distance le robot Follower via le Leader
- Tester la synchronisation entre les deux robots
- Valider la configuration avant l'enregistrement
- S'entraîner aux manipulations pour l'apprentissage


### 📋 Étape 1 : Préparation

**Activation de l'environnement**

```bash
# Activer l'environnement conda
conda activate lerobot
# Se placer dans le dossier des scripts
cd ~/lerobot/Scripts_SEM/scripts
# Vérifier les scripts disponibles
ls SEM_so101_5_config_teleoperation.py SEM_so101_6_teleoperation.py
```

Vous devriez voir :
- `SEM_so101_5_config_teleoperation.py` — Configuration COPIE/MIROIR par servo
- `SEM_so101_6_teleoperation.py` — Téléopération temps réel

**Configuration matérielle**

| Élément | Vérification |
| :--- | :--- |
| Leader | Débranché au départ |
| Follower | Débranché au départ |
| Alimentations | 2× prêtes (5V ou 12V selon kit) |
| Espace de travail | Dégagé pour les deux robots |
| Calibrations | Fichiers présents (Phase 3 complétée) |

> **⚠️ Important :** Les scripts demandent de brancher les robots un par un dans un ordre précis. NE PAS brancher les deux robots tout de suite !


### 🔧 Étape 2 : Configuration de la téléopération (Script 5)

Ce script configure le mode COPIE ou MIROIR **pour chaque servo individuellement**. Vous testez les deux modes en temps réel et choisissez celui qui convient.

**Lancement**

```bash
python SEM_so101_5_config_teleoperation.py
```

**Phase d'identification**

Le script guide l'identification des robots étape par étape :

```
╔══════════════════════════════════════════════════════════╗
║     IDENTIFICATION LEADER/FOLLOWER                      ║
╚══════════════════════════════════════════════════════════╝

⚠️  Débranchez tous les robots
   Entrée quand fait...

🔌 Branchez le LEADER
   Entrée quand branché...
✅ LEADER détecté sur /dev/ttyACM0

  🔄 Test de connexion LEADER...
     → Centre...
     → Fermé (45°)...
     → Ouvert (90°)...
     → Centre...
  ✅ LEADER connecté et testé

Pince du LEADER bougée? [O/N]: O

🔌 Branchez le FOLLOWER (gardez Leader branché)
   Entrée quand branché...
✅ FOLLOWER détecté sur /dev/ttyACM1

  🔄 Test de connexion FOLLOWER...
  ✅ FOLLOWER connecté et testé

Pince du FOLLOWER bougée? [O/N]: O

✅ Identification réussie!
```

Le test de connexion fait bouger la pince (servo 6) de chaque robot pour confirmer visuellement que le bon robot est connecté.

**Choix de la disposition**

```
[C]ôte à côte ou [F]ace à face ?
Choix : _
```

- **Côte à côte** : les deux robots sont côte à côte, orientés dans la même direction
- **Face à face** : les deux robots se font face

**Configuration servo par servo**

Pour chaque servo (1 à 6), le script procède ainsi :

1. **Test en COPIE** : le servo du Leader est libéré, bougez-le — le Follower reproduit le mouvement identique. Appuyez sur Entrée pour passer au test suivant.
2. **Recentrage automatique** : les deux robots reviennent au centre en douceur.
3. **Test en MIROIR** : même principe, mais le mouvement du Follower est inversé. Appuyez sur Entrée.
4. **Choix** : le script demande `[C]opie ou [M]iroir ?` pour ce servo.

```
TEST SERVO 1/6 : BASE
========================================

📋 MODE COPIE
Bougez le Leader maintenant
Appuyez ENTRÉE pour passer en miroir
L:2048 → F:2048 [COPIE]

🔄 Recentrage pour transition...

📋 MODE MIROIR
Bougez le Leader maintenant
Appuyez ENTRÉE pour choisir
L:2048 → F:2048 [MIROIR]

Servo 1: [C]opie ou [M]iroir ?
Choix : _
```

**Validation et sauvegarde**

Après les 6 servos, un récapitulatif s'affiche :

```
VALIDATION CÔTÉ À CÔTÉ
========================================
Servo 1 (BASE      ): COPIE  → COPIE
Servo 2 (ÉPAULE    ): COPIE  → COPIE
Servo 3 (COUDE     ): COPIE  → MIROIR
Servo 4 (POIGNET-F ): COPIE  → COPIE
Servo 5 (POIGNET-R ): COPIE  → MIROIR
Servo 6 (PINCE     ): COPIE  → COPIE

[V] Sauver, [Q] Annuler
Choix : _
```

Tapez `V` pour sauvegarder. La configuration est enregistrée dans :

```
~/lerobot/calibration/teleoperation_config_cote.json
```
ou
```
~/lerobot/calibration/teleoperation_config_face.json
```

> **💡 Conseil :** En disposition côte à côte, la plupart des servos restent en COPIE. En face à face, certains servos (typiquement base et rotation) passent en MIROIR.


### 🎮 Étape 3 : Téléopération temps réel (Script 6)

**Lancement**

```bash
python SEM_so101_6_teleoperation.py
```

**Phase d'identification**

Le même processus que le script 5 : débrancher tout, brancher le Leader, valider, brancher le Follower, valider.

**Choix de la disposition**

```
[C]ôte à côte ou [F]ace à face?
Choix [C]: _
```

Le script charge automatiquement la configuration COPIE/MIROIR correspondante (sauvegardée par le script 5).

**Positionnement automatique**

Le script exécute dans l'ordre :

1. Centrage parallèle des deux robots (mouvement fluide)
2. Position repos parallèle (bras repliés)
3. Compte à rebours de 3 secondes pour prendre le Leader en main

> **Note :** La position repos utilisée ici (et lors de la séquence de fin) est celle définie en Phase 3 (`repos_position.json`), avec repli sur une valeur par défaut si le fichier manque.

**Interface de téléopération**

```
╔══════════════════════════════════════════════════════════╗
║     TÉLÉOPÉRATION - CÔTÉ À CÔTÉ                         ║
║     Servos miroir: [3, 5]                               ║
╚══════════════════════════════════════════════════════════╝

🎮 Commandes:
  [Q] + Enter : Quitter
  [F] + Enter : Flip mode (côté ↔ face)
----------------------------------------

✅ Téléopération active!
🤖 Bougez le LEADER, le FOLLOWER suit
```

**Commandes disponibles**

| Commande | Action |
| :--- | :--- |
| Q + Entrée | Quitter la téléopération |
| F + Entrée | Basculer entre côté à côté et face à face |

Le Leader est libéré (ses servos ne résistent pas). Le Follower reproduit les mouvements en temps réel selon la configuration COPIE/MIROIR de chaque servo.

**Séquence de fin**

Quand vous tapez Q :

1. Le script arrête la téléopération
2. Active tous les servos des deux robots
3. Ramène les deux robots en position repos (mouvement fluide)
4. Attend 2 secondes pour que vous teniez les robots
5. Libère tous les servos
6. Ferme les connexions

> **⚠️ Important :** Tenez les deux robots pendant la séquence de fin. Une fois les servos libérés, les bras ne sont plus maintenus.

**Comprendre les modes**

| Mode | Disposition physique | Mouvements | Usage |
| :--- | :--- | :--- | :--- |
| Côte à côte | Robots côte à côte | Selon config par servo | Manipulation synchronisée |
| Face à face | Robots face à face | Selon config par servo | Apprentissage par imitation |


### 📊 Étape 4 : Tests de validation

**Test 1 : Réactivité**

1. Bougez rapidement le servo 1 du Leader
2. Le Follower doit suivre quasi instantanément
3. Aucun décalage visible à l'œil nu

**Test 2 : Précision**

1. Positionnez précisément un servo du Leader
2. Vérifiez que le Follower atteint une position cohérente
3. En mode COPIE, les positions doivent être proches
4. En mode MIROIR, les positions doivent être inversées

**Test 3 : Amplitude complète**

1. Pour chaque servo, testez les positions MIN → MAX
2. Vérifiez que le Follower atteint les mêmes extrêmes
3. Les limites de calibration doivent être respectées

**Test 4 : Changement de mode**

1. Appuyez sur F + Entrée pendant la téléopération
2. Vérifiez que le mode bascule (côté ↔ face)
3. Les servos configurés en MIROIR doivent s'inverser

**Test 5 : Endurance**

1. Laissez la téléopération active pendant 5 minutes
2. Bougez régulièrement les servos
3. Vérifiez qu'il n'y a pas de dérive ou de désynchronisation

> **✅ Tests réussis si :**
> - Le Follower suit le Leader sans décalage visible
> - Les limites de calibration sont respectées
> - Pas de décrochage après 5 minutes
> - Le changement de mode (F) fonctionne
> - La séquence de fin (Q) remet les robots en position repos


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| "Aucun port détecté" | Robots branchés trop tôt | Débrancher tout, relancer le script, suivre l'ordre |
| Un seul port détecté | Follower pas branché ou même port | Brancher sur 2 ports USB différents |
| "Pince pas bougée" | Robot mal alimenté ou mauvais robot | Vérifier alimentation et câbles |
| Config non trouvée (script 6) | Script 5 non exécuté | Lancer d'abord le script 5 |
| Follower ne suit pas | Perte de communication | Vérifier câbles, relancer script 5 |
| Positions décalées | Mode incorrect | Appuyer sur F pour changer de mode |
| Dérive progressive | Surchauffe des servos | Pause de 5 minutes pour refroidir |
| Permission denied | Permissions insuffisantes | Vérifier le groupe `dialout` (voir Phase 1, Étape 6) |
| "Module not found" | Environnement non activé | `conda activate lerobot` |


### 💡 Conseils d'utilisation

1. **Ordre de branchement :** Toujours débrancher tout, puis Leader, puis Follower
2. **Ports USB :** Utilisez des ports USB directs sur la carte mère, évitez les hubs
3. **Alimentations :** Vérifiez que les deux alimentations sont stables
4. **Mouvements doux :** Commencez par des mouvements lents pour tester
5. **Position de sécurité :** Quittez avec Q — le script ramène en position repos
6. **Pause régulière :** Faites des pauses toutes les 10 minutes pour éviter la surchauffe


### 📝 Comprendre les fichiers de configuration

| Fichier | Créé par | Contenu |
| :--- | :--- | :--- |
| `~/lerobot/calibration/leader_calibration.json` | Phase 3 | Limites MIN/MAX/CENTRE Leader |
| `~/lerobot/calibration/follower_calibration.json` | Phase 3 | Limites MIN/MAX/CENTRE Follower |
| `~/lerobot/calibration/teleoperation_config_cote.json` | Script 5 | Config COPIE/MIROIR par servo (côte à côte) |
| `~/lerobot/calibration/teleoperation_config_face.json` | Script 5 | Config COPIE/MIROIR par servo (face à face) |


### 🚀 Commandes de référence rapide

```bash
# Configuration initiale (Script 5)
conda activate lerobot
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_5_config_teleoperation.py

# Lancement téléopération (Script 6)
python SEM_so101_6_teleoperation.py
```

**Commandes clavier dans le script 6 :**
- `Q` + Entrée — Quitter proprement
- `F` + Entrée — Basculer côté à côte ↔ face à face


### ✅ Notes finales

**✅ Phase 5 terminée quand :**

- Les deux robots sont détectés automatiquement
- La configuration par servo (script 5) se termine sans erreur
- Le Follower suit le Leader en temps réel (script 6)
- Le changement de mode fonctionne
- Vous maîtrisez les manipulations du Leader

> **🚀 Objectif atteint :** Votre système de téléopération est maintenant opérationnel ! Les robots peuvent travailler ensemble pour l'enregistrement de trajectoires et l'apprentissage par imitation qui seront couverts dans les phases suivantes.

Service Écoles-Médias — DIP Genève
Guide Phase 5 — Version 2.0
