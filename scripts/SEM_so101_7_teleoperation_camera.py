#!/usr/bin/env python3
"""
Script SEM_so101_7_teleoperation_camera.py
Téléopération Leader → Follower AVEC CAMÉRA
Basé EXACTEMENT sur le script 6 avec JUSTE l'ajout de la caméra
"""
import os
import sys
import json
import time
import math
import threading
import queue
import numpy as np

# Auto-activation de l'environnement lerobot si nécessaire
try:
    sys.path.append(os.path.expanduser('~/lerobot'))
    from dynamixel_sdk import *
    import cv2
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

# Variable globale pour arrêt propre
stop_threads = False
urgence = False  # CTRL+C = arrêt d'urgence : libération immédiate, pas de retour repos

# Masque de zone utile (polygone à 5 points du plateau), partagé avec scripts 8 et 12
MASK_FILE = os.path.expanduser("~/lerobot/calibration/camera_mask.json")

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
    """Charge la calibration d'un robot"""
    calib_file = os.path.expanduser(f"~/lerobot/calibration/{robot_type}_calibration.json")
    if os.path.exists(calib_file):
        with open(calib_file, 'r') as f:
            return json.load(f)
    return None

# Fichier externe centralisant la position repos (partagé entre tous les scripts)
REPOS_FILE = os.path.expanduser("~/lerobot/calibration/repos_position.json")

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

def charger_config_teleoperation(mode):
    """Charge la configuration COPIE/MIROIR"""
    config_file = os.path.expanduser(f"~/lerobot/calibration/teleoperation_config_{mode}.json")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            data = json.load(f)
            print(f"  📁 Configuration chargée depuis : {config_file}")
            return data.get('servos_miroir', [])
    else:
        print(f"  ⚠️ Pas de configuration trouvée, tout en COPIE par défaut")
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

def test_connexion_fluide(packet, port, robot_name, calib):
    """Test fluide de connexion avec calibration"""
    print(f"\n  🔄 Test de connexion {robot_name}...")

    # Activer le servo 6
    packet.write1ByteTxRx(port, 6, 40, 1)

    if calib and 'servo_6' in calib:
        centre = calib['servo_6']['center']
        min_val = calib['servo_6']['min']
        max_val = calib['servo_6']['max']

        # Calculer positions à 45° (environ 25% et 75% de l'amplitude)
        amplitude = max_val - min_val
        pos_25 = int(min_val + amplitude * 0.25)
        pos_75 = int(min_val + amplitude * 0.75)

        # Lire position actuelle
        pos_actuelle, _, _ = packet.read2ByteTxRx(port, 6, 56)

        # Séquence fluide : Actuel → Centre → 25% → 75% → Centre
        print("     → Centre...")
        mouvement_fluide(packet, port, 6, pos_actuelle, centre, 1.0)
        print("     → Fermé (45°)...")
        mouvement_fluide(packet, port, 6, centre, pos_25, 0.8)
        print("     → Ouvert (90°)...")
        mouvement_fluide(packet, port, 6, pos_25, pos_75, 1.2)
        print("     → Centre...")
        mouvement_fluide(packet, port, 6, pos_75, centre, 0.8)
    else:
        # Valeurs par défaut si pas de calibration
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
╔══════════════════════════════════════════════════════════╗
║     IDENTIFICATION LEADER/FOLLOWER                      ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Débrancher tout
    ports = detect_ports()
    while len(ports) > 0:
        print(f"⚠️ Débranchez tous les robots")
        input("   Entrée quand fait...")
        ports = detect_ports()

    # Leader
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

    # Charger calibration Leader pour test
    calib_l = charger_calibration('leader')

    # Test fluide Leader avec calibration
    test_connexion_fluide(lk, lp, "LEADER", calib_l)

    if input("\nPince du LEADER bougée? [O/N]: ").upper() != 'O':
        return None, None, None, None, None, None

    # Follower
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

    # Charger calibration Follower pour test
    calib_f = charger_calibration('follower')

    # Test fluide Follower avec calibration
    test_connexion_fluide(fk, fp, "FOLLOWER", calib_f)

    if input("\nPince du FOLLOWER bougée? [O/N]: ").upper() != 'O':
        return None, None, None, None, None, None

    print("\n✅ Identification réussie!")
    return lp, lk, fp, fk, calib_l, calib_f

def centrage_parallele(lk, lp, fk, fp, calib_l, calib_f):
    """Centre tous les servos EN PARALLÈLE de manière fluide"""
    print("\n🎯 Centrage simultané des robots...")

    # Activer tous les servos
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 1)
        fk.write1ByteTxRx(fp, i, 40, 1)

    # Lire positions actuelles
    pos_l = {}
    pos_f = {}
    for i in range(1, 7):
        pos_l[i], _, _ = lk.read2ByteTxRx(lp, i, 56)
        pos_f[i], _, _ = fk.read2ByteTxRx(fp, i, 56)

    # Mouvement simultané fluide vers centre
    duree = 2.0
    steps = int(duree * 50)

    for step in range(steps + 1):
        t = step / steps
        smooth = (1 - math.cos(t * math.pi)) / 2

        for i in range(1, 7):
            # Leader
            centre_l = calib_l[f'servo_{i}']['center'] if calib_l else 2048
            new_pos_l = int(pos_l[i] + (centre_l - pos_l[i]) * smooth)
            lk.write2ByteTxRx(lp, i, 42, new_pos_l)

            # Follower
            centre_f = calib_f[f'servo_{i}']['center'] if calib_f else 2048
            new_pos_f = int(pos_f[i] + (centre_f - pos_f[i]) * smooth)
            fk.write2ByteTxRx(fp, i, 42, new_pos_f)

        time.sleep(duree / steps)

    print("✅ Robots centrés")

def position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f):
    """Met les deux robots en position repos (repos partagé, séquence sûre)."""
    print("\n🏁 Position repos simultanée...")

    # Repos lu depuis le fichier unique partagé, atteint via la séquence sûre
    # (servo 4 en l'air d'abord, etc.) appliquée à l'identique aux deux robots
    repos_pct = charger_repos_pct()
    aller_a_position_2robots(lk, lp, fk, fp, calib_l, calib_f, repos_pct, duree=2.0)

    print("✅ Position repos atteinte (robot replié)")

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

    # Calcul ratio
    ratio = (pos_leader - min_l) / (max_l - min_l) if max_l > min_l else 0.5
    ratio = max(0, min(1, ratio))

    # Appliquer miroir si configuré
    if servo_id in servos_miroir:
        ratio = 1 - ratio

    pos_follower = int(min_f + ratio * (max_f - min_f))
    return max(min_f, min(max_f, pos_follower))

def teleoperation(lk, lp, fk, fp, calib_l, calib_f, mode, camera_index, mask_img=None):
    """Boucle principale de téléopération.
    `mask_img` : masque binaire précalculé (uint8 0/255). None = pas de masquage."""
    global stop_threads, urgence

    # AJOUT CAMÉRA - INIT
    cap = cv2.VideoCapture(camera_index)
    camera_ok = False
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
        cv2.namedWindow('Camera SO-ARM 101', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Camera SO-ARM 101', 1280, 720)
        camera_ok = True
        print("📷 Caméra activée")

    clear_screen()
    mode_name = "CÔTÉ À CÔTÉ" if mode == "cote" else "FACE À FACE"
    servos_miroir = charger_config_teleoperation(mode)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║     TÉLÉOPÉRATION - {mode_name:20}        ║
║     Servos miroir: {str(servos_miroir):20}         ║
╚══════════════════════════════════════════════════════════╝
    """)

    print("\n🎮 Commandes:")
    print("  [Q] + Enter : Quitter")
    print("  [F] + Enter : Flip mode (côté ↔ face)")
    print("  [M] + Enter : Refaire le masque caméra (téléop en pause)")
    print("-" * 40)

    # Libérer Leader, Activer Follower
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 0)
        fk.write1ByteTxRx(fp, i, 40, 1)

    print("\n✅ Téléopération active!")
    print("🤖 Bougez le LEADER, le FOLLOWER suit\n")

    running = True
    stop_threads = False
    cmd_queue = queue.Queue()
    input_paused = [False]  # liste = closure mutable pour le thread

    # Thread pour input non-bloquant
    def input_thread():
        while not stop_threads:
            if input_paused[0]:
                time.sleep(0.1)
                continue
            try:
                import select
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    cmd = input()
                    if cmd:
                        cmd_queue.put(cmd[0].upper())
            except:
                pass

    thread = threading.Thread(target=input_thread, daemon=True)
    thread.start()

    try:
        while running:
            # Check commandes
            try:
                cmd = cmd_queue.get_nowait()

                if cmd == 'Q':
                    print("\n👋 Arrêt de la téléopération...")
                    stop_threads = True
                    running = False

                elif cmd == 'F':
                    mode = "face" if mode == "cote" else "cote"
                    servos_miroir = charger_config_teleoperation(mode)
                    mode_name = "CÔTÉ À CÔTÉ" if mode == "cote" else "FACE À FACE"
                    print(f"\n🔄 Mode inversé : {mode_name}")
                    print(f"   Servos miroir : {servos_miroir}")

                elif cmd == 'M':
                    # Pause téléop pour refaire le masque caméra.
                    # Séquence : repos → verrouillage → masque → reprise (leader OFF)
                    print("\n🔧 Pause téléopération — refaire le masque caméra")
                    input_paused[0] = True
                    time.sleep(0.2)  # laisser le thread input voir le drapeau
                    if camera_ok:
                        cap.release()
                        cv2.destroyWindow('Camera SO-ARM 101')
                        cv2.waitKey(50)

                    # 1) Retour repos (avec fin de la danse), 2) verrouillage des deux bras
                    repos_pct = charger_repos_pct()
                    deja_repos = (_est_en_repos_1robot(lk, lp, calib_l, repos_pct)
                                  and _est_en_repos_1robot(fk, fp, calib_f, repos_pct))
                    if deja_repos:
                        print("✅ Déjà au repos — verrouillage des servos.")
                        for i in range(1, 7):
                            lk.write1ByteTxRx(lp, i, 40, 1)
                            fk.write1ByteTxRx(fp, i, 40, 1)
                    else:
                        print("🏁 Retour repos avant la définition du masque...")
                        position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)

                    # 3) Définition du masque (interactif)
                    new_pts = creer_masque_interactif(camera_index)
                    if new_pts:
                        mask_img = construire_mask_image(new_pts, 640, 360)
                        print("✅ Nouveau masque actif.")
                    else:
                        print("⚠️  Recréation annulée — masque inchangé.")

                    # 4) Rouverture caméra
                    if camera_ok:
                        cap = cv2.VideoCapture(camera_index)
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
                        cv2.namedWindow('Camera SO-ARM 101', cv2.WINDOW_NORMAL)
                        cv2.resizeWindow('Camera SO-ARM 101', 1280, 720)

                    # 5) Restaurer l'état téléop : Leader couple OFF (Follower déjà ON)
                    for i in range(1, 7):
                        lk.write1ByteTxRx(lp, i, 40, 0)

                    # Vider d'éventuelles commandes parasites accumulées pendant la pause
                    while not cmd_queue.empty():
                        try:
                            cmd_queue.get_nowait()
                        except queue.Empty:
                            break
                    input_paused[0] = False
                    print("▶️  Téléopération reprise.")

            except queue.Empty:
                pass

            # Téléopération active - lecture et écriture groupées
            positions_leader = {}
            for servo_id in range(1, 7):
                pos, result, _ = lk.read2ByteTxRx(lp, servo_id, 56)
                if result == 0:
                    positions_leader[servo_id] = pos

            # Envoyer toutes les commandes au Follower
            for servo_id, pos_l in positions_leader.items():
                pos_f = mapper_position(pos_l, servo_id, calib_l, calib_f, servos_miroir)
                fk.write2ByteTxRx(fp, servo_id, 42, pos_f)

            # AJOUT CAMÉRA - AFFICHAGE (6 lignes seulement)
            if camera_ok:
                ret, frame = cap.read()
                if ret:
                    if mask_img is not None:
                        frame = cv2.bitwise_and(frame, frame, mask=mask_img)
                    cv2.imshow('Camera SO-ARM 101', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        stop_threads = True

            time.sleep(0.01)

    except KeyboardInterrupt:
        stop_threads = True
        urgence = True
        print("\n🛑 ARRÊT D'URGENCE (CTRL+C) — libération immédiate des servos.")
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 0)
            fk.write1ByteTxRx(fp, i, 40, 0)

    # AJOUT CAMÉRA - FERMETURE (3 lignes seulement)
    if camera_ok:
        cap.release()
        cv2.destroyAllWindows()
        print("📷 Caméra fermée")


def detect_cameras():
    """Détecte les caméras disponibles (sonde les indices 0 à 9)."""
    cameras = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cameras.append(i)
            cap.release()
    return cameras


def apercu_camera(camera_index):
    """Aperçu bref avant les robots : ouvre la caméra à l'indice donné,
    force 640x360, affiche la résolution réelle et une image figée, puis
    libère. Pas de phase de validation."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"❌ Impossible d'ouvrir la caméra {camera_index}")
        return False
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    largeur = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    hauteur = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"\n📷 Caméra détectée à l'index {camera_index}")
    print(f"   Résolution réelle : {largeur}x{hauteur} @ {fps:.0f} fps")
    ret, frame = cap.read()
    if ret:
        cv2.putText(frame, f"{largeur}x{hauteur}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow('Apercu camera', frame)
        cv2.waitKey(100)
        input("\nAppuyez sur ENTRÉE pour passer à l'identification des robots...")
        cv2.destroyWindow('Apercu camera')
        cv2.waitKey(1)
    cap.release()
    return True


# ============================================
# MASQUE DE ZONE UTILE (polygone 5 points du plateau)
# ============================================

def creer_masque_interactif(camera_index):
    """Création obligatoire du masque : clic des 5 points du plateau,
    aperçu masqué, sauvegarde dans MASK_FILE.
    Retourne la liste des 5 points (ou None si abandon)."""
    print("\n" + "="*60)
    print("🎯 DÉFINITION DU MASQUE DE ZONE UTILE (obligatoire)")
    print("="*60)
    print("\n📌 Une image figée de la caméra va s'ouvrir.")
    print("   Clique sur 5 points qui délimitent le plateau,")
    print("   dans le sens horaire en partant du haut-gauche.")
    print("\n   ESC pour abandonner. Appuie sur ENTRÉE pour commencer...")
    input()

    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("❌ Impossible de capturer une image.")
        return None

    h, w = frame.shape[:2]
    while True:  # permet de recommencer si l'aperçu ne convient pas
        points = []
        display = frame.copy()
        window = "Cliquez 5 points (sens horaire en partant du haut-gauche)"

        def on_click(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN and len(points) < 5:
                points.append((x, y))
                cv2.circle(display, (x, y), 6, (0, 255, 0), -1)
                cv2.putText(display, str(len(points)), (x+8, y-8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                if len(points) > 1:
                    cv2.line(display, points[-2], points[-1], (0, 255, 0), 2)
                if len(points) == 5:
                    cv2.line(display, points[-1], points[0], (0, 255, 0), 2)
                cv2.imshow(window, display)

        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window, 1280, 720)
        cv2.setMouseCallback(window, on_click)
        cv2.imshow(window, display)

        abandon = False
        while len(points) < 5:
            key = cv2.waitKey(50) & 0xFF
            if key == 27:  # ESC
                abandon = True
                break
        cv2.destroyWindow(window)
        cv2.waitKey(50)
        if abandon:
            print("❌ Définition du masque abandonnée.")
            return None

        # Aperçu masqué
        pts = np.array(points, np.int32)
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [pts], 255)
        apercu = cv2.bitwise_and(frame, frame, mask=mask)
        cv2.putText(apercu, "Apercu - validez dans le terminal", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        cv2.namedWindow("Apercu du masque", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Apercu du masque", 1280, 720)
        cv2.imshow("Apercu du masque", apercu)
        cv2.waitKey(100)

        print(f"\n   Points cliqués : {points}")
        choix = input("   [V = valider / R = recommencer / A = abandonner] : ").strip().upper()
        cv2.destroyWindow("Apercu du masque")
        cv2.waitKey(50)

        if choix == 'V':
            data = {
                "shape": "polygon",
                "points": [[int(x), int(y)] for x, y in points],
                "reference_resolution": {"width": w, "height": h},
            }
            os.makedirs(os.path.dirname(MASK_FILE), exist_ok=True)
            with open(MASK_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✅ Masque sauvegardé : {MASK_FILE}")
            return points
        elif choix == 'A':
            print("❌ Abandon.")
            return None
        else:
            print(f"⚠️  Saisie '{choix}' non reconnue — on recommence la sélection des points.")
        # sinon → recommencer


def charger_ou_creer_masque(camera_index, forcer=False):
    """Si MASK_FILE existe ET forcer=False → charge silencieusement.
    Sinon (ou si fichier absent) → lance la création interactive (obligatoire)."""
    if not forcer and os.path.exists(MASK_FILE):
        try:
            with open(MASK_FILE, 'r') as f:
                data = json.load(f)
            pts = [tuple(p) for p in data["points"]]
            ref = data.get("reference_resolution", {})
            print(f"✅ Masque chargé : {len(pts)} points "
                  f"(réf. {ref.get('width','?')}×{ref.get('height','?')})")
            return pts
        except Exception as e:
            print(f"⚠️  Masque existant illisible ({e}), recréation nécessaire.")
    if forcer:
        print("\n🔄 Recréation du masque demandée (--refaire-masque).")
    else:
        print("\n📌 Aucun masque trouvé — création obligatoire avant la téléopération.")
    return creer_masque_interactif(camera_index)


def construire_mask_image(points, width, height):
    """Construit le masque binaire (uint8 0/255) à partir des 4 points."""
    if points is None:
        return None
    mask = np.zeros((height, width), dtype=np.uint8)
    pts = np.array(points, np.int32)
    cv2.fillPoly(mask, [pts], 255)
    return mask


def main():
    global stop_threads

    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     TÉLÉOPÉRATION SO-ARM 101                            ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Détection et aperçu de la caméra (avant les robots)
    cameras = detect_cameras()
    if not cameras:
        print("\n❌ Aucune caméra détectée.")
        print("   Branchez une caméra USB et relancez le script.")
        return
    camera_index = cameras[0]
    apercu_camera(camera_index)

    # Masque de zone utile : menu interactif si un masque existe déjà
    # Flag --refaire-masque utilisable pour automatiser (force la recréation sans menu)
    forcer_masque = '--refaire-masque' in sys.argv
    if os.path.exists(MASK_FILE) and not forcer_masque:
        print("\n🎭 GESTION DU MASQUE")
        print("  [Entrée] : Garder le masque actuel")
        print("  [M]      : Forcer la création d'un nouveau masque")
        if input("Choix : ").strip().upper() == 'M':
            forcer_masque = True
    mask_pts = charger_ou_creer_masque(camera_index, forcer=forcer_masque)
    mask_img = construire_mask_image(mask_pts, 640, 360) if mask_pts else None
    if mask_img is None:
        print("⚠️  Pas de masque actif — la téléopération continuera sans masquage.")

    # Identification
    result = identification_guidee()
    if not result[0]:
        print("❌ Identification échouée")
        return

    lp, lk, fp, fk, calib_l, calib_f = result

    # Choix mode
    print("\n[C]ôte à côte ou [F]ace à face?")
    choix = input("Choix [C]: ").upper()
    mode = "face" if choix == 'F' else "cote"
    mode_name = "CÔTÉ À CÔTÉ" if mode == "cote" else "FACE À FACE"

    print(f"\n✅ Mode sélectionné : {mode_name}")

    # Centrage automatique après connexion
    print("\n🎯 Positionnement automatique...")
    centrage_parallele(lk, lp, fk, fp, calib_l, calib_f)

    time.sleep(0.5)  # Petite pause

    # Position repos automatique
    position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)

    print("\n⚠️  Tenez le LEADER - Téléopération dans 3 secondes...")
    time.sleep(3)

    # Téléopération
    teleoperation(lk, lp, fk, fp, calib_l, calib_f, mode, camera_index, mask_img=mask_img)

    if urgence:
        # Arrêt d'urgence (CTRL+C) : servos déjà libérés, AUCUN retour repos
        lp.closePort()
        fp.closePort()
        print("\n✅ Arrêt d'urgence terminé (aucun retour repos).")
    else:
        # Position repos avant libération — sauf si déjà au repos (fin de la danse)
        stop_threads = True

        # Activer tous les servos pour le mouvement final
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 1)
            fk.write1ByteTxRx(fp, i, 40, 1)

        repos_pct = charger_repos_pct()
        deja_repos = (_est_en_repos_1robot(lk, lp, calib_l, repos_pct)
                      and _est_en_repos_1robot(fk, fp, calib_f, repos_pct))
        if deja_repos:
            print("\n✅ Déjà en position repos (pas de repositionnement).")
        else:
            print("\n🏁 Retour position repos...")
            position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f)

        print("\n⚠️  Assurez-vous de tenir les robots")
        time.sleep(2)

        # Libération finale
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 0)
            fk.write1ByteTxRx(fp, i, 40, 0)

        # Fermeture
        lp.closePort()
        fp.closePort()

        print("\n✅ Téléopération terminée!")
        print("📊 Configuration utilisée :")
        print(f"   Mode : {mode_name}")
        print(f"   Fichier : ~/lerobot/calibration/teleoperation_config_{mode}.json")

if __name__ == "__main__":
    main()
