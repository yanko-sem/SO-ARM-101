#!/usr/bin/env python3
"""
Script SEM_so101_calibrate.py
Service Ecoles Médias - Calibration des servos SO-ARM 101

Ce script permet de :
1. Calibrer les limites min/max de chaque servo
2. Sauvegarder automatiquement après chaque calibration
3. Afficher un tableau récapitulatif
"""

import json
import os
import sys
import time
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

print("""
==================================================
       CALIBRATION SO-ARM-101
       Service Ecoles Médias (SEM)
==================================================
""")

PORT = detect_port()
if not PORT:
    print("ERREUR: Pas d'adaptateur USB detecte")
    exit()

print(f"Port detecte : {PORT}")

print("\nQuel bras ?")
print("  1 - LEADER (avec poignee)")
print("  2 - FOLLOWER (avec pince)")
choix_bras = input("Choix (1 ou 2) : ")

arm_name = "leader" if choix_bras == "1" else "follower"

# Affichage clair du robot actif
print("\n" + "="*50)
print(f"     ROBOT ACTIF: {arm_name.upper()}")
print("="*50)

# Charger calibration existante
calib_dir = os.path.expanduser("~/.cache/calibration/so101")
os.makedirs(calib_dir, exist_ok=True)
calib_file = os.path.join(calib_dir, f"{arm_name}_calibration.json")

if os.path.exists(calib_file):
    with open(calib_file, 'r') as f:
        calibration = json.load(f)
    print(f"Calibration existante chargee pour {arm_name.upper()}")
else:
    calibration = {}
    print(f"Nouvelle calibration pour {arm_name.upper()}")

BAUDRATE = 1000000
portHandler = PortHandler(PORT)
packetHandler = PacketHandler(1.0)

if not portHandler.openPort() or not portHandler.setBaudRate(BAUDRATE):
    print("ERREUR: connexion")
    exit()

servo_names = {
    1: "BASE", 2: "EPAULE", 3: "COUDE",
    4: "POIGNET FLEXION", 5: "POIGNET ROTATION", 6: "PINCE/POIGNEE"
}

def sauvegarder_calibration():
    """Sauvegarde automatique"""
    with open(calib_file, 'w') as f:
        json.dump(calibration, f, indent=2)
    print("  [Sauvegarde automatique effectuee]")

def centrage_doux(servo_id, position_cible, duree=1.5):
    """Centrage avec mouvement fluide"""
    pos_actuelle, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
    packetHandler.write1ByteTxRx(portHandler, servo_id, 40, 1)
    
    steps = 50
    for step in range(steps + 1):
        t = step / steps
        smooth_t = (1 - math.cos(t * math.pi)) / 2
        
        pos_inter = int(pos_actuelle + (position_cible - pos_actuelle) * smooth_t)
        packetHandler.write2ByteTxRx(portHandler, servo_id, 42, pos_inter)
        time.sleep(duree / steps)
    
    time.sleep(0.5)
    packetHandler.write1ByteTxRx(portHandler, servo_id, 40, 0)

def afficher_tableau_recap():
    """Affiche le tableau recapitulatif"""
    print("\n" + "="*60)
    print("         TABLEAU RECAPITULATIF")
    print("="*60)
    print("ID  Nom                MIN    CENTRE  MAX    Amplitude")
    print("-"*60)
    
    for i in range(1, 7):
        if f"servo_{i}" in calibration:
            data = calibration[f"servo_{i}"]
            print(f"{i}   {data['name']:<18} {data['min']:<6} {data['center']:<7} {data['max']:<6} {data['amplitude']}")
        else:
            print(f"{i}   {servo_names[i]:<18} ---    ---     ---    ---")
    print("="*60)

# Liberer tous les servos au debut
print("\nLiberation des servos...")
for i in range(1, 7):
    packetHandler.write1ByteTxRx(portHandler, i, 40, 0)

while True:
    print(f"\n[ROBOT: {arm_name.upper()}]")
    print("="*50)
    print("MENU PRINCIPAL:")
    print("  1-6 : Calibrer UN servo specifique")
    print("  T   : Calibrer TOUS les servos")
    print("  V   : Voir calibration actuelle")
    print("  Q   : QUITTER et sauvegarder")
    print("="*50)
    
    choix = input(f"\n{arm_name}> ").upper().strip()
    
    if choix == 'Q':
        sauvegarder_calibration()
        print(f"Calibration finale sauvegardee pour {arm_name.upper()}")
        break
        
    elif choix == 'V':
        print(f"\nCALIBRATION ACTUELLE ({arm_name.upper()}):")
        for i in range(1, 7):
            if f"servo_{i}" in calibration:
                data = calibration[f"servo_{i}"]
                print(f"  Servo {i}: MIN={data['min']}, CENTRE={data['center']}, MAX={data['max']}")
            else:
                print(f"  Servo {i}: Non calibre")
                
    elif choix == 'T':
        print(f"\nCALIBRATION COMPLETE ({arm_name.upper()} - 6 servos)")
        for servo_id in range(1, 7):
            print(f"\n{'='*40}")
            print(f"SERVO {servo_id} : {servo_names[servo_id]}")
            print("="*40)
            
            print("-> Bougez le servo a une BUTEE (extreme 1)")
            input("   Appuyez ENTREE... ")
            pos1, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
            print(f"   Position 1 = {pos1}")
            
            print("\n-> Bougez le servo a l'AUTRE BUTEE (extreme 2)")
            input("   Appuyez ENTREE... ")
            pos2, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
            print(f"   Position 2 = {pos2}")
            
            pos_min = min(pos1, pos2)
            pos_max = max(pos1, pos2)
            pos_center = (pos_min + pos_max) // 2
            amplitude = pos_max - pos_min
            
            print(f"\n  MIN={pos_min}, CENTRE={pos_center}, MAX={pos_max}")
            print(f"  Amplitude={amplitude}")
            
            print("\n-> Centrage dans 2 secondes...")
            time.sleep(2)
            print("-> Centrage en douceur...")
            centrage_doux(servo_id, pos_center)
            print("OK: Servo recentre et libere")
            
            calibration[f"servo_{servo_id}"] = {
                "min": pos_min,
                "max": pos_max,
                "center": pos_center,
                "amplitude": amplitude,
                "name": servo_names[servo_id]
            }
            
            # Sauvegarde automatique apres chaque servo
            sauvegarder_calibration()
        
        # Afficher tableau recap a la fin
        afficher_tableau_recap()
            
    elif choix in '123456':
        servo_id = int(choix)
        print(f"\n{'='*40}")
        print(f"CALIBRATION SERVO {servo_id} : {servo_names[servo_id]}")
        print(f"ROBOT: {arm_name.upper()}")
        print("="*40)
        
        if f"servo_{servo_id}" in calibration:
            old = calibration[f"servo_{servo_id}"]
            print(f"Ancienne: MIN={old['min']}, MAX={old['max']}, CENTRE={old['center']}")
        
        print("\n-> Bougez le servo a une BUTEE (extreme 1)")
        input("   Appuyez ENTREE... ")
        pos1, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
        print(f"   Position 1 = {pos1}")
        
        print("\n-> Bougez le servo a l'AUTRE BUTEE (extreme 2)")
        input("   Appuyez ENTREE... ")
        pos2, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
        print(f"   Position 2 = {pos2}")
        
        pos_min = min(pos1, pos2)
        pos_max = max(pos1, pos2)
        pos_center = (pos_min + pos_max) // 2
        amplitude = pos_max - pos_min
        
        print(f"\nNOUVELLE CALIBRATION:")
        print(f"  MIN    : {pos_min}")
        print(f"  CENTRE : {pos_center}")
        print(f"  MAX    : {pos_max}")
        print(f"  Amplitude : {amplitude}")
        
        # Alerte si amplitude anormale
        if amplitude < 500:
            print("  ATTENTION: Amplitude faible!")
        elif amplitude > 3500 and not (arm_name == "leader" and servo_id == 3):
            print("  ATTENTION: Amplitude elevee!")
        
        print("\n-> Centrage dans 2 secondes...")
        time.sleep(2)
        print("-> Centrage en douceur...")
        centrage_doux(servo_id, pos_center)
        print("OK: Servo recentre et libere")
        
        calibration[f"servo_{servo_id}"] = {
            "min": pos_min,
            "max": pos_max,
            "center": pos_center,
            "amplitude": amplitude,
            "name": servo_names[servo_id]
        }
        
        # Sauvegarde automatique
        sauvegarder_calibration()
        print("Calibration enregistree et sauvegardee!")

# Liberation finale
for i in range(1, 7):
    packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
portHandler.closePort()

print(f"\nTERMINE! Calibration {arm_name.upper()} complete.")
print(f"Fichier: {calib_file}")
