# Guide Téléopération SO-ARM 101

## Phase 5 : Téléopération Leader-Follower

Service Écoles-Médias (SEM)

### 🧩 Scripts utilisés

- `SEM_so101_5_config_teleoperation.py` — configuration des modes COPIE/MIROIR par servo, identification guidée Leader/Follower et sauvegarde des fichiers de téléopération.
- `SEM_so101_6_teleoperation.py` — téléopération temps réel Leader → Follower, chargement de la configuration, bascule de mode et sortie sécurisée.

### 📋 Prérequis

- Phase 1 complétée (LeRobot et `dynamixel-sdk` installés)
- Phase 2 complétée (Servos configurés avec IDs 1-6)
- Phase 3 complétée (calibration **complète et valide** des deux robots — **obligatoire**)
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
| Calibrations | **Complètes et valides** (Leader ET Follower) — les scripts refusent de démarrer sinon |

> **⚠️ Important :** Les scripts demandent de brancher les robots un par un dans un ordre précis. NE PAS brancher les deux robots tout de suite ! La détection est **stricte** : exactement 1 robot attendu après le Leader, exactement 2 après le Follower (sinon le script s'arrête).


### 🔧 Étape 2 : Configuration de la téléopération (Script 5)

Ce script configure le mode COPIE ou MIROIR **pour chaque servo individuellement**. Vous testez les deux modes en temps réel et choisissez celui qui convient.

**Lancement**

```bash
python SEM_so101_5_config_teleoperation.py
```

> **Note :** Au lancement, le script **vérifie d'abord les calibrations** Leader et Follower (Phase 3) et **refuse de démarrer** si l'une est absente, incomplète ou invalide. Il est normal qu'**aucune configuration de téléopération n'existe encore** au premier lancement : c'est précisément ce script qui la crée.

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
     → Pince fermée...
     → Pince ouverte...
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
Choix [C/F] : _
```

- **Côte à côte** : les deux robots sont côte à côte, orientés dans la même direction
- **Face à face** : les deux robots se font face

**Configuration existante**

Le script 5 sert à créer ou modifier la configuration. Trois cas :

- Si **aucune configuration n'existe** encore pour le mode choisi, c'est normal : le script démarre avec une configuration par défaut en **tout-COPIE**.
- Si une configuration existe et est **valide**, elle est chargée et affichée comme état initial.
- Si une configuration existe mais est **illisible ou mal formée**, le script affiche un avertissement et repart en tout-COPIE pour permettre une nouvelle configuration propre.

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
Choix [C/M] : _
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
Choix [V/Q] : _
```

Tapez `V` pour sauvegarder. La configuration est enregistrée dans :

```
~/lerobot/calibration/teleoperation_config_cote.json
```
ou
```
~/lerobot/calibration/teleoperation_config_face.json
```

> **Note :** Tous les choix clavier (`C/F`, `C/M`, `V/Q`) sont **explicites** : une entrée vide ou invalide est refusée et redemandée. La sauvegarde est **atomique** (fichier temporaire puis remplacement) : le fichier de configuration ne peut pas rester à moitié écrit si le script est interrompu.

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
[C]ôte à côte ou [F]ace à face ?
Choix [C/F] : _
```

Le script charge la configuration COPIE/MIROIR du mode choisi (créée par le script 5). **Cette configuration est obligatoire** : si le fichier du mode choisi est **absent, illisible ou mal formé**, le script **refuse de démarrer** et vous renvoie au script 5 pour ce mode. Une configuration enregistrée « tout en COPIE » (aucun servo en miroir) reste **valide**.

> **Note :** Au lancement, le script vérifie aussi les **calibrations** Leader et Follower et **refuse de démarrer** si l'une est absente, incomplète ou invalide.

**Positionnement automatique**

Le script exécute dans l'ordre :

1. Centrage parallèle des deux robots (mouvement fluide)
2. Position repos parallèle (position de repos définie en Phase 3)
3. Pause de 3 secondes pour prendre le Leader en main

> **Note :** La position repos utilisée ici (et lors de la séquence de fin) est celle définie en Phase 3 (`repos_position.json`), avec repli **annoncé** sur une valeur par défaut si le fichier manque **ou est invalide**.

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
| Q + Entrée | Quitter proprement : retour repos **puis** libération |
| F + Entrée | Basculer côté à côte ↔ face à face — **uniquement si la config du mode cible est valide** ; sinon la bascule est refusée et le **mode courant est conservé** (la téléop continue) |
| `CTRL+C` | Interruption immédiate : libération des servos, **sans** retour repos |

Le Leader est libéré (ses servos ne résistent pas). Le Follower reproduit les mouvements en temps réel selon la configuration COPIE/MIROIR de chaque servo.

**Séquence de fin**

Deux façons d'arrêter, au comportement **différent** :

- **`Q` + Entrée (sortie normale)** : le script arrête la téléopération, ramène les deux robots en position **repos** (mouvement fluide), attend 2 secondes pour que vous les teniez, puis **libère** les servos et ferme les connexions.
- **`CTRL+C` (interruption)** : libération **immédiate** des servos, **sans** retour repos. À utiliser en cas de besoin d'arrêt rapide.

Dans les deux cas, une fois les servos libérés, les bras **ne sont plus maintenus**.

> **⚠️ Important :** Tenez les deux robots au moment de la libération (fin de `Q`, ou dès le `CTRL+C`).

**Comprendre les modes**

| Mode | Disposition physique | Mouvements | Usage |
| :--- | :--- | :--- | :--- |
| Côte à côte | Robots côte à côte | Selon config par servo | Manipulation synchronisée |
| Face à face | Robots face à face | Selon config par servo | Apprentissage par imitation |


### 📊 Étape 4 : Tests de validation

**Test 1 : Réactivité**

1. Bougez rapidement le servo 1 du Leader
2. Le Follower doit suivre de manière fluide
3. Le Follower doit suivre sans retard gênant ni décrochage

**Test 2 : Précision**

1. Positionnez précisément un servo du Leader
2. Vérifiez que le Follower atteint une position cohérente dans **sa propre** calibration
3. En mode COPIE, le Follower suit le **même sens** de mouvement (position proportionnellement cohérente — pas forcément la même valeur en ticks)
4. En mode MIROIR, le Follower suit le mouvement **inverse**, toujours dans ses propres limites

**Test 3 : Amplitude complète**

1. Pour chaque servo, testez progressivement les positions MIN → MAX
2. Ne forcez **jamais** mécaniquement contre les butées
3. Vérifiez que le Follower parcourt **sa plage correspondante** sans dépasser ses limites de calibration (les valeurs en ticks peuvent différer entre Leader et Follower : c'est le **ratio** qui est conservé)

**Test 4 : Changement de mode**

1. Appuyez sur F + Entrée pendant la téléopération
2. **Si la config du mode cible existe et est valide** : le mode bascule (côté ↔ face) et les servos configurés en MIROIR s'inversent
3. **Si la config du mode cible est absente ou invalide** : la bascule est **refusée**, un message s'affiche, et la téléopération **continue dans le mode courant** (pas d'arrêt)

**Test 5 : Endurance**

1. Laissez la téléopération active pendant 5 minutes
2. Bougez régulièrement les servos
3. Vérifiez qu'il n'y a pas de dérive ou de désynchronisation

> **✅ Tests réussis si :**
> - Le Follower suit le Leader de manière fluide, sans retard gênant ni décrochage
> - Les limites de calibration sont respectées
> - Pas de décrochage après 5 minutes
> - Le changement de mode (F) bascule si la config cible est valide, et conserve le mode courant sinon
> - `Q` ramène les robots en position repos puis libère ; `CTRL+C` libère immédiatement **sans** retour repos (les deux comportements sont compris)


### 🔧 Dépannage

| Problème | Cause possible | Solution |
| :--- | :--- | :--- |
| Calibration absente, incomplète ou invalide | Phase 3 non faite ou fichier incomplet (Leader et/ou Follower) | Refaire la calibration (Phase 3) |
| Nombre de robots ≠ 1 après le Leader (0 = non détecté, >1 = trop) | Branché trop tôt, ou plusieurs adaptateurs | Débrancher tout, relancer, ne brancher que le Leader |
| Nombre de robots ≠ 2 après le Follower (1 = Follower absent, >2 = trop) | Follower pas branché / même port, ou adaptateur en trop | Brancher le Follower sur un 2ᵉ port USB ; débrancher tout adaptateur superflu |
| "Pince pas bougée" | Robot mal alimenté ou mauvais robot | Vérifier alimentation et câbles |
| Le script 6 **refuse de démarrer** | Config du mode choisi absente ou invalide | Lancer le script 5 pour configurer ce mode |
| Flip F sans effet | Config du mode cible absente/invalide (bascule refusée, mode conservé) | Lancer le script 5 pour configurer ce mode |
| Follower ne suit pas | Perte de communication | Vérifier câbles, relancer |
| Positions décalées | Mode incorrect | Appuyer sur F pour changer de mode (si config cible valide) |
| Dérive progressive | Surchauffe des servos | Pause de 5 minutes pour refroidir |
| Permission denied | Permissions insuffisantes | Vérifier le groupe `dialout` (voir Phase 1, Étape 6) |
| "Module not found" | Environnement non activé | `conda activate lerobot` |


### 💡 Conseils d'utilisation

1. **Ordre de branchement :** Toujours débrancher tout, puis Leader, puis Follower
2. **Ports USB :** Utilisez des ports USB directs sur la carte mère, évitez les hubs
3. **Alimentations :** Vérifiez que les deux alimentations sont stables
4. **Mouvements doux :** Commencez par des mouvements lents pour tester
5. **Pause régulière :** Faites des pauses toutes les 10 minutes pour éviter la surchauffe


### 📝 Comprendre les fichiers de configuration

| Fichier | Créé par | Contenu |
| :--- | :--- | :--- |
| `~/lerobot/calibration/leader_calibration.json` | Phase 3 | Limites MIN/MAX/CENTRE Leader |
| `~/lerobot/calibration/follower_calibration.json` | Phase 3 | Limites MIN/MAX/CENTRE Follower |
| `~/lerobot/calibration/repos_position.json` | Phase 3 | Position repos partagée ; **repli annoncé** sur une valeur par défaut si absent ou invalide |
| `~/lerobot/calibration/teleoperation_config_cote.json` | Script 5 | Config COPIE/MIROIR par servo (côte à côte) — **exigée par le script 6** pour ce mode |
| `~/lerobot/calibration/teleoperation_config_face.json` | Script 5 | Config COPIE/MIROIR par servo (face à face) — **exigée par le script 6** pour ce mode |


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
- `Q` + Entrée — Quitter proprement (retour repos puis libération)
- `F` + Entrée — Basculer côté à côte ↔ face à face (si la config du mode cible est valide ; sinon mode conservé)
- `CTRL+C` — Libération immédiate, sans retour repos


### 📝 Notes finales

**✅ Phase 5 terminée quand :**

- Les calibrations Leader et Follower sont **complètes et valides**
- Les deux robots sont identifiés correctement (détection stricte)
- La configuration par servo (script 5) se termine sans erreur
- Le fichier de configuration du mode utilisé **existe et est valide**
- Le Follower suit le Leader en temps réel (script 6)
- La bascule de mode (`F`) fonctionne, ou refuse proprement une configuration absente
- Vous maîtrisez la sortie normale (`Q`, retour repos) et l'interruption immédiate (`CTRL+C`, sans repos)

> **🚀 Objectif atteint :** Votre système de téléopération est maintenant opérationnel ! Les robots peuvent travailler ensemble pour l'enregistrement de trajectoires et l'apprentissage par imitation qui seront couverts dans les phases suivantes.
