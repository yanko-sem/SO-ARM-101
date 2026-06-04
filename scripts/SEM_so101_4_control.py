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
    """Détecte les ports des robots.

    Teste chaque port candidat en interrogeant le servo 1 : ne garde que les
    ports qui répondent au protocole servo (= robots). Les autres périphériques
    série (téléphone en charge, etc.) sont ignorés. Le robot doit être alimenté
    pour être détecté.
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
                # Interroger le servo 1 : seul un vrai robot répond
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

def mouvement_parallele(packetHandler, portHandler, calibration, cibles_pct, servos, duree=2.0):
    """Déplace plusieurs servos SIMULTANÉMENT vers leurs cibles (en %) via courbe sinusoïdale.

    cibles_pct : dict {servo_id: pourcentage}
    servos     : liste des servos à bouger en parallèle
    """
    # Lire positions de départ
    pos_debut = {}
    for s in servos:
        pos, _, _ = packetHandler.read2ByteTxRx(portHandler, s, 56)
        pos_debut[s] = pos

    # Calculer les cibles en ticks
    cibles_ticks = {}
    for s in servos:
        if calibration and f'servo_{s}' in calibration:
            min_val = calibration[f'servo_{s}']['min']
            max_val = calibration[f'servo_{s}']['max']
            cibles_ticks[s] = int(min_val + (max_val - min_val) * cibles_pct[s] / 100)
        else:
            cibles_ticks[s] = 2048

    # Interpolation parallèle : tous les servos avancent en même temps
    steps = 100
    for step in range(steps + 1):
        t = step / steps
        smooth_t = (1 - math.cos(t * math.pi)) / 2
        for s in servos:
            pos = int(pos_debut[s] + (cibles_ticks[s] - pos_debut[s]) * smooth_t)
            packetHandler.write2ByteTxRx(portHandler, s, 42, pos)
        time.sleep(duree / steps)

    return cibles_ticks

def _cible_ticks(calibration, servo_id, pct):
    """Convertit un pourcentage en ticks pour un servo donné (avec fallback 2048)."""
    if calibration and f'servo_{servo_id}' in calibration:
        min_val = calibration[f'servo_{servo_id}']['min']
        max_val = calibration[f'servo_{servo_id}']['max']
        return int(min_val + (max_val - min_val) * pct / 100)
    return 2048

def _est_en_repos(packetHandler, portHandler, calibration, tolerance_pct=5):
    """Vérifie si le robot est actuellement en position repos.
    Compare le % actuel de chaque servo à la valeur repos (du fichier externe),
    avec une tolérance. Retourne True si TOUS les servos sont proches du repos."""
    repos_pct = charger_repos_pct()
    for i in range(1, 7):
        pos, _, _ = packetHandler.read2ByteTxRx(portHandler, i, 56)
        if calibration and f'servo_{i}' in calibration:
            min_val = calibration[f'servo_{i}']['min']
            max_val = calibration[f'servo_{i}']['max']
            if max_val > min_val:
                pct_actuel = (pos - min_val) / (max_val - min_val) * 100
            else:
                pct_actuel = 50
        else:
            pct_actuel = 50
        if abs(pct_actuel - repos_pct.get(i, 50)) > tolerance_pct:
            return False
    return True

def aller_a_position(packetHandler, portHandler, calibration, cibles_pct, duree=2.0):
    """Déplace le bras vers une position cible (dict de % par servo) en respectant
    les contraintes physiques de l'installation, via une séquence sûre en 3 phases :

      Phase 1 : servo 4 -> 20%  (pince orientée vers le haut)
                => dégage la pince du sol ET prépare le dégagement caméra
      Phase 2 : servos 1, 2, 3, 5, 6 -> cibles, EN PARALLÈLE
                => sûr car la pince pointe en l'air (pas de collision sol)
                   et le servo 4 a déjà bougé (pas de collision caméra)
      Phase 3 : servo 4 -> sa valeur cible finale
                => orientation finale de la pince, bras déjà positionné

    Retourne le dict des positions finales lues.
    """
    # Activer tous les servos
    for i in range(1, 7):
        packetHandler.write1ByteTxRx(portHandler, i, 40, 1)

    # --- Phase 0 (conditionnelle) : dégagement si la pince est près du sol ---
    # Cas : servo 4 actuel > 2700 (pince pointe vers le bas) ET robot pas en repos.
    # Alors la pince est probablement près du sol. Tourner le servo 4 en premier
    # la ferait racler. On lève d'abord le bras en DIMINUANT le servo 2
    # (ce qui SOULÈVE la pince sur cette installation), via min() pour ne jamais
    # augmenter le servo 2 par erreur.
    pos4_initial, _, _ = packetHandler.read2ByteTxRx(portHandler, 4, 56)
    if pos4_initial > 2700 and not _est_en_repos(packetHandler, portHandler, calibration):
        pos2_actuel, _, _ = packetHandler.read2ByteTxRx(portHandler, 2, 56)
        cible_2_degagement = min(pos2_actuel, 1027)  # 1027 ticks, ajustable
        mouvement_fluide(packetHandler, portHandler, 2, pos2_actuel, cible_2_degagement, duree)

    # --- Phase 1 : servo 4 vers 20% (pince en l'air) ---
    pos4, _, _ = packetHandler.read2ByteTxRx(portHandler, 4, 56)
    cible_4_securite = _cible_ticks(calibration, 4, 20)
    mouvement_fluide(packetHandler, portHandler, 4, pos4, cible_4_securite, duree)

    # --- Phase 2 : servos 1, 2, 3, 5, 6 en parallèle ---
    mouvement_parallele(packetHandler, portHandler, calibration,
                        cibles_pct, [1, 2, 3, 5, 6], duree)

    # --- Phase 3 : servo 4 vers sa cible finale ---
    pos4_now, _, _ = packetHandler.read2ByteTxRx(portHandler, 4, 56)
    cible_4_finale = _cible_ticks(calibration, 4, cibles_pct[4])
    mouvement_fluide(packetHandler, portHandler, 4, pos4_now, cible_4_finale, duree)

    # Lire et retourner les positions finales
    positions = {}
    for i in range(1, 7):
        pos, _, _ = packetHandler.read2ByteTxRx(portHandler, i, 56)
        positions[i] = pos
    return positions

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
    Retourne un dict {1: %, 2: %, ...}.
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

def get_servo_center(servo_id, calibration):
    """Obtient la position centrale d'un servo"""
    if calibration and f"servo_{servo_id}" in calibration:
        return calibration[f"servo_{servo_id}"]["center"]
    else:
        # Valeurs par défaut si pas de calibration
        defaults = {1: 2079, 2: 1991, 3: 2073, 4: 2027, 5: 2075, 6: 2483}
        return defaults.get(servo_id, 2048)

def position_initiale(packetHandler, portHandler, calibration):
    """Position initiale sécurisée (séquence sûre en 3 phases via aller_a_position)"""
    print("🔄 Mise en position initiale...")

    # Position initiale basée sur VOS MESURES
    positions_pct = {
        1: 66,  # BASE 65.6%
        2: 27,  # ÉPAULE 26.6%
        3: 62,  # COUDE 61.8%
        4: 22,  # POIGNET-F 21.9%
        5: 77,  # ROTATION 76.5%
        6: 60   # PINCE 60.1%
    }

    positions = aller_a_position(packetHandler, portHandler, calibration, positions_pct)
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
    """Position repos (séquence sûre en 3 phases via aller_a_position)"""
    print("😴 Position repos...")

    # Position repos en pourcentages, lue depuis le fichier externe partagé
    # (fallback sur valeurs par défaut si le fichier est absent)
    repos_pct = charger_repos_pct()

    positions = aller_a_position(packetHandler, portHandler, calibration, repos_pct)
    return positions

def position_attraper(packetHandler, portHandler, calibration):
    """Position pour attraper/manipuler (séquence sûre en 3 phases via aller_a_position)"""
    print("🤏 Position manipulation...")

    # Position manipulation en pourcentages
    manip_pct = {
        1: 50,     # BASE centrée
        2: 45,     # ÉPAULE position moyenne
        3: 65,     # COUDE un peu haut
        4: 82.92,  # POIGNET vers le bas (= 2792 ticks, pince près du sol)
        5: 50,     # ROTATION centrée
        6: 75      # PINCE ouverte
    }

    positions = aller_a_position(packetHandler, portHandler, calibration, manip_pct)
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

    urgence = False  # Devient True si arrêt d'urgence (touche X) : pas de retour repos

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

            elif key.lower() == 'x':  # ARRÊT D'URGENCE
                print("\n⚠️  ARRÊT D'URGENCE!")
                for i in range(1, 7):
                    packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
                print("🛑 Tous les servos libérés immédiatement.")
                print("⚠️  Tenez le robot, il est libre !")
                urgence = True
                break

            elif key.lower() == 'q':  # Quitter
                print("\n👋 Arrêt en cours...")
                break

    except KeyboardInterrupt:
        print("\n⚠️  Interruption clavier")

    if urgence:
        # Arrêt d'urgence : servos déjà libérés, AUCUN retour repos
        portHandler.closePort()
        print("\n✅ Arrêt d'urgence terminé (aucun retour repos).")
    else:
        # Quitter normalement : retour repos puis libération
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
