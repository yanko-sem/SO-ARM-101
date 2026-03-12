#!/usr/bin/env python3
"""
Script SEM_so101_8_record_dataset.py
Service Écoles-Médias (SEM) - DIP Genève

ENREGISTREMENT DE DATASET POUR APPRENTISSAGE PAR IMITATION (2 CAMÉRAS)
======================================================================

Architecture inspirée de LeRobot : threads de lecture dédiés par caméra.

Ce script permet d'enregistrer des démonstrations de téléopération
pour l'apprentissage par imitation avec LeRobot.

Tâche : Prendre un cube à l'une des 5 positions et le déposer dans la boîte

Contrôles pendant l'enregistrement:
    D : Démarrer l'enregistrement d'un épisode
    T : Terminer l'épisode (succès)
    A : Annuler l'épisode en cours
    S : Stopper la session complètement

Auteur: Service Écoles-Médias (SEM)
Version: 2.0 (architecture LeRobot)
Date: Janvier 2025
"""

import os
import sys
import json
import time
import math
import threading
import queue
from datetime import datetime
from pathlib import Path

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
    'camera_height': 480,
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

def refresh_display():
    """Rafraîchit l'affichage des caméras (doit tourner dans le thread principal)"""
    if CV2_AVAILABLE:
        if _display_cam_top and _display_cam_top.is_connected:
            frame = _display_cam_top.async_read()
            if frame is not None:
                cv2.imshow(f'{CAM_TOP} (globale)', frame)
        if _display_cam_follower and _display_cam_follower.is_connected:
            frame = _display_cam_follower.async_read()
            if frame is not None:
                cv2.imshow(f'{CAM_FOLLOWER} (pince)', frame)
        cv2.waitKey(1)

# ============================================
# CLASSE THREADED CAMERA (architecture LeRobot)
# ============================================

class ThreadedCamera:
    """
    Caméra avec thread de lecture dédié (architecture LeRobot).
    Le thread lit en continu et stocke la dernière frame.
    async_read() retourne immédiatement la dernière frame disponible.
    """

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
        """Connecte la caméra et démarre le thread de lecture"""
        if self.is_connected:
            return True

        if not CV2_AVAILABLE:
            return False

        self.camera = cv2.VideoCapture(self.camera_index)
        if not self.camera.isOpened():
            print(f"❌ Impossible d'ouvrir {self.name} (index {self.camera_index})")
            return False

        # Configurer la caméra
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.camera.set(cv2.CAP_PROP_FPS, self.fps)

        # Lire une première frame pour initialiser (warmup comme LeRobot)
        ret, frame = self.camera.read()
        if ret:
            self.current_frame = frame

        self.is_connected = True

        # Démarrer le thread de lecture
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

        print(f"   ✅ {self.name} connectée (index {self.camera_index})")
        return True

    def _read_loop(self):
        """Boucle de lecture en continu (dans son propre thread)"""
        while not self.stop_event.is_set():
            if self.camera and self.camera.isOpened():
                ret, frame = self.camera.read()
                if ret:
                    with self.frame_lock:
                        self.current_frame = frame
            # Petite pause pour ne pas surcharger le CPU
            time.sleep(0.001)

    def async_read(self):
        """Retourne la dernière frame disponible (non-bloquant)"""
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None

    def disconnect(self):
        """Arrête le thread et libère la caméra"""
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

    for idx in cameras[:2]:  # Tester les 2 premières
        print(f"\n🎥 Test caméra index {idx}...")
        cap = cv2.VideoCapture(idx)

        if not cap.isOpened():
            print(f"   ❌ Impossible d'ouvrir la caméra {idx}")
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG['camera_width'])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG['camera_height'])

        window_name = f"Camera {idx} - Identifiez cette camera"

        # Capturer une image et l'afficher (thread principal, compatible Qt)
        ret, frame = cap.read()
        if ret:
            cv2.putText(frame, f"Camera {idx}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, "Repondez dans le TERMINAL", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
            cv2.imshow(window_name, frame)
            cv2.waitKey(100)

        # Saisie dans le terminal (fiable)
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
# FONCTIONS UTILITAIRES (identiques aux scripts 6/7)
# ============================================

def clear_screen():
    os.system('clear')

def detect_ports():
    """Détecte les ports USB disponibles"""
    ports = []
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']:
        if os.path.exists(port):
            ports.append(port)
    return ports

def charger_calibration(robot_type):
    """Charge la calibration d'un robot"""
    calib_file = os.path.expanduser(f"~/lerobot/calibration/{robot_type}_calibration.json")
    if os.path.exists(calib_file):
        with open(calib_file, 'r') as f:
            return json.load(f)
    return None

def charger_config_teleoperation(mode):
    """Charge la configuration COPIE/MIROIR"""
    config_file = os.path.expanduser(f"~/lerobot/calibration/teleoperation_config_{mode}.json")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            data = json.load(f)
            return data.get('servos_miroir', [])
    return []

def mouvement_fluide(packet, port, servo, debut, fin, duree=1.5):
    """Mouvement fluide entre deux positions"""
    steps = int(duree * 50)
    for i in range(steps + 1):
        t = i / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        pos = int(debut + (fin - debut) * smooth)
        packet.write2ByteTxRx(port, servo, 42, pos)
        time.sleep(duree / steps)

def mapper_position(pos_leader, servo_id, calib_leader, calib_follower, servos_miroir):
    """Mapping proportionnel avec gestion COPIE/MIROIR"""
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
# IDENTIFICATION (du script 7)
# ============================================

def test_connexion_fluide(packet, port, robot_name, calib):
    """Test fluide de connexion avec calibration"""
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
    """Identifie Leader et Follower avec test fluide"""
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

# ============================================
# POSITIONNEMENT (du script 7)
# ============================================

def centrage_parallele(lk, lp, fk, fp, calib_l, calib_f):
    """Centre tous les servos en parallèle"""
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

def position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f):
    """Met les deux robots en position repos"""
    print("\n🏁 Position repos simultanée...")

    repos_pct = {
        1: 50, 2: 10, 3: 88, 4: 76, 5: 50, 6: 75
    }

    repos_l = {}
    repos_f = {}

    for i in range(1, 7):
        pct = repos_pct[i] / 100.0

        if calib_l and f'servo_{i}' in calib_l:
            min_l = calib_l[f'servo_{i}']['min']
            max_l = calib_l[f'servo_{i}']['max']
            repos_l[i] = int(min_l + (max_l - min_l) * pct)
        else:
            repos_l[i] = 2048

        if calib_f and f'servo_{i}' in calib_f:
            min_f = calib_f[f'servo_{i}']['min']
            max_f = calib_f[f'servo_{i}']['max']
            repos_f[i] = int(min_f + (max_f - min_f) * pct)
        else:
            repos_f[i] = 2048

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
            new_pos_l = int(pos_l[i] + (repos_l[i] - pos_l[i]) * smooth)
            lk.write2ByteTxRx(lp, i, 42, new_pos_l)

            new_pos_f = int(pos_f[i] + (repos_f[i] - pos_f[i]) * smooth)
            fk.write2ByteTxRx(fp, i, 42, new_pos_f)

        time.sleep(duree / steps)

    print("✅ Position repos atteinte")

# ============================================
# CLASSE DATASET RECORDER
# ============================================

class DatasetRecorder:
    """Gère l'enregistrement et la sauvegarde du dataset (2 caméras)"""

    def __init__(self, base_name="so101_pick_place"):
        self.base_name = base_name
        self.base_path = Path(os.path.expanduser(
            f"~/.cache/huggingface/lerobot/local/{base_name}"
        ))

        # Statistiques par position
        self.episodes_par_position = {i: 0 for i in range(1, 6)}

        # Charger l'état existant si disponible
        self._charger_etat()

        # Données épisode en cours (2 listes de frames)
        self.current_episode_data = []
        self.current_frames_top = []
        self.current_frames_follower = []
        self.episode_start_time = None
        self.is_recording = False

    def _charger_etat(self):
        """Charge l'état des enregistrements précédents"""
        state_file = self.base_path / "sem_state.json"
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
                self.episodes_par_position = state.get('episodes_par_position',
                                                        {str(i): 0 for i in range(1, 6)})
                # Convertir les clés en int
                self.episodes_par_position = {int(k): v for k, v in self.episodes_par_position.items()}

    def _sauvegarder_etat(self):
        """Sauvegarde l'état des enregistrements"""
        self.base_path.mkdir(parents=True, exist_ok=True)
        state_file = self.base_path / "sem_state.json"
        with open(state_file, 'w') as f:
            json.dump({
                'episodes_par_position': self.episodes_par_position,
                'last_update': datetime.now().isoformat()
            }, f, indent=2)

    def get_dataset_path(self, position_id):
        """Retourne le chemin du dataset pour une position"""
        pos_name = POSITIONS[position_id]['nom'].lower()
        return self.base_path / f"position_{position_id}_{pos_name}"

    def start_episode(self, position_id):
        """Démarre l'enregistrement d'un épisode"""
        self.current_position = position_id
        self.current_episode_data = []
        self.current_frames_top = []
        self.current_frames_follower = []
        self.episode_start_time = time.time()
        self.is_recording = True

        episode_num = self.episodes_par_position[position_id] + 1
        print(f"\n🔴 ENREGISTREMENT - Position {position_id} ({POSITIONS[position_id]['nom']}) - Épisode {episode_num}")

    def record_frame(self, positions_follower, positions_leader, frame_top=None, frame_follower=None):
        """Enregistre une frame de données avec 2 caméras"""
        if not self.is_recording:
            return

        timestamp = time.time() - self.episode_start_time
        frame_index = len(self.current_episode_data)

        data_point = {
            "observation.state": positions_follower,
            "action": positions_leader,
            "timestamp": timestamp,
            "frame_index": frame_index,
        }
        self.current_episode_data.append(data_point)

        if frame_top is not None:
            self.current_frames_top.append(frame_top.copy())
        if frame_follower is not None:
            self.current_frames_follower.append(frame_follower.copy())

    def cancel_episode(self):
        """Annule l'épisode en cours"""
        self.current_episode_data = []
        self.current_frames_top = []
        self.current_frames_follower = []
        self.is_recording = False
        print("❌ Épisode annulé")

    def save_episode(self):
        """Sauvegarde l'épisode terminé avec 2 vidéos"""
        if not self.current_episode_data:
            print("⚠️  Aucune donnée à sauvegarder")
            self.is_recording = False
            return False

        position_id = self.current_position
        episode_idx = self.episodes_par_position[position_id]
        num_frames = len(self.current_episode_data)

        # Créer les dossiers
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

        # 1. Sauvegarder données
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

        # 2. Sauvegarder vidéo cam_top
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

        # 3. Sauvegarder vidéo cam_follower
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

        # 4. Mettre à jour metadata
        self._update_metadata(position_id, episode_idx, num_frames)

        # 5. Mettre à jour compteur
        self.episodes_par_position[position_id] += 1
        self._sauvegarder_etat()

        # Nettoyer
        self.current_episode_data = []
        self.current_frames_top = []
        self.current_frames_follower = []
        self.is_recording = False

        # Feedback
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
        """Met à jour les fichiers de metadata pour 2 caméras"""
        dataset_path = self.get_dataset_path(position_id)
        meta_path = dataset_path / "meta"

        # info.json
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

        # tasks.jsonl
        task_desc = f"Prendre le cube à la position {pos_name} et le déposer dans la boîte"
        with open(meta_path / "tasks.jsonl", 'w') as f:
            f.write(json.dumps({"task_index": 0, "task": task_desc}) + "\n")

        # episodes.jsonl (append)
        with open(meta_path / "episodes.jsonl", 'a') as f:
            f.write(json.dumps({
                "episode_index": episode_idx,
                "tasks": [task_desc],
                "length": num_frames
            }) + "\n")

    def effacer_position(self, position_id):
        """Efface toutes les données d'une position"""
        import shutil
        dataset_path = self.get_dataset_path(position_id)
        if dataset_path.exists():
            shutil.rmtree(dataset_path)
        self.episodes_par_position[position_id] = 0
        self._sauvegarder_etat()
        return True

    def effacer_tout(self):
        """Efface toutes les données de toutes les positions"""
        import shutil
        for pos_id in range(1, 6):
            dataset_path = self.get_dataset_path(pos_id)
            if dataset_path.exists():
                shutil.rmtree(dataset_path)
            self.episodes_par_position[pos_id] = 0
        self._sauvegarder_etat()
        return True

    def get_resume(self):
        """Retourne un résumé des enregistrements"""
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
    """
    Thread de téléopération avec 2 caméras (architecture LeRobot).
    Les caméras ont leurs propres threads de lecture.
    Ce thread récupère les dernières frames de manière non-bloquante.
    """
    global stop_threads, pause_teleop

    frame_interval = 1.0 / CONFIG['fps']
    last_record_time = 0

    while not stop_threads:
        loop_start = time.time()

        # Si en pause, ne pas envoyer de commandes aux servos
        if pause_teleop:
            time.sleep(0.05)
            continue

        # Lire positions Leader
        positions_leader = []
        positions_follower = []

        for servo_id in range(1, 7):
            pos_l, result, _ = lk.read2ByteTxRx(lp, servo_id, 56)
            if result == 0:
                positions_leader.append(float(pos_l))

                # Mapper et envoyer au Follower
                pos_f = mapper_position(pos_l, servo_id, calib_l, calib_f, servos_miroir)
                fk.write2ByteTxRx(fp, servo_id, 42, pos_f)

                # Lire position réelle Follower
                pos_f_real, _, _ = fk.read2ByteTxRx(fp, servo_id, 56)
                positions_follower.append(float(pos_f_real))
            else:
                positions_leader.append(2048.0)
                positions_follower.append(2048.0)

        # Récupérer les frames des caméras (non-bloquant via async_read)
        frame_top = None
        frame_follower = None

        if cam_top and cam_top.is_connected:
            frame_top = cam_top.async_read()

        if cam_follower and cam_follower.is_connected:
            frame_follower = cam_follower.async_read()

        # Enregistrer si actif (à la bonne fréquence)
        current_time = time.time()
        if recorder.is_recording and (current_time - last_record_time >= frame_interval):
            recorder.record_frame(positions_follower, positions_leader, frame_top, frame_follower)
            last_record_time = current_time

        # Maintenir la fréquence
        elapsed = time.time() - loop_start
        if elapsed < 0.01:
            time.sleep(0.01 - elapsed)


# ============================================
# THREAD DE LECTURE CLAVIER
# ============================================

def keyboard_thread():
    """Thread pour lire les commandes clavier"""
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
                    if ch in ['D', 'T', 'A', 'S', 'Q', '1', '2', '3', '4', '5', 'M', 'R', 'O']:
                        cmd_queue.put(ch)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    except:
        # Fallback si termios pas disponible
        while not stop_threads:
            try:
                cmd = input().strip().upper()
                if cmd:
                    cmd_queue.put(cmd[0])
            except:
                pass

def get_command():
    """Récupère une commande si disponible"""
    try:
        return cmd_queue.get_nowait()
    except queue.Empty:
        return None

# ============================================
# ÉCRANS D'INTERFACE
# ============================================

def afficher_instructions():
    """Affiche les instructions complètes"""
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                         INSTRUCTIONS                                  ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  OBJECTIF : Enregistrer 50 démonstrations de la tâche                ║
║             "Prendre un cube et le déposer dans la boîte"            ║
║                                                                       ║
║  DISPOSITION DES POSITIONS :                                          ║
║                                                                       ║
║                    Position 3 (Haut/Loin)                            ║
║                           ●                                           ║
║                           |                                           ║
║       Position 4 ● ───────●─────── ● Position 5                      ║
║       (Gauche)      Position 1       (Droite)                        ║
║          |           (Centre)           |                            ║
║       [BOÎTE]                        [BOÎTE]                         ║
║                           |                                           ║
║                           ●                                           ║
║                    Position 2 (Bas/Proche)                           ║
║                                                                       ║
║                        🤖 ROBOT                                       ║
║                                                                       ║
╠══════════════════════════════════════════════════════════════════════╣
║  CONTRÔLES PENDANT L'ENREGISTREMENT :                                ║
║                                                                       ║
║    D = Démarrer l'enregistrement                                     ║
║    T = Terminer l'épisode (succès)                                   ║
║    A = Annuler l'épisode en cours                                    ║
║    S = Stopper la session                                            ║
║                                                                       ║
╠══════════════════════════════════════════════════════════════════════╣
║  CONSEILS :                                                           ║
║  • Gardez la caméra fixe                                             ║
║  • Soyez cohérent dans vos gestes                                    ║
║  • Le cube doit toujours être visible à la caméra                    ║
║  • 10 épisodes par position = 50 épisodes au total                   ║
║                                                                       ║
╚══════════════════════════════════════════════════════════════════════╝

    Appuyez sur ENTRÉE pour revenir au menu...""")
    input()

def afficher_menu_principal(recorder):
    """Affiche le menu principal"""
    clear_screen()

    # Construire le statut des positions
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
║                                                                       ║
║  🎮 TÉLÉOPÉRATION ACTIVE - Bougez le Leader, le Follower suit        ║
║                                                                       ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  1. 📖 Lire les instructions                                         ║
║                                                                       ║
║  2. 🧪 Test rapide (2 épisodes)                                      ║
║                                                                       ║
║  3. 📹 Enregistrer 10 épisodes pour une position :                   ║
║                                                                       ║
{chr(10).join(pos_status)}
║                                                                       ║
║  4. 👁️  Visualiser vos datasets                                      ║
║                                                                       ║
║  5. 🗑️  Effacer des données                                          ║
║                                                                       ║
║  Q. 🚪 Quitter (affiche le résumé)                                   ║
║                                                                       ║
╚══════════════════════════════════════════════════════════════════════╝

    Votre choix : """, end="", flush=True)

def menu_effacer_donnees(recorder):
    """Menu pour effacer des données"""

    while True:
        clear_screen()

        # Construire le statut des positions
        pos_lines = []
        for pos_id in range(1, 6):
            count = recorder.episodes_par_position[pos_id]
            pos_lines.append(f"║     {pos_id}. {POSITIONS[pos_id]['nom']:8} ({count} épisodes)                                  ║")

        total = sum(recorder.episodes_par_position.values())

        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║           EFFACER DES DONNÉES                                        ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  1-5. Effacer une position spécifique :                              ║
║                                                                       ║
{chr(10).join(pos_lines)}
║                                                                       ║
║  T. 🗑️  TOUT effacer ({total} épisodes)                               ║
║                                                                       ║
║  R. ↩️  Retour au menu                                               ║
║                                                                       ║
╚══════════════════════════════════════════════════════════════════════╝

    Votre choix : """, end="", flush=True)

        # Attendre un choix avec get_command()
        choix = None
        while choix is None and not stop_threads:
            cmd = get_command()
            if cmd in ['1', '2', '3', '4', '5', 'T', 'R']:
                choix = cmd
            refresh_display()

        if stop_threads:
            return

        if choix == 'R':
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

def session_enregistrement(recorder, position_id, num_episodes, lk, lp, fk, fp, calib_l, calib_f):
    """Gère une session d'enregistrement pour une position"""
    global stop_threads, pause_teleop

    pos_name = POSITIONS[position_id]['nom']
    episodes_done = 0

    while episodes_done < num_episodes and not stop_threads:
        current_count = recorder.episodes_par_position[position_id]

        clear_screen()
        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║  ENREGISTREMENT - Position {position_id} ({pos_name:8})                          ║
║  Épisodes : {current_count}/{current_count + num_episodes - episodes_done} (session) | Total: {current_count}/{CONFIG['episodes_per_position']}              ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  📍 Placez le cube à la position {pos_name:8}                            ║
║                                                                       ║
║  Commandes :                                                          ║
║    D = Démarrer l'enregistrement                                     ║
║    T = Terminer l'épisode (succès)                                   ║
║    A = Annuler l'épisode                                             ║
║    S = Stopper et revenir au menu                                    ║
║                                                                       ║
║  État : ⏸️  EN ATTENTE - Appuyez sur D pour démarrer                  ║
║                                                                       ║
╚══════════════════════════════════════════════════════════════════════╝
        """)

        # Attendre commande D ou S
        while not stop_threads:
            cmd = get_command()
            if cmd == 'D':
                break
            elif cmd == 'S':
                return episodes_done
            refresh_display()

        if stop_threads:
            break

        # Démarrer l'enregistrement
        recorder.start_episode(position_id)

        clear_screen()
        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║  🔴 ENREGISTREMENT EN COURS - Position {position_id} ({pos_name:8})              ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  🎬 Effectuez la tâche : Prenez le cube → Déposez dans la boîte      ║
║                                                                       ║
║  Commandes :                                                          ║
║    T = Terminer l'épisode (succès)                                   ║
║    A = Annuler l'épisode                                             ║
║    S = Stopper la session                                            ║
║                                                                       ║
╚══════════════════════════════════════════════════════════════════════╝
        """)

        # Attendre T, A ou S
        start_time = time.time()
        while not stop_threads:
            cmd = get_command()

            if cmd == 'T':
                # Terminer avec succès
                if recorder.save_episode():
                    episodes_done += 1
                    print(f"\n✅ Épisode sauvegardé! ({episodes_done}/{num_episodes} cette session)")

                    # Repositionnement automatique vers position repos
                    print("\n🏁 Repositionnement automatique vers position repos.")
                    input("   Appuyez sur Entrée pour continuer...")

                    # Suspendre la téléopération pendant le repositionnement
                    pause_teleop = True
                    time.sleep(0.1)  # Laisser le thread se mettre en pause

                    # Activer tous les servos pour le mouvement
                    for i in range(1, 7):
                        lk.write1ByteTxRx(lp, i, 40, 1)
                        fk.write1ByteTxRx(fp, i, 40, 1)

                    position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)

                    # Libérer Leader, Activer Follower pour reprendre téléopération
                    for i in range(1, 7):
                        lk.write1ByteTxRx(lp, i, 40, 0)
                        fk.write1ByteTxRx(fp, i, 40, 1)

                    # Reprendre la téléopération
                    pause_teleop = False

                    print("✅ Robots en position. Replacez le cube.")
                break

            elif cmd == 'A':
                # Annuler
                recorder.cancel_episode()
                print("\n↩️  Épisode annulé, on recommence...")
                time.sleep(1)
                break

            elif cmd == 'S':
                # Stopper
                recorder.cancel_episode()
                return episodes_done

            # Afficher durée
            elapsed = time.time() - start_time
            frames = len(recorder.current_episode_data)
            print(f"\r  ⏱️  {elapsed:.1f}s | Frames: {frames}   ", end="", flush=True)

            refresh_display()

    return episodes_done

# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main():
    global stop_threads, cmd_queue

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

    # ========================================
    # ÉTAPE 1 : Identification des CAMÉRAS
    # ========================================
    cam_top_index, cam_follower_index = identification_cameras()

    if cam_top_index is None and cam_follower_index is None:
        print("\n❌ Aucune caméra identifiée. Continuer quand même? (O/N)")
        if input().upper() != 'O':
            return

    input("\n✅ Caméras identifiées. Appuyez sur ENTRÉE pour continuer avec les robots...")

    # ========================================
    # ÉTAPE 2 : Identification des ROBOTS
    # ========================================
    result = identification_guidee()
    if not result[0]:
        print("❌ Identification échouée")
        return

    lp, lk, fp, fk, calib_l, calib_f = result

    # Choix du mode
    print("\n[C]ôte à côte ou [F]ace à face?")
    choix = input("Choix [C]: ").upper()
    mode = "face" if choix == 'F' else "cote"
    servos_miroir = charger_config_teleoperation(mode)

    # Positionnement initial
    print("\n🎯 Positionnement automatique...")
    centrage_parallele(lk, lp, fk, fp, calib_l, calib_f)
    time.sleep(0.5)
    position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)

    # Libérer Leader, Activer Follower
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 0)  # Leader libre
        fk.write1ByteTxRx(fp, i, 40, 1)  # Follower actif

    # ========================================
    # ÉTAPE 3 : Connexion des CAMÉRAS avec threads
    # ========================================
    cam_top = None
    cam_follower = None

    if CV2_AVAILABLE:
        print("\n📷 Connexion des caméras identifiées...")

        # Utiliser les index identifiés par l'utilisateur
        if cam_top_index is not None:
            cam_top = ThreadedCamera(
                cam_top_index, CAM_TOP,
                CONFIG['camera_width'], CONFIG['camera_height'], CONFIG['fps']
            )
            cam_top.connect()

        if cam_follower_index is not None:
            cam_follower = ThreadedCamera(
                cam_follower_index, CAM_FOLLOWER,
                CONFIG['camera_width'], CONFIG['camera_height'], CONFIG['fps']
            )
            cam_follower.connect()

        if cam_top is None and cam_follower is None:
            print("   ⚠️  Aucune caméra connectée")

    # Créer le recorder
    recorder = DatasetRecorder()

    # Démarrer threads
    stop_threads = False
    cmd_queue = queue.Queue()

    # Thread de téléopération (utilise async_read des caméras)
    teleop_t = threading.Thread(
        target=teleoperation_thread,
        args=(lk, lp, fk, fp, calib_l, calib_f, servos_miroir, recorder, cam_top, cam_follower),
        daemon=True
    )
    teleop_t.start()

    # Thread d'affichage → remplacé par refresh_display() dans le thread principal
    global _display_cam_top, _display_cam_follower
    _display_cam_top = cam_top
    _display_cam_follower = cam_follower

    # Thread clavier
    kb_t = threading.Thread(target=keyboard_thread, daemon=True)
    kb_t.start()

    print("\n✅ Téléopération active!")
    print("⚠️  Tenez le LEADER")
    time.sleep(2)

    # Boucle menu principal
    try:
        while not stop_threads:
            afficher_menu_principal(recorder)

            # Attendre choix
            choix = None
            while choix is None and not stop_threads:
                cmd = get_command()
                if cmd in ['1', '2', '3', '4', '5', 'Q', 'M']:
                    choix = cmd
                refresh_display()

            if stop_threads or choix == 'Q':
                break

            if choix == '1':
                afficher_instructions()

            elif choix == '2':
                # Test rapide
                print("\n🧪 Test rapide - Choisissez une position (1-5): ", end="", flush=True)
                pos = None
                while pos is None and not stop_threads:
                    cmd = get_command()
                    if cmd in ['1', '2', '3', '4', '5']:
                        pos = int(cmd)
                    refresh_display()

                if pos:
                    session_enregistrement(recorder, pos, 2, lk, lp, fk, fp, calib_l, calib_f)

            elif choix == '3':
                # Enregistrer 10 épisodes
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
                        done = session_enregistrement(recorder, pos, remaining, lk, lp, fk, fp, calib_l, calib_f)
                        if done > 0:
                            print(f"\n✅ {done} épisodes enregistrés pour la position {pos}!")
                            time.sleep(2)

            elif choix == '4':
                # Visualiser datasets
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
                # Effacer des données
                menu_effacer_donnees(recorder)

            elif choix in ['1', '2', '3', '4', '5']:
                # Accès direct à une position depuis le menu
                pos = int(choix)
                remaining = CONFIG['episodes_per_position'] - recorder.episodes_par_position[pos]
                if remaining <= 0:
                    print(f"\n✅ Position {pos} déjà complète!")
                    time.sleep(2)
                else:
                    done = session_enregistrement(recorder, pos, remaining, lk, lp, fk, fp, calib_l, calib_f)
                    if done > 0:
                        print(f"\n✅ {done} épisodes enregistrés pour la position {pos}!")
                        time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interruption...")

    finally:
        stop_threads = True

        # Attendre un peu pour que les threads s'arrêtent
        time.sleep(0.5)

        # Fermer les caméras (ThreadedCamera)
        if cam_top:
            cam_top.disconnect()
        if cam_follower:
            cam_follower.disconnect()

        cv2.destroyAllWindows()

        # Afficher résumé
        print(recorder.get_resume())

        # Position repos
        print("\n🏁 Retour position repos...")
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 1)
            fk.write1ByteTxRx(fp, i, 40, 1)

        position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)

        print("\n⚠️  Assurez-vous de tenir les robots")
        time.sleep(2)

        # Libération finale
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 0)
            fk.write1ByteTxRx(fp, i, 40, 0)

        lp.closePort()
        fp.closePort()

        print("\n✅ Session terminée!")

if __name__ == "__main__":
    main()
