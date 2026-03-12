# Scripts SEM pour SO-ARM 101

Collection de scripts Python pour la configuration, calibration et contrôle des robots SO-ARM 101.

## 🔧 Prérequis

```bash
# Environnement conda activé
conda activate lerobot

# Permissions USB (configuré une fois en Phase 1, Étape 6)
# L'utilisateur doit être dans les groupes dialout et video
groups | grep dialout
groups | grep video
```

## 📋 Liste des Scripts

### 1️⃣ SEM_so101_1_configure.py
Configuration initiale des servos avec leurs IDs (1-6) pendant le montage.
- Configuration un servo à la fois
- Test de mouvement automatique
- Centre et bloque pour le montage
- Options B (bloquer) et L (libérer) dans le menu

**Utilisation :**
```bash
python SEM_so101_1_configure.py
```

### 2️⃣ SEM_so101_2_calibrate.py
Calibration des limites de mouvement (min/max) pour chaque servo.
- Sauvegarde automatique après chaque servo
- Mode manuel : bougez le bras aux limites physiques
- Mouvement fluide de centrage (courbe sinusoïdale)

**Fichiers sauvés dans :** `~/lerobot/calibration/`

**Utilisation :**
```bash
python SEM_so101_2_calibrate.py
# Choisir L (Leader) ou F (Follower)
# Option T pour calibrer tous les servos
```

### 3️⃣ SEM_so101_3_monitor.py
Monitoring temps réel des positions des servos.
- Affichage en tableau avec barres graphiques
- Servos libérés pour manipulation manuelle
- Calcul FPS en temps réel
- Ctrl+C pour quitter

**Utilisation :**
```bash
python SEM_so101_3_monitor.py
# Choisir L (Leader) ou F (Follower)
```

### 4️⃣ SEM_so101_4_control.py
Contrôle manuel du robot avec le clavier (script unifié Leader/Follower).
- Choix Leader ou Follower au lancement
- Mouvements fluides (100 steps)
- Positions prédéfinies : Initiale (I), Attraper (A), Repos (R)
- Mode précis ON/OFF (P)
- Arrêt d'urgence (X)

**Utilisation :**
```bash
python SEM_so101_4_control.py
# Choisir L (Leader) ou F (Follower)
```

### 5️⃣ SEM_so101_5_config_teleoperation.py
Configuration COPIE/MIROIR de la téléopération, servo par servo.
- Identification guidée des robots (débrancher/brancher)
- Choix côte à côte ou face à face
- Test interactif COPIE puis MIROIR pour chaque servo
- Sauvegarde de la configuration par disposition

**Utilisation :**
```bash
python SEM_so101_5_config_teleoperation.py
```

### 6️⃣ SEM_so101_6_teleoperation.py
Téléopération en temps réel : le Leader contrôle le Follower.
- Identification guidée des robots
- Centrage et position repos automatiques
- Basculement côté à côte ↔ face à face avec F + Entrée
- Position repos sécurisée en fin de session

**Commandes :**
- `Q` + Entrée — Quitter
- `F` + Entrée — Basculer le mode

**Utilisation :**
```bash
python SEM_so101_6_teleoperation.py
```

### 7️⃣ SEM_so101_7_teleoperation_camera.py
Téléopération avec retour vidéo d'une caméra.
- Identique au script 6 + affichage vidéo en temps réel
- Fenêtre OpenCV `Camera SO-ARM 101`
- Test de la caméra avant enregistrement (Phase 7)

**Commandes :**
- `Q` + Entrée — Quitter (terminal)
- `F` + Entrée — Basculer le mode (terminal)
- `q` — Quitter (fenêtre vidéo)

**Utilisation :**
```bash
python SEM_so101_7_teleoperation_camera.py
```

### 8️⃣ SEM_so101_8_record_dataset.py
Enregistrement de dataset pour l'apprentissage par imitation.
- 2 caméras simultanées (cam_top + cam_follower)
- Identification caméras via le terminal (G = Globale, P = Pince)
- Affichage des 2 flux vidéo pendant la téléopération
- Format LeRobotDataset v2.1
- 5 positions × 10 épisodes = 50 démonstrations
- Tâche : prendre un cube et le déposer dans une boîte

**Utilisation :**
```bash
python SEM_so101_8_record_dataset.py
# G = identifier caméra Globale (vue d'ensemble)
# P = identifier caméra Pince (sur le follower)
# D = Démarrer un enregistrement
# T = Terminer l'épisode, A = Annuler, S = Stopper
```


## 🎮 Contrôles Clavier (Script 4 — Contrôle manuel)

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


## 🎮 Contrôles (Script 8 — Enregistrement)

**Identification caméras :**

| Touche | Action |
|--------|--------|
| G + Entrée | Identifier caméra Globale (vue d'ensemble) |
| P + Entrée | Identifier caméra Pince (follower) |
| Q + Entrée | Passer la caméra |

**Pendant l'enregistrement :**

| Touche | Action |
|--------|--------|
| D | Démarrer l'enregistrement d'un épisode |
| T | Terminer l'épisode (succès) |
| A | Annuler l'épisode en cours |
| S | Stopper la session |
| Q | Quitter le programme |


## 📁 Fichiers de Calibration

Les calibrations sont automatiquement sauvegardées dans :
- `~/lerobot/calibration/leader_calibration.json`
- `~/lerobot/calibration/follower_calibration.json`

Les configurations de téléopération :
- `~/lerobot/calibration/teleoperation_config_cote.json`
- `~/lerobot/calibration/teleoperation_config_face.json`


## 📁 Datasets Enregistrés

Les datasets sont sauvegardés dans :
- `~/.cache/huggingface/lerobot/local/so101_pick_place/`


## ⚠️ Notes Importantes

1. **Un seul robot connecté à la fois** (sauf scripts 5, 6, 7 et 8)
2. **Alimentation :** 5V ou 12V selon le kit
3. **Ordre d'exécution :** Script 1 → 2 → 3/4 → 5 → 6 → 7 → 8
4. **Sauvegarde automatique :** Pas besoin de sauver manuellement
5. **Permissions USB :** L'utilisateur doit être dans les groupes `dialout` et `video` (voir Phase 1, Étape 6)
6. **Environnement :** Toujours activer avec `conda activate lerobot` (les scripts 7 et 8 s'auto-activent si lancés depuis `base`)
7. **2 caméras USB** requises pour le script 8


## 🔄 Workflow Complet

```
1. SEM_so101_1_configure.py      → Configuration des IDs pendant le montage
2. SEM_so101_2_calibrate.py      → Calibration des limites après montage
3. SEM_so101_3_monitor.py        → Vérification des positions
4. SEM_so101_4_control.py        → Test de contrôle manuel
5. SEM_so101_5_config_teleoperation.py → Configuration COPIE/MIROIR
6. SEM_so101_6_teleoperation.py  → Téléopération temps réel
7. SEM_so101_7_teleoperation_camera.py → Téléopération avec caméra
8. SEM_so101_8_record_dataset.py → Enregistrement de dataset (2 caméras)
```

---

**Service Écoles-Médias — DIP Genève**
*Dernière mise à jour : 12.03.2026*
