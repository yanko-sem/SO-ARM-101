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

# Noms des servos (source unique, partagee par l'affichage et le tableau)
SERVO_NAMES = {1: "BASE", 2: "ÉPAULE", 3: "COUDE",
               4: "POIGNET-F", 5: "POIGNET-R", 6: "PINCE"}

# Amplitude minimale exigee d'une calibration pour etre exploitable (meme seuil que scripts 2/3)
MIN_AMPLITUDE = 500

# ----------------------------------------------------------------------------
# Politique de gestion des erreurs (lecture de position) :
# Certains servos Feetech peuvent renvoyer un octet de statut interne non nul
# tout en conservant une position parfaitement lisible. Seul l'echec de
# communication (result != COMM_SUCCESS) invalide la lecture ; l'octet de
# statut interne est ignore (tolere silencieusement, contexte controle
# manuel). Cause a identifier sur la table de controle Feetech STS3215 (hors
# urgence). Regle limitee aux LECTURES ; ecritures/mouvements au cas par cas.
# ----------------------------------------------------------------------------
def lire_position(packetHandler, portHandler, servo_id):
    """Lecture de la position (registre 56). Retourne (position, ok).

    Seule une vraie panne de communication (result) invalide la lecture.
    L'octet de statut interne du servo est ignore (tolere silencieusement,
    contexte controle manuel) : la position reste valide ; la cause de ce
    statut n'est PAS presumee ici, elle reste a identifier.
    """
    pos, result, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
    if result != COMM_SUCCESS:
        return None, False
    return pos, True

def lire_positions_toutes(packetHandler, portHandler):
    """Relit les 6 positions reelles (verifiees). Retourne le dict {1:pos,...}
    ou None si une lecture echoue (etat du bras incertain). Sert a resynchroniser
    l'etat logiciel sur le bras reel apres l'echec d'une sequence (mouvement partiel
    possible) : sans ca, une fleche calculerait un mouvement depuis une position perimee."""
    positions = {}
    for i in range(1, 7):
        pos, ok = lire_position(packetHandler, portHandler, i)
        if not ok:
            print(f"❌ Lecture impossible du servo {i} — état du bras incertain")
            return None
        positions[i] = pos
    return positions

def detect_port():
    """Détecte LE port du robot (fail-closed).

    Teste chaque port candidat en interrogeant le servo 1 : ne garde que les
    ports qui répondent (= robots). S'il y en a exactement un, on le retourne.
    S'il y en a plusieurs (Leader ET Follower branchés), on REFUSE : l'ordre
    d'énumération ne dit rien sur le rôle, donc on ne peut pas deviner le bon
    bras. Les autres périphériques série sont ignorés. Le robot doit être alimenté.
    """
    BAUDRATE = 1000000
    ports_robot = []
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']:
        if not os.path.exists(port):
            continue
        ph = PortHandler(port)
        pk = PacketHandler(1.0)
        try:
            if ph.openPort() and ph.setBaudRate(BAUDRATE):
                # Interroger le servo 1 : seul un vrai robot répond
                _, result, _ = pk.read2ByteTxRx(ph, 1, 56)
                if result == COMM_SUCCESS:
                    ports_robot.append(port)
        finally:
            try:
                ph.closePort()
            except Exception:
                pass

    if len(ports_robot) == 1:
        return ports_robot[0]
    if len(ports_robot) > 1:
        print("❌ Plusieurs robots/adaptateurs détectés :")
        for port in ports_robot:
            print(f"  - {port}")
        print("   Débranchez tous les adaptateurs sauf celui du bras à contrôler.")
    return None

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
    # Lire positions de départ (verifiees : un echec annule la sequence)
    pos_debut = {}
    for s in servos:
        pos, ok = lire_position(packetHandler, portHandler, s)
        if not ok:
            print(f"❌ Lecture impossible du servo {s} — mouvement annulé")
            return None
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
    repos_pct, _ = charger_repos_pct()
    for i in range(1, 7):
        pos, ok = lire_position(packetHandler, portHandler, i)
        if not ok:
            # Lecture impossible : etat repos INDETERMINE -> l'appelant doit annuler
            print(f"❌ Lecture impossible du servo {i} — état repos indéterminé")
            return None
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
    pos4_initial, ok = lire_position(packetHandler, portHandler, 4)
    if not ok:
        print("❌ Lecture impossible du servo 4 — mouvement annulé")
        return None
    if pos4_initial > 2700:
        etat_repos = _est_en_repos(packetHandler, portHandler, calibration)
        if etat_repos is None:
            print("❌ Impossible de vérifier l'état de repos — mouvement annulé")
            return None
        if not etat_repos:
            pos2_actuel, ok = lire_position(packetHandler, portHandler, 2)
            if not ok:
                print("❌ Lecture impossible du servo 2 — mouvement annulé")
                return None
            cible_2_degagement = min(pos2_actuel, 1027)  # 1027 ticks, ajustable
            mouvement_fluide(packetHandler, portHandler, 2, pos2_actuel, cible_2_degagement, duree)

    # --- Phase 1 : servo 4 vers 20% (pince en l'air) ---
    pos4, ok = lire_position(packetHandler, portHandler, 4)
    if not ok:
        print("❌ Lecture impossible du servo 4 — mouvement annulé")
        return None
    cible_4_securite = _cible_ticks(calibration, 4, 20)
    mouvement_fluide(packetHandler, portHandler, 4, pos4, cible_4_securite, duree)

    # --- Phase 2 : servos 1, 2, 3, 5, 6 en parallèle ---
    if mouvement_parallele(packetHandler, portHandler, calibration,
                           cibles_pct, [1, 2, 3, 5, 6], duree) is None:
        return None

    # --- Phase 3 : servo 4 vers sa cible finale ---
    pos4_now, ok = lire_position(packetHandler, portHandler, 4)
    if not ok:
        print("❌ Lecture impossible du servo 4 — mouvement annulé")
        return None
    cible_4_finale = _cible_ticks(calibration, 4, cibles_pct[4])
    mouvement_fluide(packetHandler, portHandler, 4, pos4_now, cible_4_finale, duree)

    # Lire et retourner les positions finales (verifiees)
    positions = {}
    for i in range(1, 7):
        pos, ok = lire_position(packetHandler, portHandler, i)
        if not ok:
            print(f"❌ Lecture impossible du servo {i} — position finale incertaine")
            return None
        positions[i] = pos
    return positions

def charger_calibration(robot_type):
    """Charge la calibration d'un robot"""
    calib_file = os.path.expanduser(f"~/lerobot/calibration/{robot_type}_calibration.json")
    if os.path.exists(calib_file):
        with open(calib_file, 'r') as f:
            return json.load(f)
    return None

def calibration_complete(calibration):
    """Vrai uniquement si les 6 servos sont calibres avec une plage exploitable
    (presents, valeurs numeriques, amplitude >= MIN_AMPLITUDE). Meme exigence que
    les scripts 2/3. Sert de verrou : le controle est refuse sans calibration valide,
    sinon les fleches clampent a 0-4095 et peuvent forcer contre les butees."""
    if not calibration:
        return False
    for i in range(1, 7):
        key = f"servo_{i}"
        if key not in calibration:
            return False
        cal = calibration[key]
        min_v = cal.get("min")
        max_v = cal.get("max")
        if not isinstance(min_v, (int, float)) or not isinstance(max_v, (int, float)):
            return False
        if max_v - min_v < MIN_AMPLITUDE:
            return False
        # center est utilise directement par get_servo_center (ESPACE, C) : on l'exige
        center_v = cal.get("center")
        if not isinstance(center_v, (int, float)):
            return False
        if not (min_v <= center_v <= max_v):
            return False
    return True

# Fichier externe centralisant la position repos (partagé entre tous les scripts)
REPOS_FILE = os.path.expanduser("~/lerobot/calibration/repos_position.json")

def charger_repos_pct():
    """Charge la position repos (% par servo) depuis le fichier externe.
    Retourne (dict {1:%,...}, origine) ou origine vaut 'custom' ou 'default'.
    Valide le contenu (6 servos, numeriques, [0,100]) ; sinon fallback par defaut
    ANNONCE par l'appelant (jamais silencieux)."""
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
    if positions is None:
        return None
    print("✅ Position initiale atteinte")
    return positions

def centrer_tous(packetHandler, portHandler, calibration, positions):
    """Centre tous les servos avec séquence sécurisée"""
    print("🎯 Centrage de tous les servos...")

    # Lire positions actuelles (verifiees)
    for i in range(1, 7):
        pos, ok = lire_position(packetHandler, portHandler, i)
        if not ok:
            print(f"❌ Lecture impossible du servo {i} — centrage annulé")
            return None
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

    # Position repos en pourcentages, lue depuis le fichier externe partagé.
    # Fallback ANNONCE sur valeurs par défaut si le fichier est absent ou invalide.
    repos_pct, origine = charger_repos_pct()
    if origine == "default":
        print("⚠️  repos_position.json absent ou invalide — position de repos PAR DÉFAUT utilisée.")

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

            print(f"Servo {i} ({SERVO_NAMES[i]:10}): Pos={pos:4} "
                  f"[Min:{min_val:4} Ctr:{center:4} Max:{max_val:4}] "
                  f"{pct:5.1f}% [{status}]")
        else:
            print(f"Servo {i} ({SERVO_NAMES[i]:10}): Pos={pos:4} [{status}]")

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

    # Choix du robot (explicite : pas de defaut silencieux)
    print("\nContrôler [L]eader ou [F]ollower?")
    robot_type = None
    while robot_type is None:
        choix = input("Choix [L/F]: ").strip().upper()
        if choix == 'L':
            robot_type = "leader"
        elif choix == 'F':
            robot_type = "follower"
        else:
            print("❌ Choix invalide : tapez L ou F")

    # Détection du port (unique, fail-closed : refus si plusieurs robots)
    port = detect_port()
    if not port:
        print("❌ Connexion au robot impossible.")
        print("   Vérifiez le branchement (un seul adaptateur à la fois).")
        return

    # Calibration OBLIGATOIRE : sans elle, les fleches clampent a 0-4095 et
    # peuvent forcer contre les butees mecaniques.
    calibration = charger_calibration(robot_type)
    if not calibration_complete(calibration):
        print(f"❌ Calibration du {robot_type} absente, incomplète ou invalide (amplitude < {MIN_AMPLITUDE}).")
        print("   Effectuez d'abord la Phase 3 (SEM_so101_2_calibrate.py).")
        return

    print(f"\n🔌 Connexion au {robot_type} sur {port}...")
    portHandler = PortHandler(port)
    packetHandler = PacketHandler(1.0)

    if not portHandler.openPort():
        print(f"❌ Impossible d'ouvrir le port {port}")
        return
    if not portHandler.setBaudRate(1000000):
        print("❌ Impossible de configurer le baudrate")
        portHandler.closePort()
        return

    print("✅ Connecté !")
    print("✅ Calibration chargée")

    # Etat
    servo_actif = 1
    pas_normal = 50
    pas_precis = 10
    mode_precis = False
    urgence = False         # True si arret d'urgence (X) : pas de retour repos
    sortie_normale = False  # True uniquement sur sortie normale (Q) : retour repos

    # Le port est ouvert : tout ce qui suit est sous try/finally (pas de fuite de port,
    # meme sur Ctrl+C pendant la confirmation).
    try:
        # Confirmation avant le mouvement automatique de demarrage
        print("\n⚠️  Le bras va rejoindre la position initiale.")
        print("    Dégagez l'espace de travail.")
        if input("    Entrée pour continuer, ou Q pour quitter : ").strip().upper() == 'Q':
            print("Annulé.")
            return  # -> finally : pas de repos (sortie_normale False), liberation, fermeture
        # Position initiale (sequence verifiee) — un echec arrete le script proprement
        positions = position_initiale(packetHandler, portHandler, calibration)
        if positions is None:
            print("❌ Échec de la mise en position initiale — arrêt.")
            return

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

        # Affichage initial des 3 lignes d'état
        print(f"Servo actif: {servo_actif} ({SERVO_NAMES[servo_actif]})")
        print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
        print(f"Position: {positions[servo_actif]}")

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
                print(f"Servo actif: {servo_actif} ({SERVO_NAMES[servo_actif]})")
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
                print(f"Servo actif: {servo_actif} ({SERVO_NAMES[servo_actif]})")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]} ↓")

            elif key == '[D':  # Flèche GAUCHE
                servo_actif = max(1, servo_actif - 1)
                clear_lines(3)
                print(f"Servo actif: {servo_actif} ({SERVO_NAMES[servo_actif]}) ←")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]}")

            elif key == '[C':  # Flèche DROITE
                servo_actif = min(6, servo_actif + 1)
                clear_lines(3)
                print(f"Servo actif: {servo_actif} ({SERVO_NAMES[servo_actif]}) →")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]}")

            # Commandes
            elif key == ' ':  # ESPACE - Centrer servo actif
                centre = get_servo_center(servo_actif, calibration)
                positions[servo_actif] = mouvement_fluide(packetHandler, portHandler,
                                                         servo_actif, positions[servo_actif],
                                                         centre, 1.5)
                clear_lines(3)
                print(f"Servo actif: {servo_actif} ({SERVO_NAMES[servo_actif]}) [CENTRÉ]")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]}")

            elif key.lower() == 'i':  # Position initiale
                result = position_initiale(packetHandler, portHandler, calibration)
                if result is None:
                    # Mouvement partiel possible : resynchroniser sur le bras reel
                    positions_reelles = lire_positions_toutes(packetHandler, portHandler)
                    if positions_reelles is None:
                        print("\n❌ État du bras incertain — arrêt du contrôle.")
                        break
                    positions = positions_reelles
                else:
                    positions = result
                clear_lines(3)
                print("Position INITIALE activée!" if result is not None
                      else "❌ INITIALE interrompue — positions réelles relues")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position servo {servo_actif}: {positions[servo_actif]}")

            elif key.lower() == 'c':  # Centrer TOUS
                result = centrer_tous(packetHandler, portHandler, calibration, dict(positions))
                if result is None:
                    positions_reelles = lire_positions_toutes(packetHandler, portHandler)
                    if positions_reelles is None:
                        print("\n❌ État du bras incertain — arrêt du contrôle.")
                        break
                    positions = positions_reelles
                else:
                    positions = result
                clear_lines(3)
                print("Tous les servos centrés!" if result is not None
                      else "❌ Centrage interrompu — positions réelles relues")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position servo {servo_actif}: {positions[servo_actif]}")

            elif key.lower() == 'p':  # Mode précis
                mode_precis = not mode_precis
                clear_lines(3)
                print(f"Servo actif: {servo_actif} ({SERVO_NAMES[servo_actif]})")
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
                print(f"Servo actif: {servo_actif} ({SERVO_NAMES[servo_actif]})")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position: {positions[servo_actif]}")

            elif key.lower() == 'a':  # Position attraper
                result = position_attraper(packetHandler, portHandler, calibration)
                if result is None:
                    positions_reelles = lire_positions_toutes(packetHandler, portHandler)
                    if positions_reelles is None:
                        print("\n❌ État du bras incertain — arrêt du contrôle.")
                        break
                    positions = positions_reelles
                else:
                    positions = result
                clear_lines(3)
                print("Position ATTRAPER activée!" if result is not None
                      else "❌ ATTRAPER interrompue — positions réelles relues")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position servo {servo_actif}: {positions[servo_actif]}")

            elif key.lower() == 'r':  # Position repos
                result = position_repos(packetHandler, portHandler, calibration)
                if result is None:
                    positions_reelles = lire_positions_toutes(packetHandler, portHandler)
                    if positions_reelles is None:
                        print("\n❌ État du bras incertain — arrêt du contrôle.")
                        break
                    positions = positions_reelles
                else:
                    positions = result
                clear_lines(3)
                print("Position REPOS activée!" if result is not None
                      else "❌ REPOS interrompue — positions réelles relues")
                print(f"Mode: {'PRÉCIS (pas=10)' if mode_precis else 'NORMAL (pas=50)'}")
                print(f"Position servo {servo_actif}: {positions[servo_actif]}")

            elif key.lower() == 'x':  # ARRÊT D'URGENCE
                print("\n⚠️  ARRÊT D'URGENCE!")
                for i in range(1, 7):
                    try:
                        packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
                    except Exception:
                        pass
                print("🛑 Tous les servos libérés immédiatement.")
                print("⚠️  Tenez le robot, il est libre !")
                urgence = True
                break

            elif key.lower() == 'q':  # Quitter
                print("\n👋 Arrêt en cours...")
                sortie_normale = True
                break

            elif key == '\x03':  # Ctrl+C capté en mode raw (pas de SIGINT) : interruption clavier
                print("\n⚠️  Interruption clavier")
                break

    except KeyboardInterrupt:
        print("\n⚠️  Interruption clavier")
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
    finally:
        # Nettoyage GARANTI. Trois cas distincts :
        #   Q (sortie normale) : retour repos -> liberation -> fermeture
        #   X (urgence)        : pas de retour repos (deja libere)
        #   Exception/Ctrl+C   : pas de retour repos (un mouvement de plus serait risque)
        if sortie_normale and not urgence:
            print("\n🏁 Position repos avant libération...")
            try:
                result = position_repos(packetHandler, portHandler, calibration)
                if result is None:
                    print("❌ Retour repos non confirmé — état du bras incertain.")
                else:
                    print("✅ Position repos atteinte.")
                print("⚠️  Tenez le robot avant libération")
                time.sleep(2)
            except Exception:
                pass

        # Liberation best-effort puis fermeture du port (toujours atteinte)
        for i in range(1, 7):
            try:
                packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
            except Exception:
                pass
        try:
            portHandler.closePort()
        except Exception:
            pass

        if urgence:
            print("\n✅ Arrêt d'urgence terminé (aucun retour repos).")
        else:
            print("\n✅ Terminé !")

if __name__ == "__main__":
    main()
