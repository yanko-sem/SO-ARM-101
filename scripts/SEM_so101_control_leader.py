#!/usr/bin/env python3
"""
Script SEM_so101_control_leader.py
Service Ecoles Médias - Contrôle manuel du Leader SO-ARM 101

Ce script permet de :
1. Contrôler le Leader depuis le PC
2. Utiliser les flèches du clavier
3. Mouvements fluides et sécurisés
"""

import sys
import os
import time
import termios
import tty
import json
import math

# Ajout du chemin LeRobot
sys.path.append(os.path.expanduser('~/lerobot'))
from dynamixel_sdk import *

def detect_port():
    """Détection automatique du port USB"""
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0']:
        if os.path.exists(port):
            os.system(f"sudo chmod 666 {port} 2>/dev/null")
            return port
    return None

def getch():
    """Capture d'une touche clavier"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b':  # Sequence ESC pour fleches
            ch = sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def mouvement_fluide(packetHandler, portHandler, servo_id, pos_actuelle, pos_cible, duree=2.5):
    """Mouvement fluide avec courbe sinusoïdale"""
    steps = 100  # Plus de steps pour plus de fluidité
    for step in range(steps + 1):
        t = step / steps
        # Courbe sinusoïdale pour fluidité
        smooth_t = (1 - math.cos(t * math.pi)) / 2
        pos_inter = int(pos_actuelle + (pos_cible - pos_actuelle) * smooth_t)
        packetHandler.write2ByteTxRx(portHandler, servo_id, 42, pos_inter)
        time.sleep(duree / steps)
    return pos_cible

def get_servo_center(servo_id, calibration):
    """Obtient la position centrale d'un servo"""
    if f"servo_{servo_id}" in calibration:
        return calibration[f"servo_{servo_id}"]["center"]
    else:
        # Valeurs par défaut si pas de calibration
        defaults = {1: 2079, 2: 1991, 3: 2073, 4: 2027, 5: 2075, 6: 2483}
        return defaults.get(servo_id, 2048)

def position_initiale(packetHandler, portHandler, calibration):
    """Position initiale sécurisée"""
    print("🔄 Mise en position initiale...")
    positions = {}
    
    # Positions initiales définies
    positions_initiales = {
        1: 2529,  # BASE
        2: 1391,  # EPAULE
        3: 2073,  # COUDE
        4: 1527,  # POIGNET-F
        5: 2625,  # POIGNET-R
        6: 2500   # POIGNEE
    }
    
    # D'abord activer tous les servos
    for i in range(1, 7):
        packetHandler.write1ByteTxRx(portHandler, i, 40, 1)
    
    # SÉQUENCE CORRECTE :
    # 1. Servo 3 → centre
    pos_actuelle, _, _ = packetHandler.read2ByteTxRx(portHandler, 3, 56)
    centre3 = get_servo_center(3, calibration)
    positions[3] = mouvement_fluide(packetHandler, portHandler, 3, pos_actuelle, centre3, 2.5)
    
    # 2. Servo 2 → centre
    pos_actuelle, _, _ = packetHandler.read2ByteTxRx(portHandler, 2, 56)
    centre2 = get_servo_center(2, calibration)
    positions[2] = mouvement_fluide(packetHandler, portHandler, 2, pos_actuelle, centre2, 2.5)
    
    # 3. Tous les servos → positions initiales
    for servo_id in range(1, 7):
        if servo_id in [2, 3]:
            pos_actuelle = positions[servo_id]  # Déjà au centre
        else:
            pos_actuelle, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
        positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                              pos_actuelle, positions_initiales[servo_id], 2.5)
    
    print("✅ Position initiale atteinte\n")
    return positions

def arret_urgence(packetHandler, portHandler):
    """Arrêt d'urgence - libère immédiatement tous les servos"""
    print("\n\n⚠️  ARRÊT D'URGENCE !")
    for i in range(1, 7):
        packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
    print("❌ Tous les servos libérés")
    return True

def position_repos_securisee(packetHandler, portHandler, positions, calibration):
    """Met le robot en position de repos avec logique conditionnelle"""
    print("\n🔄 Mise en position de repos sécurisée...")
    
    # Positions de repos
    repos_positions = {
        1: 2079,  # BASE centrée
        2: 1000,  # EPAULE basse avec marge
        3: 2800,  # COUDE replié avec marge
        4: 2700,  # POIGNET-F avec marge
        5: 2075,  # POIGNET-R centré
        6: 2000   # POIGNEE légèrement ouverte
    }
    
    # Lire position actuelle du servo 2
    pos_servo2 = positions[2]
    centre_servo2 = get_servo_center(2, calibration)
    
    if pos_servo2 >= centre_servo2:
        # Séquence si bras haut
        print("  → Séquence bras haut")
        positions[2] = mouvement_fluide(packetHandler, portHandler, 2, positions[2], repos_positions[2], 2.5)
        positions[4] = mouvement_fluide(packetHandler, portHandler, 4, positions[4], get_servo_center(4, calibration), 2.5)
        positions[3] = mouvement_fluide(packetHandler, portHandler, 3, positions[3], repos_positions[3], 2.5)
        positions[5] = mouvement_fluide(packetHandler, portHandler, 5, positions[5], get_servo_center(5, calibration), 2.5)
        positions[6] = mouvement_fluide(packetHandler, portHandler, 6, positions[6], repos_positions[6], 2.5)
        positions[4] = mouvement_fluide(packetHandler, portHandler, 4, positions[4], repos_positions[4], 2.5)
        # Tous les autres pas encore à R
        for servo_id in [1, 5]:
            if positions[servo_id] != repos_positions[servo_id]:
                positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id, 
                                                      positions[servo_id], repos_positions[servo_id], 2.5)
    else:
        # Séquence si bras bas
        print("  → Séquence bras bas")
        positions[3] = mouvement_fluide(packetHandler, portHandler, 3, positions[3], get_servo_center(3, calibration), 2.5)
        positions[4] = mouvement_fluide(packetHandler, portHandler, 4, positions[4], get_servo_center(4, calibration), 2.5)
        positions[2] = mouvement_fluide(packetHandler, portHandler, 2, positions[2], repos_positions[2], 2.5)
        # Tous les servos pas encore à R
        for servo_id in [1, 3, 4, 5, 6]:
            if positions[servo_id] != repos_positions[servo_id]:
                positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id, 
                                                      positions[servo_id], repos_positions[servo_id], 2.5)
    
    print("✅ Robot en position de repos")
    time.sleep(0.5)
    return positions

def position_attraper(packetHandler, portHandler, positions, calibration):
    """Position pour attraper - séquence simplifiée"""
    print("\n🤏 Position ATTRAPER...")
    
    # Positions cibles
    attraper_positions = {
        1: 2079,  # BASE
        2: 2091,  # EPAULE
        3: 2023,  # COUDE
        4: 2727,  # POIGNET-F
        5: 2075,  # POIGNET-R
        6: 2533   # POIGNEE
    }
    
    # SÉQUENCE SIMPLE ET CORRECTE :
    # 1. Servo 3 → centre
    centre3 = get_servo_center(3, calibration)
    positions[3] = mouvement_fluide(packetHandler, portHandler, 3, positions[3], centre3, 2.5)
    
    # 2. Servo 2 → centre
    centre2 = get_servo_center(2, calibration)
    positions[2] = mouvement_fluide(packetHandler, portHandler, 2, positions[2], centre2, 2.5)
    
    # 3. Tous les servos → position A
    for servo_id in range(1, 7):
        positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                              positions[servo_id], attraper_positions[servo_id], 2.5)
    
    print("✅ Position d'approche atteinte")
    return positions

def centrage_tous_servos(packetHandler, portHandler, positions, calibration):
    """Centre tous les servos avec logique conditionnelle"""
    print("\n🔄 Centrage fluide de tous les servos...")
    
    # Lire position actuelle du servo 2
    pos_servo2 = positions[2]
    centre_servo2 = get_servo_center(2, calibration)
    
    if pos_servo2 >= centre_servo2:
        # Séquence si bras haut - descendre prudemment
        print("  → Séquence bras haut")
        # D'abord centrer servo 2
        positions[2] = mouvement_fluide(packetHandler, portHandler, 2, positions[2], centre_servo2, 2.5)
        # Puis les autres
        for servo_id in [3, 4, 5, 6, 1]:
            centre = get_servo_center(servo_id, calibration)
            positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                                  positions[servo_id], centre, 2.5)
    else:
        # Séquence si bras bas - monter prudemment
        print("  → Séquence bras bas")
        # D'abord centrer servos 3 et 4 pour éviter collision
        for servo_id in [3, 4]:
            centre = get_servo_center(servo_id, calibration)
            positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                                  positions[servo_id], centre, 2.5)
        # Puis servo 2
        positions[2] = mouvement_fluide(packetHandler, portHandler, 2, positions[2], centre_servo2, 2.5)
        # Enfin les autres
        for servo_id in [5, 6, 1]:
            centre = get_servo_center(servo_id, calibration)
            positions[servo_id] = mouvement_fluide(packetHandler, portHandler, servo_id,
                                                  positions[servo_id], centre, 2.5)
    
    print("✅ Tous les servos centrés")
    return positions

def clear_lines(n=1):
    """Efface n lignes au-dessus du curseur"""
    for _ in range(n):
        print('\033[1A\033[K', end='')

# Clear screen
os.system('clear')

print("""
╔══════════════════════════════════════════════════════════╗
║     SEM - CONTROLE LEADER SO-ARM 101                    ║
║     Service Ecoles Médias                               ║
╚══════════════════════════════════════════════════════════╝
""")

PORT = detect_port()
if not PORT:
    print("❌ Pas d'adaptateur USB détecté")
    exit()

print(f"✅ Port détecté : {PORT}")

# Charger la calibration
calib_file = os.path.expanduser("~/.cache/calibration/so101/leader_calibration.json")
if os.path.exists(calib_file):
    with open(calib_file, 'r') as f:
        calibration = json.load(f)
    print("✅ Calibration chargée")
else:
    print("⚠️  Pas de calibration - utilisation des valeurs par défaut")
    calibration = {}

BAUDRATE = 1000000
portHandler = PortHandler(PORT)
packetHandler = PacketHandler(1.0)

if not portHandler.openPort() or not portHandler.setBaudRate(BAUDRATE):
    print("❌ Erreur connexion")
    exit()

print("")

# Position initiale avec séquence correcte
positions = position_initiale(packetHandler, portHandler, calibration)

servo_actif = 1
pas_normal = 50
pas_precis = 10
mode_precis = False
arret_urgence_active = False

print("""
╔════════════════════════════════════════════════════════╗
║                    CONTROLES                           ║
╠════════════════════════════════════════════════════════╣
║  ↑/↓       : Augmenter/Diminuer position              ║
║  ←/→       : Changer de servo (1-6)                   ║
║  ESPACE    : Centrer le servo actif                   ║
║  C         : Centrer TOUS les servos (fluide)         ║
║  P         : Mode précis ON/OFF (pas 10 vs 50)        ║
║  S         : Afficher toutes les positions            ║
║  A         : Position ATTRAPER (manipulation)          ║
║  R         : Position REPOS                            ║
║  Q         : Quitter (repos puis libération)           ║
║  X         : ARRÊT D'URGENCE                           ║
╚════════════════════════════════════════════════════════╝

État actuel:
""")

try:
    while True:
        # Affichage du servo actif sur une ligne fixe
        servo_names = {1:"BASE", 2:"EPAULE", 3:"COUDE", 4:"POIGNET-F", 5:"POIGNET-R", 6:"POIGNEE"}
        status = f"Servo {servo_actif}:{servo_names[servo_actif]:10} Pos:{positions[servo_actif]:4}"
        if mode_precis:
            status += " [PRECIS]"
        else:
            status += " [NORMAL]"
        
        # Effacer et réafficher la ligne d'état
        print(f"\r{status}                    ", end='', flush=True)
        
        key = getch()
        
        if key == 'x' or key == 'X':
            # ARRÊT D'URGENCE
            arret_urgence_active = arret_urgence(packetHandler, portHandler)
            break
            
        elif key == 'q' or key == 'Q':
            # Position repos puis libération
            positions = position_repos_securisee(packetHandler, portHandler, positions, calibration)
            break
            
        elif key == '[A':  # Flèche haut
            pas = pas_precis if mode_precis else pas_normal
            if f"servo_{servo_actif}" in calibration:
                max_pos = calibration[f"servo_{servo_actif}"]["max"]
                positions[servo_actif] = min(positions[servo_actif] + pas, max_pos)
            else:
                positions[servo_actif] = min(positions[servo_actif] + pas, 4095)
            packetHandler.write2ByteTxRx(portHandler, servo_actif, 42, positions[servo_actif])
            
        elif key == '[B':  # Flèche bas
            pas = pas_precis if mode_precis else pas_normal
            if f"servo_{servo_actif}" in calibration:
                min_pos = calibration[f"servo_{servo_actif}"]["min"]
                positions[servo_actif] = max(positions[servo_actif] - pas, min_pos)
            else:
                positions[servo_actif] = max(positions[servo_actif] - pas, 0)
            packetHandler.write2ByteTxRx(portHandler, servo_actif, 42, positions[servo_actif])
            
        elif key == '[D':  # Flèche gauche
            servo_actif = 6 if servo_actif == 1 else servo_actif - 1
            
        elif key == '[C':  # Flèche droite
            servo_actif = 1 if servo_actif == 6 else servo_actif + 1
            
        elif key == ' ':  # Espace - centrer servo actif
            centre = get_servo_center(servo_actif, calibration)
            clear_lines(1)
            print(f"\n🔄 Centrage servo {servo_actif}...", end='', flush=True)
            positions[servo_actif] = mouvement_fluide(packetHandler, portHandler, 
                                                      servo_actif, positions[servo_actif], centre, 2.5)
            clear_lines(1)
            print("")
            
        elif key == 'c' or key == 'C':  # Centrer tous avec logique conditionnelle
            positions = centrage_tous_servos(packetHandler, portHandler, positions, calibration)
            
        elif key == 'p' or key == 'P':  # Mode précis
            mode_precis = not mode_precis
            
        elif key == 's' or key == 'S':  # Afficher positions
            print("\n\n╔════════════════════════════════════╗")
            print("║       POSITIONS ACTUELLES          ║")
            print("╠════════════════════════════════════╣")
            for i in range(1, 7):
                print(f"║ Servo {i} ({servo_names[i]:10}): {positions[i]:4}    ║")
            print("╚════════════════════════════════════╝\n")
            print("État actuel:")
            
        elif key == 'a' or key == 'A':  # Position attraper avec séquence simple
            positions = position_attraper(packetHandler, portHandler, positions, calibration)
            
        elif key == 'r' or key == 'R':  # Position repos avec logique
            positions = position_repos_securisee(packetHandler, portHandler, positions, calibration)
            
except KeyboardInterrupt:
    # Si Ctrl+C, arrêt d'urgence
    arret_urgence_active = arret_urgence(packetHandler, portHandler)

finally:
    if not arret_urgence_active:
        print("\n\n🔌 Libération des servos...")
        for i in range(1, 7):
            packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
    portHandler.closePort()
    if arret_urgence_active:
        print("⚠️  Arrêt d'urgence effectué")
    else:
        print("✅ Terminé - Robot en position de repos")