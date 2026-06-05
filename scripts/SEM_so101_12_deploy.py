#!/usr/bin/env python3
"""
Script SEM_so101_12_deploy.py
Service Écoles-Médias (SEM) - DIP Genève

DÉPLOIEMENT DU MODÈLE ACT — INFÉRENCE AUTONOME
================================================

Ce script charge un modèle ACT entraîné et laisse le bras Follower
agir de façon autonome : aucun opérateur n'est nécessaire.

Le modèle observe en continu les deux caméras et les positions actuelles
des servos du Follower, calcule les positions cibles, et les envoie
directement aux servos à ~30 images/seconde.

Contrôles pendant l'inférence (au clavier, dans le terminal):
    P      : Pause / Reprendre
    R      : Retour repos + désactivation du modèle (fin d'essai)
    Entrée : Relancer le modèle pour un nouvel essai
    Q      : Quitter

Auteur: Service Écoles-Médias (SEM)
Version: 1.0
Date: Avril 2026
"""

import os
import sys
import json
import math
import time
import queue
import threading
from pathlib import Path

# Supprimer les messages d'erreur OpenCV
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"

# Tentative d'import OpenCV
try:
    import cv2
    cv2.setNumThreads(1)
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("⚠️  OpenCV non disponible - déploiement sans affichage vidéo")

# Auto-activation de l'environnement lerobot si nécessaire
try:
    sys.path.append(os.path.expanduser('~/lerobot'))
    from dynamixel_sdk import *
except ImportError:
    print("\n🔧 Activation automatique de l'environnement lerobot...")
    import subprocess
    lerobot_python = os.path.expanduser("~/miniconda3/envs/lerobot/bin/python3")
    if os.path.exists(lerobot_python):
        print("✅ Relancement avec lerobot...")
        subprocess.call([lerobot_python] + sys.argv)
        sys.exit(0)
    else:
        print("❌ Environnement lerobot non trouvé!")
        print("Solution: conda activate lerobot")
        sys.exit(1)

import numpy as np
import torch

try:
    from lerobot.common.policies.act.modeling_act import ACTPolicy
except ImportError:
    print("❌ LeRobot non disponible!")
    print("Solution: conda activate lerobot")
    sys.exit(1)

# Module de configuration caméra — partagé avec le script 8 (même camera_settings.json).
# Le script 12 propose au lancement de revérifier/refaire les réglages (capturer_reglages_camera,
# papier blanc) puis les APPLIQUE (verrouiller_camera) — cohérence colorimétrie entraînement↔déploiement.
# Import protégé : si le module est absent, mal placé ou cassé, on le signalera plus bas
# par un message clair + arrêt propre, au lieu d'un traceback illisible au démarrage.
try:
    from SEM_8_camera_config import verrouiller_camera, capturer_reglages_camera
    CAMERA_LOCK_AVAILABLE = True
    CAMERA_LOCK_IMPORT_ERROR = None
except Exception as e:
    verrouiller_camera = None
    capturer_reglages_camera = None
    CAMERA_LOCK_AVAILABLE = False
    CAMERA_LOCK_IMPORT_ERROR = e

# ============================================
# CONFIGURATION
# ============================================

CONFIG = {
    'fps': 30,
    'camera_width': 640,
    'camera_height': 360,   # 16:9 — doit correspondre exactement à la résolution d'entraînement
    'baud_rate': 1000000,
}

# Chemin du dossier d'entraînement (portable, fonctionne sur tout PC)
TRAIN_OUTPUT_DIR = Path.home() / "lerobot" / "outputs" / "train" / "act_so101_pick_place"

# Calibration
CALIB_DIR = Path.home() / "lerobot" / "calibration"

# Noms des caméras — doivent correspondre exactement au dataset d'entraînement
CAM_TOP      = "cam_top"
CAM_FOLLOWER = "cam_follower"

# Position repos — fichier externe partagé entre tous les scripts (cohérence 7/8/12)
REPOS_FILE = Path.home() / "lerobot" / "calibration" / "repos_position.json"

# Masque de zone utile — fichier externe créé par le script 7 (cohérence 7/8/12)
MASK_FILE = Path.home() / "lerobot" / "calibration" / "camera_mask.json"

# Device GPU ou CPU
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Variables globales
stop_threads = False          # arrête le thread clavier
cmd_queue    = queue.Queue()  # file des commandes clavier (P / R / Q)
urgence      = False          # devient True sur CTRL+C : arrêt d'urgence, pas de retour repos
_MASK_GLOBALE_IMG = None      # image binaire du masque globale (None tant que le fichier n'est pas chargé)

# ============================================
# FONCTIONS UTILITAIRES
# ============================================

def clear_screen():
    os.system('clear')


def detect_ports():
    """Détecte les ports des robots.

    Teste chaque port candidat en interrogeant le servo 1 : ne garde que les
    ports qui répondent au protocole servo (= robots). Les autres périphériques
    série (téléphone en charge, etc.) sont ignorés. Le robot doit être alimenté.
    """
    ports = []
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']:
        if not os.path.exists(port):
            continue
        ph = PortHandler(port)
        pk = PacketHandler(1.0)
        try:
            if ph.openPort() and ph.setBaudRate(CONFIG['baud_rate']):
                _, result, _ = pk.read2ByteTxRx(ph, 1, 56)
                ph.closePort()
                if result == COMM_SUCCESS:
                    ports.append(port)
            else:
                ph.closePort()
        except Exception:
            try:
                ph.closePort()
            except Exception:
                pass
    return ports


def charger_calibration(robot_type):
    """Charge la calibration d'un robot depuis le fichier JSON"""
    calib_file = CALIB_DIR / f"{robot_type}_calibration.json"
    if calib_file.exists():
        with open(calib_file, 'r') as f:
            return json.load(f)
    return None


def lire_positions(packet_handler, port_handler):
    """Lit les positions actuelles de tous les servos (1 à 6)"""
    positions = {}
    for servo_id in range(1, 7):
        pos, _, _ = packet_handler.read2ByteTxRx(port_handler, servo_id, 56)
        positions[servo_id] = pos
    return positions


def ecrire_position(packet_handler, port_handler, servo_id, position):
    """Écrit une position cible sur un servo avec clipping [0, 4095]"""
    position = max(0, min(4095, int(position)))
    packet_handler.write2ByteTxRx(port_handler, servo_id, 42, position)


def charger_masque_globale():
    """Lit MASK_FILE (créé par le script 7) et renvoie la liste des points
    du polygone, ou None si le fichier est absent ou invalide."""
    if not MASK_FILE.exists():
        return None
    try:
        with open(MASK_FILE, 'r') as f:
            data = json.load(f)
        pts = [tuple(p) for p in data["points"]]
        return pts
    except Exception:
        return None


def construire_mask_image(points, width, height):
    """Construit le masque binaire (uint8 0/255) à partir des points du polygone."""
    if points is None:
        return None
    mask = np.zeros((height, width), dtype=np.uint8)
    pts = np.array(points, np.int32)
    cv2.fillPoly(mask, [pts], 255)
    return mask


def charger_repos_pct():
    """Charge la position repos (% par servo) depuis le fichier externe partagé.
    Fallback sur les valeurs par défaut si le fichier est absent ou invalide.
    Identique aux scripts 7/8 : garantit que le Follower démarre l'inférence
    depuis la pose exacte des épisodes d'enregistrement (évite le hors-distribution)."""
    defaut = {1: 50, 2: 10, 3: 88, 4: 76, 5: 50, 6: 11}
    if REPOS_FILE.exists():
        try:
            with open(REPOS_FILE, 'r') as f:
                data = json.load(f)
                return {int(k): float(v) for k, v in data.items()}
        except Exception:
            return defaut
    return defaut


def _cible_ticks(calib, servo_id, pct):
    """Convertit un pourcentage en ticks pour un servo (fallback 2048)."""
    if calib and f'servo_{servo_id}' in calib:
        min_val = calib[f'servo_{servo_id}']['min']
        max_val = calib[f'servo_{servo_id}']['max']
        return int(min_val + (max_val - min_val) * pct / 100)
    return 2048


def _est_en_repos(packet, port, calib, repos_pct, tolerance_pct=5):
    """Vrai si le bras est actuellement proche de la position repos (tous les servos)."""
    for i in range(1, 7):
        pos, _, _ = packet.read2ByteTxRx(port, i, 56)
        if calib and f'servo_{i}' in calib:
            min_val = calib[f'servo_{i}']['min']
            max_val = calib[f'servo_{i}']['max']
            pct_actuel = (pos - min_val) / (max_val - min_val) * 100 if max_val > min_val else 50
        else:
            pct_actuel = 50
        if abs(pct_actuel - repos_pct.get(i, 50)) > tolerance_pct:
            return False
    return True


def mouvement_servos(packet, port, calib, cibles_pct, servos, duree=2.0):
    """Déplace les servos indiqués vers cibles_pct (%) avec un profil cosinus."""
    pos = {}
    for s in servos:
        pos[s], _, _ = packet.read2ByteTxRx(port, s, 56)
    cible = {}
    for s in servos:
        cible[s] = _cible_ticks(calib, s, cibles_pct[s])
    steps = 100
    for step in range(steps + 1):
        t = step / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        for s in servos:
            packet.write2ByteTxRx(port, s, 42, int(pos[s] + (cible[s] - pos[s]) * smooth))
        time.sleep(duree / steps)


def aller_a_position(packet, port, calib, cibles_pct, duree=2.0):
    """Déplace le bras Follower vers cibles_pct (%) en respectant les contraintes
    physiques (séquence sûre anti-collision). Version mono-bras de la séquence
    du script 8 :
      Phase 0 (conditionnelle) : si servo 4 > 2700 et bras pas en repos, lever
                                 l'épaule (servo 2 -> min(actuel, 1027)) pour
                                 dégager la pince du sol/de la boîte
      Phase 1 : servo 4 -> 20% (pince en l'air)
      Phase 2 : servos 1,2,3,5,6 -> cibles, en parallèle
      Phase 3 : servo 4 -> cible finale
    """
    # Activer le couple sur tous les servos
    for i in range(1, 7):
        packet.write1ByteTxRx(port, i, 40, 1)

    repos_pct = charger_repos_pct()

    # --- Phase 0 (conditionnelle) : levée d'épaule pour dégager la pince ---
    pos4, _, _ = packet.read2ByteTxRx(port, 4, 56)
    if pos4 > 2700 and not _est_en_repos(packet, port, calib, repos_pct):
        deb, _, _ = packet.read2ByteTxRx(port, 2, 56)
        fin = min(deb, 1027)
        steps = int(duree * 50)
        for step in range(steps + 1):
            t = step / steps
            smooth = (1 - math.cos(t * math.pi)) / 2
            packet.write2ByteTxRx(port, 2, 42, int(deb + (fin - deb) * smooth))
            time.sleep(duree / steps)

    # --- Phase 1 : servo 4 -> 20% (pince en l'air) ---
    mouvement_servos(packet, port, calib, {4: 20}, [4], duree)

    # --- Phase 2 : servos 1,2,3,5,6 en parallèle ---
    mouvement_servos(packet, port, calib, cibles_pct, [1, 2, 3, 5, 6], duree)

    # --- Phase 3 : servo 4 -> cible finale ---
    mouvement_servos(packet, port, calib, cibles_pct, [4], duree)


def aller_position_repos(packet_handler, port_handler, calib):
    """Déplace le Follower vers la position repos partagée via la séquence sûre."""
    print("\n🏁 Retour en position repos...")
    repos_pct = charger_repos_pct()
    aller_a_position(packet_handler, port_handler, calib, repos_pct, duree=2.0)
    print("✅ Position repos atteinte")


def frame_vers_tensor(frame):
    """
    Convertit une frame OpenCV (BGR uint8) en tenseur PyTorch.
    Format de sortie : [1, 3, H, W] float32 dans [0.0, 1.0] sur DEVICE.
    """
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    tensor = torch.from_numpy(rgb).float() / 255.0
    tensor = tensor.permute(2, 0, 1).unsqueeze(0)   # [H,W,C] → [1,C,H,W]
    return tensor.to(DEVICE)


# ============================================
# CLASSE THREADED CAMERA (identique au script 8)
# ============================================

class ThreadedCamera:
    """
    Caméra avec thread de lecture dédié (architecture LeRobot).
    Le thread lit en continu et stocke la dernière frame disponible.
    async_read() retourne immédiatement la dernière frame sans bloquer.
    """

    def __init__(self, camera_index, name, width=640, height=360, fps=30):
        self.camera_index  = camera_index
        self.name          = name
        self.width         = width
        self.height        = height
        self.fps           = fps
        self.camera        = None
        self.is_connected  = False
        self.thread        = None
        self.stop_event    = None
        self.current_frame = None
        self.frame_lock    = threading.Lock()

    def connect(self):
        """Connecte la caméra et démarre le thread de lecture"""
        if self.is_connected:
            return True
        if not CV2_AVAILABLE:
            return False

        self.camera = cv2.VideoCapture(self.camera_index)
        if not self.camera.isOpened():
            print(f"❌ Impossible d'ouvrir {self.name} (index {self.camera_index})")
            return False

        # Forcer le format MJPG aide souvent sur Linux pour les hautes résolutions
        self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.camera.set(cv2.CAP_PROP_FPS,          self.fps)

        # Warmup : vider le buffer matériel (les premières frames sont souvent corrompues)
        print(f"   ⏳ Initialisation du capteur {self.name}...")
        for _ in range(5):
            ret, frame = self.camera.read()
            if ret:
                self.current_frame = frame
            time.sleep(0.1)

        if self.current_frame is None:
            print(f"❌ La caméra {self.name} ne renvoie aucune image valide.")
            self.camera.release()
            return False

        self.is_connected = True
        self.stop_event   = threading.Event()
        self.thread       = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

        print(f"   ✅ {self.name} connectée (index {self.camera_index})")
        return True

    def _read_loop(self):
        """
        Boucle de lecture en continu (dans son propre thread).
        camera.read() est bloquant — il attend la prochaine frame matérielle.
        Pas de time.sleep() nécessaire : il créerait du lag inutilement.
        """
        while not self.stop_event.is_set():
            if self.camera and self.camera.isOpened():
                ret, frame = self.camera.read()
                if ret:
                    with self.frame_lock:
                        self.current_frame = frame

    def async_read(self):
        """Retourne la dernière frame disponible (non-bloquant)"""
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None

    def disconnect(self):
        """Arrête le thread et libère la caméra"""
        if self.thread is not None:
            self.stop_event.set()
            self.thread.join(timeout=2.0)
            self.thread = None
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        self.is_connected = False


# ============================================
# SÉLECTION DU CHECKPOINT
# ============================================

def selectionner_checkpoint():
    """
    Liste les checkpoints disponibles dans le sous-dossier 'checkpoints/'
    et demande à l'utilisateur d'en choisir un.
    Retourne le Path vers le dossier pretrained_model/ du checkpoint
    sélectionné (chemin attendu par ACTPolicy.from_pretrained()),
    ou None en cas d'erreur.

    Structure LeRobot réelle :
    outputs/train/act_so101_pick_place/
    └── checkpoints/
        ├── 002000/
        │   └── pretrained_model/   ← from_pretrained() pointe ici
        ├── 010000/
        │   └── pretrained_model/
        └── ...
    """
    print("\n" + "=" * 60)
    print("📂 SÉLECTION DU CHECKPOINT")
    print("=" * 60)

    checkpoints_dir = TRAIN_OUTPUT_DIR / "checkpoints"

    if not checkpoints_dir.exists():
        print(f"\n❌ Dossier de checkpoints introuvable :")
        print(f"   {checkpoints_dir}")
        print("   → Vérifiez que l'entraînement (Script 11) a bien été effectué.")
        return None

    # Scanner les sous-dossiers qui contiennent un dossier pretrained_model/
    checkpoints = sorted(
        [item for item in checkpoints_dir.iterdir()
         if item.is_dir() and (item / "pretrained_model").is_dir()]
    )

    if not checkpoints:
        print("❌ Aucun checkpoint valide trouvé dans :")
        print(f"   {checkpoints_dir}")
        return None

    print(f"\n📋 Checkpoints disponibles ({len(checkpoints)}) :\n")
    for i, cp in enumerate(checkpoints):
        marker = "  ← recommandé" if cp.name == "last" else ""
        print(f"   [{i + 1}] {cp.name}{marker}")

    print(f"\n   [Entrée] Utiliser le dernier checkpoint (recommandé)")
    choix = input("\n→ Votre choix (numéro ou Entrée) : ").strip()

    # Préférer "last", sinon prendre le dernier de la liste triée
    last_cp = next((cp for cp in checkpoints if cp.name == "last"), checkpoints[-1])

    if choix == "":
        print(f"\n✅ Checkpoint sélectionné : {last_cp.name}")
        return last_cp / "pretrained_model"

    try:
        idx = int(choix) - 1
        if 0 <= idx < len(checkpoints):
            print(f"\n✅ Checkpoint sélectionné : {checkpoints[idx].name}")
            return checkpoints[idx] / "pretrained_model"
        else:
            print(f"❌ Numéro invalide — utilisation de '{last_cp.name}'.")
            return last_cp / "pretrained_model"
    except ValueError:
        print(f"❌ Saisie invalide — utilisation de '{last_cp.name}'.")
        return last_cp / "pretrained_model"


# ============================================
# CHARGEMENT DU MODÈLE
# ============================================

def charger_modele(checkpoint_path):
    """
    Charge la politique ACT depuis le checkpoint sélectionné.
    Le modèle est placé en mode évaluation (pas d'entraînement).
    """
    print(f"\n🤖 Chargement du modèle ACT...")
    print(f"   Checkpoint : {checkpoint_path.parent.name}")
    print(f"   Chemin     : {checkpoint_path}")
    print(f"   Device     : {DEVICE}")

    try:
        policy = ACTPolicy.from_pretrained(str(checkpoint_path))
        policy = policy.to(DEVICE)
        policy.eval()
        print("✅ Modèle chargé avec succès")
        return policy
    except Exception as e:
        print(f"❌ Erreur lors du chargement du modèle : {e}")
        return None


# ============================================
# IDENTIFICATION DES CAMÉRAS
# ============================================

def detect_cameras():
    """Détecte les caméras disponibles"""
    if not CV2_AVAILABLE:
        return []
    cameras = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cameras.append(i)
            cap.release()
    return cameras


def identification_cameras():
    """
    Identification interactive des caméras AVANT le démarrage.
    Affiche chaque caméra et demande à l'utilisateur de les identifier.
    Retourne (index_cam_top, index_cam_follower) ou (None, None) si échec.
    Code identique au script 8.
    """
    if not CV2_AVAILABLE:
        print("❌ OpenCV non disponible")
        return None, None

    print("\n" + "="*60)
    print("📷 IDENTIFICATION DES CAMÉRAS")
    print("="*60)

    # Détecter les caméras
    cameras = detect_cameras()
    print(f"\n🔍 Caméras détectées: {cameras}")

    if len(cameras) < 2:
        print(f"❌ Le modèle requiert 2 caméras. Seulement {len(cameras)} détectée(s).")
        print("   Vérifiez vos branchements USB.")
        return None, None

    print("\n📌 Vous allez voir chaque caméra tour à tour.")
    print("   Identifiez laquelle est la caméra GLOBALE (vue d'ensemble)")
    print("   et laquelle est sur la PINCE du follower.")
    print("\n   Appuyez sur une touche pour continuer...")
    input()

    cam_top_index = None
    cam_follower_index = None

    for idx in cameras[:2]:  # Tester les 2 premières
        print(f"\n🎥 Test caméra index {idx}...")
        cap = cv2.VideoCapture(idx)

        if not cap.isOpened():
            print(f"   ❌ Impossible d'ouvrir la caméra {idx}")
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG['camera_width'])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG['camera_height'])
        window_name = f"Camera {idx} - Identifiez cette camera"

        ret, frame = cap.read()
        if ret:
            cv2.putText(frame, f"Camera {idx}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, "Repondez dans le TERMINAL", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
            cv2.imshow(window_name, frame)
            cv2.waitKey(100)   # rendu de l'image figée uniquement (pas de capture de touche)

        print(f"   📺 Regardez la fenêtre '{window_name}'")
        print(f"   → Tapez G + Entrée si c'est la caméra GLOBALE (vue d'ensemble)")
        print(f"   → Tapez P + Entrée si c'est la caméra PINCE (sur le follower)")
        print(f"   → Tapez Q + Entrée pour passer")
        choix_cam = input("   Votre choix : ").strip().upper()

        if choix_cam == 'G':
            cam_top_index = idx
            print(f"   ✅ Caméra {idx} = {CAM_TOP} (globale)")
        elif choix_cam == 'P':
            cam_follower_index = idx
            print(f"   ✅ Caméra {idx} = {CAM_FOLLOWER} (pince)")
        elif choix_cam == 'Q':
            print(f"   ⏭️  Caméra {idx} passée")

        cap.release()
        cv2.destroyWindow(window_name)
        cv2.waitKey(100)

    cv2.destroyAllWindows()

    # Vérifier qu'on a bien les deux
    if cam_top_index is None and cam_follower_index is not None:
        # On a identifié follower, l'autre est top
        for idx in cameras[:2]:
            if idx != cam_follower_index:
                cam_top_index = idx
                print(f"\n   → Caméra {idx} assignée automatiquement comme {CAM_TOP}")
                break

    if cam_follower_index is None and cam_top_index is not None:
        # On a identifié top, l'autre est follower
        for idx in cameras[:2]:
            if idx != cam_top_index:
                cam_follower_index = idx
                print(f"\n   → Caméra {idx} assignée automatiquement comme {CAM_FOLLOWER}")
                break

    print("\n" + "-"*40)
    print("📷 Résultat de l'identification:")
    print(f"   {CAM_TOP} (globale): index {cam_top_index}")
    print(f"   {CAM_FOLLOWER} (pince): index {cam_follower_index}")
    print("-"*40)

    return cam_top_index, cam_follower_index


# ============================================
# CONNEXION DU BRAS FOLLOWER
# ============================================

def connexion_follower():
    """
    Connecte uniquement le bras Follower.
    Le Leader n'est pas nécessaire : le modèle le remplace.
    Retourne (port_handler, packet_handler, calib) ou (None, None, None) en cas d'erreur.
    """
    print("\n" + "=" * 60)
    print("🤖 CONNEXION DU BRAS FOLLOWER")
    print("=" * 60)
    print("\n   Le bras Leader n'est pas nécessaire pour le déploiement.")
    print("   Le modèle ACT remplace l'opérateur humain.\n")

    print("🔌 Branchez le bras FOLLOWER")
    input("   Appuyez sur Entrée quand branché...")

    time.sleep(1)
    ports = detect_ports()

    if not ports:
        print("❌ Aucun port USB détecté")
        print("   → Vérifiez le branchement et les permissions (groupe dialout)")
        return None, None, None

    follower_port = ports[0]
    print(f"\n✅ Port détecté : {follower_port}")

    port_handler   = PortHandler(follower_port)
    packet_handler = PacketHandler(1.0)

    if not port_handler.openPort():
        print(f"❌ Impossible d'ouvrir le port {follower_port}")
        return None, None, None

    if not port_handler.setBaudRate(CONFIG['baud_rate']):
        print("❌ Impossible de régler le baud rate")
        return None, None, None

    # Activer le couple sur tous les servos
    for i in range(1, 7):
        packet_handler.write1ByteTxRx(port_handler, i, 40, 1)

    calib = charger_calibration('follower')
    if calib:
        print("✅ Calibration Follower chargée")
    else:
        print("⚠️  Calibration Follower non trouvée — positions brutes utilisées (0-4095)")

    print("✅ Bras Follower connecté et prêt")
    return port_handler, packet_handler, calib


# ============================================
# THREAD DE LECTURE CLAVIER
# ============================================

def keyboard_thread():
    """Lit les touches au terminal sans bloquer (mode cbreak), comme le script 8.
    Capte P / R / Q et la touche Entrée (relance du modèle après un R).
    CTRL+C reste actif (ISIG conservé) pour l'arrêt d'urgence."""
    global stop_threads, cmd_queue
    try:
        import select
        import termios
        import tty
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            while not stop_threads:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1).upper()
                    if ch in ['P', 'R', 'Q']:
                        cmd_queue.put(ch)
                    elif ch in ['\r', '\n']:
                        cmd_queue.put('ENTER')
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    except Exception:
        # Fallback (terminal non interactif) : lecture ligne par ligne
        while not stop_threads:
            try:
                cmd = input().strip().upper()
                if cmd:
                    cmd_queue.put(cmd[0])
                else:
                    cmd_queue.put('ENTER')   # ligne vide = touche Entrée
            except Exception:
                pass


def get_command():
    """Retourne la prochaine commande clavier, ou None si la file est vide."""
    try:
        return cmd_queue.get_nowait()
    except queue.Empty:
        return None


# ============================================
# AFFICHAGE (thread principal uniquement)
# ============================================

def construire_affichage(frame_top, frame_follower, step, en_pause, derniere_action):
    """
    Compose l'image d'affichage :
    - Les deux caméras côte à côte
    - Overlay avec le numéro d'étape, l'état et les commandes
    """
    w = CONFIG['camera_width']
    h = CONFIG['camera_height']
    vide = np.zeros((h, w, 3), dtype=np.uint8)

    img_top = frame_top.copy()      if frame_top      is not None else vide.copy()
    img_fol = frame_follower.copy() if frame_follower is not None else vide.copy()

    if img_top.shape[:2] != (h, w):
        img_top = cv2.resize(img_top, (w, h))
    if img_fol.shape[:2] != (h, w):
        img_fol = cv2.resize(img_fol, (w, h))

    # Overlay caméra globale
    cv2.putText(img_top, "CAM GLOBALE", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(img_top, f"Step : {step}", (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # Overlay caméra pince
    cv2.putText(img_fol, "CAM PINCE", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    if derniere_action is not None:
        action_str = " ".join([f"{a:.0f}" for a in derniere_action])
        cv2.putText(img_fol, f"Action: {action_str}", (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 50), 1)

    # Bandeau PAUSE
    if en_pause:
        for img in [img_top, img_fol]:
            cv2.putText(img, "PAUSE", (img.shape[1] // 2 - 60, img.shape[0] // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 255), 3)

    # Barre de commandes en bas
    barre = np.zeros((40, w * 2, 3), dtype=np.uint8)
    cv2.putText(barre, "P = Pause/Reprendre   R = Repos + stop modele   Entree = Relancer   Q = Quitter",
                (10, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    display = np.vstack([np.hstack([img_top, img_fol]), barre])
    return display


# ============================================
# BOUCLE D'INFÉRENCE
# ============================================

def boucle_inference(policy, cam_top, cam_follower_cam, port_handler, packet_handler, calib):
    """
    Boucle principale d'inférence autonome.

    À chaque itération (~30 Hz) :
    1. Lit les frames des deux caméras
    2. Lit les positions actuelles des servos du Follower
    3. Construit l'observation pour le modèle ACT
    4. Demande au modèle de calculer l'action suivante
    5. Envoie les positions cibles au Follower
    6. Affiche les caméras avec overlay

    Le modèle gère en interne le "action chunking" (prédiction et file
    d'attente de N actions à la fois, pour une exécution plus fluide).
    """
    global stop_threads, urgence

    print("\n" + "=" * 60)
    print("🚀 DÉMARRAGE DE L'INFÉRENCE AUTONOME")
    print("=" * 60)
    print("\n   Le bras va bouger seul. Assurez-vous que la zone est dégagée.")
    print("\n   Contrôles (au clavier, dans le terminal) :")
    print("   P      : Pause / Reprendre")
    print("   R      : Retour repos + désactivation du modèle (fin d'essai)")
    print("   Entrée : Relancer le modèle pour un nouvel essai")
    print("   Q      : Quitter")
    print("\n   Appuyez sur Entrée pour démarrer...")
    input()

    en_pause        = False
    modele_actif    = True    # le modèle agit ; R le désactive (retour repos), Entrée le réactive
    step            = 0
    derniere_action = None
    premiere_action = True
    frequence       = 1.0 / CONFIG['fps']

    # Cache des dernières frames valides (évite un KeyError si une caméra saute une image)
    cache_frame_top = None
    cache_frame_fol = None

    # Réinitialiser l'état interne de la politique (vide la file d'actions)
    policy.reset()

    print("\n✅ Inférence en cours...\n")

    # Thread clavier : lecture des touches au terminal (P / R / Q), comme le script 8
    stop_threads = False
    kb_t = threading.Thread(target=keyboard_thread, daemon=True)
    kb_t.start()

    _window_created = False  # la fenêtre d'affichage n'est créée/dimensionnée qu'une seule fois

    try:
        while True:
            t_debut = time.time()

            # ---- Lecture des caméras avec cache ----
            lecture_top = (cam_top.async_read()
                           if cam_top and cam_top.is_connected else None)
            lecture_fol = (cam_follower_cam.async_read()
                           if cam_follower_cam and cam_follower_cam.is_connected else None)

            if lecture_top is not None:
                cache_frame_top = lecture_top
            if lecture_fol is not None:
                cache_frame_fol = lecture_fol

            frame_top = cache_frame_top
            frame_fol = cache_frame_fol

            # Masque appliqué à la globale → la même frame masquée part en affichage ET en inférence.
            # Critique pour C1 (cohérence entraînement↔déploiement) : si le 8 a enregistré masqué,
            # le 12 doit masquer aussi avant que la politique voie l'image.
            if frame_top is not None and _MASK_GLOBALE_IMG is not None:
                frame_top = cv2.bitwise_and(frame_top, frame_top, mask=_MASK_GLOBALE_IMG)

            # Si les caches sont encore vides au tout début, attendre
            if cam_top and cam_top.is_connected and cache_frame_top is None:
                time.sleep(frequence)
                continue
            if cam_follower_cam and cam_follower_cam.is_connected and cache_frame_fol is None:
                time.sleep(frequence)
                continue

            # ---- Affichage (thread principal obligatoire pour cv2.imshow) ----
            if CV2_AVAILABLE:
                display = construire_affichage(frame_top, frame_fol,
                                               step, en_pause, derniere_action)
                # Fenêtre redimensionnable + taille ×1.5 (1920×540) — créée/dimensionnée une seule fois
                if not _window_created:
                    cv2.namedWindow("SEM — Déploiement ACT (Script 12)", cv2.WINDOW_NORMAL)
                    cv2.resizeWindow("SEM — Déploiement ACT (Script 12)", 1920, 540)
                    _window_created = True
                cv2.imshow("SEM — Déploiement ACT (Script 12)", display)
                cv2.waitKey(1)   # pompe d'événements GUI uniquement (rafraîchit la fenêtre)

            # ---- Commandes clavier (lues au terminal, comme le script 8) ----
            cmd = get_command()
            if cmd == 'Q':
                print("\n🛑 Arrêt demandé (Q)")
                break
            elif cmd == 'P':
                en_pause = not en_pause
                print(f"\n{'⏸️  PAUSE' if en_pause else '▶️  REPRISE'}")
            elif cmd == 'R':
                # Fin d'essai : retour repos (non-IA) PUIS désactivation du modèle.
                # Sans cette désactivation, la boucle relancerait l'inférence dès l'itération
                # suivante (depuis le repos, qui est le point de départ des démos) → mouvements
                # erratiques. On attend donc un relancement explicite (Entrée).
                aller_position_repos(packet_handler, port_handler, calib)
                policy.reset()
                step            = 0
                derniere_action = None
                premiere_action = True
                en_pause        = False   # repart d'un état propre (annule une éventuelle pause)
                modele_actif    = False   # modèle désactivé jusqu'au prochain Entrée
                print("\n✅ Retour au repos — modèle DÉSACTIVÉ.")
                print("   Replacez la pièce, puis appuyez sur Entrée pour relancer un essai.")
            elif cmd == 'ENTER':
                if not modele_actif:
                    modele_actif    = True
                    premiere_action = True   # redémarrage en douceur (interpolation 1 s)
                    print("\n▶️  Modèle RÉACTIVÉ — nouvel essai en cours.")

            if en_pause:
                time.sleep(frequence)
                continue

            # Modèle désactivé (après un R) : aucune action envoyée, le bras reste au repos.
            # L'affichage continue de tourner et le clavier reste actif (Entrée pour relancer).
            if not modele_actif:
                time.sleep(frequence)
                continue

            # ---- Construction de l'observation ----
            obs = {}

            if frame_top is not None:
                obs[f"observation.images.{CAM_TOP}"] = frame_vers_tensor(frame_top)

            if frame_fol is not None:
                obs[f"observation.images.{CAM_FOLLOWER}"] = frame_vers_tensor(frame_fol)

            # Positions des servos du Follower : liste [s1, s2, s3, s4, s5, s6]
            positions   = lire_positions(packet_handler, port_handler)
            state_list  = [float(positions[i]) for i in range(1, 7)]
            state_tensor = torch.tensor([state_list], dtype=torch.float32).to(DEVICE)
            obs["observation.state"] = state_tensor

            # ---- Inférence optimisée ----
            with torch.inference_mode():
                action = policy.select_action(obs)

            # ---- Application des actions aux servos ----
            action_np       = action.cpu().numpy().flatten()
            derniere_action = action_np

            if premiere_action:
                # Interpolation fluide sur 1 seconde pour éviter un "coup de fouet" initial
                positions_depart = lire_positions(packet_handler, port_handler)
                duree_interp = 1.0
                steps_interp = int(duree_interp * 50)
                for s in range(steps_interp + 1):
                    t = s / steps_interp
                    smooth = (1 - math.cos(t * math.pi)) / 2
                    for i, servo_id in enumerate(range(1, 7)):
                        if i < len(action_np):
                            depart  = float(positions_depart[servo_id])
                            cible   = float(action_np[i])
                            new_pos = int(depart + (cible - depart) * smooth)
                            ecrire_position(packet_handler, port_handler, servo_id, new_pos)
                    time.sleep(duree_interp / steps_interp)
                premiere_action = False
            else:
                for i, servo_id in enumerate(range(1, 7)):
                    if i < len(action_np):
                        ecrire_position(packet_handler, port_handler, servo_id, action_np[i])

            step += 1

            # ---- Régulation de la fréquence ----
            elapsed    = time.time() - t_debut
            sleep_time = frequence - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\n🛑 ARRÊT D'URGENCE (CTRL+C) — coupure immédiate du couple.")
        for i in range(1, 7):
            packet_handler.write1ByteTxRx(port_handler, i, 40, 0)
        urgence = True

    finally:
        stop_threads = True   # arrête le thread clavier (restaure le terminal)
        if CV2_AVAILABLE:
            cv2.destroyAllWindows()
        print(f"\n📊 Étapes d'inférence exécutées : {step}")


# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main():
    global urgence
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     SEM — DÉPLOIEMENT MODÈLE ACT (Script 12)                        ║
║     Service Écoles-Médias (SEM) - DIP Genève                        ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    print(f"🖥️  Device     : {DEVICE}")
    print(f"📂 Modèles    : {TRAIN_OUTPUT_DIR}")
    print(f"📷 Résolution : {CONFIG['camera_width']}×{CONFIG['camera_height']} @ {CONFIG['fps']} fps")

    # 1. Sélection du checkpoint
    checkpoint_path = selectionner_checkpoint()
    if checkpoint_path is None:
        sys.exit(1)

    # 2. Chargement du modèle ACT
    policy = charger_modele(checkpoint_path)
    if policy is None:
        sys.exit(1)

    # 3. Identification des caméras
    idx_top, idx_follower = identification_cameras()
    if idx_top is None or idx_follower is None:
        print("\n❌ Déploiement annulé : les deux caméras (globale + pince) sont requises.")
        sys.exit(1)

    # Réglages caméra (exposition / balance des blancs) — un réglage par caméra, comme le script 8.
    # capturer_reglages_camera affiche les réglages enregistrés et propose [Entrée] garder / [R] refaire
    # (guvcview + papier blanc, à recaler sous la lumière du moment). À faire AVANT d'ouvrir les caméras
    # avec cv2, car guvcview a besoin du périphérique libre.
    if not CAMERA_LOCK_AVAILABLE:
        print("\n❌ Module de configuration caméra (SEM_8_camera_config.py) indisponible.")
        print(f"   Erreur : {CAMERA_LOCK_IMPORT_ERROR}")
        print("   → Impossible de régler puis verrouiller les caméras.")
        print("   → Déploiement annulé pour éviter des images en mode auto (incohérence avec l'entraînement).")
        print("   → Vérifiez que SEM_8_camera_config.py est dans le même dossier que ce script.")
        sys.exit(1)

    capturer_reglages_camera(f"/dev/video{idx_top}", CAM_TOP, titre="GLOBALE (cam_top)   [1/2]")
    capturer_reglages_camera(f"/dev/video{idx_follower}", CAM_FOLLOWER, titre="PINCE (cam_follower)   [2/2]")

    # 3bis. Chargement du masque globale (créé par le script 7, partagé avec le 8).
    # Si absent → message + inférence avec image brute (pas de crash, mais cohérence rompue avec l'entraînement).
    global _MASK_GLOBALE_IMG
    mask_pts = charger_masque_globale()
    if mask_pts:
        _MASK_GLOBALE_IMG = construire_mask_image(
            mask_pts, CONFIG['camera_width'], CONFIG['camera_height']
        )
        print(f"\n✅ Masque globale actif ({len(mask_pts)} points)")
    else:
        print("\n⚠️  Aucun masque trouvé — l'inférence utilisera l'image brute.")
        print("   Si le modèle a été entraîné avec un masque, la cohérence sera rompue.")

    # 4. Connexion des caméras (ThreadedCamera)
    cam_top          = None
    cam_follower_cam = None

    def _abort_cameras(code=1):
        """Sortie propre pendant la phase caméra : libère les caméras déjà ouvertes.
        À ce stade le bras Follower n'est pas encore connecté → aucun moteur sous tension."""
        if cam_top:
            cam_top.disconnect()
        if cam_follower_cam:
            cam_follower_cam.disconnect()
        if CV2_AVAILABLE:
            cv2.destroyAllWindows()
        sys.exit(code)

    if CV2_AVAILABLE:
        if idx_top is not None:
            cam_top = ThreadedCamera(
                idx_top, CAM_TOP,
                CONFIG['camera_width'], CONFIG['camera_height'], CONFIG['fps']
            )
            # Point A : arrêt si la connexion physique échoue
            if not cam_top.connect() or not cam_top.is_connected:
                print("\n❌ Caméra globale non connectée — arrêt.")
                _abort_cameras(1)
            # Point B : arrêt si la résolution réelle n'est pas celle attendue
            frame_test = cam_top.async_read()
            if frame_test is not None and frame_test.shape[:2] != (CONFIG['camera_height'], CONFIG['camera_width']):
                print(f"\n❌ Résolution caméra globale incorrecte : {frame_test.shape[:2]}")
                print(f"   Attendu : {(CONFIG['camera_height'], CONFIG['camera_width'])}")
                _abort_cameras(1)

        if idx_follower is not None:
            cam_follower_cam = ThreadedCamera(
                idx_follower, CAM_FOLLOWER,
                CONFIG['camera_width'], CONFIG['camera_height'], CONFIG['fps']
            )
            # Point A : arrêt si la connexion physique échoue
            if not cam_follower_cam.connect() or not cam_follower_cam.is_connected:
                print("\n❌ Caméra pince non connectée — arrêt.")
                _abort_cameras(1)
            # Point B : arrêt si la résolution réelle n'est pas celle attendue
            frame_test = cam_follower_cam.async_read()
            if frame_test is not None and frame_test.shape[:2] != (CONFIG['camera_height'], CONFIG['camera_width']):
                print(f"\n❌ Résolution caméra pince incorrecte : {frame_test.shape[:2]}")
                print(f"   Attendu : {(CONFIG['camera_height'], CONFIG['camera_width'])}")
                _abort_cameras(1)

        # 4bis. Verrouillage matériel des caméras (exposition / balance des blancs / gain).
        # Applique les réglages enregistrés par le script 8 dans camera_settings.json.
        # CRITIQUE pour la cohérence entraînement↔déploiement : le modèle a été entraîné sur
        # des images à réglages verrouillés. Sans ce verrouillage, l'auto-exposition / auto-WB
        # ferait dériver la luminosité et la colorimétrie au déploiement.
        # Garde-fou : si le module n'a pas pu être importé, on ne peut PAS appliquer ces
        # réglages → arrêt propre (fail closed) plutôt que déployer avec des caméras en mode auto.
        if not CAMERA_LOCK_AVAILABLE:
            print("\n❌ Module de configuration caméra (SEM_8_camera_config.py) indisponible.")
            print(f"   Erreur : {CAMERA_LOCK_IMPORT_ERROR}")
            print("   → Impossible d'appliquer les réglages caméra enregistrés par le script 8.")
            print("   → Déploiement annulé pour éviter une incohérence entraînement↔déploiement.")
            print("   → Vérifiez que SEM_8_camera_config.py est dans le même dossier que ce script.")
            _abort_cameras(1)

        ok_lock = True
        ok_lock &= verrouiller_camera(f"/dev/video{idx_top}", CAM_TOP)
        ok_lock &= verrouiller_camera(f"/dev/video{idx_follower}", CAM_FOLLOWER)
        if not ok_lock:
            reponse = input("\n⚠️  Verrouillage caméra incomplet. Continuer quand même ? [O/N] : ").strip().upper()
            if reponse != 'O':
                _abort_cameras(1)

    # 5. Connexion du bras Follower
    port_handler, packet_handler, calib = connexion_follower()
    if port_handler is None:
        if cam_top:
            cam_top.disconnect()
        if cam_follower_cam:
            cam_follower_cam.disconnect()
        sys.exit(1)

    # 6. Position repos initiale + boucle d'inférence, sous protection CTRL+C
    try:
        # Position repos initiale (sécurité avant inférence)
        aller_position_repos(packet_handler, port_handler, calib)

        # Boucle d'inférence
        boucle_inference(
            policy,
            cam_top, cam_follower_cam,
            port_handler, packet_handler, calib
        )

    except KeyboardInterrupt:
        # CTRL+C pendant le repos initial (la boucle d'inférence gère le sien en interne) :
        # coupure immédiate du couple, pas de retour repos.
        print("\n\n🛑 ARRÊT D'URGENCE (CTRL+C) — coupure immédiate du couple.")
        for i in range(1, 7):
            packet_handler.write1ByteTxRx(port_handler, i, 40, 0)
        urgence = True

    finally:
        # 8. Nettoyage
        print("\n🧹 Nettoyage...")

        if urgence:
            # Arrêt d'urgence (CTRL+C) : couple déjà coupé dans la boucle.
            # AUCUN retour repos — le bras peut être coincé ou en butée.
            port_handler.closePort()
            if cam_top:
                cam_top.disconnect()
            if cam_follower_cam:
                cam_follower_cam.disconnect()
            if CV2_AVAILABLE:
                cv2.destroyAllWindows()
            print("\n✅ Arrêt d'urgence terminé (aucun retour repos).")
        else:
            # Retour position repos (séquence sûre)
            aller_position_repos(packet_handler, port_handler, calib)

            # ⚠️ Tenir le robot avant de désactiver le couple
            print("\n⚠️  Tenez le bras — désactivation du couple dans 3 secondes...")
            time.sleep(3)

            # Désactiver le couple sur tous les servos
            for i in range(1, 7):
                packet_handler.write1ByteTxRx(port_handler, i, 40, 0)

            # Fermer le port série
            port_handler.closePort()

            # Fermer les caméras
            if cam_top:
                cam_top.disconnect()
            if cam_follower_cam:
                cam_follower_cam.disconnect()

            if CV2_AVAILABLE:
                cv2.destroyAllWindows()

            print("\n✅ Script 12 terminé proprement.")

        print("━" * 60)
        print(f"   Checkpoint utilisé : {checkpoint_path.parent.name}")
        print("━" * 60)


if __name__ == "__main__":
    main()
