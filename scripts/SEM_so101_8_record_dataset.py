#!/usr/bin/env python3
"""
Script SEM_so101_8_record_dataset.py
Service Écoles-Médias (SEM) - DIP Genève

ENREGISTREMENT DE DATASET POUR APPRENTISSAGE PAR IMITATION (2 CAMÉRAS)
======================================================================

Architecture inspirée de LeRobot : threads de lecture dédiés par caméra.
Boucle d'affichage sécurisée dans le thread principal.

Tâche : Prendre un cube à l'une des 5 positions et le déposer dans la boîte
"""

import os
import sys
import json
import time
import math
import threading
import queue
import numpy as np
from datetime import datetime
from pathlib import Path

# Module de configuration caméra (verrouillage + capture des réglages).
# Import protégé : si le module est absent, mal placé ou cassé, on le signalera par un
# message clair + arrêt propre plus bas, au lieu d'un traceback illisible au démarrage.
try:
    from SEM_8_camera_config import verrouiller_camera, capturer_reglages_camera
    CAMERA_LOCK_AVAILABLE = True
    CAMERA_LOCK_IMPORT_ERROR = None
except Exception as e:
    verrouiller_camera = None
    capturer_reglages_camera = None
    CAMERA_LOCK_AVAILABLE = False
    CAMERA_LOCK_IMPORT_ERROR = e

# Supprimer les messages d'erreur OpenCV
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"

# Auto-activation de l'environnement lerobot si nécessaire
try:
    sys.path.append(os.path.expanduser('~/lerobot'))
    from dynamixel_sdk import *
    import cv2
    cv2.setNumThreads(1)
    CV2_AVAILABLE = True
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    # Tenter l'auto-activation
    import subprocess
    lerobot_python = os.path.expanduser("~/miniconda3/envs/lerobot/bin/python3")
    if os.path.exists(lerobot_python):
        print("\n🔧 Activation automatique de l'environnement lerobot...")
        print("✅ Relancement avec lerobot...")
        subprocess.call([lerobot_python] + sys.argv)
        sys.exit(0)
    else:
        # On est dans lerobot mais il manque des modules optionnels
        try:
            from dynamixel_sdk import *
        except ImportError:
            print("❌ Environnement lerobot non trouvé!")
            print("Solution: conda activate lerobot")
            sys.exit(1)
        try:
            import cv2
            cv2.setNumThreads(1)
            CV2_AVAILABLE = True
        except ImportError:
            CV2_AVAILABLE = False
            print("⚠️  OpenCV non disponible - enregistrement sans vidéo")
        try:
            import pandas as pd
            PANDAS_AVAILABLE = True
        except ImportError:
            PANDAS_AVAILABLE = False
            print("⚠️  Pandas non disponible - sauvegarde en JSON")

# ============================================
# CONFIGURATION
# ============================================

# Les 5 positions de cube
POSITIONS = {
    1: {"nom": "Centre", "description": "Position centrale"},
    2: {"nom": "Bas", "description": "Position proche du robot"},
    3: {"nom": "Haut", "description": "Position éloignée du robot"},
    4: {"nom": "Gauche", "description": "Position gauche (boîte en dessous)"},
    5: {"nom": "Droite", "description": "Position droite (boîte en dessous)"},
}

CONFIG = {
    'fps': 30,
    'episodes_per_position': 10,
    'camera_width': 640,
    'camera_height': 360, # Gardé en 360p comme dans la V1 pour les perfs, modifiable si besoin
}

# Noms des caméras (comme LeRobot)
CAM_TOP = "cam_top"
CAM_FOLLOWER = "cam_follower"

# Variables globales
stop_threads = False
pause_teleop = False
cmd_queue = queue.Queue()

# Références caméras pour l'affichage dans le thread principal
_display_cam_top = None
_display_cam_follower = None
_MASK_GLOBALE_IMG = None  # image binaire du masque globale (None tant que le fichier n'est pas chargé)
_window_created = False  # la fenêtre d'affichage n'est créée/dimensionnée qu'une seule fois

def refresh_display():
    """Rafraîchit l'affichage des caméras dans UNE fenêtre combinée (thread principal)."""
    global _window_created
    if not CV2_AVAILABLE:
        return
    w = CONFIG['camera_width']
    h = CONFIG['camera_height']
    frame_top = _display_cam_top.async_read() if (_display_cam_top and _display_cam_top.is_connected) else None
    frame_fol = _display_cam_follower.async_read() if (_display_cam_follower and _display_cam_follower.is_connected) else None
    # Masque appliqué uniquement à la globale, avant l'étiquette → on voit en direct ce qui sera enregistré
    if frame_top is not None and _MASK_GLOBALE_IMG is not None:
        frame_top = cv2.bitwise_and(frame_top, frame_top, mask=_MASK_GLOBALE_IMG)
    images = []
    for frame, label in [(frame_top, "CAM GLOBALE"), (frame_fol, "CAM PINCE")]:
        if frame is None:
            continue
        if frame.shape[:2] != (h, w):
            frame = cv2.resize(frame, (w, h))
        cv2.putText(frame, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        images.append(frame)
    if not images:
        time.sleep(0.03)
        return
    display = images[0] if len(images) == 1 else cv2.hconcat(images)
    # Fenêtre redimensionnable + taille ×1.5 (1920×540) — créée/dimensionnée une seule fois
    if not _window_created:
        cv2.namedWindow('Cameras SO-ARM 101', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Cameras SO-ARM 101', 1920, 540)
        _window_created = True
    cv2.imshow('Cameras SO-ARM 101', display)
    cv2.waitKey(30)  # throttle l'affichage à ~33 Hz (évite la saturation CPU des boucles menu)

# ============================================
# CLASSE THREADED CAMERA (architecture LeRobot)
# ============================================

class ThreadedCamera:
    def __init__(self, camera_index, name, width=640, height=480, fps=30):
        self.camera_index = camera_index
        self.name = name
        self.width = width
        self.height = height
        self.fps = fps

        self.camera = None
        self.is_connected = False
        self.thread = None
        self.stop_event = None
        self.current_frame = None
        self.frame_lock = threading.Lock()

    def connect(self):
        if self.is_connected:
            return True
        if not CV2_AVAILABLE:
            return False

        self.camera = cv2.VideoCapture(self.camera_index)
        if not self.camera.isOpened():
            print(f"❌ Impossible d'ouvrir {self.name} (index {self.camera_index})")
            return False

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.camera.set(cv2.CAP_PROP_FPS, self.fps)

        # Warmup : lire 5 frames pour vider le buffer matériel (les premières sont souvent
        # corrompues) et garder la dernière valide. Aligné sur le connect() du script 12.
        for _ in range(5):
            ret, frame = self.camera.read()
            if ret:
                self.current_frame = frame
            time.sleep(0.1)

        # Refuser la connexion si aucune image valide n'a été obtenue (sinon is_connected
        # serait True sans frame, et le contrôle de résolution serait silencieusement sauté).
        if self.current_frame is None:
            print(f"❌ La caméra {self.name} ne renvoie aucune image valide.")
            self.camera.release()
            return False

        self.is_connected = True
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        print(f"   ✅ {self.name} connectée (index {self.camera_index})")
        return True

    def _read_loop(self):
        while not self.stop_event.is_set():
            if self.camera and self.camera.isOpened():
                ret, frame = self.camera.read()
                if ret:
                    with self.frame_lock:
                        self.current_frame = frame
            time.sleep(0.001)

    def async_read(self):
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None

    def disconnect(self):
        if self.thread is not None:
            self.stop_event.set()
            self.thread.join(timeout=1.0)
            self.thread = None
            self.stop_event = None

        if self.camera is not None:
            self.camera.release()
            self.camera = None

        self.is_connected = False
        self.current_frame = None

def detect_cameras():
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
    if not CV2_AVAILABLE:
        print("❌ OpenCV non disponible")
        return None, None

    print("\n" + "="*60)
    print("📷 IDENTIFICATION DES CAMÉRAS")
    print("="*60)
    cameras = detect_cameras()
    print(f"\n🔍 Caméras détectées: {cameras}")

    if len(cameras) < 2:
        print("❌ Moins de 2 caméras détectées!")
        if len(cameras) == 1:
            print(f"   Une seule caméra à l'index {cameras[0]}")
            return cameras[0], None
        return None, None

    print("\n📌 Vous allez voir chaque caméra tour à tour.")
    print("   Identifiez laquelle est la caméra GLOBALE (vue d'ensemble)")
    print("   et laquelle est sur la PINCE du follower.")
    print("\n   Appuyez sur une touche pour continuer...")
    input()

    cam_top_index = None
    cam_follower_index = None

    for idx in cameras[:2]:
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
            cv2.waitKey(100)

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

    if cam_top_index is None and cam_follower_index is not None:
        for idx in cameras[:2]:
            if idx != cam_follower_index:
                cam_top_index = idx
                print(f"\n   → Caméra {idx} assignée automatiquement comme {CAM_TOP}")
                break

    if cam_follower_index is None and cam_top_index is not None:
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
    BAUDRATE = 1000000
    ports = []
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']:
        if not os.path.exists(port):
            continue
        ph = PortHandler(port)
        pk = PacketHandler(1.0)
        try:
            if ph.openPort() and ph.setBaudRate(BAUDRATE):
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
    calib_file = os.path.expanduser(f"~/lerobot/calibration/{robot_type}_calibration.json")
    if os.path.exists(calib_file):
        with open(calib_file, 'r') as f:
            return json.load(f)
    return None

def charger_config_teleoperation(mode):
    config_file = os.path.expanduser(f"~/lerobot/calibration/teleoperation_config_{mode}.json")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            data = json.load(f)
            return data.get('servos_miroir', [])
    return []

def mouvement_fluide(packet, port, servo, debut, fin, duree=1.5):
    steps = int(duree * 50)
    for i in range(steps + 1):
        t = i / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        pos = int(debut + (fin - debut) * smooth)
        packet.write2ByteTxRx(port, servo, 42, pos)
        time.sleep(duree / steps)

def mapper_position(pos_leader, servo_id, calib_leader, calib_follower, servos_miroir):
    if calib_leader and f"servo_{servo_id}" in calib_leader:
        min_l = calib_leader[f"servo_{servo_id}"]["min"]
        max_l = calib_leader[f"servo_{servo_id}"]["max"]
    else:
        min_l, max_l = 0, 4095

    if calib_follower and f"servo_{servo_id}" in calib_follower:
        min_f = calib_follower[f"servo_{servo_id}"]["min"]
        max_f = calib_follower[f"servo_{servo_id}"]["max"]
    else:
        min_f, max_f = 0, 4095

    ratio = (pos_leader - min_l) / (max_l - min_l) if max_l > min_l else 0.5
    ratio = max(0, min(1, ratio))

    if servo_id in servos_miroir:
        ratio = 1 - ratio

    pos_follower = int(min_f + ratio * (max_f - min_f))
    return max(min_f, min(max_f, pos_follower))

# ============================================
# IDENTIFICATION & POSITIONNEMENT
# ============================================

def test_connexion_fluide(packet, port, robot_name, calib):
    print(f"\n  🔄 Test de connexion {robot_name}...")
    packet.write1ByteTxRx(port, 6, 40, 1)

    if calib and 'servo_6' in calib:
        centre = calib['servo_6']['center']
        min_val = calib['servo_6']['min']
        max_val = calib['servo_6']['max']

        amplitude = max_val - min_val
        pos_25 = int(min_val + amplitude * 0.25)
        pos_75 = int(min_val + amplitude * 0.75)

        pos_actuelle, _, _ = packet.read2ByteTxRx(port, 6, 56)

        print("     → Centre...")
        mouvement_fluide(packet, port, 6, pos_actuelle, centre, 1.0)
        print("     → Fermé (45°)...")
        mouvement_fluide(packet, port, 6, centre, pos_25, 0.8)
        print("     → Ouvert (90°)...")
        mouvement_fluide(packet, port, 6, pos_25, pos_75, 1.2)
        print("     → Centre...")
        mouvement_fluide(packet, port, 6, pos_75, centre, 0.8)
    else:
        packet.write2ByteTxRx(port, 6, 42, 2048)
        time.sleep(1)
        packet.write2ByteTxRx(port, 6, 42, 1500)
        time.sleep(1)
        packet.write2ByteTxRx(port, 6, 42, 2500)
        time.sleep(1)
        packet.write2ByteTxRx(port, 6, 42, 2048)
    print(f"  ✅ {robot_name} connecté et testé")

def identification_guidee():
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     IDENTIFICATION LEADER/FOLLOWER                                   ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    ports = detect_ports()
    while len(ports) > 0:
        print(f"⚠️  Débranchez tous les robots")
        input("   Entrée quand fait...")
        ports = detect_ports()

    print("\n🔌 Branchez le LEADER")
    input("   Entrée quand branché...")
    time.sleep(1)
    ports = detect_ports()
    if len(ports) == 0:
        print("❌ Aucun port détecté")
        return None, None, None, None, None, None
    leader_port = ports[0]
    print(f"✅ LEADER détecté sur {leader_port}")

    lp = PortHandler(leader_port)
    lk = PacketHandler(1.0)
    if not lp.openPort() or not lp.setBaudRate(1000000):
        print("❌ Erreur connexion Leader")
        return None, None, None, None, None, None

    calib_l = charger_calibration('leader')
    test_connexion_fluide(lk, lp, "LEADER", calib_l)

    if input("\nPince du LEADER bougée? [O/N]: ").upper() != 'O':
        return None, None, None, None, None, None

    print("\n🔌 Branchez le FOLLOWER (gardez Leader branché)")
    input("   Entrée quand branché...")
    time.sleep(1)
    ports = detect_ports()
    if len(ports) < 2:
        print("❌ Follower non détecté")
        return None, None, None, None, None, None
    follower_port = ports[1] if ports[0] == leader_port else ports[0]
    print(f"✅ FOLLOWER détecté sur {follower_port}")

    fp = PortHandler(follower_port)
    fk = PacketHandler(1.0)
    if not fp.openPort() or not fp.setBaudRate(1000000):
        print("❌ Erreur connexion Follower")
        return None, None, None, None, None, None

    calib_f = charger_calibration('follower')
    test_connexion_fluide(fk, fp, "FOLLOWER", calib_f)

    if input("\nPince du FOLLOWER bougée? [O/N]: ").upper() != 'O':
        return None, None, None, None, None, None

    print("\n✅ Identification réussie!")
    return lp, lk, fp, fk, calib_l, calib_f

def centrage_parallele(lk, lp, fk, fp, calib_l, calib_f):
    print("\n🎯 Centrage simultané des robots...")
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 1)
        fk.write1ByteTxRx(fp, i, 40, 1)

    pos_l = {}
    pos_f = {}
    for i in range(1, 7):
        pos_l[i], _, _ = lk.read2ByteTxRx(lp, i, 56)
        pos_f[i], _, _ = fk.read2ByteTxRx(fp, i, 56)

    duree = 2.0
    steps = int(duree * 50)
    for step in range(steps + 1):
        t = step / steps
        smooth = (1 - math.cos(t * math.pi)) / 2

        for i in range(1, 7):
            centre_l = calib_l[f'servo_{i}']['center'] if calib_l else 2048
            new_pos_l = int(pos_l[i] + (centre_l - pos_l[i]) * smooth)
            lk.write2ByteTxRx(lp, i, 42, new_pos_l)

            centre_f = calib_f[f'servo_{i}']['center'] if calib_f else 2048
            new_pos_f = int(pos_f[i] + (centre_f - pos_f[i]) * smooth)
            fk.write2ByteTxRx(fp, i, 42, new_pos_f)

        time.sleep(duree / steps)
    print("✅ Robots centrés")

# Fichier externe centralisant la position repos (partagé entre tous les scripts)
REPOS_FILE = os.path.expanduser("~/lerobot/calibration/repos_position.json")

# Fichier externe du masque de zone utile (créé par le script 7, partagé avec le 12)
MASK_FILE = os.path.expanduser("~/lerobot/calibration/camera_mask.json")


def charger_masque_globale():
    """Lit MASK_FILE (créé par le script 7) et renvoie la liste des points
    du polygone, ou None si le fichier est absent ou invalide."""
    if not os.path.exists(MASK_FILE):
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
    """Charge la position repos (% par servo) depuis le fichier externe.
    Fallback sur les valeurs par défaut si le fichier est absent ou invalide."""
    defaut = {1: 50, 2: 10, 3: 88, 4: 76, 5: 50, 6: 11}
    if os.path.exists(REPOS_FILE):
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

def _est_en_repos_1robot(packet, port, calib, repos_pct, tolerance_pct=5):
    """Vrai si le robot est actuellement proche de la position repos (tous les servos)."""
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

def mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, servos, duree=2.0):
    """Déplace les servos indiqués sur Leader ET Follower simultanément vers cibles_pct (%)."""
    pos_l, pos_f = {}, {}
    for s in servos:
        pos_l[s], _, _ = lk.read2ByteTxRx(lp, s, 56)
        pos_f[s], _, _ = fk.read2ByteTxRx(fp, s, 56)
    cible_l, cible_f = {}, {}
    for s in servos:
        cible_l[s] = _cible_ticks(cl, s, cibles_pct[s])
        cible_f[s] = _cible_ticks(cf, s, cibles_pct[s])
    steps = 100
    for step in range(steps + 1):
        t = step / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        for s in servos:
            lk.write2ByteTxRx(lp, s, 42, int(pos_l[s] + (cible_l[s] - pos_l[s]) * smooth))
            fk.write2ByteTxRx(fp, s, 42, int(pos_f[s] + (cible_f[s] - pos_f[s]) * smooth))
        time.sleep(duree / steps)

def aller_a_position_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, duree=2.0):
    """Déplace Leader ET Follower vers cibles_pct (%) en respectant les contraintes
    physiques (séquence sûre), appliquée IDENTIQUEMENT aux deux robots :
      Phase 0 (par robot) : si servo 4 > 2700 et robot pas en repos, lever le bras
                            (servo 2 -> min(actuel, 1027)) pour dégager la pince du sol
      Phase 1 : servo 4 -> 20% (pince en l'air)
      Phase 2 : servos 1,2,3,5,6 -> cibles, en parallèle
      Phase 3 : servo 4 -> cible finale
    """
    # Activer tous les servos
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 1)
        fk.write1ByteTxRx(fp, i, 40, 1)

    repos_pct = charger_repos_pct()

    # --- Phase 0 (conditionnelle, par robot) : levée d'épaule EN PARALLÈLE sur les deux robots ---
    pos4_l, _, _ = lk.read2ByteTxRx(lp, 4, 56)
    pos4_f, _, _ = fk.read2ByteTxRx(fp, 4, 56)
    besoin_l = pos4_l > 2700 and not _est_en_repos_1robot(lk, lp, cl, repos_pct)
    besoin_f = pos4_f > 2700 and not _est_en_repos_1robot(fk, fp, cf, repos_pct)
    if besoin_l or besoin_f:
        deb_l, _, _ = lk.read2ByteTxRx(lp, 2, 56)
        deb_f, _, _ = fk.read2ByteTxRx(fp, 2, 56)
        fin_l = min(deb_l, 1027) if besoin_l else deb_l
        fin_f = min(deb_f, 1027) if besoin_f else deb_f
        steps = int(duree * 50)
        for step in range(steps + 1):
            t = step / steps
            smooth = (1 - math.cos(t * math.pi)) / 2
            lk.write2ByteTxRx(lp, 2, 42, int(deb_l + (fin_l - deb_l) * smooth))
            fk.write2ByteTxRx(fp, 2, 42, int(deb_f + (fin_f - deb_f) * smooth))
            time.sleep(duree / steps)

    # --- Phase 1 : servo 4 -> 20% sur les deux robots ---
    mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, {4: 20}, [4], duree)

    # --- Phase 2 : servos 1,2,3,5,6 en parallèle ---
    mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, [1, 2, 3, 5, 6], duree)

    # --- Phase 3 : servo 4 -> cible finale ---
    mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, [4], duree)

def position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f):
    """Met les deux robots en position repos (repos partagé, séquence sûre)."""
    print("\n🏁 Position repos simultanée...")

    # Repos lu depuis le fichier unique partagé, atteint via la séquence sûre
    # (servo 4 en l'air d'abord, etc.) appliquée à l'identique aux deux robots
    repos_pct = charger_repos_pct()
    aller_a_position_2robots(lk, lp, fk, fp, calib_l, calib_f, repos_pct, duree=2.0)

    print("✅ Position repos atteinte (robot replié)")


# ============================================
# CLASSE DATASET RECORDER
# ============================================

class DatasetRecorder:
    def __init__(self, base_name="so101_pick_place"):
        self.base_name = base_name
        self.base_path = Path(os.path.expanduser(
            f"~/.cache/huggingface/lerobot/local/{base_name}"
        ))
        self.episodes_par_position = {i: 0 for i in range(1, 6)}
        self._charger_etat()
        self.current_episode_data = []
        self.current_frames_top = []
        self.current_frames_follower = []
        self.episode_start_time = None
        self.is_recording = False

    def _charger_etat(self):
        state_file = self.base_path / "sem_state.json"
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
                self.episodes_par_position = state.get('episodes_par_position',
                                                        {str(i): 0 for i in range(1, 6)})
                self.episodes_par_position = {int(k): v for k, v in self.episodes_par_position.items()}

    def _sauvegarder_etat(self):
        self.base_path.mkdir(parents=True, exist_ok=True)
        state_file = self.base_path / "sem_state.json"
        with open(state_file, 'w') as f:
            json.dump({
                'episodes_par_position': self.episodes_par_position,
                'last_update': datetime.now().isoformat()
            }, f, indent=2)

    def get_dataset_path(self, position_id):
        pos_name = POSITIONS[position_id]['nom'].lower()
        return self.base_path / f"position_{position_id}_{pos_name}"

    def start_episode(self, position_id):
        self.current_position = position_id
        self.current_episode_data = []
        self.current_frames_top = []
        self.current_frames_follower = []
        self.episode_start_time = time.time()
        self.is_recording = True
        episode_num = self.episodes_par_position[position_id] + 1
        print(f"\n🔴 ENREGISTREMENT - Position {position_id} ({POSITIONS[position_id]['nom']}) - Épisode {episode_num}")

    def record_frame(self, positions_follower, action_cible, frame_top=None, frame_follower=None):
        if not self.is_recording:
            return
        timestamp = time.time() - self.episode_start_time
        frame_index = len(self.current_episode_data)
        data_point = {
            "observation.state": positions_follower,
            "action": action_cible,
            "timestamp": timestamp,
            "frame_index": frame_index,
        }
        self.current_episode_data.append(data_point)
        if frame_top is not None:
            self.current_frames_top.append(frame_top.copy())
        if frame_follower is not None:
            self.current_frames_follower.append(frame_follower.copy())

    def cancel_episode(self):
        self.current_episode_data = []
        self.current_frames_top = []
        self.current_frames_follower = []
        self.is_recording = False
        print("❌ Épisode annulé")

    def save_episode(self):
        if not self.current_episode_data:
            print("⚠️  Aucune donnée à sauvegarder")
            self.is_recording = False
            return False

        position_id = self.current_position
        episode_idx = self.episodes_par_position[position_id]
        num_frames = len(self.current_episode_data)

        dataset_path = self.get_dataset_path(position_id)
        data_path = dataset_path / "data" / "chunk-000"
        video_path_top = dataset_path / "videos" / "chunk-000" / f"observation.images.{CAM_TOP}"
        video_path_follower = dataset_path / "videos" / "chunk-000" / f"observation.images.{CAM_FOLLOWER}"
        meta_path = dataset_path / "meta"

        data_path.mkdir(parents=True, exist_ok=True)
        video_path_top.mkdir(parents=True, exist_ok=True)
        video_path_follower.mkdir(parents=True, exist_ok=True)
        meta_path.mkdir(parents=True, exist_ok=True)

        print(f"\n💾 Sauvegarde épisode {episode_idx + 1} ({num_frames} frames)...")

        if PANDAS_AVAILABLE:
            records = []
            for i, dp in enumerate(self.current_episode_data):
                records.append({
                    "observation.state": dp["observation.state"],
                    "action": dp["action"],
                    "timestamp": dp["timestamp"],
                    "episode_index": episode_idx,
                    "frame_index": i,
                    "index": i,
                    "task_index": 0
                })
            df = pd.DataFrame(records)
            parquet_file = data_path / f"episode_{episode_idx:06d}.parquet"
            df.to_parquet(parquet_file, index=False)
            print(f"  ✅ Données: {parquet_file.name}")
        else:
            json_file = data_path / f"episode_{episode_idx:06d}.json"
            with open(json_file, 'w') as f:
                json.dump(self.current_episode_data, f)
            print(f"  ✅ Données (JSON): {json_file.name}")

        taille_video_top = 0
        if CV2_AVAILABLE and self.current_frames_top:
            video_file_top = video_path_top / f"episode_{episode_idx:06d}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            h, w = self.current_frames_top[0].shape[:2]
            out = cv2.VideoWriter(str(video_file_top), fourcc, CONFIG['fps'], (w, h))
            for frame in self.current_frames_top:
                out.write(frame)
            out.release()
            taille_video_top = video_file_top.stat().st_size
            print(f"  ✅ Vidéo {CAM_TOP}: {video_file_top.name}")

        taille_video_follower = 0
        if CV2_AVAILABLE and self.current_frames_follower:
            video_file_follower = video_path_follower / f"episode_{episode_idx:06d}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            h, w = self.current_frames_follower[0].shape[:2]
            out = cv2.VideoWriter(str(video_file_follower), fourcc, CONFIG['fps'], (w, h))
            for frame in self.current_frames_follower:
                out.write(frame)
            out.release()
            taille_video_follower = video_file_follower.stat().st_size
            print(f"  ✅ Vidéo {CAM_FOLLOWER}: {video_file_follower.name}")

        self._update_metadata(position_id, episode_idx, num_frames)
        self.episodes_par_position[position_id] += 1
        self._sauvegarder_etat()

        self.current_episode_data = []
        self.current_frames_top = []
        self.current_frames_follower = []
        self.is_recording = False

        parquet_file = data_path / f"episode_{episode_idx:06d}.parquet"
        taille_parquet = parquet_file.stat().st_size if parquet_file.exists() else 0
        taille_totale = taille_parquet + taille_video_top + taille_video_follower
        duree = num_frames / CONFIG['fps']

        if taille_totale > 1024 * 1024:
            taille_str = f"{taille_totale / (1024*1024):.1f} MB"
        else:
            taille_str = f"{taille_totale / 1024:.0f} KB"

        print(f"\n  ✅ Épisode {episode_idx + 1} sauvegardé !")
        print(f"     📊 Durée: {duree:.1f}s | Frames: {num_frames} | Taille: {taille_str}")
        return True

    def _update_metadata(self, position_id, episode_idx, num_frames):
        dataset_path = self.get_dataset_path(position_id)
        meta_path = dataset_path / "meta"
        pos_name = POSITIONS[position_id]['nom']
        info = {
            "codebase_version": "v2.1",
            "robot_type": "so101_follower",
            "total_episodes": episode_idx + 1,
            "total_frames": (episode_idx + 1) * num_frames,
            "total_tasks": 1,
            "total_videos": (episode_idx + 1) * 2,
            "fps": CONFIG['fps'],
            "splits": {"train": f"0:{episode_idx + 1}"},
            "features": {
                "observation.state": {"dtype": "float32", "shape": [6]},
                "action": {"dtype": "float32", "shape": [6]},
                f"observation.images.{CAM_TOP}": {
                    "dtype": "video",
                    "shape": [CONFIG['camera_height'], CONFIG['camera_width'], 3]
                },
                f"observation.images.{CAM_FOLLOWER}": {
                    "dtype": "video",
                    "shape": [CONFIG['camera_height'], CONFIG['camera_width'], 3]
                }
            }
        }
        with open(meta_path / "info.json", 'w') as f:
            json.dump(info, f, indent=2)

        task_desc = f"Prendre le cube à la position {pos_name} et le déposer dans la boîte"
        with open(meta_path / "tasks.jsonl", 'w') as f:
            f.write(json.dumps({"task_index": 0, "task": task_desc}) + "\n")

        with open(meta_path / "episodes.jsonl", 'a') as f:
            f.write(json.dumps({
                "episode_index": episode_idx,
                "tasks": [task_desc],
                "length": num_frames
            }) + "\n")

    def effacer_position(self, position_id):
        import shutil
        dataset_path = self.get_dataset_path(position_id)
        if dataset_path.exists():
            shutil.rmtree(dataset_path)
        self.episodes_par_position[position_id] = 0
        self._sauvegarder_etat()
        return True

    def effacer_tout(self):
        import shutil
        for pos_id in range(1, 6):
            dataset_path = self.get_dataset_path(pos_id)
            if dataset_path.exists():
                shutil.rmtree(dataset_path)
            self.episodes_par_position[pos_id] = 0
        self._sauvegarder_etat()
        return True

    def get_resume(self):
        total = sum(self.episodes_par_position.values())
        lines = [f"\n📊 Résumé des enregistrements ({total} épisodes au total):"]
        for pos_id in range(1, 6):
            count = self.episodes_par_position[pos_id]
            target = CONFIG['episodes_per_position']
            status = "✅" if count >= target else "○"
            lines.append(f"   {status} Position {pos_id} ({POSITIONS[pos_id]['nom']}): {count}/{target}")
        lines.append(f"\n📁 Datasets: {self.base_path}")
        return "\n".join(lines)

# ============================================
# THREAD DE TÉLÉOPÉRATION
# ============================================

def teleoperation_thread(lk, lp, fk, fp, calib_l, calib_f, servos_miroir, recorder, cam_top, cam_follower):
    global stop_threads, pause_teleop
    frame_interval = 1.0 / CONFIG['fps']
    last_record_time = 0

    while not stop_threads:
        loop_start = time.time()
        if pause_teleop:
            time.sleep(0.05)
            continue

        actions_cibles, positions_follower = [], []
        serial_ok = True   # passe à False si une lecture/écriture série échoue → instant non enregistré
        for servo_id in range(1, 7):
            pos_l, result, _ = lk.read2ByteTxRx(lp, servo_id, 56)
            if result == COMM_SUCCESS:
                pos_f = mapper_position(pos_l, servo_id, calib_l, calib_f, servos_miroir)
                result_w, _ = fk.write2ByteTxRx(fp, servo_id, 42, pos_f)
                if result_w == COMM_SUCCESS:
                    actions_cibles.append(float(pos_f))   # cible Follower réellement envoyée (action)
                else:
                    # Écriture Follower échouée : la consigne n'a peut-être pas été appliquée.
                    serial_ok = False
                    actions_cibles.append(0.0)            # placeholder neutre, jamais enregistré
                pos_f_real, result_f, _ = fk.read2ByteTxRx(fp, servo_id, 56)
                if result_f == COMM_SUCCESS:
                    positions_follower.append(float(pos_f_real))
                else:
                    # Lecture Follower échouée : aucune valeur fabriquée (plus de 2048.0).
                    serial_ok = False
                    positions_follower.append(0.0)   # placeholder neutre, jamais enregistré (serial_ok=False)
            else:
                # Lecture Leader échouée : aucune consigne envoyée (le Follower tient sa position),
                # aucune valeur fabriquée. L'instant sera ignoré côté enregistrement.
                serial_ok = False
                actions_cibles.append(0.0)        # placeholder neutre, jamais enregistré
                positions_follower.append(0.0)    # placeholder neutre, jamais enregistré

        frame_top = cam_top.async_read() if cam_top and cam_top.is_connected else None
        frame_follower = cam_follower.async_read() if cam_follower and cam_follower.is_connected else None
        # Masque appliqué à la globale → le .mp4 enregistré ne contient que la zone utile
        if frame_top is not None and _MASK_GLOBALE_IMG is not None:
            frame_top = cv2.bitwise_and(frame_top, frame_top, mask=_MASK_GLOBALE_IMG)

        current_time = time.time()
        if recorder.is_recording and (current_time - last_record_time >= frame_interval):
            # Atomicité : on n'enregistre l'instant t que si les DEUX images sont présentes
            # ET les lectures série sont valides — invariant 1 ligne parquet = 1 frame globale
            # = 1 frame pince = 1 état série valide = 1 action valide. Aucune valeur fabriquée.
            if frame_top is not None and frame_follower is not None and serial_ok:
                recorder.record_frame(positions_follower, actions_cibles, frame_top, frame_follower)
                last_record_time = current_time
            else:
                print("\n⚠️  Instant ignoré (image manquante ou lecture série invalide) — dataset préservé.")

        elapsed = time.time() - loop_start
        if elapsed < 0.01:
            time.sleep(0.01 - elapsed)

# ============================================
# THREAD DE LECTURE CLAVIER
# ============================================

def keyboard_thread():
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
                    if ch in ['D', 'T', 'A', 'S', 'Q', '1', '2', '3', '4', '5', '6', 'R', 'O']:
                        cmd_queue.put(ch)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    except:
        while not stop_threads:
            try:
                cmd = input().strip().upper()
                if cmd:
                    cmd_queue.put(cmd[0])
            except:
                pass

def get_command():
    try:
        return cmd_queue.get_nowait()
    except queue.Empty:
        return None

# ============================================
# ÉCRANS D'INTERFACE
# ============================================

def afficher_instructions():
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                         INSTRUCTIONS                                 ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  OBJECTIF : Enregistrer 50 démonstrations de la tâche                ║
║             "Prendre un cube et le déposer dans la boîte"            ║
║                                                                      ║
║  DISPOSITION DES POSITIONS :                                         ║
║                                                                      ║
║                    Position 3 (Haut/Loin)                            ║
║                           ●                                          ║
║                           |                                          ║
║       Position 4 ● ───────●─────── ● Position 5                      ║
║       (Gauche)      Position 1       (Droite)                        ║
║          |           (Centre)           |                            ║
║       [BOÎTE]                        [BOÎTE]                         ║
║                           |                                          ║
║                           ●                                          ║
║                    Position 2 (Bas/Proche)                           ║
║                                                                      ║
║                        🤖 ROBOT                                      ║
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  CONTRÔLES PENDANT L'ENREGISTREMENT :                                ║
║                                                                      ║
║    D = Démarrer (retour repos automatique avant enregistrement)      ║
║    T = Terminer (retour repos automatique enregistré + sauvegarde)   ║
║    A = Annuler l'épisode en cours                                    ║
║    S = Stopper la session                                            ║
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  CONSEILS :                                                          ║
║  • Gardez la caméra fixe                                             ║
║  • Soyez cohérent dans vos gestes                                    ║
║  • Le cube doit toujours être visible à la caméra                    ║
║  • 10 épisodes par position = 50 épisodes au total                   ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

    Appuyez sur ENTRÉE pour revenir au menu...""")
    input()

def afficher_menu_principal(recorder):
    clear_screen()
    pos_status = []
    for pos_id in range(1, 6):
        count = recorder.episodes_par_position[pos_id]
        target = CONFIG['episodes_per_position']
        if count >= target:
            status = "✅"
        elif count > 0:
            status = "◐"
        else:
            status = "○"
        pos_status.append(f"     {pos_id}. {POSITIONS[pos_id]['nom']:8} {status} ({count}/{target})")

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║           ENREGISTREMENT DATASET SO-ARM 101 - Phase 8                ║
║           Service Écoles-Médias (SEM) - DIP Genève                   ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  🎮 TÉLÉOPÉRATION ACTIVE - Bougez le Leader, le Follower suit        ║
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  1. 📖 Lire les instructions                                         ║
║                                                                      ║
║  2. 🧪 Test rapide (2 épisodes)                                      ║
║                                                                      ║
║  3. 📹 Enregistrer 10 épisodes pour une position :                   ║
║                                                                      ║
{chr(10).join(pos_status)}
║                                                                      ║
║  4. 👁️  Visualiser vos datasets                                      ║
║                                                                      ║
║  5. 🗑️  Effacer des données                                          ║
║                                                                      ║
║  6. 🏁 Repositionner le robot à repos                                ║
║                                                                      ║
║  Q. 🚪 Quitter (affiche le résumé)                                   ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

    Votre choix : """, end="", flush=True)

def menu_effacer_donnees(recorder):
    while True:
        clear_screen()
        pos_lines = []
        for pos_id in range(1, 6):
            count = recorder.episodes_par_position[pos_id]
            pos_lines.append(f"║     {pos_id}. {POSITIONS[pos_id]['nom']:8} ({count} épisodes)                                  ║")

        total = sum(recorder.episodes_par_position.values())

        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║           EFFACER DES DONNÉES                                        ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  1-5. Effacer une position spécifique :                              ║
║                                                                      ║
{chr(10).join(pos_lines)}
║                                                                      ║
║  T. 🗑️  TOUT effacer ({total} épisodes)                               ║
║                                                                      ║
║  R. ↩️  Retour au menu                                               ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

    Votre choix : """, end="", flush=True)

        choix = None
        while choix is None and not stop_threads:
            cmd = get_command()
            if cmd in ['1', '2', '3', '4', '5', 'T', 'R']:
                choix = cmd
            refresh_display()

        if stop_threads or choix == 'R':
            return

        elif choix == 'T':
            if total == 0:
                print("\n⚠️  Aucune donnée à effacer.")
                time.sleep(1.5)
                continue
            print(f"\n⚠️  ATTENTION: Effacer TOUTES les données ({total} épisodes) ?")
            print("    Appuyez sur O pour confirmer, autre touche pour annuler...")
            confirm = None
            while confirm is None and not stop_threads:
                cmd = get_command()
                if cmd is not None:
                    confirm = cmd
                refresh_display()
            if confirm == 'O':
                recorder.effacer_tout()
                print("\n✅ Toutes les données ont été effacées.")
                time.sleep(1.5)
            else:
                print("\n❌ Annulé.")
                time.sleep(1)

        elif choix in ['1', '2', '3', '4', '5']:
            pos_id = int(choix)
            count = recorder.episodes_par_position[pos_id]
            pos_name = POSITIONS[pos_id]['nom']

            if count == 0:
                print(f"\n⚠️  Aucune donnée pour la position {pos_name}.")
                time.sleep(1.5)
                continue

            print(f"\n⚠️  Effacer la position {pos_name} ({count} épisodes) ?")
            print("    Appuyez sur O pour confirmer, autre touche pour annuler...")
            confirm = None
            while confirm is None and not stop_threads:
                cmd = get_command()
                if cmd is not None:
                    confirm = cmd
                refresh_display()
            if confirm == 'O':
                recorder.effacer_position(pos_id)
                print(f"\n✅ Position {pos_name} effacée.")
                time.sleep(1.5)
            else:
                print("\n❌ Annulé.")
                time.sleep(1)

def session_enregistrement(recorder, position_id, num_episodes, lk, lp, fk, fp, calib_l, calib_f, cam_top=None, cam_follower=None):
    global stop_threads, pause_teleop

    pos_name = POSITIONS[position_id]['nom']
    episodes_done = 0

    while episodes_done < num_episodes and not stop_threads:
        current_count = recorder.episodes_par_position[position_id]

        # ====== ÉTAT : ATTENTE ======
        # Les DEUX robots sont RIGIDES (torque=1) à repos et la téléopération est en PAUSE.
        # => mains libres pour placer le cube ; le Follower ne suit RIEN (aucun risque de chute).
        pause_teleop = True
        time.sleep(0.1)
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 1)
            fk.write1ByteTxRx(fp, i, 40, 1)
        repos_pct = charger_repos_pct()
        deja_repos = (_est_en_repos_1robot(lk, lp, calib_l, repos_pct)
                      and _est_en_repos_1robot(fk, fp, calib_f, repos_pct))
        if not deja_repos:
            print("\n🏁 Repositionnement automatique vers repos...")
            position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)
        # Les deux robots RESTENT rigides ; la téléopération RESTE en pause.

        clear_screen()
        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║  ENREGISTREMENT - Position {position_id} ({pos_name:8})                          ║
║  Épisodes : {current_count}/{current_count + num_episodes - episodes_done} (session) | Total: {current_count}/{CONFIG['episodes_per_position']}              ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  📍 Placez le cube à la position {pos_name:8}                            ║
║  ✋ Mains libres : les robots sont RIGIDES à repos.                   ║
║                                                                      ║
║  Quand vous êtes prêt :                                              ║
║     1. Placez le cube                                                ║
║     2. PRENEZ le Leader en main                                      ║
║     3. Appuyez sur D pour DÉMARRER l'enregistrement                  ║
║                                                                      ║
║  Autres :  R = repositionner à repos   S = revenir au menu           ║
║  État : ⏸️  EN ATTENTE (robots rigides à repos)                       ║
╚══════════════════════════════════════════════════════════════════════╝
        """)

        action = None
        while not stop_threads:
            cmd = get_command()
            if cmd == 'D':
                action = 'start'
                break
            elif cmd == 'R':
                action = 'repos'
                break
            elif cmd == 'S':
                # Restaurer l'état du menu (téléop active, Leader libre) avant de sortir
                for i in range(1, 7):
                    lk.write1ByteTxRx(lp, i, 40, 0)
                    fk.write1ByteTxRx(fp, i, 40, 1)
                pause_teleop = False
                return episodes_done
            refresh_display()

        if stop_threads:
            break

        if action == 'repos':
            # Repositionnement forcé ; les robots restent rigides à repos ensuite.
            print("\n🏁 Repositionnement à repos...")
            position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)
            time.sleep(1.0)
            continue

        # ====== TRANSITION « GO » ======
        # L'utilisateur tient le Leader (rigide) à repos. On libère le Leader,
        # on arme l'enregistrement, puis on active la téléop => transition fluide, aucun bond.
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 0)
        recorder.start_episode(position_id)
        pause_teleop = False

        clear_screen()
        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║  🔴 ENREGISTREMENT EN COURS - Position {position_id} ({pos_name:8})              ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  🎬 Effectuez la tâche : Prenez le cube → Déposez dans la boîte       ║
║                                                                      ║
║  Commandes :                                                         ║
║     T = Terminer + sauvegarder (retour repos hors enregistrement)    ║
║     A = Annuler l'épisode                                            ║
║     S = Stopper la session                                           ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
        """)

        start_time = time.time()
        while not stop_threads:
            cmd = get_command()

            if cmd == 'T':
                # Stop enregistrement (dataset propre) -> gel du Follower -> retour sûr HORS caméra.
                # Les DEUX robots restent RIGIDES, la téléop NE reprend PAS : retour à l'attente.
                pause_teleop = True
                time.sleep(0.1)
                saved = recorder.save_episode()
                if saved:
                    episodes_done += 1
                    print(f"\n✅ Épisode sauvegardé! ({episodes_done}/{num_episodes} cette session)")

                print("\n🏁 Retour à repos (hors enregistrement)...")
                aller_a_position_2robots(lk, lp, fk, fp, calib_l, calib_f, charger_repos_pct(), duree=2.0)
                # aller_a_position_2robots laisse les deux robots rigides (torque=1) : on n'y touche pas.
                print("✅ À repos. Vous pouvez replacer le cube pour le prochain épisode.")
                time.sleep(1.0)
                break

            elif cmd == 'A':
                pause_teleop = True
                recorder.cancel_episode()
                print("\n↩️  Épisode annulé, on recommence...")
                time.sleep(1)
                break

            elif cmd == 'S':
                pause_teleop = True
                recorder.cancel_episode()
                # Restaurer l'état du menu (téléop active, Leader libre) avant de sortir
                for i in range(1, 7):
                    lk.write1ByteTxRx(lp, i, 40, 0)
                    fk.write1ByteTxRx(fp, i, 40, 1)
                pause_teleop = False
                return episodes_done

            elapsed = time.time() - start_time
            frames = len(recorder.current_episode_data)
            print(f"\r  ⏱️  {elapsed:.1f}s | Frames: {frames}   ", end="", flush=True)
            refresh_display()

    # Fin de session : restaurer l'état du menu (téléop active, Leader libre)
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 0)
        fk.write1ByteTxRx(fp, i, 40, 1)
    pause_teleop = False
    return episodes_done

# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main():
    global stop_threads, cmd_queue, _display_cam_top, _display_cam_follower, pause_teleop
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     SEM - ENREGISTREMENT DATASET SO-ARM 101                          ║
║     Phase 8 : Apprentissage par Imitation (2 caméras)                ║
║     Service Écoles-Médias - DIP Genève                               ║
╚══════════════════════════════════════════════════════════════════════╝

Ce script enregistre des démonstrations de téléopération pour
l'apprentissage par imitation avec LeRobot.

Tâche : Prendre un cube à l'une des 5 positions et le déposer
        dans la boîte.

Format de sortie : LeRobotDataset v2.1 (2 caméras: top + follower)
    """)
    input("\nAppuyez sur ENTRÉE pour commencer...")

    cam_top_index, cam_follower_index = identification_cameras()
    if cam_top_index is None or cam_follower_index is None:
        print("\n❌ Enregistrement annulé : les deux caméras (globale + pince) sont requises.")
        sys.exit(1)

    # Garde-fou : le module de configuration caméra doit être disponible.
    # Sans lui, impossible de régler puis verrouiller les caméras → on arrête (fail closed)
    # plutôt que d'enregistrer en auto-exposition, incohérent avec le déploiement.
    if not CAMERA_LOCK_AVAILABLE:
        print("\n❌ Module de configuration caméra (SEM_8_camera_config.py) indisponible.")
        print(f"   Erreur : {CAMERA_LOCK_IMPORT_ERROR}")
        print("   → Impossible de régler puis verrouiller les caméras.")
        print("   → Enregistrement annulé pour éviter des images en mode auto (incohérence avec le déploiement).")
        print("   → Vérifiez que SEM_8_camera_config.py est dans le même dossier que ce script.")
        sys.exit(1)

    # Réglages caméra (exposition / balance des blancs) — un réglage par caméra
    if cam_top_index is not None:
        capturer_reglages_camera(f"/dev/video{cam_top_index}", CAM_TOP, titre="GLOBALE (cam_top)   [1/2]")
    if cam_follower_index is not None:
        capturer_reglages_camera(f"/dev/video{cam_follower_index}", CAM_FOLLOWER, titre="PINCE (cam_follower)   [2/2]")

    # Chargement du masque globale (créé par le script 7, partagé avec le 12).
    # Si absent → message + enregistrement avec l'image brute, pas de crash.
    global _MASK_GLOBALE_IMG
    mask_pts = charger_masque_globale()
    if mask_pts:
        _MASK_GLOBALE_IMG = construire_mask_image(
            mask_pts, CONFIG['camera_width'], CONFIG['camera_height']
        )
        print(f"\n✅ Masque globale actif ({len(mask_pts)} points)")
    else:
        print("\n⚠️  Aucun masque trouvé — l'enregistrement utilisera l'image brute.")
        print("   Lance le script 7 d'abord pour créer le masque si tu veux le bénéfice du cadrage.")

    input("\n✅ Caméras identifiées. Appuyez sur ENTRÉE pour continuer avec les robots...")
    result = identification_guidee()
    if not result[0]:
        print("❌ Identification échouée")
        return

    lp, lk, fp, fk, calib_l, calib_f = result
    print("\n[C]ôte à côte ou [F]ace à face?")
    choix = input("Choix [C]: ").upper()
    mode = "face" if choix == 'F' else "cote"
    servos_miroir = charger_config_teleoperation(mode)

    urgence = False  # Devient True sur CTRL+C : arrêt d'urgence, pas de retour repos
    # Variables de nettoyage définies AVANT le try : si un CTRL+C ou une exception survient
    # pendant position_repos_parallele (avant leur création), le finally les référence sans NameError.
    recorder = DatasetRecorder()
    cam_top = None
    cam_follower = None
    try:
        print("\n🎯 Positionnement automatique (séquence sûre vers repos)...")
        position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)

        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 0)
            fk.write1ByteTxRx(fp, i, 40, 1)

        if CV2_AVAILABLE:
            print("\n📷 Connexion des caméras identifiées...")
            if cam_top_index is not None:
                cam_top = ThreadedCamera(cam_top_index, CAM_TOP, CONFIG['camera_width'], CONFIG['camera_height'], CONFIG['fps'])
                # Point A : arrêt si la connexion physique échoue
                if not cam_top.connect() or not cam_top.is_connected:
                    print("\n❌ Caméra globale non connectée — arrêt.")
                    sys.exit(1)
                # Point B : arrêt si la résolution réelle n'est pas celle attendue
                frame_test = cam_top.async_read()
                if frame_test is not None and frame_test.shape[:2] != (CONFIG['camera_height'], CONFIG['camera_width']):
                    print(f"\n❌ Résolution caméra globale incorrecte : {frame_test.shape[:2]}")
                    print(f"   Attendu : {(CONFIG['camera_height'], CONFIG['camera_width'])}")
                    sys.exit(1)

            if cam_follower_index is not None:
                cam_follower = ThreadedCamera(cam_follower_index, CAM_FOLLOWER, CONFIG['camera_width'], CONFIG['camera_height'], CONFIG['fps'])
                # Point A : arrêt si la connexion physique échoue
                if not cam_follower.connect() or not cam_follower.is_connected:
                    print("\n❌ Caméra pince non connectée — arrêt.")
                    sys.exit(1)
                # Point B : arrêt si la résolution réelle n'est pas celle attendue
                frame_test = cam_follower.async_read()
                if frame_test is not None and frame_test.shape[:2] != (CONFIG['camera_height'], CONFIG['camera_width']):
                    print(f"\n❌ Résolution caméra pince incorrecte : {frame_test.shape[:2]}")
                    print(f"   Attendu : {(CONFIG['camera_height'], CONFIG['camera_width'])}")
                    sys.exit(1)

            # Verrouillage matériel APRÈS connexion + contrôle du résultat (comme le script 10)
            ok_lock = True
            if cam_top_index is not None:
                ok_lock &= verrouiller_camera(f"/dev/video{cam_top_index}", CAM_TOP)
            if cam_follower_index is not None:
                ok_lock &= verrouiller_camera(f"/dev/video{cam_follower_index}", CAM_FOLLOWER)
            if not ok_lock:
                if input("\n⚠️  Verrouillage caméra incomplet. Continuer quand même ? [O/N] : ").strip().upper() != 'O':
                    return

            if cam_top is None and cam_follower is None:
                print("   ⚠️  Aucune caméra connectée")

        stop_threads = False
        cmd_queue = queue.Queue()

        teleop_t = threading.Thread(
            target=teleoperation_thread,
            args=(lk, lp, fk, fp, calib_l, calib_f, servos_miroir, recorder, cam_top, cam_follower),
            daemon=True
        )
        teleop_t.start()

        # Assignation pour la boucle d'affichage dans le main thread
        _display_cam_top = cam_top
        _display_cam_follower = cam_follower

        kb_t = threading.Thread(target=keyboard_thread, daemon=True)
        kb_t.start()

        print("\n✅ Téléopération active!")
        print("⚠️  Tenez le LEADER")
        time.sleep(2)

        while not stop_threads:
            afficher_menu_principal(recorder)
            choix = None
            while choix is None and not stop_threads:
                cmd = get_command()
                if cmd in ['1', '2', '3', '4', '5', '6', 'Q']:
                    choix = cmd
                refresh_display()

            if stop_threads or choix == 'Q':
                break

            if choix == '1':
                afficher_instructions()

            elif choix == '2':
                print("\n🧪 Test rapide - Choisissez une position (1-5): ", end="", flush=True)
                pos = None
                while pos is None and not stop_threads:
                    cmd = get_command()
                    if cmd in ['1', '2', '3', '4', '5']:
                        pos = int(cmd)
                    refresh_display()

                if pos:
                    session_enregistrement(recorder, pos, 2, lk, lp, fk, fp, calib_l, calib_f, cam_top=cam_top, cam_follower=cam_follower)

            elif choix == '3':
                print("\n📹 Choisissez une position (1-5): ", end="", flush=True)
                pos = None
                while pos is None and not stop_threads:
                    cmd = get_command()
                    if cmd in ['1', '2', '3', '4', '5']:
                        pos = int(cmd)
                    elif cmd == 'S':
                        break
                    refresh_display()

                if pos:
                    remaining = CONFIG['episodes_per_position'] - recorder.episodes_par_position[pos]
                    if remaining <= 0:
                        print(f"\n✅ Position {pos} déjà complète!")
                        time.sleep(2)
                    else:
                        done = session_enregistrement(recorder, pos, remaining, lk, lp, fk, fp, calib_l, calib_f, cam_top=cam_top, cam_follower=cam_follower)
                        if done > 0:
                            print(f"\n✅ {done} épisodes enregistrés pour la position {pos}!")
                            time.sleep(2)

            elif choix == '4':
                clear_screen()
                print("\n📁 Datasets disponibles:\n")
                for pos_id in range(1, 6):
                    path = recorder.get_dataset_path(pos_id)
                    if path.exists():
                        count = recorder.episodes_par_position[pos_id]
                        print(f"  Position {pos_id} ({POSITIONS[pos_id]['nom']}): {count} épisodes")
                        print(f"    → {path}")
                    else:
                        print(f"  Position {pos_id} ({POSITIONS[pos_id]['nom']}): Pas encore de données")
                print(f"\n💡 Pour visualiser: python lerobot/scripts/visualize_dataset_html.py")
                input("\nAppuyez sur ENTRÉE pour revenir au menu...")

            elif choix == '5':
                menu_effacer_donnees(recorder)

            elif choix == '6':
                # Repositionner le robot à repos (sécurité après les mouvements de démarrage)
                clear_screen()
                print("\n🏁 Repositionnement du robot à repos...")
                pause_teleop = True
                time.sleep(0.1)
                for i in range(1, 7):
                    lk.write1ByteTxRx(lp, i, 40, 1)
                    fk.write1ByteTxRx(fp, i, 40, 1)
                position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)
                # Libérer Leader, garder Follower actif pour reprendre la téléopération
                for i in range(1, 7):
                    lk.write1ByteTxRx(lp, i, 40, 0)
                    fk.write1ByteTxRx(fp, i, 40, 1)
                pause_teleop = False
                print("\n✅ Robot repositionné à repos.")
                time.sleep(1.5)

    except KeyboardInterrupt:
        print("\n\n🛑 ARRÊT D'URGENCE (CTRL+C) — libération immédiate des servos.")
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 0)
            fk.write1ByteTxRx(fp, i, 40, 0)
        urgence = True
    finally:
        stop_threads = True
        time.sleep(0.5)

        if cam_top:
            cam_top.disconnect()
        if cam_follower:
            cam_follower.disconnect()
        if CV2_AVAILABLE:
            cv2.destroyAllWindows()

        print(recorder.get_resume())

        if urgence:
            # Arrêt d'urgence (CTRL+C) : servos déjà libérés, AUCUN retour repos
            lp.closePort()
            fp.closePort()
            print("\n✅ Arrêt d'urgence terminé (aucun retour repos).")
        else:
            print("\n🏁 Retour position repos...")
            for i in range(1, 7):
                lk.write1ByteTxRx(lp, i, 40, 1)
                fk.write1ByteTxRx(fp, i, 40, 1)

            repos_pct = charger_repos_pct()
            deja_repos = (_est_en_repos_1robot(lk, lp, calib_l, repos_pct)
                          and _est_en_repos_1robot(fk, fp, calib_f, repos_pct))
            if deja_repos:
                print("✅ Déjà en position repos (pas de repositionnement).")
            else:
                position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)

            print("\n⚠️  Assurez-vous de tenir les robots")
            time.sleep(2)

            for i in range(1, 7):
                lk.write1ByteTxRx(lp, i, 40, 0)
                fk.write1ByteTxRx(fp, i, 40, 0)

            lp.closePort()
            fp.closePort()
            print("\n✅ Session terminée!")

if __name__ == "__main__":
    main()
