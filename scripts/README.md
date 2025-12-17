# Scripts SEM pour SO-ARM 101

Collection de scripts Python pour la configuration, calibration et contrôle des robots SO-ARM 101.

## 🔧 Prérequis

```bash
# Environnement conda activé
conda activate lerobot

# Permissions USB
sudo chmod 666 /dev/ttyACM*
```

## 📋 Liste des Scripts

### 1️⃣ SEM_so101_1_configure.py
Configuration initiale des servos avec leurs IDs (1-6) pendant le montage.
* Configuration un servo à la fois
* Test de mouvement automatique
* Centre et bloque pour le montage
* Options B (bloquer) et L (libérer) dans le menu

**Utilisation :**
```bash
python SEM_so101_1_configure.py
```

### 2️⃣ SEM_so101_2_calibrate.py
Calibration des limites de mouvement (min/max) pour chaque servo.
* Sauvegarde automatique après chaque servo
* Mode manuel : bougez le bras aux limites physiques
* Fichiers sauvés dans `~/lerobot/calibration/`
* Mouvement fluide de centrage

**Utilisation :**
```bash
python SEM_so101_2_calibrate.py
# Choisir L (Leader) ou F (Follower)
# Option T pour calibrer tous les servos
```

### 3️⃣ SEM_so101_3_monitor.py
Monitoring temps réel des positions des servos.
* Affichage en tableau avec barres graphiques
* Servos libérés pour manipulation manuelle
* Calcul FPS en temps réel
* Ctrl+C pour quitter

**Utilisation :**
```bash
python SEM_so101_3_monitor.py
# Choisir L (Leader) ou F (Follower)
```

### 4️⃣ SEM_so101_4_control.py
Contrôle manuel du robot avec le clavier.
* Mouvements fluides avec 100 steps
* Positions prédéfinies (ATTRAPER, REPOS, INITIAL)
* Mode précis ON/OFF
* Arrêt d'urgence (X)

**Utilisation :**
```bash
python SEM_so101_4_control.py
# Choisir L (Leader) ou F (Follower)
```

### 5️⃣ SEM_so101_5_config_teleoperation.py
Configuration de la téléopération Leader-Follower.
* Configure les deux robots
* Synchronisation automatique
* Test de miroir/copie
* Validation des mouvements

**Utilisation :**
```bash
python SEM_so101_5_config_teleoperation.py
```

### 6️⃣ SEM_so101_6_teleoperation.py
Téléopération en temps réel : le Leader contrôle le Follower.
* Mode MIROIR ou COPIE
* Transition fluide entre modes
* Position repos sécurisée
* Affichage temps réel

**Utilisation :**
```bash
python SEM_so101_6_teleoperation.py
```

## 🎮 Contrôles Clavier (Script 4 - Contrôle manuel)

| Touche | Action |
|--------|--------|
| ↑/↓ | Augmenter/Diminuer position |
| ←/→ | Changer de servo (1-6) |
| ESPACE | Centrer le servo actif |
| I | Position initiale |
| C | Centrer TOUS les servos |
| P | Mode précis ON/OFF |
| S | Afficher tableau des positions |
| A | Position ATTRAPER |
| R | Position REPOS |
| Q | Quitter (avec repos sécurisé) |
| X | ARRÊT D'URGENCE |

## 📁 Fichiers de Calibration

Les calibrations sont automatiquement sauvegardées dans :
* `~/lerobot/calibration/leader_calibration.json`
* `~/lerobot/calibration/follower_calibration.json`

## ⚠️ Notes Importantes

1. **Un seul robot connecté à la fois** (sauf scripts 5 et 6)
2. **Alimentation 12V 3A** requise
3. **Ordre d'exécution** : Script 1 → 2 → 3/4 → 5 → 6
4. **Sauvegarde automatique** : pas besoin de sauver manuellement

## 🔄 Workflow Complet

1. `SEM_so101_1_configure.py` - Configuration des IDs pendant le montage
2. `SEM_so101_2_calibrate.py` - Calibration des limites après montage
3. `SEM_so101_3_monitor.py` - Vérification des positions
4. `SEM_so101_4_control.py` - Test de contrôle manuel
5. `SEM_so101_5_config_teleoperation.py` - Configuration téléopération
6. `SEM_so101_6_teleoperation.py` - Mode téléopération

---

**Service Ecoles Médias - Genève**  
*Dernière mise à jour : 17.12.2025*
