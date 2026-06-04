# Fichiers STL pour SO-ARM 101

Fichiers d'impression 3D pour les robots SO-ARM 101 et les supports de caméras.

## 📂 Structure

### 🤖 Leader/
Pièces à imprimer pour le bras de contrôle (Leader)
- Ratios servos spécifiques : 1:191, 1:345, 1:147

### 🤖 Follower/
Pièces à imprimer pour le bras suiveur (Follower)
- Tous les servos au ratio 1:345

### 📸 CAM/
Supports de caméras pour InnoMaker U20CAM-1080P-S1 (32x32mm)
- Support poignet : vue rapprochée de la pince
- Support aérien : vue d'ensemble de l'espace de travail

## 🖨️ Paramètres d'impression recommandés

### Configuration générale
- **Type d'imprimante** : FDM (Prusa, Ender, etc.)
- **Matériau** : PLA ou PETG
- **Température buse** : 210°C (PLA) / 240°C (PETG)
- **Température plateau** : 60°C (PLA) / 80°C (PETG)

### Qualité d'impression
- **Hauteur de couche** : 0.2mm (buse 0.4mm) ou 0.4mm (buse 0.6mm)
- **Épaisseur parois** : 2-3 périmètres (1.2mm minimum)
- **Remplissage** : 30-40% (Gyroïde ou Cubique)
- **Supports** : Arborescent (Tree) si nécessaire

### Paramètres spécifiques par pièce

#### Pièces Robot (Leader/Follower)
- **Remplissage** : 30% minimum
- **Orientation** : Comme dans les fichiers STL fournis
- **Supports** : Selon la géométrie
- **Temps d'impression** : ~15-20h total par robot

#### Supports Caméra
- **Remplissage** : 40% (plus de rigidité)
- **Supports** : Arborescent recommandé
- **Post-traitement** : Retirer les supports avec précaution

## ⚠️ Conseils importants

### Préparation
1. **Nettoyer le plateau** : Dégraisser avec alcool isopropylique
2. **Calibrer le plateau** : Niveau parfait indispensable
3. **Première couche** : Surveiller l'adhérence
4. **Colle** : Bâton de colle si nécessaire (verre/PEI)

### Impression
- **Ventilation** : 100% après la 2ème couche (PLA)
- **Vitesse** : 50-60 mm/s pour qualité optimale
- **Rétraction** : 5-6mm à 45mm/s (bowden) / 1-2mm (direct drive)

### Post-traitement
1. **Laisser refroidir** avant de décoller
2. **Ébavurer** les trous avec un foret
3. **Poncer légèrement** les surfaces de contact si nécessaire
4. **Vérifier** l'ajustement des vis M2/M3 avant assemblage

## 🔧 Matériel nécessaire

### Pour assemblage robot
- Vis M2 et M3 (fournies avec servos)
- Tournevis cruciforme #0 et #1
- Clé Allen 2mm et 2.5mm

### Pour supports caméra
- **Poignet** : 4x vis M2 + 2x vis M3 + 2x écrous hex M3
- **Aérien** : 8x vis M2 + 1x boulon hexagonal

## 📥 Sources des fichiers

### Fichiers robots originaux
- **GitHub officiel** : [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100)
- **Leader** : `/STL/SO101/Leader/`
- **Follower** : `/STL/SO101/Follower/`

### Fichiers supports caméra
- **Poignet** : [Wrist Camera Mount](https://github.com/TheRobotStudio/SO-ARM100/tree/main/Optional/SO101_Wrist_Cam_Hex-Nut_Mount_32x32_UVC_Module)
- **Aérien** : [Overhead Camera Mount](https://github.com/TheRobotStudio/SO-ARM100/tree/main/Optional/Overhead_Cam_Mount_Webcam)

## 📊 Estimation des coûts

### Matière première
- **1 robot** : ~200-300g de filament (~5-8€)
- **Supports caméra** : ~50g de filament (~1-2€)
- **Total pour kit complet** : ~10-15€ de filament

### Temps d'impression
- **Leader** : ~15-20h
- **Follower** : ~15-20h
- **Supports caméra** : ~3-4h
- **Total** : ~35-45h d'impression

## 💡 Dépannage

| Problème | Solution |
|----------|----------|
| Warping (décollement) | Augmenter température plateau, utiliser brim |
| Stringing (fils) | Augmenter rétraction, baisser température |
| Couches qui se décollent | Vérifier ventilation, augmenter température |
| Trous trop serrés | Percer avec foret du bon diamètre |
| Pièces fragiles | Augmenter remplissage à 40-50% |

---
Service Ecoles Médias - Genève
