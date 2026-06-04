#!/usr/bin/env python3
"""
Script SEM_so101_3_monitor.py
Service Ecoles Médias - SO-ARM 101
Description: Monitoring temps réel des positions des servos
Version: 3.0 - Ultra simplifié
"""
import sys, os, time, json, math

# Imports pour la détection clavier non-bloquante (capture position repos)
try:
    import termios, tty, select
    TERMIOS_AVAILABLE = True
except ImportError:
    TERMIOS_AVAILABLE = False

# Fichier externe centralisant la position repos (partagé entre tous les scripts)
REPOS_FILE = os.path.expanduser("~/lerobot/calibration/repos_position.json")

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
    """Efface l'écran"""
    os.system('clear')

def detect_port():
    """Détection du port du robot.

    Au lieu de prendre le premier port qui existe (qui peut être un téléphone
    ou un autre périphérique série), on TESTE chaque port candidat en interrogeant
    le servo 1. Le port qui répond au protocole servo est le robot ; les autres
    périphériques (téléphone en charge, etc.) sont ignorés.
    """
    BAUDRATE = 1000000
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
                    return port
            else:
                ph.closePort()
        except Exception:
            try:
                ph.closePort()
            except Exception:
                pass
    return None

def arret_urgence(packetHandler, portHandler):
    """Arrêt d'urgence - libère tous les servos"""
    print("\n⚠️  ARRÊT D'URGENCE ACTIVÉ!")
    for i in range(1, 7):
        try:
            packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
        except:
            pass
    print("✅ Tous les servos libérés")
    return True

def charger_calibration(robot_type='leader'):
    """Charge la calibration d'un robot"""
    calib_file = os.path.expanduser(f"~/lerobot/calibration/{robot_type}_calibration.json")
    if os.path.exists(calib_file):
        with open(calib_file, 'r') as f:
            return json.load(f)
    return None

# ============================================
# GESTION DE LA POSITION REPOS (fichier externe)
# ============================================

def charger_repos():
    """Charge la position repos existante (% par servo). Retourne dict {1:%,...} ou None."""
    if os.path.exists(REPOS_FILE):
        try:
            with open(REPOS_FILE, 'r') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception:
            return None
    return None

def sauvegarder_repos(repos_pct):
    """Sauvegarde la position repos (% par servo) dans le fichier JSON externe."""
    os.makedirs(os.path.dirname(REPOS_FILE), exist_ok=True)
    data = {str(i): repos_pct[i] for i in range(1, 7)}
    with open(REPOS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def ticks_vers_pct(positions, calibration):
    """Convertit des positions (ticks bruts) en pourcentages via la calibration.
    Pourcentage = (tick - min) / (max - min) * 100, borné à [0, 100], arrondi à 2 décimales."""
    repos_pct = {}
    for i in range(1, 7):
        if calibration and f"servo_{i}" in calibration:
            min_v = calibration[f"servo_{i}"]['min']
            max_v = calibration[f"servo_{i}"]['max']
            if max_v > min_v:
                pct = (positions[i] - min_v) / (max_v - min_v) * 100
                repos_pct[i] = round(max(0.0, min(100.0, pct)), 2)
            else:
                repos_pct[i] = 50.0
        else:
            repos_pct[i] = 50.0
    return repos_pct

def verifier_limites(positions, calibration):
    """Vérifie que chaque position est dans [min, max]. Retourne dict {servo: bool}."""
    result = {}
    for i in range(1, 7):
        if calibration and f"servo_{i}" in calibration:
            min_v = calibration[f"servo_{i}"]['min']
            max_v = calibration[f"servo_{i}"]['max']
            result[i] = (min_v <= positions[i] <= max_v)
        else:
            result[i] = True
    return result

def afficher_recap_repos(positions, repos_pct, limites):
    """Affiche un récapitulatif de la position repos (ticks + % + vérif limites)."""
    servo_names = {1: "BASE", 2: "EPAULE", 3: "COUDE",
                   4: "POIGN-F", 5: "POIGN-R", 6: "PINCE"}
    print("\n┌─────────┬────────┬──────────┬────────────┐")
    print("│ SERVO   │ TICKS  │    %     │  LIMITES   │")
    print("├─────────┼────────┼──────────┼────────────┤")
    for i in range(1, 7):
        nom = f"{i}:{servo_names[i]}"
        etat = "OK" if limites[i] else "HORS !"
        print(f"│ {nom:<7} │ {positions[i]:6} │ {repos_pct[i]:7.2f}% │ {etat:<10} │")
    print("└─────────┴────────┴──────────┴────────────┘")

def capturer_repos_mode_A(packetHandler, portHandler, calibration, robot_type):
    """Mode A : capture la position physique actuelle du robot comme position repos."""
    clear_screen()
    print("="*60)
    print("📍 CAPTURE POSITION REPOS - Mode A (position physique actuelle)")
    print("="*60)
    print(f"\nRobot monitoré : {robot_type.upper()}")
    if robot_type != 'follower':
        print("⚠️  Recommandation : capturer depuis le FOLLOWER (référence du déploiement).")

    # Lecture fraîche des positions au moment de la capture
    positions = {}
    for i in range(1, 7):
        pos, result, _ = packetHandler.read2ByteTxRx(portHandler, i, 56)
        positions[i] = pos if result == COMM_SUCCESS else 0

    repos_pct = ticks_vers_pct(positions, calibration)
    limites = verifier_limites(positions, calibration)
    afficher_recap_repos(positions, repos_pct, limites)

    if not all(limites.values()):
        print("\n⚠️  Une ou plusieurs valeurs sont HORS des limites de calibration.")
        print("    Elles seront bornées à [0%, 100%]. Repositionnez si nécessaire.")

    print("\n→ Enregistrer cette position comme repos ? [O/N] : ", end="", flush=True)
    confirm = input().strip().upper()
    if confirm == 'O':
        sauvegarder_repos(repos_pct)
        print(f"\n✅ Position repos enregistrée dans :\n   {REPOS_FILE}")
    else:
        print("\n❌ Annulé, aucune modification.")
    input("\nAppuyez sur Entrée pour revenir au monitoring...")

def saisir_repos_mode_B(calibration, robot_type):
    """Mode B : saisie manuelle des 6 valeurs (ticks bruts) comme position repos."""
    clear_screen()
    print("="*60)
    print("⌨️  CAPTURE POSITION REPOS - Mode B (saisie manuelle des ticks)")
    print("="*60)
    print(f"\nCalibration utilisée : {robot_type.upper()}")
    servo_names = {1: "BASE", 2: "EPAULE", 3: "COUDE",
                   4: "POIGN-F", 5: "POIGN-R", 6: "PINCE"}

    positions = {}
    for i in range(1, 7):
        if calibration and f"servo_{i}" in calibration:
            min_v = calibration[f"servo_{i}"]['min']
            max_v = calibration[f"servo_{i}"]['max']
        else:
            min_v, max_v = 0, 4095
        while True:
            saisie = input(f"Servo {i} ({servo_names[i]}) [min {min_v}, max {max_v}] : ").strip()
            try:
                tick = int(saisie)
                if min_v <= tick <= max_v:
                    positions[i] = tick
                    break
                else:
                    print(f"   ⚠️  {tick} hors limites [{min_v}, {max_v}]. Réessayez.")
            except ValueError:
                print("   ⚠️  Entrez un nombre entier. Réessayez.")

    repos_pct = ticks_vers_pct(positions, calibration)
    limites = verifier_limites(positions, calibration)
    afficher_recap_repos(positions, repos_pct, limites)

    print("\n→ Enregistrer cette position comme repos ? [O/N] : ", end="", flush=True)
    confirm = input().strip().upper()
    if confirm == 'O':
        sauvegarder_repos(repos_pct)
        print(f"\n✅ Position repos enregistrée dans :\n   {REPOS_FILE}")
    else:
        print("\n❌ Annulé, aucune modification.")
    input("\nAppuyez sur Entrée pour revenir au monitoring...")

def calculer_barre_progression(valeur, min_val, max_val, largeur=20):
    """Crée une barre de progression visuelle"""
    if max_val <= min_val:
        return "░" * largeur

    position = (valeur - min_val) / (max_val - min_val)
    position = max(0, min(1, position))  # Limiter entre 0 et 1

    rempli = int(position * largeur)
    return "█" * rempli + "░" * (largeur - rempli)

def afficher_tableau_temps_reel(positions, calibration, stats=None):
    """Affiche un tableau formaté avec les positions en temps réel"""

    # Noms des servos (sans accents pour l'alignement)
    servo_names = {
        1: "BASE", 2: "EPAULE", 3: "COUDE",
        4: "POIGN-F", 5: "POIGN-R", 6: "PINCE"
    }

    # Clear complet à chaque fois
    clear_screen()

    # En-tête
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     MONITORING TEMPS REEL - POSITIONS SERVOS            ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Tableau principal
    print("╔═══════════╦═══════╦═══════╦═══════╦═══════╦═══════╦══════════════════════╗")
    print("║ SERVO     ║  POS  ║   %   ║  MIN  ║ CENTRE║  MAX  ║     GRAPHIQUE        ║")
    print("╠═══════════╬═══════╬═══════╬═══════╬═══════╬═══════╬══════════════════════╣")

    for i in range(1, 7):
        nom = f"{i}:{servo_names[i]}"
        pos = positions.get(i, 0)

        if calibration and f"servo_{i}" in calibration:
            cal = calibration[f"servo_{i}"]
            min_val = cal.get('min', 0)
            center = cal.get('center', 2048)
            max_val = cal.get('max', 4095)
        else:
            min_val, center, max_val = 0, 2048, 4095

        barre = calculer_barre_progression(pos, min_val, max_val, 20)
        pct = (pos - min_val) / (max_val - min_val) * 100 if max_val > min_val else 0.0

        # Format fixe pour éviter les décalages
        print(f"║ {nom:<9} ║ {pos:5} ║ {pct:5.1f} ║ {min_val:5} ║ {center:5} ║ {max_val:5} ║ {barre} ║")

    print("╚═══════════╩═══════╩═══════╩═══════╩═══════╩═══════╩══════════════════════╝")

    # Statistiques simplifiées
    if stats:
        print(f"\n📊 Rafraîchissement: {stats['FPS']} Hz")

    # Position repos actuellement enregistrée (si présente)
    repos_actuel = charger_repos()
    if repos_actuel:
        parts = []
        for i in range(1, 7):
            p = repos_actuel.get(i, 0)
            if calibration and f"servo_{i}" in calibration:
                mn = calibration[f"servo_{i}"]['min']
                mx = calibration[f"servo_{i}"]['max']
                tick = int(mn + (mx - mn) * p / 100)
            else:
                tick = 0
            parts.append(f"S{i}:{p:.1f}%({tick})")
        repos_str = "  ".join(parts)
        etat_repos = f"✅ Repos enregistré : {repos_str}"
    else:
        etat_repos = "⚠️  AUCUNE position repos enregistrée pour l'instant"

    # Encadré dédié à la création/modification de la position repos
    print()
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║              📍  CRÉER / MODIFIER LA POSITION REPOS                  ║")
    print("╠════════════════════════════════════════════════════════════════════╣")
    print("║   Point de départ ET de retour commun à TOUS les scripts.          ║")
    print("║   Un défaut est fourni ; personnalisez-le ci-dessous si besoin.    ║")
    print("╠════════════════════════════════════════════════════════════════════╣")
    print("║                                                                      ║")
    print("║   [C]  CAPTURER la position physique actuelle du bras                ║")
    print("║        (placez le bras à la main, puis pressez C)                    ║")
    print("║                                                                      ║")
    print("║   [M]  SAISIR manuellement les 6 valeurs (en ticks)                  ║")
    print("║                                                                      ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    # État affiché hors du cadre (longueur variable, évite les soucis d'alignement)
    print(f"   {etat_repos}")
    print("   [Ctrl+C] Quitter le monitoring")

# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main():
    # Clear écran au démarrage
    clear_screen()

    # Bannière standard
    print("""
╔══════════════════════════════════════════════════════════╗
║     SEM SO-ARM 101 - MONITORING TEMPS RÉEL              ║
║     Service Ecoles Médias                               ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Détection du port
    PORT = detect_port()
    if not PORT:
        print("❌ Aucun adaptateur USB détecté")
        print("\nVérifiez :")
        print("  1. Câble USB branché")
        print("  2. Alimentation 12V connectée")
        print("  3. Interrupteur ON")
        return

    print(f"✅ Port détecté : {PORT}")

    # Choix du robot
    print("\n🤖 Quel robot monitorer ?")
    print("  [L] LEADER")
    print("  [F] FOLLOWER")

    choix = input("\nVotre choix : ").strip().upper()

    if choix == 'F':
        robot_type = 'follower'
    else:
        robot_type = 'leader'  # Par défaut si entrée vide ou L

    print(f"\n📡 Monitoring du {robot_type.upper()}")

    # Chargement calibration
    calibration = charger_calibration(robot_type)
    if calibration:
        print("✅ Calibration chargée")
    else:
        print("⚠️  Pas de calibration - valeurs par défaut")

    # Connexion
    BAUDRATE = 1000000
    portHandler = PortHandler(PORT)
    packetHandler = PacketHandler(1.0)

    if not portHandler.openPort() or not portHandler.setBaudRate(BAUDRATE):
        print("❌ Erreur de connexion")
        return

    print("\n🚀 Démarrage du monitoring...")
    print("   Chargement des servos...")
    time.sleep(1)

    # Variables de monitoring
    positions = {}
    fps_counter = 0
    fps_time = time.time()
    current_fps = 0
    servos_actifs = 0

    # Désactiver tous les servos au début
    for i in range(1, 7):
        packetHandler.write1ByteTxRx(portHandler, i, 40, 0)

    print("   Initialisation terminée")
    time.sleep(1)

    # Configuration du terminal pour la détection clavier non-bloquante (touches C/M)
    old_term_settings = None
    keyboard_actif = False
    if TERMIOS_AVAILABLE:
        try:
            old_term_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            keyboard_actif = True
        except Exception:
            keyboard_actif = False

    try:
        while True:
            # Lecture des positions
            for servo_id in range(1, 7):
                pos, result, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
                if result == COMM_SUCCESS:
                    positions[servo_id] = pos
                    if servo_id == 1:  # Compter une fois
                        servos_actifs = len(positions)
                else:
                    positions[servo_id] = 0

            # Calcul FPS
            fps_counter += 1
            current_time = time.time()
            if current_time - fps_time >= 1.0:
                current_fps = fps_counter
                fps_counter = 0
                fps_time = current_time

            # Statistiques minimales
            stats = {
                "FPS": f"{current_fps}"
            }

            # Affichage
            afficher_tableau_temps_reel(positions, calibration, stats)

            # Détection clavier non-bloquante (capture repos)
            if keyboard_actif and select.select([sys.stdin], [], [], 0)[0]:
                touche = sys.stdin.read(1).upper()
                if touche == 'C':
                    # Restaurer le terminal pour les input() de la capture
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_term_settings)
                    capturer_repos_mode_A(packetHandler, portHandler, calibration, robot_type)
                    tty.setcbreak(sys.stdin.fileno())
                elif touche == 'M':
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_term_settings)
                    saisir_repos_mode_B(calibration, robot_type)
                    tty.setcbreak(sys.stdin.fileno())

            # Pause pour limiter la charge CPU
            time.sleep(0.05)  # ~20 FPS max

    except KeyboardInterrupt:
        print("\n\n✅ Monitoring arrêté proprement")

    except Exception as e:
        print(f"\n❌ Erreur : {e}")

    finally:
        # Restaurer le terminal
        if keyboard_actif and old_term_settings is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_term_settings)
            except Exception:
                pass

        # Libération finale
        print("\n🔌 Libération de tous les servos...")
        for i in range(1, 7):
            try:
                packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
            except:
                pass

        portHandler.closePort()
        print("✅ Port fermé")
        print("\n👋 Monitoring terminé")

if __name__ == "__main__":
    main()
