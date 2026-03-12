#!/usr/bin/env python3
"""
Script SEM_so101_4_control.py
Contrôle manuel Leader ou Follower avec mouvements fluides
Version complète avec flèches, tableau, positions
"""
import sys, os, time, json, math
import termios, tty

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
            ports.append(port)
    return ports

def getch():
    """Capture d'une touche clavier avec gestion des flèches"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b':  # Sequence ESC pour flèches
            ch = sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def mouvement_fluide(packetHandler, portHandler, servo_id, pos_debut, pos_fin, duree=2.0):
    """Mouvement fluide avec courbe sinusoïdale"""
    steps = 100  # Plus de steps pour plus de fluidité
    for step in range(steps + 1):
        t = step / steps
        # Courbe sinusoïdale pour fluidité
        smooth_t = (1 - math.cos(t * math.pi)) / 2
        pos = int(pos_debut + (pos_fin - pos_debut) * smooth_t)
        packetHandler.write2ByteTxRx(portHandler, servo_id, 42, pos)
        time.sleep(duree / steps)
    return pos_fin

def charger_calibration(robot_type):
    """Charge la calibration d'un robot"""
    calib_file = os.path.expanduser(f"~/lerobot/calibration/{robot_type}_calibration.json")
    if os.path.exists(calib_file):
        with open(calib_file, 'r') as f:
            return json.load(f)
    return None

def get_servo_center(servo_id, calibration):
    """Obtient la position centrale d'un servo"""
    if calibration and f"servo_{servo_id}" in calibration:
        return calibration[f"servo_{servo_id}"]["center"]
    else:
        # Valeurs par défaut si pas de calibration
        defaults = {1: 2079, 2: 1991, 3: 2073, 4: 2027, 5: 2075, 6: 2483}
        return defaults.get(servo_id, 2048)

def position_initiale(packetHandler, portHandler, calibration):
    """Position initiale sécurisée avec pourcentages de vos mesures"""
    print("🔄 Mise en position initiale...")
    positions = {}

    # Position initiale basée sur VOS MESURES
    positions_pct = {
        1: 66,  # BASE 65.6%
        2: 27,  # ÉPAULE 26.6%
        3: 62,  # COUDE 61.8%
        4: 22,  # POIGNET-F 21.9%
        5: 77,  # ROTATION 76.5%
        6: 60   # PINCE 60.1%
    }

    # D'abord activer tous les servos
    for i in range(1, 7):
        packetHandler.write1ByteTxRx(portHandler, i, 40, 1)
        pos, _, _ = packetHandler.read2ByteTxRx(portHandler, i, 56)
        positions[i] = pos

    # SÉQUENCE SÉCURISÉE : Servos 3 et 2 d'abord (éviter collision)
    for servo_id in [3, 2, 1, 4, 5, 6]:
        if calibration and f'servo_{servo_id}' in calibration:
            min_val = calibration[f'servo_{servo_id}']['min']
            max_val = calibration[f'servo_{servo_id}']['max']
            target = int(min_val + (max_val - min_val) * positions_pct[servo_id] / 100)
        else:
            target = 2048

        positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                              positions[servo_id], target, 2.5)

    print("✅ Position initiale atteinte")
    return positions

def centrer_tous(packetHandler, portHandler, calibration, positions):
    """Centre tous les servos avec séquence sécurisée"""
    print("🎯 Centrage de tous les servos...")

    # Lire positions actuelles
    for i in range(1, 7):
        pos, _, _ = packetHandler.read2ByteTxRx(portHandler, i, 56)
        positions[i] = pos

    # Déterminer la séquence selon la position du servo 2
    pos_servo2 = positions[2]
    centre_servo2 = get_servo_center(2, calibration)

    if pos_servo2 >= centre_servo2:
        # Séquence si bras haut
        print("  → Séquence bras haut")
        positions[2] = mouvement_fluide(packetHandler, portHandler, 2,
                                       positions[2], centre_servo2, 2.5)
        for servo_id in [3, 4, 5, 6, 1]:
            centre = get_servo_center(servo_id, calibration)
            positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                                  positions[servo_id], centre, 2.5)
    else:
        # Séquence si bras bas
        print("  → Séquence bras bas")
        for servo_id in [3, 4]:
            centre = get_servo_center(servo_id, calibration)
            positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                                  positions[servo_id], centre, 2.5)
        positions[2] = mouvement_fluide(packetHandler, portHandler, 2,
                                       positions[2], centre_servo2, 2.5)
        for servo_id in [5, 6, 1]:
            centre = get_servo_center(servo_id, calibration)
            positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                                  positions[servo_id], centre, 2.5)

    print("✅ Tous les servos centrés")
    return positions

def position_repos(packetHandler, portHandler, calibration):
    """Position repos avec pourcentages identiques aux scripts 5 et 6"""
    print("😴 Position repos...")

    # Position repos en pourcentages
    repos_pct = {
        1: 50,  # BASE centrée
        2: 10,  # ÉPAULE très basse (replié)
        3: 88,  # COUDE très haut (replié)
        4: 76,  # POIGNET bien fléchi
        5: 50,  # ROTATION centrée
        6: 11   # PINCE presque fermée
    }

    positions = {}

    # Lire positions actuelles
    for i in range(1, 7):
        pos, _, _ = packetHandler.read2ByteTxRx(portHandler, i, 56)
        positions[i] = pos

    # Séquence sécurisée : 3, 2, 1, 4, 5, 6
    for servo_id in [3, 2, 1, 4, 5, 6]:
        if calibration and f'servo_{servo_id}' in calibration:
            min_val = calibration[f'servo_{servo_id}']['min']
            max_val = calibration[f'servo_{servo_id}']['max']
            target = int(min_val + (max_val - min_val) * repos_pct[servo_id] / 100)
        else:
            target = 2048

        positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                              positions[servo_id], target, 2.0)

    return positions

def position_attraper(packetHandler, portHandler, calibration):
    """Position pour attraper/manipuler"""
    print("🤏 Position manipulation...")

    # Position manipulation en pourcentages
    manip_pct = {
        1: 50,  # BASE centrée
        2: 45,  # ÉPAULE position moyenne
        3: 65,  # COUDE un peu haut
        4: 40,  # POIGNET position basse
        5: 50,  # ROTATION centrée
        6: 75   # PINCE ouverte
    }

    positions = {}

    # Lire positions actuelles
    for i in range(1, 7):
        pos, _, _ = packetHandler.read2ByteTxRx(portHandler, i, 56)
        positions[i] = pos

    # Appliquer positions
    for servo_id in range(1, 7):
        if calibration and f'servo_{servo_id}' in calibration:
            min_val = calibration[f'servo_{servo_id}']['min']
            max_val = calibration[f'servo_{servo_id}']['max']
            target = int(min_val + (max_val - min_val) * manip_pct[servo_id] / 100)
        else:
            target = 2048

        positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                              positions[servo_id], target, 2.0)

    return positions

def afficher_positions(packetHandler, portHandler, calibration):
    """Affiche un tableau détaillé des positions"""
    print("\n" + "="*60)
    print("TABLEAU DES POSITIONS")
    print("="*60)

    servo_names = {1: "BASE", 2: "ÉPAULE", 3: "COUDE",
                  4: "POIGNET-F", 5: "POIGNET-R", 6: "PINCE"}

    for i in range(1, 7):
        pos, _, _ = packetHandler.read2ByteTxRx(portHandler, i, 56)
        torque, _, _ = packetHandler.read1ByteTxRx(portHandler, i, 40)

        status = "ON" if torque == 1 else "OFF"

        if calibration and f'servo_{i}' in calibration:
            min_val = calibration[f'servo_{i}']['min']
            max_val = calibration[f'servo_{i}']['max']
            center = calibration[f'servo_{i}']['center']

            # Calculer pourcentage
            pct = ((pos - min_val) / (max_val - min_val)) * 100 if max_val > min_val else 50

            print(f"Servo {i} ({servo_names[i]:10}): Pos={pos:4} "
                  f"[Min:{min_val:4} Ctr:{center:4} Max:{max_val:4}] "
                  f"{pct:5.1f}% [{status}]")
        else:
            print(f"Servo {i} ({servo_names[i]:10}): Pos={pos:4} [{status}]")

    print("="*60)

def clear_lines(n=1):
    """Efface n lignes au-dessus du curseur"""
    for _ in range(n):
        print('\033[1A\033[K', end='')

def main():
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     CONTRÔLE MANUEL SO-ARM 101                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Choix du robot
    print("\nContrôler [L]eader ou [F]ollower?")
    choix = input("Choix: ").upper()

    robot_type = "leader" if choix == 'L' else "follower"

    # Détection ports
    ports = detect_ports()
    if not ports:
        print("❌ Aucun port détecté!")
        return

    # Sélection du port
    if robot_type == "leader":
        port = ports[0]
    else:
        port = ports[1] if len(ports) > 1 else ports[0]

    print(f"\n🔡 Connexion au {robot_type} sur {port}...")

    # Connexion
    portHandler = PortHandler(port)
    packetHandler = PacketHandler(1.0)

    if not portHandler.openPort() or not portHandler.setBaudRate(1000000):
        print(f"❌ Erreur connexion {port}")
        return

    print("✅ Connecté!")

    # Charger calibration
    calibration = charger_calibration(robot_type)
    if calibration:
        print("✅ Calibration chargée")
    else:
        print("⚠️  Pas de calibration")
        calibration = None

    # Position initiale
    positions = position_initiale(packetHandler, portHandler, calibration)

    servo_actif = 1
    pas_normal = 50
    pas_precis = 10
    mode_precis = False

    print("""
╔════════════════════════════════════════════════════════╗
║                    CONTRÔLES                           ║
╠════════════════════════════════════════════════════════╣
║  ↑/↓       : Augmenter/Diminuer position              ║
║  ←/→       : Changer de servo (1-6)                   ║
║  ESPACE    : Centrer le servo actif                   ║
║  I         : Position INITIALE                        ║
║  C         : Centrer TOUS les servos                  ║
║  P         : Mode précis ON/OFF (pas 10 vs 50)        ║
║  S         : Afficher tableau positions               ║
║  A         : Position ATTRAPER                        ║
║  R         : Position REPOS                           ║
║  Q         : Quitter                                  ║
║  X         : ARRÊT D'URGENCE                          ║
╚════════════════════════════════════════════════════════╝

""")

    servo_names = {1: "BASE", 2: "ÉPAULE", 3: "COUDE",
                  4: "POIGNET-F", 5: "POIGNET-R", 6: "PINCE"}

    # Affichage initial des 3 lignes d'état
    print(f"Servo actif: {servo_actif} ({servo_names[servo_actif]})")
    print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
    print(f"Position: {positions[servo_actif]}")

    try:
        while True:
            key = getch()

            # Flèches - on efface seulement les 3 dernières lignes
            if key == '[A':  # Flèche HAUT
                pas = pas_precis if mode_precis else pas_normal
                if calibration and f'servo_{servo_actif}' in calibration:
                    max_val = calibration[f'servo_{servo_actif}']['max']
                    nouvelle_pos = min(positions[servo_actif] + pas, max_val)
                else:
                    nouvelle_pos = min(positions[servo_actif] + pas, 4095)

                packetHandler.write2ByteTxRx(portHandler, servo_actif, 42, nouvelle_pos)
                positions[servo_actif] = nouvelle_pos
                clear_lines(3)
                print(f"Servo actif: {servo_actif} ({servo_names[servo_actif]})")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]} ↑")

            elif key == '[B':  # Flèche BAS
                pas = pas_precis if mode_precis else pas_normal
                if calibration and f'servo_{servo_actif}' in calibration:
                    min_val = calibration[f'servo_{servo_actif}']['min']
                    nouvelle_pos = max(positions[servo_actif] - pas, min_val)
                else:
                    nouvelle_pos = max(positions[servo_actif] - pas, 0)

                packetHandler.write2ByteTxRx(portHandler, servo_actif, 42, nouvelle_pos)
                positions[servo_actif] = nouvelle_pos
                clear_lines(3)
                print(f"Servo actif: {servo_actif} ({servo_names[servo_actif]})")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]} ↓")

            elif key == '[D':  # Flèche GAUCHE
                servo_actif = max(1, servo_actif - 1)
                clear_lines(3)
                print(f"Servo actif: {servo_actif} ({servo_names[servo_actif]}) ←")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]}")

            elif key == '[C':  # Flèche DROITE
                servo_actif = min(6, servo_actif + 1)
                clear_lines(3)
                print(f"Servo actif: {servo_actif} ({servo_names[servo_actif]}) →")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]}")

            # Commandes
            elif key == ' ':  # ESPACE - Centrer servo actif
                centre = get_servo_center(servo_actif, calibration)
                positions[servo_actif] = mouvement_fluide(packetHandler, portHandler,
                                                         servo_actif, positions[servo_actif],
                                                         centre, 1.5)
                clear_lines(3)
                print(f"Servo actif: {servo_actif} ({servo_names[servo_actif]}) [CENTRÉ]")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]}")

            elif key.lower() == 'i':  # Position initiale
                positions = position_initiale(packetHandler, portHandler, calibration)
                clear_lines(3)
                print("Position INITIALE activée!")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position servo {servo_actif}: {positions[servo_actif]}")

            elif key.lower() == 'c':  # Centrer TOUS
                positions = centrer_tous(packetHandler, portHandler, calibration, positions)
                clear_lines(3)
                print("Tous les servos centrés!")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position servo {servo_actif}: {positions[servo_actif]}")

            elif key.lower() == 'p':  # Mode précis
                mode_precis = not mode_precis
                clear_lines(3)
                print(f"Servo actif: {servo_actif} ({servo_names[servo_actif]})")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'} [CHANGÉ]")
                print(f"Position: {positions[servo_actif]}")

            elif key.lower() == 's':  # Afficher positions
                afficher_positions(packetHandler, portHandler, calibration)
                print("\n[Appuyez sur une touche pour continuer]")
                getch()
                # Réafficher le menu complet après le tableau
                clear_screen()
                print("""
╔════════════════════════════════════════════════════════╗
║                    CONTRÔLES                           ║
╠════════════════════════════════════════════════════════╣
║  ↑/↓       : Augmenter/Diminuer position              ║
║  ←/→       : Changer de servo (1-6)                   ║
║  ESPACE    : Centrer le servo actif                   ║
║  I         : Position INITIALE                        ║
║  C         : Centrer TOUS les servos                  ║
║  P         : Mode précis ON/OFF (pas 10 vs 50)        ║
║  S         : Afficher tableau positions               ║
║  A         : Position ATTRAPER                        ║
║  R         : Position REPOS                           ║
║  Q         : Quitter                                  ║
║  X         : ARRÊT D'URGENCE                          ║
╚════════════════════════════════════════════════════════╝

""")
                print(f"Servo actif: {servo_actif} ({servo_names[servo_actif]})")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]}")

            elif key.lower() == 'a':  # Position attraper
                positions = position_attraper(packetHandler, portHandler, calibration)
                clear_lines(3)
                print("Position ATTRAPER activée!")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position servo {servo_actif}: {positions[servo_actif]}")

            elif key.lower() == 'r':  # Position repos
                positions = position_repos(packetHandler, portHandler, calibration)
                clear_lines(3)
                print("Position REPOS activée!")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position servo {servo_actif}: {positions[servo_actif]}")

            elif key.lower() == 'x':  # Arrêt urgence
                print("\n⚠️  ARRÊT D'URGENCE!")
                for i in range(1, 7):
                    packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
                print("Tous les servos libérés!")
                time.sleep(2)
                break

            elif key.lower() == 'q':  # Quitter
                print("\n👋 Arrêt en cours...")
                break

    except KeyboardInterrupt:
        print("\n⚠️  Interruption clavier")

    # Séquence de fin
    print("\n🏁 Position repos avant libération...")
    position_repos(packetHandler, portHandler, calibration)

    print("⚠️  Tenez le robot avant libération")
    time.sleep(2)

    # Libération
    for i in range(1, 7):
        packetHandler.write1ByteTxRx(portHandler, i, 40, 0)

    portHandler.closePort()
    print("\n✅ Terminé!")

if __name__ == "__main__":
    main()
