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

# Positions initiales (centrées)
positions = {}
for i in range(1, 7):
    if f"servo_{i}" in calibration:
        positions[i] = calibration[f"servo_{i}"]["center"]
    else:
        positions[i] = 2048  # Centre par défaut
    # Activer et centrer le servo
    packetHandler.write1ByteTxRx(portHandler, i, 40, 1)
    packetHandler.write2ByteTxRx(portHandler, i, 42, positions[i])

servo_actif = 1
pas_normal = 50
pas_precis = 10

print("""
CONTROLES :
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ↑/↓     : Augmenter/Diminuer position
  ←/→     : Servo précédent/suivant
  ESPACE  : Centrer le servo actif
  C       : Centrer TOUS les servos
  P       : Mode précis ON/OFF
  S       : Afficher positions
  Q       : Quitter
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

mode_precis = False

try:
    while True:
        # Affichage du servo actif
        servo_names = {1:"BASE", 2:"EPAULE", 3:"COUDE", 4:"POIGNET-F", 5:"POIGNET-R", 6:"POIGNEE"}
        print(f"\rServo {servo_actif}:{servo_names[servo_actif]} Pos:{positions[servo_actif]:4} {'[PRECIS]' if mode_precis else '        '}", end='', flush=True)
        
        key = getch()
        
        if key == 'q' or key == 'Q':
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
            if f"servo_{servo_actif}" in calibration:
                center = calibration[f"servo_{servo_actif}"]["center"]
            else:
                center = 2048
            positions[servo_actif] = center
            packetHandler.write2ByteTxRx(portHandler, servo_actif, 42, center)
            print(f"\n✅ Servo {servo_actif} centré à {center}")
            
        elif key == 'c' or key == 'C':  # Centrer tous
            print("\n🔄 Centrage de tous les servos...")
            for i in range(1, 7):
                if f"servo_{i}" in calibration:
                    center = calibration[f"servo_{i}"]["center"]
                else:
                    center = 2048
                positions[i] = center
                packetHandler.write2ByteTxRx(portHandler, i, 42, center)
            print("✅ Tous les servos centrés")
            
        elif key == 'p' or key == 'P':  # Mode précis
            mode_precis = not mode_precis
            print(f"\n{'✅ Mode PRECIS activé (pas=10)' if mode_precis else '✅ Mode NORMAL activé (pas=50)'}")
            
        elif key == 's' or key == 'S':  # Afficher positions
            print("\n\nPOSITIONS ACTUELLES:")
            print("="*40)
            for i in range(1, 7):
                print(f"Servo {i} ({servo_names[i]:10}): {positions[i]:4}")
            print("="*40)
            
except KeyboardInterrupt:
    pass

finally:
    print("\n\nLibération des servos...")
    for i in range(1, 7):
        packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
    portHandler.closePort()
    print("✅ Terminé")
