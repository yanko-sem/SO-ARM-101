# SO-ARM-101 Scripts SEM

Scripts développés par le **Service Ecoles Médias (Genève)** pour les robots SO-ARM 101 avec LeRobot.

## 📦 Installation rapide

```bash
# Cloner le dépôt dans le dossier lerobot
cd ~/lerobot
git clone https://github.com/yanko-sem/SO-ARM-101.git

# Rendre les scripts exécutables
cd SO-ARM-101/scripts
chmod +x *.py
```

## 📝 Scripts disponibles

### Phase 2 : Configuration des servos
**`SEM_so101_config_servo.py`**
- Attribution des IDs (1 à 6)
- Test de mouvement
- Centrage à la position 2048
- Mode détection pour identifier les servos existants

```bash
python SEM_so101_config_servo.py
```

### Phase 3 : Calibration
**`SEM_so101_calibrate.py`**
- Calibration des limites min/max
- Sauvegarde automatique
- Tableau récapitulatif
- Support Leader et Follower

```bash
python SEM_so101_calibrate.py
```

### Phase 4 : Contrôle manuel
**`SEM_so101_control_follower.py`** et **`SEM_so101_control_leader.py`**
- Contrôle avec les flèches du clavier
- Mode précis (P)
- Centrage individuel (ESPACE) ou global (C)
- Affichage des positions (S)

```bash
# Pour le Follower
python SEM_so101_control_follower.py

# Pour le Leader  
python SEM_so101_control_leader.py
```

## 🎯 Utilisation typique

### 1. Activer l'environnement
```bash
conda activate lerobot
cd ~/lerobot/SO-ARM-101/scripts
```

### 2. Configuration initiale (une fois)
```bash
# Configurer chaque servo individuellement
python SEM_so101_config_servo.py
```

### 3. Calibration (après montage)
```bash
# Calibrer les limites de mouvement
python SEM_so101_calibrate.py
```

### 4. Test et contrôle
```bash
# Tester les mouvements
python SEM_so101_control_follower.py
```

## 🔧 Configuration matérielle

### Leader
- **Alimentation** : 5V 3A (toujours)
- **Servos** : 3 types de ratios différents
  - Servos 1,3 : Ratio 1:191 (C044)
  - Servo 2 : Ratio 1:345 (C001)
  - Servos 4,5,6 : Ratio 1:147 (C046)

### Follower
- **Alimentation** : 5V 3A ou 12V 2A selon kit
- **Servos** : Tous identiques (ratio 1:345)

## ⚠️ Points importants

1. **Un servo à la fois** lors de la configuration
2. **Position 2048** = position centrale
3. **Reconfiguration normale** après montage mécanique
4. **Permissions USB** : `sudo chmod 666 /dev/ttyACM*`

## 📂 Structure des fichiers

```
SO-ARM-101/
├── README.md (ce fichier)
├── scripts/
│   ├── SEM_so101_config_servo.py
│   ├── SEM_so101_calibrate.py
│   ├── SEM_so101_control_follower.py
│   └── SEM_so101_control_leader.py
└── docs/
    └── guides/ (PDFs disponibles séparément)
```

## 🆘 Dépannage

| Problème | Solution |
|----------|----------|
| Port USB non détecté | Vérifier branchement, essayer autre port |
| Permission denied | `sudo chmod 666 /dev/ttyACM*` |
| Servo ne bouge pas | Vérifier alimentation et câbles |
| Position perdue | Relancer script de configuration |
