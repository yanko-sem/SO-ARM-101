#!/usr/bin/env python3
"""
Script SEM_so101_teleoperation.py
Téléopération Leader → Follower

"""
import os
import sys
import json
import time
import math
import threading
import queue

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

# Variable globale pour arrêt propre
stop_threads = False
urgence = False  # CTRL+C = arrêt d'urgence : libération immédiate, pas de retour repos

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

    # --- Phase 0 (conditionnelle, par robot) ---
    pos4_l, _, _ = lk.read2ByteTxRx(lp, 4, 56)
    if pos4_l > 2700 and not _est_en_repos_1robot(lk, lp, cl, repos_pct):
        pos2_l, _, _ = lk.read2ByteTxRx(lp, 2, 56)
        mouvement_fluide(lk, lp, 2, pos2_l, min(pos2_l, 1027), duree)
    pos4_f, _, _ = fk.read2ByteTxRx(fp, 4, 56)
    if pos4_f > 2700 and not _est_en_repos_1robot(fk, fp, cf, repos_pct):
        pos2_f, _, _ = fk.read2ByteTxRx(fp, 2, 56)
        mouvement_fluide(fk, fp, 2, pos2_f, min(pos2_f, 1027), duree)

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

def teleoperation(lk, lp, fk, fp, calib_l, calib_f, mode):
    """Boucle principale de téléopération"""
    global stop_threads, urgence

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

    # Thread pour input non-bloquant
    def input_thread():
        while not stop_threads:
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

            time.sleep(0.01)

    except KeyboardInterrupt:
        stop_threads = True
        urgence = True
        print("\n🛑 ARRÊT D'URGENCE (CTRL+C) — libération immédiate des servos.")
        for i in range(1, 7):
            lk.write1ByteTxRx(lp, i, 40, 0)
            fk.write1ByteTxRx(fp, i, 40, 0)

def main():
    global stop_threads

    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     TÉLÉOPÉRATION SO-ARM 101                            ║
╚══════════════════════════════════════════════════════════╝
    """)

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
    teleoperation(lk, lp, fk, fp, calib_l, calib_f, mode)

    if urgence:
        # Arrêt d'urgence (CTRL+C) : servos déjà libérés, AUCUN retour repos
        lp.closePort()
        fp.closePort()
        print("\n✅ Arrêt d'urgence terminé (aucun retour repos).")
    else:
        # Position repos avant libération
        print("\n🏁 Retour position repos...")
        stop_threads = True

        # Activer tous les servos pour le mouvement final
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

        # Fermeture
        lp.closePort()
        fp.closePort()

        print("\n✅ Téléopération terminée!")
        print("📊 Configuration utilisée :")
        print(f"   Mode : {mode_name}")
        print(f"   Fichier : ~/lerobot/calibration/teleoperation_config_{mode}.json")

if __name__ == "__main__":
    main()
