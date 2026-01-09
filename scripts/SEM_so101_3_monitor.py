#!/usr/bin/env python3
"""
Script SEM_so101_3_monitor.py
Service Ecoles Médias - SO-ARM 101
Description: Monitoring temps réel des positions des servos
Version: 3.0 - Ultra simplifié
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
    """Efface l'écran"""
    os.system('clear')

def detect_port():
    """Détection automatique du port USB"""
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']:
        if os.path.exists(port):
            os.system(f"sudo chmod 666 {port} 2>/dev/null")
            return port
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
    print("╔═════════╦═══════╦═══════╦═══════╦═══════╦══════════════════════╗")
    print("║ SERVO   ║  POS  ║  MIN  ║ CENTRE║  MAX  ║     GRAPHIQUE        ║")
    print("╠═════════╬═══════╬═══════╬═══════╬═══════╬══════════════════════╣")
    
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
        
        # Format fixe pour éviter les décalages
        print(f"║ {nom:<7} ║ {pos:5} ║ {min_val:5} ║ {center:5} ║ {max_val:5} ║ {barre} ║")
    
    print("╚═════════╩═══════╩═══════╩═══════╩═══════╩══════════════════════╝")
    
    # Statistiques simplifiées
    if stats:
        print(f"\n📊 Rafraîchissement: {stats['FPS']} Hz")
    
    # Instruction simple
    print("\n[Appuyez sur Ctrl+C pour quitter]")

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
            
            # Pause pour limiter la charge CPU
            time.sleep(0.05)  # ~20 FPS max
            
    except KeyboardInterrupt:
        print("\n\n✅ Monitoring arrêté proprement")
    
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
    
    finally:
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
