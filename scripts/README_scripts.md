# Scripts SEM pour SO-ARM 101

Collection de scripts Python pour la configuration, calibration et contrôle des robots SO-ARM 101.

## 📋 Liste des Scripts

### 1️⃣ **SEM_so101_config_servo.py**
Configuration initiale des servos avec leurs IDs (1-6) et ratios spécifiques.
- Configuration un servo à la fois
- Test de mouvement automatique
- Compatible Leader et Follower

**Utilisation :**
```bash
python SEM_so101_config_servo.py
```

### 2️⃣ **SEM_so101_calibrate.py**
Calibration des limites de mouvement (min/max) pour chaque servo.
- Sauvegarde automatique après chaque servo
- Mode manuel : bougez le bras aux limites physiques
- Fichiers sauvés dans `~/.cache/calibration/so101/`

**Utilisation :**
```bash
python SEM_so101_calibrate.py
# Choisir L (Leader) ou F (Follower)
# Option T pour calibrer tous les servos
```

### 3️⃣ **SEM_so101_control_follower.py**
Contrôle manuel du bras Follower avec le clavier.
- Mouvements fluides avec courbe sinusoïdale
- Positions prédéfinies (ATTRAPER, REPOS)
- Arrêt d'urgence (X)

**Utilisation :**
```bash
python SEM_so101_control_follower.py
```

### 4️⃣ **SEM_so101_control_leader.py**
Contrôle manuel du bras Leader avec le clavier.
- Mêmes fonctionnalités que le Follower
- Adapté aux ratios spécifiques du Leader

**Utilisation :**
```bash
python SEM_so101_control_leader.py
```

## 🎮 Contrôles Clavier (Scripts de contrôle)

| Touche | Action |
|--------|--------|
| ↑/↓ | Augmenter/Diminuer position |
| ←/→ | Changer de servo (1-6) |
| ESPACE | Centrer le servo actif |
| C | Centrer TOUS les servos |
| P | Mode précis ON/OFF (pas 10 vs 50) |
| S | Afficher toutes les positions |
| A | Position ATTRAPER |
| R | Position REPOS |
| Q | Quitter (avec repos sécurisé) |
| X | ARRÊT D'URGENCE |

## 🔧 Prérequis

```bash
# Environnement conda activé
conda activate lerobot

# Permissions USB
sudo chmod 666 /dev/ttyACM*
```

## 📁 Fichiers de Calibration

Les calibrations sont automatiquement sauvegardées dans :
- `~/.cache/calibration/so101/leader_calibration.json`
- `~/.cache/calibration/so101/follower_calibration.json`

## ⚠️ Notes Importantes

1. **Un seul robot** connecté à la fois
2. **Alimentation 5V 3A** minimum requise
3. **Phase 2** (config) avant Phase 3 (calibration)
4. **Sauvegarde automatique** : pas besoin de sauver manuellement

## 🔄 Ordre d'Exécution

1. `SEM_so101_config_servo.py` - Configuration des IDs
2. `SEM_so101_calibrate.py` - Calibration des limites
3. `SEM_so101_control_*.py` - Test et contrôle

---
Service Ecoles Médias - Genève
