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

# Module de configuration caméra (verrouillage matériel des réglages).
# Import protégé : si le module est absent, mal placé ou cassé, on le signalera par un
# message clair + arrêt propre plus bas, au lieu d'un traceback illisible au démarrage.
try:
    from SEM_so101_camera_config import verrouiller_camera
    CAMERA_LOCK_AVAILABLE = True
    CAMERA_LOCK_IMPORT_ERROR = None
except Exception as _e_config_canonique:
    try:
        from SEM_so101_8_camera_config import verrouiller_camera
        CAMERA_LOCK_AVAILABLE = True
        CAMERA_LOCK_IMPORT_ERROR = None
    except Exception:
        try:
            from SEM_8_camera_config import verrouiller_camera
            CAMERA_LOCK_AVAILABLE = True
            CAMERA_LOCK_IMPORT_ERROR = None
        except Exception as e:
            verrouiller_camera = None
            CAMERA_LOCK_AVAILABLE = False
            CAMERA_LOCK_IMPORT_ERROR = _e_config_canonique

# Module de qualité caméra (étape 5) : contrôle de QUALITÉ ABSOLUE de l'image
# (exploitable : ni noire, ni cramée, ni instable), au démarrage et avant chaque
# bloc — sans référence colorimétrique ni matching.
# Décision validée (Q1) : sans ce module, on N'ENREGISTRE PAS (fail closed),
# même logique que le module de configuration caméra ci-dessus.
try:
    from SEM_so101_camera_reference import controle_qualite_camera
    CAMERA_QUALITY_AVAILABLE = True
    CAMERA_QUALITY_IMPORT_ERROR = None
except Exception as e:
    controle_qualite_camera = None
    CAMERA_QUALITY_AVAILABLE = False
    CAMERA_QUALITY_IMPORT_ERROR = e

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
    2: {"nom": "Libre", "description": "Position libre"},
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
keyboard_pause = False
cmd_queue = queue.Queue()

# Instances caméra pour l'affichage dans le thread principal
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

        # Forcer le format MJPG aide souvent sur Linux pour les hautes
        # résolutions ; surtout, il UNIFIE l'acquisition entre l'enregistrement,
        # le déploiement et le module qualité caméra (mêmes conditions caméra).
        self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.camera.set(cv2.CAP_PROP_FPS, self.fps)

        # Warmup : lire 5 frames pour vider le buffer matériel (les premières sont souvent
        # corrompues) et garder la dernière valide. Acquisition (MJPG + warmup)
        # alignée sur le script de déploiement.
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

    def async_read(self):
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None

    def disconnect(self):
        if self.thread is not None:
            self.stop_event.set()
            self.thread.join(timeout=2.0)
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
    """Identification VISUELLE des deux caméras (globale cam_top + pince cam_follower).
    Les deux caméras du projet sont identiques : aucune détection automatique possible.
    Parcourt TOUTES les caméras détectées (pas seulement les deux premières) ; pour
    chacune dont l'image est lisible, affiche le flux et demande G/P/Q. S'arrête dès
    que les DEUX sont identifiées. AUCUNE auto-assignation : cam_top et cam_follower
    doivent être désignées explicitement (exigence d'intégrité du dataset)."""
    if not CV2_AVAILABLE:
        print("❌ OpenCV non disponible")
        return None, None

    print("\n" + "="*60)
    print("📷 IDENTIFICATION DES CAMÉRAS")
    print("="*60)
    cameras = detect_cameras()
    print(f"\n🔍 Caméras détectées: {cameras}")

    if len(cameras) < 2:
        print("❌ Deux caméras sont requises (globale + pince) pour l'enregistrement.")
        print(f"   Détecté : {len(cameras)} caméra(s). Branchez les deux caméras et relancez.")
        return None, None

    print("\n📌 Vous allez voir chaque caméra tour à tour.")
    print("   Identifiez la caméra GLOBALE (vue d'ensemble du plateau) et")
    print("   la caméra PINCE (sur le follower). Les deux étant identiques,")
    print("   distinguez-les par ce qu'elles cadrent.")
    print("\n   Appuyez sur ENTRÉE pour continuer...")
    input()

    cam_top_index = None
    cam_follower_index = None

    for idx in cameras:
        if cam_top_index is not None and cam_follower_index is not None:
            break  # les deux caméras sont identifiées, inutile de continuer
        print(f"\n🎥 Caméra index {idx}...")
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            print(f"   ❌ Impossible d'ouvrir la caméra {idx} — passée.")
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG['camera_width'])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG['camera_height'])
        window_name = f"Camera {idx} - Identifiez cette camera"

        ret, frame = cap.read()
        fenetre_ouverte = False
        if ret:
            cv2.putText(frame, f"Camera {idx}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, "Repondez dans le TERMINAL", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
            cv2.imshow(window_name, frame)
            cv2.waitKey(100)
            fenetre_ouverte = True
        cap.release()

        # Sans image lisible, l'identification visuelle est impossible : on ne propose
        # PAS cette caméra (pas de confirmation à l'aveugle) et on ne détruit pas une
        # fenêtre qui n'a jamais été affichée.
        if not fenetre_ouverte:
            print(f"   ⚠️  Image indisponible pour la caméra {idx} — identification impossible, on passe.")
            continue

        print(f"   📺 Regardez la fenêtre '{window_name}'")
        print(f"   → Tapez G + Entrée si c'est la caméra GLOBALE (vue d'ensemble)")
        print(f"   → Tapez P + Entrée si c'est la caméra PINCE (sur le follower)")
        print(f"   → Tapez Q + Entrée pour passer")
        choix_cam = input("   Votre choix : ").strip().upper()
        cv2.destroyWindow(window_name)
        cv2.waitKey(1)

        if choix_cam == 'G':
            cam_top_index = idx
            print(f"   ✅ Caméra {idx} = {CAM_TOP} (globale)")
        elif choix_cam == 'P':
            cam_follower_index = idx
            print(f"   ✅ Caméra {idx} = {CAM_FOLLOWER} (pince)")
        else:
            print(f"   ⏭️  Caméra {idx} passée")

    cv2.destroyAllWindows()
    cv2.waitKey(1)

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

MIN_AMPLITUDE = 500

# Fichier externe centralisant la position repos (partage entre tous les scripts)
REPOS_FILE = os.path.expanduser("~/lerobot/calibration/repos_position.json")

def detect_ports():
    """Détecte les ports des robots (liste).

    Teste chaque port candidat en interrogeant le servo 1 : ne garde que les
    ports qui répondent au protocole servo (= robots). Les autres périphériques
    série sont ignorés. La téléopération a besoin des deux robots ; l'identification
    guidée s'appuie sur le nombre exact de ports attendus.
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
                if result == COMM_SUCCESS:
                    ports.append(port)
        except Exception:
            # Périphérique série qui se comporte mal : on l'ignore proprement
            pass
        finally:
            try:
                ph.closePort()
            except Exception:
                pass
    return ports

# ----------------------------------------------------------------------------
# Politique de gestion des erreurs (lecture de position) :
# Certains servos Feetech peuvent renvoyer un octet de statut interne non nul
# tout en conservant une position parfaitement lisible. Seul l'echec de
# communication (result != COMM_SUCCESS) invalide la lecture ; l'octet de
# statut interne est ignore (tolere silencieusement, contexte teleoperation).
# Cause a identifier sur la table de controle Feetech STS3215 (hors urgence).
# Regle limitee aux LECTURES ; ecritures/mouvements traites au cas par cas.
# ----------------------------------------------------------------------------
def lire_position(packet, port, servo_id):
    """Lecture de la position (registre 56). Retourne (position, ok).

    Seule une vraie panne de communication (result) invalide la lecture.
    L'octet de statut interne du servo est ignore (tolere silencieusement,
    contexte teleoperation) : la position reste valide ; la cause de ce
    statut n'est PAS presumee ici, elle reste a identifier.
    """
    pos, result, _ = packet.read2ByteTxRx(port, servo_id, 56)
    if result != COMM_SUCCESS:
        return None, False
    return pos, True

def cleanup_ports(lp=None, fp=None, lk=None, fk=None, release=True):
    """Nettoyage best-effort, idempotent et tolérant aux initialisations partielles.
    Libère les servos (si les handlers existent) puis ferme les ports ouverts.
    Ne lève jamais d'exception (appelable dans un finally ou avant un retour d'échec)."""
    if release:
        for pk, ph in ((lk, lp), (fk, fp)):
            if pk is not None and ph is not None:
                for i in range(1, 7):
                    try:
                        pk.write1ByteTxRx(ph, i, 40, 0)
                    except Exception:
                        pass
    for ph in (lp, fp):
        if ph is not None:
            try:
                ph.closePort()
            except Exception:
                pass

def charger_calibration(robot_type):
    """Charge la calibration d'un robot (ou None si absente/illisible)."""
    calib_file = os.path.expanduser(f"~/lerobot/calibration/{robot_type}_calibration.json")
    if os.path.exists(calib_file):
        try:
            with open(calib_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    return None

def calibration_complete(calibration):
    """Vrai uniquement si les 6 servos sont calibres avec une plage exploitable
    (presents, min/max/center numeriques, amplitude >= MIN_AMPLITUDE, min<=center<=max).
    Meme exigence que les scripts 4/5. Sans calibration valide, le mapping retomberait
    sur 0-4095 -> risque de butees sur le Follower piloté."""
    if not calibration:
        return False
    for i in range(1, 7):
        key = f"servo_{i}"
        if key not in calibration:
            return False
        cal = calibration[key]
        min_v = cal.get("min")
        max_v = cal.get("max")
        center_v = cal.get("center")
        if not isinstance(min_v, (int, float)) or not isinstance(max_v, (int, float)):
            return False
        if max_v - min_v < MIN_AMPLITUDE:
            return False
        if not isinstance(center_v, (int, float)):
            return False
        if not (min_v <= center_v <= max_v):
            return False
    return True

def charger_repos_pct():
    """Charge la position repos (% par servo) depuis le fichier externe.
    Retourne (dict {1:%,...}, origine) ou origine vaut 'custom' ou 'default'.
    Valide le contenu ; le fallback par defaut est ANNONCE par l'appelant."""
    defaut = {1: 50, 2: 10, 3: 88, 4: 76, 5: 50, 6: 11}
    if not os.path.exists(REPOS_FILE):
        return defaut, "default"
    try:
        with open(REPOS_FILE, 'r') as f:
            data = json.load(f)
        repos = {int(k): float(v) for k, v in data.items()}
        for i in range(1, 7):
            if i not in repos or not (0.0 <= repos[i] <= 100.0):
                return defaut, "default"
        return repos, "custom"
    except Exception:
        return defaut, "default"

def valider_servos_miroir(data):
    """Valide une valeur 'servos_miroir' : liste d'entiers 1-6, sans doublon.
    Retourne la liste triee, ou None si invalide. Une liste vide est VALIDE
    (configuration tout-COPIE)."""
    if not isinstance(data, list):
        return None
    vus = set()
    for v in data:
        if isinstance(v, bool) or not isinstance(v, int):
            return None
        if v < 1 or v > 6 or v in vus:
            return None
        vus.add(v)
    return sorted(vus)

def charger_servos_miroir_fichier(path):
    """Lit un fichier de config telleop et renvoie la liste servos_miroir validee,
    ou None si le fichier est illisible / mal forme / invalide."""
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict) or 'servos_miroir' not in data:
        return None
    return valider_servos_miroir(data['servos_miroir'])

def charger_config_teleoperation(mode):
    """Charge la config COPIE/MIROIR du mode. Retourne la liste servos_miroir
    VALIDÉE (entiers 1-6, sans doublon ; liste vide = tout-COPIE, valide), ou None
    si le fichier est ABSENT, illisible ou mal formé. Le script 6 REFUSE alors de
    lancer ce mode (au démarrage) ou de basculer dessus (flip F)."""
    config_file = os.path.expanduser(f"~/lerobot/calibration/teleoperation_config_{mode}.json")
    if not os.path.exists(config_file):
        return None
    miroir = charger_servos_miroir_fichier(config_file)
    if miroir is None:
        return None
    print(f"  📁 Configuration chargée : {config_file}")
    return miroir

def _cible_ticks(calib, servo_id, pct):
    """Convertit un pourcentage en ticks (calibration garantie valide au demarrage)."""
    min_val = calib[f'servo_{servo_id}']['min']
    max_val = calib[f'servo_{servo_id}']['max']
    return int(min_val + (max_val - min_val) * pct / 100)

def _est_en_repos_1robot(packet, port, calib, repos_pct, tolerance_pct=5):
    """True si le robot est proche de la position repos (tous les servos).
    False si au moins un servo en est eloigne. None si une lecture echoue
    (etat indetermine -> l'appelant doit annuler la sequence)."""
    for i in range(1, 7):
        pos, ok = lire_position(packet, port, i)
        if not ok:
            return None
        min_val = calib[f'servo_{i}']['min']
        max_val = calib[f'servo_{i}']['max']
        pct_actuel = (pos - min_val) / (max_val - min_val) * 100 if max_val > min_val else 50
        if abs(pct_actuel - repos_pct.get(i, 50)) > tolerance_pct:
            return False
    return True

def mouvement_fluide(packet, port, servo, debut, fin, duree=1.5):
    """Mouvement fluide entre deux positions (interpolation cosinus)."""
    steps = int(duree * 50)
    for i in range(steps + 1):
        t = i / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        pos = int(debut + (fin - debut) * smooth)
        packet.write2ByteTxRx(port, servo, 42, pos)
        time.sleep(duree / steps)

def mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, servos, duree=2.0):
    """Déplace les servos indiqués sur Leader ET Follower vers cibles_pct (%).
    Lectures de départ vérifiées : retourne None si une lecture échoue (mouvement
    annulé), True sinon."""
    pos_l, pos_f = {}, {}
    for s in servos:
        p, ok = lire_position(lk, lp, s)
        if not ok:
            print(f"❌ Lecture Leader servo {s} impossible — mouvement annulé")
            return None
        pos_l[s] = p
        p, ok = lire_position(fk, fp, s)
        if not ok:
            print(f"❌ Lecture Follower servo {s} impossible — mouvement annulé")
            return None
        pos_f[s] = p
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
    return True


def aller_a_position_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, duree=2.0):
    """Déplace Leader ET Follower vers cibles_pct (%) via la séquence sûre
    (servo 4 en l'air d'abord, etc.), appliquée à l'identique aux deux robots.
    Lectures vérifiées partout : retourne None si une lecture critique échoue
    (mouvement annulé), True sinon.

    Phase 0 (par robot) : si servo 4 > 2700 et robot pas en repos, lever le bras
    (servo 2 -> min(actuel, 1027)) pour dégager la pince du sol. La levée se fait
    EN PARALLÈLE sur les deux robots (cohérent avec les scripts 8/11). 2700 et 1027
    sont des réglages empiriques de l'installation, identiques aux scripts 4 et 5."""
    # Activer tous les servos
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 1)
        fk.write1ByteTxRx(fp, i, 40, 1)

    repos_pct, _ = charger_repos_pct()

    # --- Phase 0 (conditionnelle, par robot, exécutée EN PARALLÈLE) ---
    # Lectures vérifiées : toute lecture critique ratée annule le mouvement.
    pos4_l, ok = lire_position(lk, lp, 4)
    if not ok:
        print("❌ Lecture Leader servo 4 impossible — mouvement annulé")
        return None
    pos4_f, ok = lire_position(fk, fp, 4)
    if not ok:
        print("❌ Lecture Follower servo 4 impossible — mouvement annulé")
        return None

    besoin_l = False
    if pos4_l > 2700:
        etat = _est_en_repos_1robot(lk, lp, cl, repos_pct)
        if etat is None:
            print("❌ État repos Leader indéterminé — mouvement annulé")
            return None
        besoin_l = not etat
    besoin_f = False
    if pos4_f > 2700:
        etat = _est_en_repos_1robot(fk, fp, cf, repos_pct)
        if etat is None:
            print("❌ État repos Follower indéterminé — mouvement annulé")
            return None
        besoin_f = not etat

    if besoin_l or besoin_f:
        deb_l = deb_f = None
        if besoin_l:
            deb_l, ok = lire_position(lk, lp, 2)
            if not ok:
                print("❌ Lecture Leader servo 2 impossible — mouvement annulé")
                return None
        if besoin_f:
            deb_f, ok = lire_position(fk, fp, 2)
            if not ok:
                print("❌ Lecture Follower servo 2 impossible — mouvement annulé")
                return None
        fin_l = min(deb_l, 1027) if besoin_l else None
        fin_f = min(deb_f, 1027) if besoin_f else None
        steps = int(duree * 50)
        for step in range(steps + 1):
            t = step / steps
            smooth = (1 - math.cos(t * math.pi)) / 2
            if besoin_l:
                lk.write2ByteTxRx(lp, 2, 42, int(deb_l + (fin_l - deb_l) * smooth))
            if besoin_f:
                fk.write2ByteTxRx(fp, 2, 42, int(deb_f + (fin_f - deb_f) * smooth))
            time.sleep(duree / steps)

    # --- Phase 1 : servo 4 -> 20% ---
    if mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, {4: 20}, [4], duree) is None:
        return None
    # --- Phase 2 : servos 1,2,3,5,6 ---
    if mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, [1, 2, 3, 5, 6], duree) is None:
        return None
    # --- Phase 3 : servo 4 -> cible finale ---
    if mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, [4], duree) is None:
        return None
    return True


def test_connexion_fluide(packet, port, robot_name, calib):
    """Test fluide de connexion : fait bouger la pince (servo 6) pour confirmer
    visuellement le bon robot. Calibration GARANTIE valide (validée au démarrage),
    pas de fallback brut. Retourne False si la lecture échoue."""
    print(f"\n  🔄 Test de connexion {robot_name}...")

    # Activer le servo 6
    packet.write1ByteTxRx(port, 6, 40, 1)

    centre = calib['servo_6']['center']
    min_val = calib['servo_6']['min']
    max_val = calib['servo_6']['max']
    amplitude = max_val - min_val
    pos_25 = int(min_val + amplitude * 0.25)
    pos_75 = int(min_val + amplitude * 0.75)

    pos_actuelle, ok = lire_position(packet, port, 6)
    if not ok:
        print(f"  ❌ Lecture servo 6 impossible sur {robot_name}")
        return False

    print("     → Centre...")
    mouvement_fluide(packet, port, 6, pos_actuelle, centre, 1.0)
    print("     → Pince fermée...")
    mouvement_fluide(packet, port, 6, centre, pos_25, 0.8)
    print("     → Pince ouverte...")
    mouvement_fluide(packet, port, 6, pos_25, pos_75, 1.2)
    print("     → Centre...")
    mouvement_fluide(packet, port, 6, pos_75, centre, 0.8)

    print(f"  ✅ {robot_name} connecté et testé")
    return True

def identification_guidee(calib_l, calib_f):
    """Identifie Leader et Follower avec test fluide. Calibrations déjà validées,
    passées en argument. Détection STRICTE : exactement 1 port après le Leader,
    exactement 2 après le Follower. Chaque échec (et toute exception/CTRL+C interne)
    ferme proprement les ports déjà ouverts. Retourne (True, lp, lk, fp, fk) ou
    (False, None, None, None, None)."""
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     IDENTIFICATION LEADER/FOLLOWER                      ║
╚══════════════════════════════════════════════════════════╝
    """)

    lp = fp = lk = fk = None
    try:
        # Débrancher tout
        ports = detect_ports()
        while len(ports) > 0:
            print("⚠️  Débranchez tous les robots")
            input("   Entrée quand fait...")
            ports = detect_ports()

        # LEADER
        print("\n🔌 Branchez le LEADER")
        input("   Entrée quand branché...")

        time.sleep(1)
        ports = detect_ports()
        if len(ports) != 1:
            print(f"❌ Attendu exactement 1 robot après branchement du Leader, détecté : {len(ports)}.")
            print("   Débranchez tout et recommencez (un seul adaptateur pour le Leader).")
            return False, None, None, None, None

        leader_port = ports[0]
        print(f"✅ LEADER détecté sur {leader_port}")

        lp = PortHandler(leader_port)
        lk = PacketHandler(1.0)
        if not lp.openPort() or not lp.setBaudRate(1000000):
            print("❌ Erreur connexion Leader")
            cleanup_ports(lp, None, lk, None)
            return False, None, None, None, None

        if not test_connexion_fluide(lk, lp, "LEADER", calib_l):
            cleanup_ports(lp, None, lk, None)
            return False, None, None, None, None

        if input("\nPince du LEADER bougée? [O/N]: ").strip().upper() != 'O':
            cleanup_ports(lp, None, lk, None)
            return False, None, None, None, None

        # FOLLOWER
        print("\n🔌 Branchez le FOLLOWER (gardez Leader branché)")
        input("   Entrée quand branché...")

        time.sleep(1)
        ports = detect_ports()
        if len(ports) != 2:
            print(f"❌ Attendu exactement 2 robots après branchement du Follower, détecté : {len(ports)}.")
            cleanup_ports(lp, None, lk, None)
            return False, None, None, None, None

        follower_port = ports[1] if ports[0] == leader_port else ports[0]
        print(f"✅ FOLLOWER détecté sur {follower_port}")

        fp = PortHandler(follower_port)
        fk = PacketHandler(1.0)
        if not fp.openPort() or not fp.setBaudRate(1000000):
            print("❌ Erreur connexion Follower")
            cleanup_ports(lp, fp, lk, fk)
            return False, None, None, None, None

        if not test_connexion_fluide(fk, fp, "FOLLOWER", calib_f):
            cleanup_ports(lp, fp, lk, fk)
            return False, None, None, None, None

        if input("\nPince du FOLLOWER bougée? [O/N]: ").strip().upper() != 'O':
            cleanup_ports(lp, fp, lk, fk)
            return False, None, None, None, None

        print("\n✅ Identification réussie!")
        return True, lp, lk, fp, fk

    except BaseException:
        # Exception ou CTRL+C avant le retour : fermer les ports ouverts localement
        cleanup_ports(lp, fp, lk, fk)
        raise

def position_repos_parallele(lk, lp, fk, fp, cl, cf):
    """Met les deux robots en position repos (séquence sûre partagée). Fallback
    repos ANNONCÉ. Retourne False si une lecture critique échoue (mouvement
    annulé), True sinon."""
    print("\n🏁 Position repos simultanée...")
    repos_pct, origine = charger_repos_pct()
    if origine == "default":
        print("⚠️  repos_position.json absent ou invalide — position de repos PAR DÉFAUT utilisée.")
    if aller_a_position_2robots(lk, lp, fk, fp, cl, cf, repos_pct, duree=2.0) is None:
        print("⚠️  Retour repos incomplet (lecture servo) — vérifiez la posture des robots.")
        return False
    print("✅ Position repos atteinte")
    return True

def mapper_position(pos_leader, servo_id, calib_leader, calib_follower, servos_miroir):
    """Mapping proportionnel Leader -> Follower avec COPIE/MIROIR (calibration
    garantie valide), borné sur les limites Follower, retour int."""
    min_l = calib_leader[f"servo_{servo_id}"]["min"]
    max_l = calib_leader[f"servo_{servo_id}"]["max"]
    min_f = calib_follower[f"servo_{servo_id}"]["min"]
    max_f = calib_follower[f"servo_{servo_id}"]["max"]

    ratio = (pos_leader - min_l) / (max_l - min_l) if max_l > min_l else 0.5
    ratio = max(0, min(1, ratio))

    if servo_id in servos_miroir:
        ratio = 1 - ratio

    return int(max(min_f, min(max_f, int(min_f + ratio * (max_f - min_f)))))

def choisir_mode():
    """Choix explicite de la disposition (boucle jusqu'à C ou F)."""
    print("\n[C]ôte à côte ou [F]ace à face ?")
    while True:
        c = input("Choix [C/F] : ").strip().upper()
        if c == 'C':
            return "cote", "CÔTÉ À CÔTÉ"
        if c == 'F':
            return "face", "FACE À FACE"
        print("❌ Choix invalide : tapez C ou F")

# Fichier externe du masque de zone utile (cree par le script 7, partage avec le 11)
MASK_FILE = os.path.expanduser("~/lerobot/calibration/camera_mask.json")


def charger_masque_globale():
    """Lit et VALIDE STRICTEMENT le masque cam_top (MASK_FILE, cree par le script 7).
    Retourne la liste des 5 points (tuples) si valide, sinon None.
    Validation : exactement 5 points, coordonnees numeriques. Si une resolution de
    reference est presente, elle DOIT correspondre a la resolution d'enregistrement
    (CONFIG camera_width x camera_height) ; sinon le masque serait applique a la
    mauvaise echelle -> refus (le script 8 impose deja 640x360 aux frames)."""
    if not os.path.exists(MASK_FILE):
        return None
    try:
        with open(MASK_FILE, 'r') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("structure JSON invalide")
        pts_raw = data.get("points")
        if not isinstance(pts_raw, list) or len(pts_raw) != 5:
            raise ValueError("le masque doit contenir exactement 5 points")
        pts = []
        for p in pts_raw:
            if not isinstance(p, (list, tuple)) or len(p) != 2:
                raise ValueError("chaque point doit contenir exactement 2 coordonnees")
            x, y = p
            if (isinstance(x, bool) or isinstance(y, bool)
                    or not isinstance(x, (int, float)) or not isinstance(y, (int, float))):
                raise ValueError("coordonnees non numeriques")
            pts.append((int(x), int(y)))
        ref = data.get("reference_resolution", {})
        rw = ref.get("width") if isinstance(ref, dict) else None
        rh = ref.get("height") if isinstance(ref, dict) else None
        if (isinstance(rw, (int, float)) and not isinstance(rw, bool)
                and isinstance(rh, (int, float)) and not isinstance(rh, bool)):
            if int(rw) != CONFIG['camera_width'] or int(rh) != CONFIG['camera_height']:
                raise ValueError(
                    f"masque cree en {int(rw)}x{int(rh)}, attendu "
                    f"{CONFIG['camera_width']}x{CONFIG['camera_height']} (recreer via le script 7)")
        return pts
    except Exception as e:
        print(f"⚠️  Masque existant illisible ou invalide ({e}).")
        return None


def construire_mask_image(points, width, height):
    """Construit le masque binaire (uint8 0/255) à partir des points du polygone."""
    if points is None:
        return None
    mask = np.zeros((height, width), dtype=np.uint8)
    pts = np.array(points, np.int32)
    cv2.fillPoly(mask, [pts], 255)
    return mask



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
        # Lectures de position : on ne bloque que sur `result` (intégrité de la
        # communication). L'octet `error` (statut interne non identifié du servo,
        # cf. servo 2 Leader error=1 intermittent) n'invalide PAS une position tant
        # que result == COMM_SUCCESS — même règle que lire_position(). Ici, la
        # lecture Follower (état enregistré) est en plus contrôlée pour l'intégrité
        # du dataset : un instant n'est sauvegardé que si serial_ok ET les 2 images.
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
    """Lecture clavier caractère-par-caractère pour les menus d'enregistrement.

    PAUSE (keyboard_pause=True) : le thread restaure le terminal en mode
    normal et CESSE de lire stdin, pour que les input() classiques (contrôle
    caméra, contrôle qualité, confirmations) reçoivent les touches sans
    concurrence. À la reprise, le mode caractère est rétabli. Sans ce
    mécanisme, deux lecteurs se partagent stdin et se volent les touches."""
    global stop_threads, cmd_queue
    try:
        import select
        import termios
        import tty
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            while not stop_threads:
                if keyboard_pause:
                    # Rendre le terminal aux input() pendant la pause
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                    while keyboard_pause and not stop_threads:
                        time.sleep(0.1)
                    if stop_threads:
                        break
                    tty.setcbreak(sys.stdin.fileno())
                    continue
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1).upper()
                    if ch in ['D', 'T', 'A', 'S', 'Q', '1', '2', '3', '4', '5', '6', 'R', 'O']:
                        cmd_queue.put(ch)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    except:
        while not stop_threads:
            try:
                if keyboard_pause:
                    time.sleep(0.1)
                    continue
                cmd = input().strip().upper()
                if cmd:
                    cmd_queue.put(cmd[0])
            except:
                pass


def suspendre_clavier():
    """Pause du thread clavier avant des input() interactifs (laisse 0,3 s
    au thread pour restaurer le terminal)."""
    global keyboard_pause
    keyboard_pause = True
    time.sleep(0.3)


def reprendre_clavier():
    """Reprise du thread clavier après les input() ; purge les touches
    tapées entre-temps pour éviter des commandes fantômes au menu."""
    global keyboard_pause
    while True:
        try:
            cmd_queue.get_nowait()
        except queue.Empty:
            break
    keyboard_pause = False

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
║                    Position 2 (Libre)                                ║
║                                                                      ║
║                        🤖 ROBOT                                      ║
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  CONTRÔLES PENDANT L'ENREGISTREMENT :                                ║
║                                                                      ║
║    D = Démarrer (retour repos automatique avant enregistrement)      ║
║    T = Terminer + sauvegarder (retour repos hors enregistrement)     ║
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
║           ENREGISTREMENT DATASET SO-ARM 101 - Phase 7                ║
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
        repos_pct, _ = charger_repos_pct()
        deja_repos = (_est_en_repos_1robot(lk, lp, calib_l, repos_pct)
                      and _est_en_repos_1robot(fk, fp, calib_f, repos_pct))
        if not deja_repos:
            print("\n🏁 Repositionnement automatique vers repos...")
            if not position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f):
                print("❌ Retour repos impossible — session interrompue.")
                return episodes_done
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
            if not position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f):
                print("❌ Repositionnement à repos impossible — vérifiez la posture des robots.")
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
                repos_pct_t, _ = charger_repos_pct()
                if aller_a_position_2robots(lk, lp, fk, fp, calib_l, calib_f, repos_pct_t, duree=2.0) is None:
                    print("❌ Retour repos impossible — session interrompue.")
                    return episodes_done
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

def controle_camera_bloc(pos, cam_top, cam_top_index, cam_follower,
                         cam_follower_index, lk, lp, fk, fp, calib_l, calib_f):
    """Contrôle caméra avant un bloc d'enregistrement (spec multi-caméra
    §5 ; décision Q2 : appliqué au bloc complet ET au test rapide).

    Les DEUX caméras sont contrôlées, l'une après l'autre (jamais en
    parallèle — règle d'architecture du module) ; l'enregistrement n'est
    autorisé que si LES DEUX images sont exploitables.

    Séquence (le module mesure avec SA propre capture, caméras du script
    LIBÉRÉES) :
      1. robots au repos, maintenus (scène stable) ;
      2. les deux caméras du script libérées ;
      3. contrôle GLOBALE puis contrôle PINCE — autorisation = ET ;
      4. reconnexion des deux + vérification résolution + verrouillage
         (un réglage [R] a pu changer les réglages) ;
      5. reprise de la téléopération.
    Retourne True si l'enregistrement du bloc est autorisé."""
    global pause_teleop
    clear_screen()
    print(f"\n📷 Contrôle des deux caméras avant le bloc (position {pos})...")

    # Le contrôle qualité (réglages [R]) utilise input() : suspension du thread
    # clavier pour qu'il ne vole pas les touches (terminal rendu au mode
    # normal), reprise + purge à la fin.
    suspendre_clavier()
    try:

        # 1) Robots au repos — scène stable et reproductible pour le contrôle qualité
        pause_teleop = True
        time.sleep(0.1)
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 1)
            fk.write1ByteTxRx(fp, i, 40, 1)
        if not position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f):
            # Retour repos échoué → scène non standardisée : on ANNULE le contrôle
            # (fail-safe). On restaure l'état téléop normal (Leader libéré,
            # Follower actif) avant de rendre la main au menu.
            print("\n❌ Position repos impossible — contrôle caméra annulé (scène non standardisée).")
            for i in range(1, 7):
                lk.write1ByteTxRx(lp, i, 40, 0)
                fk.write1ByteTxRx(fp, i, 40, 1)
            pause_teleop = False
            return False

        # 2) Libération des DEUX caméras (le module ouvre les siennes)
        if cam_top is not None:
            cam_top.disconnect()
        if cam_follower is not None:
            cam_follower.disconnect()

        # 3) Contrôles qualité séquentiels — autorisation = LES DEUX exploitables (ET).
        #    Toute exception = bloc annulé, jamais de crash. Si la première
        #    caméra annule, la seconde n'est pas contrôlée (inutile).
        autorise = True
        for nom_cam, idx_cam, lib in ((CAM_TOP, cam_top_index, "GLOBALE"),
                                      (CAM_FOLLOWER, cam_follower_index, "PINCE")):
            if not autorise:
                break
            try:
                res = controle_qualite_camera(
                    idx_cam, nom_cam,
                    contexte=f"bloc position {pos} — {lib}")
                if not bool(res.get("autorise")):
                    autorise = False
            except Exception as e:
                print(f"\n⚠️  Contrôle {lib} interrompu ({e}) — bloc annulé.")
                autorise = False

        # 4) Reconnexion des deux mêmes instances caméra +
        #    mêmes vérifications qu'au démarrage + verrouillage
        def _reconnecter(cam, idx_cam, nom_cam, lib):
            nonlocal autorise
            if cam is None:
                return
            if not cam.connect() or not cam.is_connected:
                print(f"\n❌ Caméra {lib} non reconnectée — arrêt.")
                sys.exit(1)
            frame_test = cam.async_read()
            if frame_test is not None and frame_test.shape[:2] != (CONFIG['camera_height'], CONFIG['camera_width']):
                print(f"\n❌ Résolution caméra {lib} incorrecte : {frame_test.shape[:2]}")
                print(f"   Attendu : {(CONFIG['camera_height'], CONFIG['camera_width'])}")
                sys.exit(1)
            if not verrouiller_camera(f"/dev/video{idx_cam}", nom_cam):
                print(f"\n❌ Verrouillage {lib} incomplet — bloc annulé (fail closed).")
                autorise = False

        _reconnecter(cam_top, cam_top_index, CAM_TOP, "GLOBALE")
        _reconnecter(cam_follower, cam_follower_index, CAM_FOLLOWER, "PINCE")

        # 5) Reprise téléopération : libérer Leader, garder Follower actif
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 0)
            fk.write1ByteTxRx(fp, i, 40, 1)
        pause_teleop = False

    finally:
        # Quoi qu'il arrive (exception comprise) : terminal restauré.
        reprendre_clavier()
    if not autorise:
        print("\n⛔ Bloc annulé (contrôle caméra non concluant).")
        time.sleep(2)
    return autorise


def main():
    global stop_threads, cmd_queue, _display_cam_top, _display_cam_follower, pause_teleop
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     SEM - ENREGISTREMENT DATASET SO-ARM 101                          ║
║     Phase 7 : Apprentissage par Imitation (2 caméras)                ║
║     Service Écoles-Médias - DIP Genève                               ║
╚══════════════════════════════════════════════════════════════════════╝

Ce script enregistre des démonstrations de téléopération pour
l'apprentissage par imitation avec LeRobot.

Tâche : Prendre un cube à l'une des 5 positions et le déposer
        dans la boîte.

Format de sortie : LeRobotDataset v2.1 (2 caméras: top + follower)
    """)
    input("\nAppuyez sur ENTRÉE pour commencer...")

    # Calibrations OBLIGATOIRES et VALIDES (Leader + Follower) — vérifiées en TÊTE,
    # avant toute interaction caméra/robot (échec rapide ; mêmes garde-fous que 4-7).
    calib_l = charger_calibration('leader')
    calib_f = charger_calibration('follower')
    if not calibration_complete(calib_l):
        print("❌ Calibration Leader absente, incomplète ou invalide — refaire la Phase 3.")
        return
    if not calibration_complete(calib_f):
        print("❌ Calibration Follower absente, incomplète ou invalide — refaire la Phase 3.")
        return

    # Garde-fou : le module de configuration caméra doit être disponible.
    # Sans lui, impossible de régler puis verrouiller les caméras → on arrête (fail closed)
    # plutôt que d'enregistrer en auto-exposition, incohérent avec le déploiement.
    if not CAMERA_LOCK_AVAILABLE:
        print("\n❌ Module de configuration caméra (SEM_so101_camera_config.py) indisponible.")
        print(f"   Erreur : {CAMERA_LOCK_IMPORT_ERROR}")
        print("   → Impossible de régler puis verrouiller les caméras.")
        print("   → Enregistrement annulé pour éviter des images en mode auto (incohérence avec le déploiement).")
        print("   → Vérifiez que SEM_so101_camera_config.py est dans le même dossier que ce script.")
        sys.exit(1)

    # Garde-fou étape 5 (décision Q1, fail closed) : sans le module de
    # qualité caméra, on n'enregistre PAS. Vérifié ICI (tôt) ; le contrôle
    # qualité lui-même est fait plus bas, robots au repos.
    if not CAMERA_QUALITY_AVAILABLE:
        print("\n❌ Module qualité caméra (SEM_so101_camera_reference.py) indisponible.")
        print(f"   Erreur : {CAMERA_QUALITY_IMPORT_ERROR}")
        print("   → Impossible de contrôler la qualité absolue de l'image (image exploitable).")
        print("   → Enregistrement annulé. Vérifiez que SEM_so101_camera_reference.py est")
        print("     dans le même dossier que ce script.")
        sys.exit(1)

    # Chargement + VALIDATION STRICTE du masque globale (créé par le script 7, partagé
    # avec le 11). OBLIGATOIRE : sans masque valide, l'enregistrement ne correspondrait
    # pas au cadrage de la Phase 6 → fail-closed (on arrête et on renvoie au script 7).
    global _MASK_GLOBALE_IMG
    mask_pts = charger_masque_globale()
    if mask_pts is None:
        print("\n❌ Masque de zone utile absent ou invalide — enregistrement annulé.")
        print("   Le masque est obligatoire pour l'enregistrement (cohérence du cadrage avec le déploiement).")
        print("   Lancez d'abord le script 7 (Phase 6) pour le créer/valider, puis relancez ce script.")
        if CV2_AVAILABLE:
            cv2.destroyAllWindows()
        sys.exit(1)
    _MASK_GLOBALE_IMG = construire_mask_image(
        mask_pts, CONFIG['camera_width'], CONFIG['camera_height']
    )
    print(f"\n✅ Masque globale actif ({len(mask_pts)} points)")

    input("\n✅ Masque chargé. Appuyez sur ENTRÉE pour passer à l'identification des robots...")

    ok, lp, lk, fp, fk = identification_guidee(calib_l, calib_f)
    if not ok:
        print("❌ Identification échouée")
        return

    mode, mode_name = choisir_mode()
    servos_miroir = charger_config_teleoperation(mode)
    if servos_miroir is None:
        print(f"❌ Configuration {mode_name} absente ou invalide.")
        print("   Lancez le script 5 pour configurer ce mode avant l'enregistrement.")
        cleanup_ports(lp, fp, lk, fk, release=True)
        return
    print(f"\n✅ Mode sélectionné : {mode_name}")

    urgence = False  # Devient True sur CTRL+C : arrêt d'urgence, pas de retour repos
    # Variables de nettoyage définies AVANT le try : si un CTRL+C ou une exception survient
    # pendant position_repos_parallele (avant leur création), le finally les référence sans NameError.
    recorder = DatasetRecorder()
    cam_top = None
    cam_follower = None
    try:
        print("\n🎯 Positionnement automatique (séquence sûre vers repos)...")
        if not position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f):
            print("❌ Position repos impossible au démarrage — arrêt.")
            return

        # Identification des CAMÉRAS APRÈS le repos (ordre validé _old1 /
        # déploiement) : la scène — surtout la vue PINCE (cam_follower), qui
        # dépend de la pose du bras — est garantie dans la posture standard.
        cam_top_index, cam_follower_index = identification_cameras()
        if cam_top_index is None or cam_follower_index is None:
            print("\n❌ Enregistrement annulé : les deux caméras (globale + pince) sont requises.")
            sys.exit(1)

        # ORDRE VALIDÉ (étape 5) : robots MAINTENUS au repos (couples actifs
        # depuis position_repos_parallele) PENDANT la préparation caméra (qualité
        # absolue) — la vue de la PINCE dépend de la pose du bras. Les caméras du
        # script ne sont pas encore connectées : le module ouvre les siennes.
        # Le thread clavier n'est pas encore lancé → les input() de préparation
        # caméra fonctionnent directement (pas de suspension nécessaire ici).
        # Préparation caméra (V1, sans référence) : image propre de séance,
        # verrouillage intra-séance, puis plancher qualité ABSOLU via
        # controle_qualite_camera — pour LES DEUX caméras. Aucun matching
        # couleur, aucune référence colorimétrique. Une caméra non exploitable
        # arrête proprement l'enregistrement.
        verdicts_prep = {}
        for nom_cam, idx_cam, lib in ((CAM_TOP, cam_top_index, "GLOBALE"),
                                      (CAM_FOLLOWER, cam_follower_index, "PINCE")):
            print(f"\n🛠️  PRÉPARATION CAMÉRA — {lib}")
            try:
                res = controle_qualite_camera(idx_cam, nom_cam, contexte="préparation")
            except Exception as e:
                print(f"\n❌ Préparation {lib} interrompue ({e}) — enregistrement annulé.")
                sys.exit(1)
            verdicts_prep[lib] = res.get("verdict", "🔴")
            if not res.get("autorise"):
                print(f"\n❌ {lib} : image non exploitable — enregistrement annulé.")
                sys.exit(1)
        print("\n📋 Verdict qualité : "
              + "   ".join(f"{lib} {v}" for lib, v in verdicts_prep.items()))

        input("\n✅ Caméras prêtes. Appuyez sur ENTRÉE pour libérer le Leader et lancer la téléopération...")

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

            # Verrouillage matériel APRÈS connexion + contrôle STRICT du résultat
            # (bool explicite : robuste même si verrouiller_camera renvoyait None)
            ok_top = True
            ok_follower = True
            if cam_top_index is not None:
                ok_top = bool(verrouiller_camera(f"/dev/video{cam_top_index}", CAM_TOP))
            if cam_follower_index is not None:
                ok_follower = bool(verrouiller_camera(f"/dev/video{cam_follower_index}", CAM_FOLLOWER))
            if not (ok_top and ok_follower):
                print("\n❌ Verrouillage caméra incomplet — enregistrement annulé (fail closed).")
                sys.exit(1)

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
                suspendre_clavier()
                afficher_instructions()
                reprendre_clavier()

            elif choix == '2':
                print("\n🧪 Test rapide - Choisissez une position (1-5): ", end="", flush=True)
                pos = None
                while pos is None and not stop_threads:
                    cmd = get_command()
                    if cmd in ['1', '2', '3', '4', '5']:
                        pos = int(cmd)
                    refresh_display()

                if pos:
                    if controle_camera_bloc(pos, cam_top, cam_top_index, cam_follower, cam_follower_index, lk, lp, fk, fp, calib_l, calib_f):
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
                    elif controle_camera_bloc(pos, cam_top, cam_top_index, cam_follower, cam_follower_index, lk, lp, fk, fp, calib_l, calib_f):
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
                suspendre_clavier()
                input("\nAppuyez sur ENTRÉE pour revenir au menu...")
                reprendre_clavier()

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
                ok_repos = position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)
                # Libérer Leader, garder Follower actif pour reprendre la téléopération
                for i in range(1, 7):
                    lk.write1ByteTxRx(lp, i, 40, 0)
                    fk.write1ByteTxRx(fp, i, 40, 1)
                pause_teleop = False
                if ok_repos:
                    print("\n✅ Robot repositionné à repos.")
                else:
                    print("\n❌ Repositionnement à repos impossible — vérifiez la posture des robots.")
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

            repos_pct, _ = charger_repos_pct()
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
