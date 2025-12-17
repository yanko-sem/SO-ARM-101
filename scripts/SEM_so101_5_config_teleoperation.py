#!/usr/bin/env python3
"""
Script SEM_so101_config_teleoperation.py
Configuration des modes COPIE/MIROIR pour chaque servo
Avec test fluide de connexion et centrage parallèle
"""
import sys, os, time, json, math

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
    
    # Garder le servo actif pour les prochains mouvements
    print(f"  ✅ {robot_name} connecté et testé")

def identification_guidee_fluide():
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
        print(f"⚠️  Débranchez tous les robots")
        input("   Entrée quand fait...")
        ports = detect_ports()
    
    # LEADER
    print("\n🔌 Branchez le LEADER")
    input("   Entrée quand branché...")
    
    time.sleep(1)
    ports = detect_ports()
    if len(ports) == 0:
        print("❌ Aucun port détecté")
        return None, None, None, None, None, None
    
    leader_port = ports[0]
    print(f"✅ LEADER détecté sur {leader_port}")
    
    # Connexion Leader
    lp = PortHandler(leader_port)
    lk = PacketHandler(1.0)
    if not lp.openPort() or not lp.setBaudRate(1000000):
        print(f"❌ Erreur connexion Leader")
        return None, None, None, None, None, None
    
    # Charger calibration Leader
    calib_l = charger_calibration('leader')
    
    # Test fluide Leader
    test_connexion_fluide(lk, lp, "LEADER", calib_l)
    
    if input("\nPince du LEADER bougée? [O/N]: ").upper() != 'O':
        return None, None, None, None, None, None
    
    # FOLLOWER
    print("\n🔌 Branchez le FOLLOWER (gardez Leader branché)")
    input("   Entrée quand branché...")
    
    time.sleep(1)
    ports = detect_ports()
    if len(ports) < 2:
        print("❌ Follower non détecté")
        return None, None, None, None, None, None
    
    follower_port = ports[1] if ports[0] == leader_port else ports[0]
    print(f"✅ FOLLOWER détecté sur {follower_port}")
    
    # Connexion Follower
    fp = PortHandler(follower_port)
    fk = PacketHandler(1.0)
    if not fp.openPort() or not fp.setBaudRate(1000000):
        print(f"❌ Erreur connexion Follower")
        return None, None, None, None, None, None
    
    # Charger calibration Follower
    calib_f = charger_calibration('follower')
    
    # Test fluide Follower
    test_connexion_fluide(fk, fp, "FOLLOWER", calib_f)
    
    if input("\nPince du FOLLOWER bougée? [O/N]: ").upper() != 'O':
        return None, None, None, None, None, None
    
    print("\n✅ Identification réussie!")
    return lp, lk, fp, fk, calib_l, calib_f

def centrage_parallele(lk, lp, fk, fp, cl, cf):
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
            centre_l = cl[f'servo_{i}']['center'] if cl else 2048
            new_pos_l = int(pos_l[i] + (centre_l - pos_l[i]) * smooth)
            lk.write2ByteTxRx(lp, i, 42, new_pos_l)
            
            # Follower
            centre_f = cf[f'servo_{i}']['center'] if cf else 2048
            new_pos_f = int(pos_f[i] + (centre_f - pos_f[i]) * smooth)
            fk.write2ByteTxRx(fp, i, 42, new_pos_f)
        
        time.sleep(duree / steps)
    
    print("✅ Robots centrés")

def mapper(pos_l, servo_id, cl, cf, miroir=False):
    """Mapping avec option miroir"""
    ml = cl[f'servo_{servo_id}']['min'] if cl else 0
    Ml = cl[f'servo_{servo_id}']['max'] if cl else 4095
    mf = cf[f'servo_{servo_id}']['min'] if cf else 0
    Mf = cf[f'servo_{servo_id}']['max'] if cf else 4095
    
    ratio = (pos_l - ml) / (Ml - ml) if Ml > ml else 0.5
    ratio = max(0, min(1, ratio))
    
    if miroir:
        ratio = 1 - ratio
    
    return int(mf + ratio * (Mf - mf))

def main():
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     CONFIGURATION TÉLÉOPÉRATION SO-ARM 101              ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Identification guidée avec test fluide
    result = identification_guidee_fluide()
    if not result[0]:
        print("❌ Identification échouée")
        return
    
    lp, lk, fp, fk, cl, cf = result
    print("\n📡 Connexions établies avec succès")
    
    # Choix mode
    print("\n[C]ôte à côte ou [F]ace à face ?")
    mode = input("Choix : ").upper()
    mode_key = "cote" if mode == 'C' else "face"
    mode_name = "CÔTÉ À CÔTÉ" if mode == 'C' else "FACE À FACE"
    
    # Charger config existante
    config = {}
    for i in range(1, 7):
        config[i] = "C"  # Par défaut tout en copie
    
    file_config = os.path.expanduser(f"~/lerobot/calibration/teleoperation_config_{mode_key}.json")
    if os.path.exists(file_config):
        with open(file_config, 'r') as f:
            data = json.load(f)
            if 'servos_miroir' in data:
                for servo in data['servos_miroir']:
                    config[servo] = "M"
    
    # Afficher config actuelle AVANT LE CENTRAGE
    servo_names = {1: "BASE", 2: "ÉPAULE", 3: "COUDE", 4: "POIGNET-F", 5: "POIGNET-R", 6: "PINCE"}
    
    print(f"\n📊 Configuration actuelle {mode_name} :")
    print("-" * 35)
    for i in range(1, 7):
        val = "MIROIR" if config[i] == "M" else "COPIE"
        print(f"  Servo {i} ({servo_names[i]:10}) : {val}")
    print("-" * 35)
    
    # CENTRAGE EN PARALLÈLE (PAS DE REPOS POUR LE SCRIPT 5!)
    input("\nEntrée pour centrer les robots...")
    centrage_parallele(lk, lp, fk, fp, cl, cf)
    
    print("\n⚠️  Vous pouvez maintenant tenir le LEADER")
    time.sleep(2)  # Temps pour prendre le robot
    
    # Test chaque servo
    new_config = {}
    
    for servo in range(1, 7):
        
        clear_screen()
        print(f"TEST SERVO {servo}/6 : {servo_names[servo]}")
        print("="*40)
        
        # Libérer SEULEMENT le servo testé
        lk.write1ByteTxRx(lp, servo, 40, 0)  # Leader libre
        fk.write1ByteTxRx(fp, servo, 40, 1)  # Follower actif
        
        # MODE COPIE - ACTIF DIRECT
        print("\n📋 MODE COPIE")
        print("Bougez le Leader maintenant")
        print("Appuyez ENTRÉE pour passer en miroir")
        
        # Téléop copie ACTIVE
        while True:
            pos_l, _, _ = lk.read2ByteTxRx(lp, servo, 56)
            pos_f = mapper(pos_l, servo, cl, cf, miroir=False)
            fk.write2ByteTxRx(fp, servo, 42, pos_f)
            print(f"L:{pos_l:4} → F:{pos_f:4} [COPIE]  ", end="\r")
            
            # Détecter Enter
            import select
            if sys.stdin in select.select([sys.stdin], [], [], 0.02)[0]:
                input()  # Consommer
                break
            time.sleep(0.02)
        
        # TRANSITION DOUCE : Recentrer avant de passer en miroir
        print("\n🔄 Recentrage pour transition...")
        
        # Activer temporairement les deux servos
        lk.write1ByteTxRx(lp, servo, 40, 1)
        fk.write1ByteTxRx(fp, servo, 40, 1)
        
        # Lire positions actuelles
        pos_l_actuel, _, _ = lk.read2ByteTxRx(lp, servo, 56)
        pos_f_actuel, _, _ = fk.read2ByteTxRx(fp, servo, 56)
        centre_l = cl[f'servo_{servo}']['center'] if cl else 2048
        centre_f = cf[f'servo_{servo}']['center'] if cf else 2048
        
        # Mouvement fluide vers centre pour les deux
        steps = 40  # 0.8 seconde
        for i in range(steps + 1):
            t = i / steps
            smooth = (1 - math.cos(t * math.pi)) / 2
            
            # Leader vers centre
            new_l = int(pos_l_actuel + (centre_l - pos_l_actuel) * smooth)
            lk.write2ByteTxRx(lp, servo, 42, new_l)
            
            # Follower vers centre
            new_f = int(pos_f_actuel + (centre_f - pos_f_actuel) * smooth)
            fk.write2ByteTxRx(fp, servo, 42, new_f)
            
            time.sleep(0.02)
        
        # Maintenant libérer le Leader pour le test miroir
        lk.write1ByteTxRx(lp, servo, 40, 0)
        
        # MODE MIROIR - ACTIF DIRECT
        print("\n📋 MODE MIROIR")
        print("Bougez le Leader maintenant")
        print("Appuyez ENTRÉE pour choisir")
        
        # Téléop miroir ACTIVE
        while True:
            pos_l, _, _ = lk.read2ByteTxRx(lp, servo, 56)
            pos_f = mapper(pos_l, servo, cl, cf, miroir=True)
            fk.write2ByteTxRx(fp, servo, 42, pos_f)
            print(f"L:{pos_l:4} → F:{pos_f:4} [MIROIR] ", end="\r")
            
            if sys.stdin in select.select([sys.stdin], [], [], 0.02)[0]:
                input()
                break
            time.sleep(0.02)
        
        # CHOIX
        print(f"\n\nServo {servo}: [C]opie ou [M]iroir ?")
        choix = input("Choix : ").upper()
        
        new_config[servo] = 'M' if choix == 'M' else 'C'
        
        # Recentrer et bloquer ce servo AVEC MOUVEMENT FLUIDE (LEADER ET FOLLOWER!)
        lk.write1ByteTxRx(lp, servo, 40, 1)  # Leader actif
        fk.write1ByteTxRx(fp, servo, 40, 1)  # Follower actif aussi !
        
        # Centres et positions actuelles
        centre_l = cl[f'servo_{servo}']['center'] if cl else 2048
        centre_f = cf[f'servo_{servo}']['center'] if cf else 2048
        pos_l, _, _ = lk.read2ByteTxRx(lp, servo, 56)
        pos_f, _, _ = fk.read2ByteTxRx(fp, servo, 56)
        
        # MOUVEMENT FLUIDE DE RETOUR AU CENTRE POUR LES DEUX
        steps = 75  # 1.5 sec
        for i in range(steps + 1):
            t = i / steps
            smooth = (1 - math.cos(t * math.pi)) / 2
            
            # Leader
            new_pos_l = int(pos_l + (centre_l - pos_l) * smooth)
            lk.write2ByteTxRx(lp, servo, 42, new_pos_l)
            
            # Follower
            new_pos_f = int(pos_f + (centre_f - pos_f) * smooth)
            fk.write2ByteTxRx(fp, servo, 42, new_pos_f)
            
            time.sleep(0.02)
    
    # VALIDATION
    clear_screen()
    print(f"VALIDATION {mode_name}")
    print("="*40)
    
    for i in range(1, 7):
        old = "MIROIR" if config[i] == 'M' else "COPIE"
        new = "MIROIR" if new_config[i] == 'M' else "COPIE"
        print(f"Servo {i} ({servo_names[i]:10}): {old:6} → {new:6}")
    
    print("\n[V] Sauver, [Q] Annuler")
    if input("Choix : ").upper() == 'V':
        servos_miroir = [s for s, m in new_config.items() if m == 'M']
        save_data = {
            "mode": mode_name,
            "servos_miroir": servos_miroir
        }
        
        os.makedirs(os.path.expanduser("~/lerobot/calibration"), exist_ok=True)
        with open(file_config, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        print(f"✅ Configuration sauvegardée !")
        print(f"📁 Fichier : {file_config}")
        print(f"📋 Servos en miroir : {servos_miroir}")
        print(f"🔗 Cette configuration sera utilisée par le script 6 de téléopération")
    
    # Position repos finale avant libération
    print("\n🏁 Position repos avant libération...")
    
    # Position repos en pourcentage - IDENTIQUE au script 6
    repos_pct = {
        1: 50,  # BASE centrée
        2: 10,  # ÉPAULE très basse (replié)
        3: 88,  # COUDE très haut (replié)
        4: 76,  # POIGNET bien fléchi
        5: 50,  # ROTATION centrée
        6: 11,  # PINCE presque fermée
    }
    
    # Calculer les positions absolues pour chaque robot
    repos_l = {}
    repos_f = {}
    
    for i in range(1, 7):
        pct = repos_pct[i] / 100.0
        
        # Leader : position selon son calibrage
        if cl and f'servo_{i}' in cl:
            min_l = cl[f'servo_{i}']['min']
            max_l = cl[f'servo_{i}']['max']
            repos_l[i] = int(min_l + (max_l - min_l) * pct)
        else:
            repos_l[i] = 2048
        
        # Follower : MÊME pourcentage avec SON calibrage  
        if cf and f'servo_{i}' in cf:
            min_f = cf[f'servo_{i}']['min']
            max_f = cf[f'servo_{i}']['max']
            repos_f[i] = int(min_f + (max_f - min_f) * pct)
        else:
            repos_f[i] = 2048
    
    # Activer tous les servos pour le mouvement
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 1)
        fk.write1ByteTxRx(fp, i, 40, 1)
    
    # Lire positions actuelles
    pos_l = {}
    pos_f = {}
    for i in range(1, 7):
        pos_l[i], _, _ = lk.read2ByteTxRx(lp, i, 56)
        pos_f[i], _, _ = fk.read2ByteTxRx(fp, i, 56)
    
    # Mouvement fluide vers repos
    steps = 100
    for step in range(steps + 1):
        t = step / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        
        for i in range(1, 7):
            # Leader
            new_l = int(pos_l[i] + (repos_l[i] - pos_l[i]) * smooth)
            lk.write2ByteTxRx(lp, i, 42, new_l)
            
            # Follower
            new_f = int(pos_f[i] + (repos_f[i] - pos_f[i]) * smooth)
            fk.write2ByteTxRx(fp, i, 42, new_f)
        
        time.sleep(0.02)
    
    print("\n⚠️  Assurez-vous de tenir les robots")
    time.sleep(2)
    
    # Libération
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 0)
        fk.write1ByteTxRx(fp, i, 40, 0)
    
    lp.closePort()
    fp.closePort()
    
    print("\n✅ Configuration terminée!")

if __name__ == "__main__":
    main()
