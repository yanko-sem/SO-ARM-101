#!/usr/bin/env python3
"""
Script SEM_so101_7_teleoperation_camera.py
Téléopération Leader → Follower (temps réel) AVEC CAMÉRA + masque de zone utile.
Basé sur le script 6 validé (Phase 5) + couche caméra/masque ajoutée :
détection/aperçu caméra, masque obligatoire (polygone 5 points du plateau),
affichage masqué temps réel, commande M pour refaire le masque.
"""
import os
import sys
import json
import time
import math
import threading
import queue
import select

# Auto-activation de l'environnement lerobot si nécessaire
try:
    sys.path.append(os.path.expanduser('~/lerobot'))
    from dynamixel_sdk import *
    import cv2
    import numpy as np
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

# Variable globale pour arrêt propre du thread clavier
stop_threads = False

# Noms des servos (source unique)
SERVO_NAMES = {1: "BASE", 2: "ÉPAULE", 3: "COUDE",
               4: "POIGNET-F", 5: "POIGNET-R", 6: "PINCE"}

# Amplitude minimale exigee d'une calibration pour etre exploitable (meme seuil que scripts 2/3/4/5)
MIN_AMPLITUDE = 500

# Fichier externe centralisant la position repos (partage entre tous les scripts)
REPOS_FILE = os.path.expanduser("~/lerobot/calibration/repos_position.json")

# Masque de zone utile (polygone 5 points du plateau), partage avec les scripts 8 et 12
MASK_FILE = os.path.expanduser("~/lerobot/calibration/camera_mask.json")

def clear_screen():
    os.system('clear')

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

def lire_position(packet, port, servo_id):
    """Lecture verifiee de la position (registre 56). Retourne (position, ok)."""
    pos, result, error = packet.read2ByteTxRx(port, servo_id, 56)
    if result != COMM_SUCCESS or error != 0:
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
    EN PARALLÈLE sur les deux robots (cohérent avec les scripts 8/12). 2700 et 1027
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
    print("     → Fermé (45°)...")
    mouvement_fluide(packet, port, 6, centre, pos_25, 0.8)
    print("     → Ouvert (90°)...")
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

def centrage_parallele(lk, lp, fk, fp, cl, cf):
    """Centre tous les servos EN PARALLÈLE de manière fluide (les deux robots).
    Lectures vérifiées : retourne False si une position de départ est illisible
    (centrage annulé), True sinon."""
    print("\n🎯 Centrage simultané des robots...")

    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 1)
        fk.write1ByteTxRx(fp, i, 40, 1)

    pos_l, pos_f = {}, {}
    for i in range(1, 7):
        p, ok = lire_position(lk, lp, i)
        if not ok:
            print(f"❌ Lecture Leader servo {i} impossible — centrage annulé")
            return False
        pos_l[i] = p
        p, ok = lire_position(fk, fp, i)
        if not ok:
            print(f"❌ Lecture Follower servo {i} impossible — centrage annulé")
            return False
        pos_f[i] = p

    duree = 2.0
    steps = int(duree * 50)
    for step in range(steps + 1):
        t = step / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        for i in range(1, 7):
            centre_l = cl[f'servo_{i}']['center']
            lk.write2ByteTxRx(lp, i, 42, int(pos_l[i] + (centre_l - pos_l[i]) * smooth))
            centre_f = cf[f'servo_{i}']['center']
            fk.write2ByteTxRx(fp, i, 42, int(pos_f[i] + (centre_f - pos_f[i]) * smooth))
        time.sleep(duree / steps)

    print("✅ Robots centrés")
    return True

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
    print("✅ Position repos atteinte (robot replié)")
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

# ============================================
# CAMÉRA + MASQUE DE ZONE UTILE (polygone 5 points du plateau)
# ============================================

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
    """Aperçu bref avant les robots : ouvre la caméra, force 640x360, affiche la
    résolution réelle et une image figée, puis libère. Pas de validation."""
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

def creer_masque_interactif(camera_index):
    """Création du masque : clic des 5 points du plateau, aperçu masqué, sauvegarde
    dans MASK_FILE. Les points sont définis sur le frame à sa TAILLE RÉELLE (stockée
    en référence). Retourne (points, (w, h)) ou (None, None) si abandon."""
    print("\n" + "=" * 60)
    print("🎯 DÉFINITION DU MASQUE DE ZONE UTILE (obligatoire)")
    print("=" * 60)
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
        return None, None

    h, w = frame.shape[:2]
    while True:  # permet de recommencer si l'aperçu ne convient pas
        points = []
        display = frame.copy()
        window = "Cliquez 5 points (sens horaire en partant du haut-gauche)"

        def on_click(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN and len(points) < 5:
                points.append((x, y))
                cv2.circle(display, (x, y), 6, (0, 255, 0), -1)
                cv2.putText(display, str(len(points)), (x + 8, y - 8),
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
            return None, None

        # Aperçu masqué (à la taille réelle du frame)
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
            tmp = MASK_FILE + ".tmp"
            with open(tmp, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, MASK_FILE)
            print(f"✅ Masque sauvegardé : {MASK_FILE}")
            return points, (w, h)
        elif choix == 'A':
            print("❌ Abandon.")
            return None, None
        else:
            print(f"⚠️  Saisie '{choix}' non reconnue — on recommence la sélection des points.")
        # sinon -> recommencer

def charger_ou_creer_masque(camera_index, forcer=False):
    """Si MASK_FILE existe ET forcer=False -> charge (points + résolution de référence).
    Sinon (ou si fichier absent/illisible) -> lance la création interactive (obligatoire).
    Retourne (points, (w, h)) ou (None, None) si abandon."""
    if not forcer and os.path.exists(MASK_FILE):
        try:
            with open(MASK_FILE, 'r') as f:
                data = json.load(f)
            # Validation stricte : un fichier corrompu mais contenant une clé "points"
            # ne doit PAS être accepté — on force la recréation dans ce cas.
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
            # Résolution de référence : exploitable uniquement si width/height numériques > 0
            ref = data.get("reference_resolution", {})
            rw = ref.get("width") if isinstance(ref, dict) else None
            rh = ref.get("height") if isinstance(ref, dict) else None
            ref_wh = None
            if (isinstance(rw, (int, float)) and not isinstance(rw, bool)
                    and isinstance(rh, (int, float)) and not isinstance(rh, bool)
                    and rw > 0 and rh > 0):
                ref_wh = (int(rw), int(rh))
            print(f"✅ Masque chargé : {len(pts)} points "
                  f"(réf. {ref_wh[0] if ref_wh else '?'}×{ref_wh[1] if ref_wh else '?'})")
            return pts, ref_wh
        except Exception as e:
            print(f"⚠️  Masque existant illisible ou invalide ({e}), recréation nécessaire.")
    if forcer:
        print("\n🔄 Recréation du masque demandée (--refaire-masque).")
    else:
        print("\n📌 Aucun masque trouvé — création obligatoire avant la téléopération.")
    return creer_masque_interactif(camera_index)

def construire_mask_image(points, ref_wh, target_w, target_h):
    """Construit le masque binaire (uint8 0/255) à la résolution CIBLE (taille réelle
    du frame). Met les points à l'échelle depuis ref_wh si elle diffère de la cible.
    Retourne None si points est None."""
    if points is None:
        return None
    if ref_wh is not None and ref_wh[0] and ref_wh[1] \
            and (ref_wh[0] != target_w or ref_wh[1] != target_h):
        sx = target_w / ref_wh[0]
        sy = target_h / ref_wh[1]
        pts_scaled = [(int(round(x * sx)), int(round(y * sy))) for (x, y) in points]
    else:
        pts_scaled = [(int(x), int(y)) for (x, y) in points]
    mask = np.zeros((target_h, target_w), dtype=np.uint8)
    cv2.fillPoly(mask, [np.array(pts_scaled, np.int32)], 255)
    return mask

def teleoperation(lk, lp, fk, fp, calib_l, calib_f, mode, servos_miroir,
                  camera_index, mask_pts, mask_ref_wh):
    """Boucle principale de téléopération temps réel AVEC caméra. La config
    (servos_miroir) est déjà chargée et validée par main. `mask_pts` (+ `mask_ref_wh`)
    décrit le masque obligatoire ; le masque binaire est (re)construit à la TAILLE
    RÉELLE du frame. Sortie normale = touche Q (terminal) ou q (fenêtre vidéo).
    Un CTRL+C n'est PAS capté ici : il remonte à main (try/finally global).
    La caméra est OBLIGATOIRE (Phase 6) : refus si indisponible. Le try/finally
    interne garantit la libération de la caméra (CTRL+C, exception ou sortie Q)."""
    global stop_threads

    # --- Init caméra (OBLIGATOIRE en Phase 6 : refus si indisponible) ---
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        try:
            cap.release()
        except Exception:
            pass
        raise RuntimeError("Caméra indisponible au lancement de la téléopération — Phase 6 impossible.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    cv2.namedWindow('Camera SO-ARM 101', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Camera SO-ARM 101', 1280, 720)
    print("📷 Caméra activée")

    # Masque binaire construit paresseusement sur le premier frame (taille réelle)
    mask_img = None
    mask_built = False

    try:
        clear_screen()
        mode_name = "CÔTÉ À CÔTÉ" if mode == "cote" else "FACE À FACE"

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
        print("  [q] (fenêtre vidéo) : Quitter")
        print("-" * 40)

        # Libérer Leader, activer Follower
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 0)
            fk.write1ByteTxRx(fp, i, 40, 1)

        print("\n✅ Téléopération active!")
        print("🤖 Bougez le LEADER, le FOLLOWER suit\n")

        running = True
        stop_threads = False
        cmd_queue = queue.Queue()
        input_paused = [False]  # liste = closure mutable (pause pendant la création du masque)

        # Thread d'entrée clavier non bloquant
        def input_thread():
            while not stop_threads:
                if input_paused[0]:
                    time.sleep(0.1)
                    continue
                try:
                    if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                        cmd = input()
                        if cmd:
                            cmd_queue.put(cmd[0].upper())
                except Exception:
                    pass

        thread = threading.Thread(target=input_thread, daemon=True)
        thread.start()

        while running:
            # Commandes clavier
            try:
                cmd = cmd_queue.get_nowait()

                if cmd == 'Q':
                    print("\n👋 Arrêt de la téléopération...")
                    stop_threads = True
                    running = False

                elif cmd == 'F':
                    nouveau_mode = "face" if mode == "cote" else "cote"
                    nouveau_miroir = charger_config_teleoperation(nouveau_mode)
                    if nouveau_miroir is None:
                        # Refus de la bascule : on NE coupe PAS la téléop, on garde le mode courant
                        print(f"\n⚠️  Configuration du mode demandé absente ou invalide — "
                              f"mode {mode_name} conservé.")
                        print("    Exécutez le script 5 pour configurer ce mode.")
                    else:
                        mode = nouveau_mode
                        servos_miroir = nouveau_miroir
                        mode_name = "CÔTÉ À CÔTÉ" if mode == "cote" else "FACE À FACE"
                        print(f"\n🔄 Mode inversé : {mode_name}")
                        print(f"   Servos miroir : {servos_miroir}")

                elif cmd == 'M':
                    # Pause téléop pour refaire le masque caméra.
                    # Séquence : repos -> verrouillage -> masque -> reprise (leader OFF).
                    print("\n🔧 Pause téléopération — refaire le masque caméra")
                    input_paused[0] = True
                    time.sleep(0.2)  # laisser le thread input voir le drapeau
                    cap.release()
                    cv2.destroyWindow('Camera SO-ARM 101')
                    cv2.waitKey(50)

                    # 1) Retour repos (si nécessaire), 2) verrouillage des deux bras
                    repos_pct, _ = charger_repos_pct()
                    etat_l = _est_en_repos_1robot(lk, lp, calib_l, repos_pct)
                    etat_f = _est_en_repos_1robot(fk, fp, calib_f, repos_pct)
                    if etat_l is True and etat_f is True:
                        print("✅ Déjà au repos — verrouillage des servos.")
                        for i in range(1, 7):
                            lk.write1ByteTxRx(lp, i, 40, 1)
                            fk.write1ByteTxRx(fp, i, 40, 1)
                    else:
                        print("🏁 Retour repos avant la définition du masque...")
                        if not position_repos_parallele(lk, lp, fk, fp, calib_l, calib_f):
                            # Retour repos raté = état des bras INCERTAIN : on ne refait PAS le
                            # masque et on arrête proprement (le finally libère la caméra, le
                            # try/finally global de main libère les servos et ferme les ports).
                            input_paused[0] = False
                            print("❌ Retour repos impossible — recréation du masque annulée, arrêt de la téléopération.")
                            raise RuntimeError("Retour repos impossible pendant la recréation du masque (commande M).")

                    # 3) Définition du masque (interactif)
                    new_pts, new_ref = creer_masque_interactif(camera_index)
                    if new_pts:
                        mask_pts = new_pts
                        mask_ref_wh = new_ref
                        mask_built = False  # reconstruit au prochain frame (taille réelle)
                        print("✅ Nouveau masque actif.")
                    else:
                        print("⚠️  Recréation annulée — masque inchangé.")

                    # 4) Réouverture caméra (obligatoire en Phase 6 : refus si échec)
                    cap = cv2.VideoCapture(camera_index)
                    if not cap.isOpened():
                        input_paused[0] = False
                        print("❌ Caméra indisponible après recréation du masque — arrêt de la téléopération.")
                        raise RuntimeError("Caméra indisponible après recréation du masque (commande M).")
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

            # Lecture Leader -> écriture Follower (servo ignoré si la lecture échoue).
            # CHOIX INTENTIONNEL : on ne vérifie que `result` (intégrité de la lecture),
            # PAS l'octet `error` (drapeau d'alarme matérielle du servo : surcharge,
            # surchauffe...). En suivi temps réel, la position reste valide même si ce
            # drapeau est levé ; passer par lire_position() (qui rejette sur error != 0)
            # ferait FIGER l'articulation du Follower sur une alarme transitoire — non
            # souhaitable ici. Les fonctions de séquence, elles, utilisent bien
            # lire_position() car un calcul de trajectoire doit s'annuler au moindre doute.
            positions_leader = {}
            for servo_id in range(1, 7):
                pos, result, _ = lk.read2ByteTxRx(lp, servo_id, 56)
                if result == COMM_SUCCESS:
                    positions_leader[servo_id] = pos

            for servo_id, pos_l in positions_leader.items():
                pos_f = mapper_position(pos_l, servo_id, calib_l, calib_f, servos_miroir)
                fk.write2ByteTxRx(fp, servo_id, 42, pos_f)

            # --- Affichage caméra (masqué). Masque construit à la TAILLE RÉELLE du frame. ---
            ret, frame = cap.read()
            if ret:
                if not mask_built and mask_pts is not None:
                    h_real, w_real = frame.shape[:2]
                    mask_img = construire_mask_image(mask_pts, mask_ref_wh, w_real, h_real)
                    if mask_ref_wh is not None and (mask_ref_wh[0] != w_real or mask_ref_wh[1] != h_real):
                        print(f"⚠️  Résolution caméra réelle {w_real}x{h_real} ≠ référence "
                              f"{mask_ref_wh[0]}x{mask_ref_wh[1]} — masque ajusté à l'échelle.")
                    mask_built = True
                if mask_img is not None:
                    frame = cv2.bitwise_and(frame, frame, mask=mask_img)
                cv2.imshow('Camera SO-ARM 101', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\n👋 Arrêt demandé (fenêtre vidéo)...")
                    stop_threads = True
                    running = False

            time.sleep(0.01)

    finally:
        stop_threads = True
        try:
            cap.release()
        except Exception:
            pass
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        print("📷 Caméra fermée")

def main():
    global stop_threads

    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     TÉLÉOPÉRATION SO-ARM 101                            ║
╚══════════════════════════════════════════════════════════╝
    """)

    # --- Calibration OBLIGATOIRE des DEUX robots, validée AVANT tout matériel ---
    calib_l = charger_calibration('leader')
    calib_f = charger_calibration('follower')
    if not calibration_complete(calib_l):
        print("❌ Calibration Leader absente, incomplète ou invalide — faites la Phase 3.")
        return
    if not calibration_complete(calib_f):
        print("❌ Calibration Follower absente, incomplète ou invalide — faites la Phase 3.")
        return

    # --- Caméra : détection + aperçu (avant les robots) ---
    cameras = detect_cameras()
    if not cameras:
        print("\n❌ Aucune caméra détectée.")
        print("   Branchez une caméra USB et relancez le script.")
        return
    camera_index = cameras[0]
    apercu_camera(camera_index)

    # --- Masque de zone utile OBLIGATOIRE (défini avant tout branchement robot) ---
    # Menu si un masque existe déjà ; --refaire-masque force la recréation sans menu.
    forcer_masque = '--refaire-masque' in sys.argv
    if os.path.exists(MASK_FILE) and not forcer_masque:
        print("\n🎭 GESTION DU MASQUE")
        print("  [Entrée] : Garder le masque actuel")
        print("  [M]      : Forcer la création d'un nouveau masque")
        if input("Choix [Entrée/M] : ").strip().upper() == 'M':
            forcer_masque = True
    mask_pts, mask_ref_wh = charger_ou_creer_masque(camera_index, forcer=forcer_masque)
    if mask_pts is None:
        # Fail-closed : pas de masque valide = pas de téléopération caméra.
        # Aucun robot n'est encore branché -> arrêt propre sans nettoyage matériel.
        print("\n❌ Masque non défini — arrêt (le masque est obligatoire en Phase 6).")
        cv2.destroyAllWindows()
        return

    lp = fp = lk = fk = None
    urgence = False

    try:
        # Identification guidée (calibrations déjà validées)
        ok, lp, lk, fp, fk = identification_guidee(calib_l, calib_f)
        if not ok:
            print("❌ Identification échouée")
            return
        cl, cf = calib_l, calib_f

        # Choix mode explicite
        mode, mode_name = choisir_mode()

        # Configuration OBLIGATOIRE pour le mode choisi (refus dur si absente/invalide)
        servos_miroir = charger_config_teleoperation(mode)
        if servos_miroir is None:
            print(f"❌ Configuration {mode_name} absente ou invalide.")
            print("   Exécutez d'abord le script 5 (SEM_so101_5_config_teleoperation.py) pour ce mode.")
            return
        print(f"\n✅ Mode sélectionné : {mode_name}")

        # Centrage (vérifié)
        print("\n🎯 Positionnement automatique...")
        if not centrage_parallele(lk, lp, fk, fp, cl, cf):
            print("❌ Centrage impossible (lecture servo) — arrêt.")
            return

        time.sleep(0.5)

        # Position repos initiale (vérifiée + annoncée)
        if not position_repos_parallele(lk, lp, fk, fp, cl, cf):
            print("❌ Position repos impossible (lecture servo) — arrêt.")
            return

        print("\n⚠️  Tenez le LEADER - Téléopération dans 3 secondes...")
        time.sleep(3)

        # Téléopération avec caméra (sortie normale = Q/q ; CTRL+C remonte au except global)
        teleoperation(lk, lp, fk, fp, cl, cf, mode, servos_miroir,
                      camera_index, mask_pts, mask_ref_wh)

        # Sortie normale -> retour repos avant libération
        print("\n🏁 Retour position repos...")
        position_repos_parallele(lk, lp, fk, fp, cl, cf)
        print("\n⚠️  Assurez-vous de tenir les robots")
        time.sleep(2)

    except KeyboardInterrupt:
        urgence = True
        print("\n🛑 Interruption (CTRL+C) — libération immédiate, aucun retour repos.")
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
    finally:
        # Nettoyage GARANTI : arrêt du thread clavier, libération best-effort, fermeture
        stop_threads = True
        cleanup_ports(lp, fp, lk, fk, release=True)
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        if urgence:
            print("\n✅ Arrêt d'urgence terminé (aucun retour repos).")
        else:
            print("\n✅ Téléopération terminée !")

if __name__ == "__main__":
    main()
