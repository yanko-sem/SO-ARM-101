# Supports de Caméra pour SO-ARM 101

Supports d'impression 3D pour caméras InnoMaker U20CAM-1080P-S1 (32x32mm).

## 📸 Configuration 2 caméras

Pour l'apprentissage par imitation optimal, chaque robot nécessite 2 caméras :

### 1️⃣ **Caméra Poignet**
- **Fichier** : `SO101_Wrist_Cam_Mount_32x32.stl`
- **Position** : Montée sur le servo 6 (poignet)
- **Vue** : Rapprochée de la pince et de l'objet
- **Utilité** : Précision de préhension

### 2️⃣ **Caméra Aérienne**
- **Dossier** : `Aerienne/` (3 pièces)
  - `arm_base.stl` - Base de fixation
  - `cam_mount_bottom.stl` - Support inférieur
  - `cam_mount_top.stl` - Support supérieur
- **Position** : Au-dessus de l'espace de travail
- **Vue** : Ensemble de la zone de manipulation
- **Utilité** : Contexte spatial

## 🔧 Installation

### Caméra Poignet

1. **Imprimer** `SO101_Wrist_Cam_Mount_32x32.stl`
   - Remplissage : 40%
   - Supports : Arborescent

2. **Matériel nécessaire**
   - 4x vis M2 (des servos)
   - 2x vis M3
   - 2x écrous hexagonaux M3

3. **Montage**
   - Démonter le servo 6
   - Insérer les écrous hex dans les logements
   - Remonter le servo 6
   - Fixer l'adaptateur avec les vis M3
   - Monter la caméra avec les vis M2

### Caméra Aérienne

1. **Imprimer les 3 pièces**
   - Remplissage : 40%
   - Supports : Arborescent

2. **Matériel nécessaire**
   - 8x vis M2
   - 1x boulon hexagonal

3. **Assemblage**
   - Assembler `cam_mount_top` + `cam_mount_bottom`
   - Fixer avec 4x vis M2
   - Monter sur `arm_base`
   - Fixer l'ensemble à la base du robot

## 📐 Dimensions caméra

**InnoMaker U20CAM-1080P-S1**
- Taille PCB : 32 x 32 mm
- Trous de fixation : 27 mm d'entraxe
- Diamètre trous : 2.2 mm (pour vis M2)
- Épaisseur : ~3 mm

## ⚙️ Configuration logicielle

### Paramètres recommandés
```
Résolution : 640 x 480
FPS : 30
Format : MJPEG
```

### Mise au point
- **IMPORTANT** : Focus manuel sur la caméra
- Ajuster avant de fixer définitivement
- Distance optimale : 15-30 cm pour poignet

## 🎯 Positionnement optimal

```
        [Caméra Aérienne]
         ↓ (50-70 cm)
    ┌─────────────┐
    │   Espace    │
    │  de travail │
    │   30x30cm   │
    └─────────────┘
         ↑
    [Robot + Caméra Poignet]
```

## 💡 Conseils

1. **Câbles USB** : Prévoir câbles suffisamment longs
2. **Hub USB** : Recommandé pour 2+ caméras
3. **Éclairage** : Uniforme, éviter ombres portées
4. **Calibration** : Faire après installation fixe

## 📥 Sources originales

- [Support Poignet GitHub](https://github.com/TheRobotStudio/SO-ARM100/tree/main/Optional/SO101_Wrist_Cam_Hex-Nut_Mount_32x32_UVC_Module)
- [Support Aérien GitHub](https://github.com/TheRobotStudio/SO-ARM100/tree/main/Optional/Overhead_Cam_Mount_Webcam)

---
Service Ecoles Médias - Genève
