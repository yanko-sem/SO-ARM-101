#!/usr/bin/env python3
"""
Script SEM_so101_11_deploy.py
Service Écoles-Médias (SEM) - DIP Genève

DÉPLOIEMENT DU MODÈLE ACT — INFÉRENCE AUTONOME
================================================

Ce script charge un modèle ACT entraîné et laisse le bras Follower
agir de façon autonome : aucun opérateur n'est nécessaire pendant
l'action autonome, après la phase de préparation.

Le modèle observe en continu les deux caméras et les positions actuelles
des servos du Follower, calcule les positions cibles, et les envoie
directement aux servos à ~30 images/seconde.

Contrôles pendant l'inférence (au clavier, dans le terminal):
    P      : Pause / Reprendre
    R      : Retour repos + désactivation du modèle (fin d'essai)
    Entrée : Relancer le modèle pour un nouvel essai
    Q      : Quitter

Auteur: Service Écoles-Médias (SEM)
Version: 1.2  (exposition auto puis figée + contrôle image simple)
"""

import os
import sys
import json
import math
import time
import queue
import threading
import re
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
    print("⚠️  OpenCV non disponible — requis pour le déploiement "
          "(caméras, masque, conversion image→tenseur).")

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

# Module caméra unifié (partagé avec le script 8) : au démarrage du déploiement,
# chaque caméra est réglée en EXPOSITION AUTO PUIS FIGÉE (adaptée à la lumière réelle
# de la salle), puis son image BRUTE passe un CONTRÔLE IMAGE SIMPLE (plancher physique ;
# GLOBALE mesurée en zone utile du masque, PINCE en plein cadre). Plus de références ni
# de verrouillage sur des réglages enregistrés — la robustesse à la lumière est portée
# par l'augmentation à l'entraînement.
# Flux : checkpoint → modèle → masque globale obligatoire → Follower au REPOS →
# identification caméras → connexion ThreadedCamera → exposition auto puis figée →
# contrôle image simple (GLOBALE puis PINCE, autorisation = les deux) → inférence.
# Import protégé : si le module est absent, mal placé ou cassé, on le signale plus bas
# par un message clair + arrêt propre, au lieu d'un traceback illisible au démarrage.
try:
    from SEM_so101_camera_auto import (
        regler_exposition_auto_puis_figee, controle_image_simple, texte_verdict)
    CAMERA_AUTO_AVAILABLE = True
    CAMERA_AUTO_IMPORT_ERROR = None
except Exception as e:
    regler_exposition_auto_puis_figee = None
    controle_image_simple = None
    texte_verdict = None
    CAMERA_AUTO_AVAILABLE = False
    CAMERA_AUTO_IMPORT_ERROR = e

# ============================================
# CONFIGURATION
# ============================================

CONFIG = {
    'fps': 30,
    'camera_width': 640,
    'camera_height': 360,   # 16:9 — doit correspondre exactement à la résolution d'entraînement
    'baud_rate': 1000000,
}

# Base commune des modèles nommés (registre local). Le modèle précis est choisi
# au lancement (selectionner_modele) ; TRAIN_OUTPUT_DIR est renseigné à ce
# moment-là. Portable, fonctionne sur tout PC.
TRAIN_BASE = Path.home() / "lerobot" / "outputs" / "train"
TRAIN_OUTPUT_DIR = None

# Calibration
CALIB_DIR = Path.home() / "lerobot" / "calibration"

# Noms des caméras — doivent correspondre exactement au dataset d'entraînement
CAM_TOP      = "cam_top"
CAM_FOLLOWER = "cam_follower"

# Position repos — fichier externe partagé entre tous les scripts (cohérence 7/8/11)
REPOS_FILE = Path.home() / "lerobot" / "calibration" / "repos_position.json"

# Masque de zone utile — fichier externe créé par le script 7 (cohérence 7/8/11)
MASK_FILE = Path.home() / "lerobot" / "calibration" / "camera_mask.json"

# Amplitude minimale exigée d'une calibration pour être exploitable (même seuil que 2/3/4/5/8)
MIN_AMPLITUDE = 500

# Device GPU ou CPU
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Variables globales
stop_threads = False          # arrête le thread clavier
cmd_queue    = queue.Queue()  # file des commandes clavier (P / R / Q)
urgence      = False          # devient True sur CTRL+C : arrêt d'urgence, pas de retour repos
_MASK_GLOBALE_IMG = None      # image binaire du masque globale (None tant que le fichier n'est pas chargé)

# Instances caméra pour l'affichage dans le thread principal (phase de préparation)
_display_cam_top = None
_display_cam_follower = None
_prep_window_created = False  # la fenêtre de préparation n'est créée/dimensionnée qu'une seule fois

def refresh_display(titre=None, legende=None):
    """Rafraîchit l'affichage des caméras dans UNE fenêtre combinée (thread principal).
    Retourne la touche lue par cv2.waitKey (& 0xFF), ou None si rien à afficher — ce
    qui permet de piloter des décisions interactives DIRECTEMENT dans la fenêtre
    caméra. Les appels existants qui ignorent ce retour fonctionnent à l'identique.
    Si `titre`/`legende` sont fournis, ils sont incrustés sur un bandeau noir EN HAUT
    (titre vert + touches jaunes), MÊME style qu'à l'identification des caméras. Sans
    eux, affichage normal (labels CAM GLOBALE / CAM PINCE)."""
    global _prep_window_created
    if not CV2_AVAILABLE:
        return None
    w = CONFIG['camera_width']
    h = CONFIG['camera_height']
    frame_top = _display_cam_top.async_read() if (_display_cam_top and _display_cam_top.is_connected) else None
    frame_fol = _display_cam_follower.async_read() if (_display_cam_follower and _display_cam_follower.is_connected) else None
    # Masque appliqué uniquement à la globale, avant l'étiquette → on voit en direct ce qui sera fourni au modèle
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
        return None
    display = images[0] if len(images) == 1 else cv2.hconcat(images)
    # Fenêtre redimensionnable + taille ×1.5 (1920×540) — créée/dimensionnée une seule fois
    if not _prep_window_created:
        cv2.namedWindow('Cameras SO-ARM 101', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Cameras SO-ARM 101', 1920, 540)
        _prep_window_created = True
    # Bandeau noir EN HAUT (titre vert + touches jaunes), MÊME style qu'à
    # l'identification G/P, pour que l'opérateur voie les choix sans le terminal.
    if titre or legende:
        dw = display.shape[1]
        cv2.rectangle(display, (0, 0), (dw, 72), (0, 0, 0), -1)
        if titre:
            cv2.putText(display, titre, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        if legende:
            cv2.putText(display, legende, (10, 58),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    cv2.imshow('Cameras SO-ARM 101', display)
    k = cv2.waitKey(30) & 0xFF   # throttle ~33 Hz + lit la touche pour les décisions live
    return None if k == 255 else k

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
    """Charge la calibration d'un robot depuis le fichier JSON. Fail-closed :
    retourne None si le fichier est absent OU illisible/corrompu — jamais une
    exception qui remonterait (potentiellement après activation du couple)."""
    calib_file = CALIB_DIR / f"{robot_type}_calibration.json"
    if not calib_file.exists():
        return None
    try:
        with open(calib_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Calibration {robot_type} illisible : {e}")
        return None


def calibration_complete(calibration):
    """Vrai uniquement si les 6 servos sont calibrés avec une plage exploitable
    (présents, min/max/center numériques, amplitude >= MIN_AMPLITUDE, min<=center<=max).
    Même exigence que les scripts 4/5/8. Sans calibration valide, le déploiement
    retomberait sur des positions brutes 0-4095 -> risque de butées sur le Follower."""
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


# ----------------------------------------------------------------------------
# Certains servos Feetech peuvent renvoyer un octet de statut interne non nul
# tout en conservant une position parfaitement lisible. Seul l'echec de
# communication (result != COMM_SUCCESS) invalide la lecture ; l'octet de
# statut interne est ignore (tolere silencieusement). Cause a identifier sur la
# table de controle Feetech STS3215 (hors urgence). Regle limitee aux LECTURES.
# ----------------------------------------------------------------------------
def lire_position(packet_handler, port_handler, servo_id):
    """Lecture de la position (registre 56). Retourne (position, ok).
    Seule une vraie panne de communication (result) invalide la lecture ;
    l'octet de statut interne du servo est ignore (tolere silencieusement)."""
    pos, result, _ = packet_handler.read2ByteTxRx(port_handler, servo_id, 56)
    if result != COMM_SUCCESS:
        return None, False
    return pos, True


def lire_positions(packet_handler, port_handler):
    """Lit les positions de tous les servos (1 à 6). Retourne (dict, ok).
    ok = False si AU MOINS une lecture échoue (communication) : l'appelant
    n'utilise PAS l'état (ne nourrit jamais la policy avec une lecture douteuse)."""
    positions = {}
    for servo_id in range(1, 7):
        pos, ok = lire_position(packet_handler, port_handler, servo_id)
        if not ok:
            return positions, False
        positions[servo_id] = pos
    return positions, True


def ecrire_position(packet_handler, port_handler, servo_id, position, calib=None):
    """Écrit une position cible sur un servo. Retourne True/False (COMM_SUCCESS).

    Clipping de sécurité : si `calib` est fourni, la cible est bornée à la plage
    CALIBRÉE [min, max] du servo — barrière contre une prédiction aberrante du
    modèle qui sortirait de l'espace de travail appris. Sinon, repli sur la plage
    registre brute [0, 4095]. En fonctionnement normal le modèle reste dans
    [min, max] : le clip ne mord qu'en cas d'aberration.
    Une panne de communication (result != COMM_SUCCESS) est signalée par False,
    pour permettre à l'appelant de détecter une défaillance persistante."""
    position = int(position)
    if calib is not None:
        info = calib.get(f'servo_{servo_id}', {})
        min_val, max_val = info.get('min'), info.get('max')
        if (isinstance(min_val, (int, float)) and isinstance(max_val, (int, float))
                and min_val < max_val):
            position = max(int(min_val), min(int(max_val), position))
        else:
            position = max(0, min(4095, position))
    else:
        position = max(0, min(4095, position))
    try:
        result = packet_handler.write2ByteTxRx(port_handler, servo_id, 42, position)
    except Exception as e:
        print(f"❌ Écriture servo {servo_id} impossible : {e}")
        return False
    comm_result = result[0] if isinstance(result, tuple) else result
    if comm_result != COMM_SUCCESS:
        return False
    return True


def charger_masque_globale():
    """Lit et VALIDE STRICTEMENT le masque cam_top (MASK_FILE, créé par le script 7).
    Retourne la liste des 5 points (tuples) si valide, sinon None.
    Validation : exactement 5 points, coordonnées numériques. Si une résolution de
    référence est présente, elle DOIT correspondre à la résolution de déploiement
    (CONFIG camera_width x camera_height) ; sinon le masque serait appliqué à la
    mauvaise échelle -> refus (cohérence entraînement↔déploiement)."""
    if not MASK_FILE.exists():
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
                raise ValueError("chaque point doit contenir exactement 2 coordonnées")
            x, y = p
            if (isinstance(x, bool) or isinstance(y, bool)
                    or not isinstance(x, (int, float)) or not isinstance(y, (int, float))):
                raise ValueError("coordonnées non numériques")
            pts.append((int(x), int(y)))
        ref = data.get("reference_resolution", {})
        rw = ref.get("width") if isinstance(ref, dict) else None
        rh = ref.get("height") if isinstance(ref, dict) else None
        if (isinstance(rw, (int, float)) and not isinstance(rw, bool)
                and isinstance(rh, (int, float)) and not isinstance(rh, bool)):
            if int(rw) != CONFIG['camera_width'] or int(rh) != CONFIG['camera_height']:
                raise ValueError(
                    f"masque créé en {int(rw)}x{int(rh)}, attendu "
                    f"{CONFIG['camera_width']}x{CONFIG['camera_height']} (recréer via le script 7)")
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


def charger_repos_pct():
    """Charge la position repos (% par servo) depuis le fichier externe partagé.
    Retourne un dict {1:%,...}. Valide chaque valeur dans [0,100] ; fallback sur
    les valeurs par défaut si le fichier est absent, illisible ou hors plage.
    Identique aux scripts 7/8 : garantit que le Follower démarre l'inférence
    depuis la pose exacte des épisodes d'enregistrement (évite le hors-distribution)."""
    defaut = {1: 50, 2: 10, 3: 88, 4: 76, 5: 50, 6: 11}
    if REPOS_FILE.exists():
        try:
            with open(REPOS_FILE, 'r') as f:
                data = json.load(f)
            repos = {int(k): float(v) for k, v in data.items()}
            for i in range(1, 7):
                if i not in repos or not (0.0 <= repos[i] <= 100.0):
                    return defaut
            return repos
        except Exception:
            return defaut
    return defaut


def _cible_ticks(calib, servo_id, pct):
    """Convertit un pourcentage en ticks (calibration garantie valide au démarrage)."""
    min_val = calib[f'servo_{servo_id}']['min']
    max_val = calib[f'servo_{servo_id}']['max']
    return int(min_val + (max_val - min_val) * pct / 100)


def _est_en_repos(packet, port, calib, repos_pct, tolerance_pct=5):
    """Vrai si le bras est proche de la position repos (tous les servos).
    Faux si au moins un servo en est éloigné. None si une lecture échoue
    (état indéterminé -> l'appelant doit annuler la séquence)."""
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


def mouvement_servos(packet, port, calib, cibles_pct, servos, duree=2.0):
    """Déplace les servos indiqués vers cibles_pct (%) avec un profil cosinus.
    Retourne True si OK, None si une lecture de position de départ échoue
    (mouvement annulé : on ne part jamais d'une position douteuse)."""
    pos = {}
    for s in servos:
        p, ok = lire_position(packet, port, s)
        if not ok:
            print(f"❌ Lecture servo {s} impossible — mouvement annulé")
            return None
        pos[s] = p
    cible = {}
    for s in servos:
        cible[s] = _cible_ticks(calib, s, cibles_pct[s])
    steps = 100
    for step in range(steps + 1):
        t = step / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        for s in servos:
            cible_pas = int(pos[s] + (cible[s] - pos[s]) * smooth)
            # Écriture contrôlée : abandon à la PREMIÈRE panne de communication
            # (symétrique avec les lectures ci-dessus). Le repos est un invariant :
            # aller_position_repos doit pouvoir renvoyer False sur un échec réel.
            if not ecrire_position(packet, port, s, cible_pas, calib):
                print(f"❌ Écriture servo {s} impossible — mouvement annulé")
                return None
        time.sleep(duree / steps)
    return True


def aller_a_position(packet, port, calib, cibles_pct, duree=2.0):
    """Déplace le bras Follower vers cibles_pct (%) en respectant les contraintes
    physiques (séquence sûre anti-collision). Version mono-bras de la séquence
    du script 8. Lectures vérifiées : retourne None si une lecture critique
    échoue (mouvement annulé), True sinon.
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
    pos4, ok = lire_position(packet, port, 4)
    if not ok:
        print("❌ Lecture servo 4 impossible — mouvement annulé")
        return None
    if pos4 > 2700:
        etat = _est_en_repos(packet, port, calib, repos_pct)
        if etat is None:
            print("❌ État repos indéterminé — mouvement annulé")
            return None
        if not etat:
            deb, ok = lire_position(packet, port, 2)
            if not ok:
                print("❌ Lecture servo 2 impossible — mouvement annulé")
                return None
            fin = min(deb, 1027)
            steps = int(duree * 50)
            for step in range(steps + 1):
                t = step / steps
                smooth = (1 - math.cos(t * math.pi)) / 2
                if not ecrire_position(packet, port, 2,
                                       int(deb + (fin - deb) * smooth), calib):
                    print("❌ Écriture servo 2 impossible — mouvement annulé")
                    return None
                time.sleep(duree / steps)

    # --- Phase 1 : servo 4 -> 20% (pince en l'air) ---
    if mouvement_servos(packet, port, calib, {4: 20}, [4], duree) is None:
        return None

    # --- Phase 2 : servos 1,2,3,5,6 en parallèle ---
    if mouvement_servos(packet, port, calib, cibles_pct, [1, 2, 3, 5, 6], duree) is None:
        return None

    # --- Phase 3 : servo 4 -> cible finale ---
    if mouvement_servos(packet, port, calib, cibles_pct, [4], duree) is None:
        return None

    return True


def aller_position_repos(packet_handler, port_handler, calib):
    """Déplace le Follower vers la position repos partagée via la séquence sûre.
    Retourne True si la position est atteinte, False si une lecture critique a
    échoué (mouvement annulé) -> permet aux appelants de refuser un faux succès."""
    print("\n🏁 Retour en position repos...")
    repos_pct = charger_repos_pct()
    if aller_a_position(packet_handler, port_handler, calib, repos_pct, duree=2.0) is None:
        print("❌ Retour repos impossible (lecture servo).")
        return False
    print("✅ Position repos atteinte")
    return True


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

NOM_MODELE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def nom_modele_valide(nom):
    """Vrai si `nom` respecte la convention sûre [a-z0-9_-], non vide (mêmes
    règles qu'au script 10). On refuse tout nom hors convention plutôt que de le
    réécrire : une espace, un accent, un '/' ou un '.' casserait le chemin."""
    return bool(nom) and NOM_MODELE_RE.match(nom) is not None


def checkpoint_chargeable(cp):
    """Vrai si le checkpoint `cp` (dossier d'un pas, ex. .../checkpoints/002000)
    est RÉELLEMENT chargeable par ACTPolicy.from_pretrained() : son
    pretrained_model/ contient config.json ET model.safetensors (les deux
    fichiers que from_pretrained consomme). Un checkpoint partiel est écarté."""
    pm = cp / "pretrained_model"
    return (pm.is_dir()
            and (pm / "config.json").exists()
            and (pm / "model.safetensors").exists())


def lister_modeles():
    """Liste triée des dossiers de modèles VALIDES sous TRAIN_BASE.

    Filtre STRUCTUREL (indépendant du nom) : au moins un checkpoint RÉELLEMENT
    chargeable, c.-à-d. un checkpoints/<step>/pretrained_model contenant
    config.json ET model.safetensors — les deux fichiers que
    ACTPolicy.from_pretrained() consomme. Un checkpoint partiel est écarté,
    pour ne pas proposer en démo un modèle qui échouerait au chargement."""
    if not TRAIN_BASE.exists():
        return []
    modeles = []
    for d in sorted(TRAIN_BASE.iterdir()):
        if not d.is_dir():
            continue
        ckpt = d / "checkpoints"
        if ckpt.is_dir() and any(
                checkpoint_chargeable(cp) for cp in ckpt.iterdir()):
            modeles.append(d)
    return modeles


def selectionner_modele():
    """Choix EXPLICITE du modèle à déployer (registre local de modèles nommés).

    Décision de conception (fail-closed) : AUCUN modèle par défaut, aucun
    « dernier modèle » mémorisé, aucun fichier d'état. L'utilisateur choisit à
    chaque démo — pas de surprise, rien à porter d'une machine à l'autre.
    Retourne le Path du dossier modèle choisi, ou None (aucun modèle / abandon).

    La sélection du CHECKPOINT à l'intérieur du modèle garde, elle, son défaut
    habituel (dernier checkpoint) : les deux niveaux sont distincts.
    """
    print("\n" + "=" * 60)
    print("📂 SÉLECTION DU MODÈLE")
    print("=" * 60)

    while True:
        modeles = lister_modeles()

        if not modeles:
            print("\n❌ Aucun modèle entraîné trouvé dans :")
            print(f"   {TRAIN_BASE}")
            print("   → Lancez d'abord l'entraînement (Script 10).")
            return None

        print(f"\n📋 Modèles disponibles ({len(modeles)}) :")
        for i, d in enumerate(modeles, start=1):
            n_ok = sum(1 for cp in (d / "checkpoints").iterdir()
                       if checkpoint_chargeable(cp))
            print(f"   [{i:>2}]  {d.name:<32} ({n_ok} checkpoint(s))")

        print("\n   [N] Entrer un nom de modèle manuellement")
        print("   [Q] Quitter")
        choix = input("\n→ Votre choix (numéro, N ou Q) : ").strip()

        if choix.upper() == "Q":
            return None

        if choix.upper() == "N":
            nom = input("\n   Nom du modèle (a-z, 0-9, '-', '_') : ").strip()
            if not nom_modele_valide(nom):
                print("\n   ❌ Nom refusé. Autorisé : a-z, 0-9, '-', '_' "
                      "(sans espace ni accent) ; le nom doit commencer par une "
                      "lettre ou un chiffre.")
                continue
            cible = TRAIN_BASE / nom
            ckpt = cible / "checkpoints"
            if not (cible.is_dir() and ckpt.is_dir() and any(
                    checkpoint_chargeable(cp) for cp in ckpt.iterdir())):
                print(f"\n   ❌ Modèle « {nom} » introuvable ou sans checkpoint "
                      f"dans {TRAIN_BASE}.")
                continue
            print(f"\n✅ Modèle sélectionné : {nom}")
            return cible

        if choix.isdigit() and 1 <= int(choix) <= len(modeles):
            d = modeles[int(choix) - 1]
            print(f"\n✅ Modèle sélectionné : {d.name}")
            return d

        print("\n   ❌ Choix invalide.")


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
        print("   → Vérifiez que l'entraînement (Script 10) a bien été effectué.")
        return None

    # Tri par valeur entière (chiffres croissants) ; 'last' et tout nom non
    # numérique placés en fin. Sinon le tri alphabétique mettrait "50000" après
    # "200000" et le repli ci-dessous recommanderait un checkpoint plus ancien.
    def _cle_checkpoint(cp):
        return (0, int(cp.name)) if cp.name.isdigit() else (1, cp.name)

    checkpoints = sorted(
        [item for item in checkpoints_dir.iterdir()
         if item.is_dir() and checkpoint_chargeable(item)],
        key=_cle_checkpoint,
    )

    if not checkpoints:
        print("❌ Aucun checkpoint valide trouvé dans :")
        print(f"   {checkpoints_dir}")
        return None

    # Checkpoint par défaut : "last" s'il existe, sinon le plus grand checkpoint
    # NUMÉRIQUE (plus de steps), et seulement à défaut un dossier non numérique.
    numeriques = [cp for cp in checkpoints if cp.name.isdigit()]
    last_cp = next((cp for cp in checkpoints if cp.name == "last"),
                   numeriques[-1] if numeriques else checkpoints[-1])

    print(f"\n📋 Checkpoints disponibles ({len(checkpoints)}) :")
    print("   (un « step » = une itération d'entraînement : le modèle ajuste ses")
    print("    poids sur un petit lot d'exemples. Plus il y a de steps, plus le")
    print("    modèle a été entraîné longtemps sur vos démonstrations.)\n")
    for i, cp in enumerate(checkpoints):
        if cp.name.isdigit():
            etiquette = f"{int(cp.name):,} steps".replace(",", " ")
        elif cp.name == "last":
            etiquette = "dernier checkpoint"
        else:
            etiquette = cp.name
        marker = "  ← recommandé" if cp == last_cp else ""
        print(f"   [{i + 1:>2}]  {cp.name:>8}  →  {etiquette}{marker}")

    print(f"\n   [Entrée] Utiliser le dernier checkpoint (recommandé)")
    choix = input("\n→ Votre choix (numéro ou Entrée) : ").strip()

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
    """Identification VISUELLE des deux caméras (globale cam_top + pince cam_follower).
    Les deux caméras du projet sont identiques : aucune détection automatique possible.
    Parcourt TOUTES les caméras détectées (pas seulement les deux premières) ; pour
    chacune dont l'image est lisible, affiche le flux et demande G/P/Q. S'arrête dès
    que les DEUX sont identifiées. AUCUNE auto-assignation : cam_top et cam_follower
    doivent être désignées explicitement (exigence de cohérence avec le dataset d'entraînement)."""
    if not CV2_AVAILABLE:
        print("❌ OpenCV non disponible")
        return None, None

    print("\n" + "="*60)
    print("📷 IDENTIFICATION DES CAMÉRAS")
    print("="*60)
    cameras = detect_cameras()
    print(f"\n🔍 Caméras détectées: {cameras}")

    if len(cameras) < 2:
        print("❌ Deux caméras sont requises (globale + pince) pour le déploiement.")
        print(f"   Détecté : {len(cameras)} caméra(s). Branchez les deux caméras et relancez.")
        return None, None

    print("\n📌 Vous allez voir chaque caméra tour à tour dans UNE seule fenêtre.")
    print("   Identifiez la caméra GLOBALE (vue d'ensemble du plateau) et")
    print("   la caméra PINCE (sur le follower). Les deux étant identiques,")
    print("   distinguez-les par ce qu'elles cadrent.")
    print("\n   ⌨️  Réponds DIRECTEMENT DANS LA FENÊTRE (pas au terminal) :")
    print("      G = globale   P = pince   Q = passer   Échap = tout annuler")
    print("\n   Appuyez sur ENTRÉE pour commencer...")
    input()

    FENETRE = "Identification camera"
    cam_top_index = None
    cam_follower_index = None

    for idx in cameras:
        if cam_top_index is not None and cam_follower_index is not None:
            break  # les deux caméras sont identifiées, inutile de continuer
        print(f"\n🎥 Caméra index {idx} — dans la FENÊTRE, appuie sur :")
        print( "      G = GLOBALE (plateau)    P = PINCE (follower)    Q = passer    Échap = annuler")
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            print(f"   ❌ Impossible d'ouvrir la caméra {idx} — passée.")
            continue

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG['camera_width'])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG['camera_height'])

        # Vue LIVE + touches lues DANS la fenêtre (une seule fenêtre persistante,
        # réutilisée pour toutes les caméras). Aucune réponse au terminal → pas de
        # clic à donner. Si aucune image lisible pendant ~2 s, on ne propose pas
        # cette caméra (pas de confirmation à l'aveugle).
        choix = None
        image_vue = False
        t0 = time.time()
        while choix is None:
            ret, frame = cap.read()
            if ret:
                image_vue = True
                # Bandeau noir en haut → légende lisible même sur une image très claire.
                cv2.rectangle(frame, (0, 0), (frame.shape[1], 72), (0, 0, 0), -1)
                cv2.putText(frame, f"Camera {idx}", (10, 28),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame, "G=GLOBALE (plateau)  P=PINCE (follower)  Q=passer  Echap=annuler", (10, 58),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                cv2.imshow(FENETRE, frame)
            k = cv2.waitKey(30) & 0xFF
            if k in (ord('g'), ord('G')):
                choix = 'G'
            elif k in (ord('p'), ord('P')):
                choix = 'P'
            elif k in (ord('q'), ord('Q')):
                choix = 'Q'
            elif k == 27:  # Échap
                choix = 'ESC'
            elif not image_vue and (time.time() - t0) > 2.0:
                choix = 'NOIMG'
        cap.release()

        if choix == 'NOIMG':
            print(f"   ⚠️  Image indisponible pour la caméra {idx} — identification impossible, on passe.")
            continue
        if choix == 'ESC':
            print("   ⏹  Identification annulée.")
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            return None, None
        if choix == 'G':
            cam_top_index = idx
            print(f"   ✅ Caméra {idx} = {CAM_TOP} (globale)")
        elif choix == 'P':
            cam_follower_index = idx
            print(f"   ✅ Caméra {idx} = {CAM_FOLLOWER} (pince)")
        else:  # Q
            print(f"   ⏭️  Caméra {idx} passée")

    # Fermeture UNE seule fois, à la fin.
    cv2.destroyAllWindows()
    cv2.waitKey(1)

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

    # Calibration OBLIGATOIRE et VALIDE chargée AVANT toute activation du couple :
    # absente, corrompue ou invalide -> on refuse ICI, alors qu'aucun servo n'est
    # encore sous tension (jamais de bras laissé rigide sur calibration illisible).
    # Sans elle, le déploiement retomberait sur des positions brutes 0-4095
    # (risque de butées) et les pourcentages repos seraient faux.
    calib = charger_calibration('follower')
    if not calibration_complete(calib):
        print("❌ Calibration Follower absente, incomplète ou invalide — refaire la Phase 3.")
        return None, None, None
    print("✅ Calibration Follower chargée")

    port_handler   = PortHandler(follower_port)
    packet_handler = PacketHandler(1.0)

    if not port_handler.openPort():
        print(f"❌ Impossible d'ouvrir le port {follower_port}")
        return None, None, None

    if not port_handler.setBaudRate(CONFIG['baud_rate']):
        print("❌ Impossible de régler le baud rate")
        port_handler.closePort()
        return None, None, None

    # Activer le couple sur tous les servos (calibration déjà validée ci-dessus)
    for i in range(1, 7):
        packet_handler.write1ByteTxRx(port_handler, i, 40, 1)

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
    repos_confirme  = True    # le bras est au repos au démarrage (garanti par main)
    step            = 0
    derniere_action = None
    premiere_action = True
    frequence       = 1.0 / CONFIG['fps']

    echecs_consecutifs = 0    # itérations consécutives avec ≥1 écriture servo en échec
    clips_total        = 0    # nb d'actions modèle bornées à la plage calibrée [min,max]

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
            # le 11 doit masquer aussi avant que la politique voie l'image.
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
                    cv2.namedWindow("SEM — Déploiement ACT (Script 11)", cv2.WINDOW_NORMAL)
                    cv2.resizeWindow("SEM — Déploiement ACT (Script 11)", 1920, 540)
                    _window_created = True
                cv2.imshow("SEM — Déploiement ACT (Script 11)", display)
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
                ok_repos = aller_position_repos(packet_handler, port_handler, calib)
                policy.reset()
                step            = 0
                derniere_action = None
                premiere_action = True
                en_pause        = False   # repart d'un état propre (annule une éventuelle pause)
                modele_actif    = False   # modèle désactivé jusqu'au prochain Entrée
                repos_confirme  = ok_repos  # le bras est-il réellement au repos ?
                if ok_repos:
                    print("\n✅ Retour au repos — modèle DÉSACTIVÉ.")
                else:
                    print("\n❌ Retour repos impossible — modèle DÉSACTIVÉ (vérifiez le bras).")
                print("   Replacez la pièce, puis appuyez sur Entrée pour relancer un essai.")
            elif cmd == 'ENTER':
                if not modele_actif:
                    # Invariant : un nouvel essai DOIT partir du repos. Si le dernier
                    # retour repos a échoué, on le retente ; réactivation uniquement
                    # si le bras est confirmé au repos.
                    if not repos_confirme:
                        print("\n🔁 Retour repos non confirmé — nouvelle tentative avant relance...")
                        repos_confirme = aller_position_repos(packet_handler, port_handler, calib)
                    if repos_confirme:
                        modele_actif    = True
                        premiere_action = True   # redémarrage en douceur (interpolation 1 s)
                        print("\n▶️  Modèle RÉACTIVÉ — nouvel essai en cours.")
                    else:
                        print("\n❌ Relance refusée : le bras n'est pas confirmé en position repos.")
                        print("   Réessayez (Entrée) ou quittez (Q).")

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
            positions, ok = lire_positions(packet_handler, port_handler)
            if not ok:
                # Lecture d'état douteuse : on ne nourrit PAS la policy (on saute l'itération).
                time.sleep(frequence)
                continue
            state_list  = [float(positions[i]) for i in range(1, 7)]
            state_tensor = torch.tensor([state_list], dtype=torch.float32).to(DEVICE)
            obs["observation.state"] = state_tensor

            # ---- Inférence optimisée ----
            with torch.inference_mode():
                action = policy.select_action(obs)

            # ---- Application des actions aux servos ----
            action_np       = action.cpu().numpy().flatten()
            derniere_action = action_np

            echec_iteration = False   # ≥1 écriture servo en échec sur cette itération

            if premiere_action:
                # Interpolation fluide sur 1 seconde pour éviter un "coup de fouet" initial
                positions_depart, ok = lire_positions(packet_handler, port_handler)
                if not ok:
                    # État de départ douteux : on n'envoie AUCUNE action interpolée
                    # (premiere_action reste True -> nouvelle tentative à l'itération suivante).
                    time.sleep(frequence)
                    continue
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
                            if not ecrire_position(packet_handler, port_handler,
                                                   servo_id, new_pos, calib):
                                echec_iteration = True
                    time.sleep(duree_interp / steps_interp)
                premiere_action = False
            else:
                for i, servo_id in enumerate(range(1, 7)):
                    if i < len(action_np):
                        # Comptage agrégé des clips : la cible du modèle sort-elle
                        # de la plage calibrée du servo ? (diagnostic, sans spam)
                        cible_modele = int(action_np[i])
                        info_cal = calib.get(f'servo_{servo_id}', {})
                        mn, mx = info_cal.get('min'), info_cal.get('max')
                        if (isinstance(mn, (int, float)) and isinstance(mx, (int, float))
                                and mn < mx and not (mn <= cible_modele <= mx)):
                            clips_total += 1
                        if not ecrire_position(packet_handler, port_handler,
                                               servo_id, action_np[i], calib):
                            echec_iteration = True

            # Panne d'écriture persistante : 3 itérations d'inférence consécutives
            # avec ≥1 écriture en échec -> arrêt sûr (un échec isolé ne déclenche
            # rien). Le compteur ne bouge que sur les itérations qui écrivent
            # réellement (pause / modèle inactif / lecture douteuse font 'continue').
            if echec_iteration:
                echecs_consecutifs += 1
            else:
                echecs_consecutifs = 0
            if echecs_consecutifs >= 3:
                print("\n🛑 ARRÊT SÛR — écritures servo en échec sur 3 itérations "
                      "consécutives (panne de communication). Coupure du couple.")
                for sid in range(1, 7):
                    packet_handler.write1ByteTxRx(port_handler, sid, 40, 0)
                urgence = True
                break

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
        if clips_total:
            print(f"   ⚠️  Actions bornées à la plage calibrée (clips) : {clips_total}")


# ============================================
# CONTRÔLE IMAGE INTERACTIF (préparation caméra)
# ============================================

def controle_camera_simple_interactif(cam, index, nom, est_globale):
    """Contrôle image simple d'UNE caméra (image BRUTE, avant masque) + retour
    lumière. Le verdict détaillé s'affiche au TERMINAL ; la décision se prend
    DANS LA FENÊTRE NORMALE « Cameras SO-ARM 101 », qui reste LIVE (on lit la
    touche renvoyée par refresh_display). Pas de fenêtre spéciale. En 🟠/🔴, un
    bandeau (titre + touches) est incrusté EN HAUT de la fenêtre, comme à
    l'identification ; en 🟢 et hors contrôle, l'affichage reste normal.

    Décision selon le verdict :
      🟢 → verdict au terminal, fenêtre live ~1,5 s, puis on continue
           AUTOMATIQUEMENT (rien à faire) ;
      🟠 → dans la fenêtre : C = continuer / R = re-régler l'exposition / Q = annuler ;
      🔴 → dans la fenêtre : R = re-régler l'exposition après correction / Q = annuler
           (PAS de C). L'image reste VIVANTE : on voit l'effet du réglage lumière.
    Le réglage d'exposition n'est relancé QUE sur demande explicite [R] (jamais en automatique).
    Retourne True si le déploiement reste autorisé pour cette caméra."""
    T_C = (ord('c'), ord('C'))
    T_R = (ord('r'), ord('R'))
    T_Q = (ord('q'), ord('Q'))
    while True:
        res = controle_image_simple(
            cam.async_read, nom, CONFIG['camera_width'], CONFIG['camera_height'],
            masque_path=str(MASK_FILE), est_globale=est_globale)
        print(f"\n📷 {texte_verdict(nom, res)}")
        verdict = res["verdict"]

        # 🟢 : fenêtre normale live ~1,5 s, puis on continue automatiquement.
        if verdict == "🟢":
            t0 = time.time()
            while time.time() - t0 < 1.5:
                refresh_display()
            return True

        # 🟠 / 🔴 : décision DANS la fenêtre normale, qui reste LIVE (on voit
        # l'effet du réglage lumière en direct). Touches lues via refresh_display.
        titre_img = "Controle lumiere - " + ("GLOBALE" if est_globale else "PINCE")
        if verdict == "🟠":
            print("   👉 Dans la fenêtre caméra : C = continuer le déploiement / R = re-régler / Q = annuler")
            continuer_possible = True
            legende_img = "C = continuer   R = re-regler   Q = annuler"
        else:  # 🔴
            print("   👉 Dans la fenêtre caméra : R = ajuste la lumière puis re-règle / Q = annuler (pas de C)")
            continuer_possible = False
            legende_img = "R = re-regler (ajuste la lumiere)   Q = annuler   (pas de C)"

        decision = None
        while decision is None:
            k = refresh_display(titre=titre_img, legende=legende_img)   # haut : titre + touches
            if k is None:
                continue
            if continuer_possible and k in T_C:
                decision = "continuer"
            elif k in T_R:
                decision = "relancer"
            elif k in T_Q:
                decision = "quitter"

        if decision == "continuer":
            return True
        if decision == "quitter":
            return False
        # relancer : l'opérateur a (éventuellement) ajusté la lumière
        print(f"   🛠️  Recalage exposition — {nom} (auto puis figée)...")
        r = regler_exposition_auto_puis_figee(index, nom, cam.async_read)
        if not r["ok"]:
            print(f"   ❌ {nom} : réglage d'exposition non appliqué — {', '.join(r['echecs'])}")
            return False
        # boucle : on recontrôle après recalage


# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main():
    global urgence, TRAIN_OUTPUT_DIR
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     SEM — DÉPLOIEMENT MODÈLE ACT (Script 11)                        ║
║     Service Écoles-Médias (SEM) - DIP Genève                        ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    # OpenCV est indispensable au déploiement (caméras, masque, conversion
    # image→tenseur, cv2.fillPoly/bitwise_and). Sans lui, le script planterait
    # plus loin ; on échoue proprement ICI, avant tout engagement des servos.
    if not CV2_AVAILABLE:
        print("\n❌ OpenCV indisponible — déploiement impossible.")
        print("   Requis pour les caméras, le masque et les images du modèle.")
        print("   → Activez l'environnement lerobot (conda activate lerobot).")
        sys.exit(1)

    print(f"🖥️  Device     : {DEVICE}")
    print(f"📂 Modèles    : {TRAIN_BASE}")
    print(f"📷 Résolution : {CONFIG['camera_width']}×{CONFIG['camera_height']} @ {CONFIG['fps']} fps")

    # Sélection du MODÈLE (choix explicite, aucun défaut) PUIS du checkpoint.
    modele_dir = selectionner_modele()
    if modele_dir is None:
        sys.exit(1)
    TRAIN_OUTPUT_DIR = modele_dir

    # 1. Sélection du checkpoint (dans le modèle choisi)
    checkpoint_path = selectionner_checkpoint()
    if checkpoint_path is None:
        sys.exit(1)

    # Garde-fou module caméra unifié : sans lui, ni exposition ni contrôle image
    # → déploiement bloqué (fail-closed).
    if not CAMERA_AUTO_AVAILABLE:
        print("\n❌ Module caméra (SEM_so101_camera_auto) indisponible.")
        print(f"   Erreur : {CAMERA_AUTO_IMPORT_ERROR}")
        print("   → Impossible de régler/contrôler les caméras. Déploiement annulé.")
        sys.exit(1)

    # 2. Chargement du modèle ACT
    policy = charger_modele(checkpoint_path)
    if policy is None:
        sys.exit(1)

    # 3. Masque globale OBLIGATOIRE (le contrôle cam_top et l'inférence en dépendent).
    global _MASK_GLOBALE_IMG, _display_cam_top, _display_cam_follower
    mask_pts = charger_masque_globale()
    if not mask_pts:
        print("\n❌ Masque globale introuvable (camera_mask.json).")
        print("   Le contrôle de la caméra GLOBALE exige ce masque.")
        print("   → Lance d'abord le script 7, puis relance le déploiement.")
        sys.exit(1)
    _MASK_GLOBALE_IMG = construire_mask_image(
        mask_pts, CONFIG['camera_width'], CONFIG['camera_height'])
    print(f"\n✅ Masque globale actif ({len(mask_pts)} points)")

    # 4. Robot Follower AU REPOS AVANT les caméras : la vue de la PINCE dépend de
    #    la pose du bras → la scène doit être celle du repos, garantie par le
    #    script. Le bras reste connecté pour l'inférence.
    port_handler, packet_handler, calib = connexion_follower()
    if port_handler is None:
        sys.exit(1)

    # Le Follower est désormais connecté et ses servos sous couple. Toute sortie
    # avant l'inférence doit relâcher le couple proprement (sinon le bras reste
    # rigide) et fermer les caméras déjà ouvertes.
    def _abort_follower(code=1):
        try:
            for sid in range(1, 7):
                packet_handler.write1ByteTxRx(port_handler, sid, 40, 0)
        except Exception:
            pass
        try:
            port_handler.closePort()
        except Exception:
            pass
        if CV2_AVAILABLE:
            cv2.destroyAllWindows()
        sys.exit(code)

    # Caméras déclarées AVANT la préparation : _abort_cameras teste « if cam_top: »
    # → sûr même quand les caméras ne sont pas encore ouvertes. On l'utilise donc
    # uniformément pendant toute la phase de préparation.
    cam_top          = None
    cam_follower_cam = None

    def _abort_cameras(code=1):
        """Sortie propre pendant la phase caméra : libère les caméras déjà
        ouvertes PUIS le bras Follower (couple relâché + port fermé) via
        _abort_follower, qui termine le processus."""
        if cam_top:
            cam_top.disconnect()
        if cam_follower_cam:
            cam_follower_cam.disconnect()
        _abort_follower(code)

    # 5. Préparation caméra (repos → identification → connexion → exposition auto
    #    puis figée → contrôle image) sous protection : un Ctrl+C ou une exception
    #    imprévue doit relâcher le couple du Follower et fermer les caméras, jamais
    #    laisser le bras rigide.
    try:
        print("\n🎯 Position repos (avant contrôle caméra)...")
        if not aller_position_repos(packet_handler, port_handler, calib):
            print("❌ Position repos impossible au démarrage — déploiement annulé.")
            _abort_cameras(1)

        # 5a. Identification des deux caméras (robot déjà au repos).
        idx_top, idx_follower = identification_cameras()
        if idx_top is None or idx_follower is None:
            print("\n❌ Déploiement annulé : les deux caméras (globale + pince) sont requises.")
            _abort_cameras(1)

        # 5b. Connexion des caméras (ThreadedCamera) AVANT le réglage d'exposition,
        #     qui a besoin d'un flux actif pour converger puis figer l'exposition.
        if not CV2_AVAILABLE:
            print("\n❌ OpenCV indisponible — déploiement annulé.")
            _abort_cameras(1)

        cam_top = ThreadedCamera(
            idx_top, CAM_TOP,
            CONFIG['camera_width'], CONFIG['camera_height'], CONFIG['fps'])
        if not cam_top.connect() or not cam_top.is_connected:
            print("\n❌ Caméra globale non connectée — arrêt.")
            _abort_cameras(1)
        frame_test = cam_top.async_read()
        if frame_test is not None and frame_test.shape[:2] != (CONFIG['camera_height'], CONFIG['camera_width']):
            print(f"\n❌ Résolution caméra globale incorrecte : {frame_test.shape[:2]}")
            print(f"   Attendu : {(CONFIG['camera_height'], CONFIG['camera_width'])}")
            _abort_cameras(1)

        cam_follower_cam = ThreadedCamera(
            idx_follower, CAM_FOLLOWER,
            CONFIG['camera_width'], CONFIG['camera_height'], CONFIG['fps'])
        if not cam_follower_cam.connect() or not cam_follower_cam.is_connected:
            print("\n❌ Caméra pince non connectée — arrêt.")
            _abort_cameras(1)
        frame_test = cam_follower_cam.async_read()
        if frame_test is not None and frame_test.shape[:2] != (CONFIG['camera_height'], CONFIG['camera_width']):
            print(f"\n❌ Résolution caméra pince incorrecte : {frame_test.shape[:2]}")
            print(f"   Attendu : {(CONFIG['camera_height'], CONFIG['camera_width'])}")
            _abort_cameras(1)

        # Affichage : assigner les caméras d'affichage dès la connexion, pour que
        # refresh_display() montre les deux flux pendant le réglage et le contrôle.
        _display_cam_top = cam_top
        _display_cam_follower = cam_follower_cam

        # 5c. Réglage d'exposition UNE fois par session (auto puis figée + 50 Hz),
        #     adapté à la lumière réelle de la salle. Fail-closed.
        for cam, idx_cam, nom_cam, lib in ((cam_top, idx_top, CAM_TOP, "GLOBALE"),
                                           (cam_follower_cam, idx_follower, CAM_FOLLOWER, "PINCE")):
            print(f"\n🛠️  RÉGLAGE EXPOSITION — {lib} (auto puis figée)...")
            r = regler_exposition_auto_puis_figee(idx_cam, nom_cam, cam.async_read)
            if not r["ok"]:
                print(f"\n❌ {lib} : réglage d'exposition non appliqué — {', '.join(r['echecs'])}")
                _abort_cameras(1)

        # 5d. Contrôle image simple (image BRUTE, avant masque) : plancher physique
        #     + retour lumière. GLOBALE en zone utile du masque, PINCE en plein cadre.
        #     🔴 = arrêt ; 🟠 = l'opérateur décide ; autorisation = les deux.
        for cam, idx_cam, nom_cam, lib, est_glob in (
                (cam_top, idx_top, CAM_TOP, "GLOBALE", True),
                (cam_follower_cam, idx_follower, CAM_FOLLOWER, "PINCE", False)):
            print(f"\n🔎 CONTRÔLE IMAGE — {lib}")
            if not controle_camera_simple_interactif(cam, idx_cam, nom_cam, est_glob):
                print(f"\n❌ {lib} : image non exploitable — déploiement annulé.")
                _abort_cameras(0)

        # Fenêtre de préparation fermée avant l'inférence (qui utilise sa propre
        # fenêtre). Sans effet si elle n'a jamais été créée.
        try:
            cv2.destroyWindow('Cameras SO-ARM 101')
            cv2.waitKey(1)
        except Exception:
            pass

    except KeyboardInterrupt:
        print("\n\n🛑 ARRÊT pendant la préparation — couple du Follower coupé.")
        _abort_cameras(130)
    except Exception as e:
        print(f"\n❌ Erreur pendant la préparation du déploiement : {e}")
        _abort_cameras(1)

    # Stabilisation déterministe avant la première lecture du modèle : laisse les
    # threads caméra rafraîchir vers des frames post-réglage.
    time.sleep(0.5)

    # 8. Boucle d'inférence, sous protection CTRL+C (le robot est déjà
    #    connecté et au repos depuis l'étape 4).
    try:
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
        # 9. Nettoyage
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

            print("\n✅ Script 11 terminé proprement.")

        print("━" * 60)
        print(f"   Modèle utilisé     : {TRAIN_OUTPUT_DIR.name}")
        print(f"   Checkpoint utilisé : {checkpoint_path.parent.name}")
        print("━" * 60)


if __name__ == "__main__":
    main()
