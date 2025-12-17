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

def clear_screen():
    os.system('clear')

def detect_ports():
    """Détecte les ports USB disponibles"""
    ports = []
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']:
        if os.path.exists(port):
            os.system(f"sudo chmod 666 {port} 2>/dev/null")
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
    """Met les deux robots en position repos IDENTIQUE (même % pour chaque servo)"""
    print("\n🏁 Position repos simultanée...")
    
    # Position repos en pourcentage - IDENTIQUE pour les deux robots
    # Validée par l'utilisateur après tests physiques
    repos_pct = {
        1: 50,  # BASE centrée (imposé)
        2: 10,  # ÉPAULE très basse (replié)
        3: 88,  # COUDE très haut (replié)
        4: 76,  # POIGNET bien fléchi
        5: 50,  # ROTATION centrée (imposé)
        6: 11,  # PINCE presque fermée
    }
    
    # Calculer les positions absolues pour chaque robot
    repos_l = {}
    repos_f = {}
    
    for i in range(1, 7):
        pct = repos_pct[i] / 100.0
        
        # Leader : position selon son calibrage
        if calib_l and f'servo_{i}' in calib_l:
            min_l = calib_l[f'servo_{i}']['min']
            max_l = calib_l[f'servo_{i}']['max']
            repos_l[i] = int(min_l + (max_l - min_l) * pct)
        else:
            repos_l[i] = 2048
        
        # Follower : MÊME pourcentage mais avec SON calibrage
        if calib_f and f'servo_{i}' in calib_f:
            min_f = calib_f[f'servo_{i}']['min']
            max_f = calib_f[f'servo_{i}']['max']
            repos_f[i] = int(min_f + (max_f - min_f) * pct)
        else:
            repos_f[i] = 2048
    
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
    
    # Mouvement simultané fluide vers repos
    duree = 2.0
    steps = int(duree * 50)
    
    for step in range(steps + 1):
        t = step / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        
        for i in range(1, 7):
            # Leader vers sa position repos
            new_pos_l = int(pos_l[i] + (repos_l[i] - pos_l[i]) * smooth)
            lk.write2ByteTxRx(lp, i, 42, new_pos_l)
            
            # Follower vers sa position repos (même % que Leader)
            new_pos_f = int(pos_f[i] + (repos_f[i] - pos_f[i]) * smooth)
            fk.write2ByteTxRx(fp, i, 42, new_pos_f)
        
        time.sleep(duree / steps)
    
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
    global stop_threads
    
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
        print("\n⚠️ Interruption clavier détectée")

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
