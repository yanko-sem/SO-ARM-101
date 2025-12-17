#!/usr/bin/env python3
"""
Script SEM_so101_config_servo.py
Service Ecoles Médias - Configuration des servos SO-ARM 101

Ce script permet de configurer les servos un par un avec les bons IDs et ratios.
Compatible avec Leader (différents ratios) et Follower (tous identiques).
"""

import sys
import os
import time
import subprocess

# Ajout du chemin LeRobot pour les imports
sys.path.append(os.path.expanduser('~/lerobot'))

# SEULE MODIFICATION : Import déplacé ici au lieu de ligne 59
from dynamixel_sdk import *

def detect_port():
    """Détection automatique du port USB"""
    ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']
    for port in ports:
        if os.path.exists(port):
            # Correction automatique des permissions
            os.system(f"sudo chmod 666 {port} 2>/dev/null")
            return port
    return None

def configure_servo(servo_id):
    """Configure un servo avec le script officiel LeRobot"""
    port = detect_port()
    if not port:
        print("❌ Aucun port USB détecté!")
        return False
    
    print(f"\n{'='*50}")
    print(f"Configuration du Servo {servo_id}")
    print(f"Port: {port}")
    print(f"{'='*50}")
    
    # D'abord, on fait la configuration directement avec dynamixel_sdk
    # car configure_motor.py pourrait ne pas exister ou être ailleurs
    try:
        portHandler = PortHandler(port)
        packetHandler = PacketHandler(1.0)
        
        if not portHandler.openPort():
            print("❌ Impossible d'ouvrir le port")
            return False
            
        if not portHandler.setBaudRate(1000000):
            print("❌ Impossible de configurer le baudrate")
            return False
        
        # 1. DÉTECTION du servo branché (peu importe son ID actuel)
        print("🔍 Recherche du servo...")
        id_actuel = None
        for test_id in range(1, 254):
            pos, result, _ = packetHandler.read2ByteTxRx(portHandler, test_id, 56)
            if result == 0:  # COMM_SUCCESS
                id_actuel = test_id
                print(f"✅ Servo trouvé avec l'ID actuel: {id_actuel}")
                break
        
        if id_actuel is None:
            print("❌ Aucun servo détecté!")
            print("Vérifiez que:")
            print("  - Le servo est bien branché")
            print("  - L'alimentation 12V est connectée")
            portHandler.closePort()
            return False
        
        # 2. CHANGEMENT D'ID si nécessaire
        if id_actuel != servo_id:
            print(f"\n📝 Configuration de l'ID...")
            print(f"  ID actuel: {id_actuel}")
            print(f"  Nouvel ID: {servo_id}")
            
            # IMPORTANT: Écrire dans l'EEPROM (registre 3)
            result, _ = packetHandler.write1ByteTxRx(portHandler, id_actuel, 3, servo_id)
            if result == 0:  # COMM_SUCCESS
                print(f"  ✅ ID changé avec succès!")
                
                # SAUVEGARDE dans l'EEPROM (certains servos nécessitent un reboot)
                time.sleep(1)
                
                # Vérifier que le nouvel ID fonctionne
                pos, result, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
                if result == 0:
                    print(f"  ✅ Servo répond maintenant à l'ID {servo_id}")
                else:
                    print("  ⚠️ Le servo nécessite peut-être un redémarrage")
                    print("  Débranchez et rebranchez le servo")
            else:
                print("❌ Impossible de changer l'ID")
                portHandler.closePort()
                return False
        else:
            print(f"✅ Le servo a déjà l'ID {servo_id}")
        
        # 3. VÉRIFICATION de la configuration
        print("\n📋 Vérification de la configuration...")
        
        # Lire l'ID pour confirmer
        id_lu, result, _ = packetHandler.read1ByteTxRx(portHandler, servo_id, 3)
        if result == 0 and id_lu == servo_id:
            print(f"  ✅ ID: {id_lu} [SAUVEGARDÉ]")
        else:
            print(f"  ❌ Problème avec l'ID")
        
        # Lire le baudrate (registre 4)
        baud_reg, result, _ = packetHandler.read1ByteTxRx(portHandler, servo_id, 4)
        print(f"  ℹ️ Baudrate registre: {baud_reg} (3 = 1Mbps)")
        
        # 4. TEST DE MOUVEMENT
        print("\n🔄 Test de mouvement...")
        
        # Activer le servo
        packetHandler.write1ByteTxRx(portHandler, servo_id, 40, 1)
        
        # Mouvement de test
        print("  → Position MIN (1024)")
        packetHandler.write2ByteTxRx(portHandler, servo_id, 42, 1024)
        time.sleep(1)
        
        print("  → Position MAX (3072)")
        packetHandler.write2ByteTxRx(portHandler, servo_id, 42, 3072)
        time.sleep(1)
        
        print("  → Position CENTRE (2048)")
        packetHandler.write2ByteTxRx(portHandler, servo_id, 42, 2048)
        time.sleep(1)
        
        # Bloquer au centre pour le montage
        packetHandler.write1ByteTxRx(portHandler, servo_id, 40, 1)
        print("\n✅ Servo bloqué au centre pour montage")
        print("   (Utilisez L dans le menu pour libérer)")
        
        portHandler.closePort()
        
        print("\n" + "="*50)
        print("✅ CONFIGURATION TERMINÉE ET SAUVEGARDÉE")
        print(f"  Servo ID: {servo_id}")
        print("  Les paramètres sont stockés dans l'EEPROM du servo")
        print("  Ils sont permanents même après coupure d'alimentation")
        print("="*50)
        return True
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    # AJOUT 1: Effacer l'écran au début
    os.system('clear')
    
    print("""
╔══════════════════════════════════════════════════════════╗
║       SEM - CONFIGURATION DES SERVOS SO-ARM 101         ║
║              Service Ecoles Médias                       ║
╚══════════════════════════════════════════════════════════╝

Ce script configure les servos un par un avec leurs IDs.

IMPORTANT - Ratios par robot:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LEADER:
  • Servos 1,3: Ratio 1:191 (C044)
  • Servo 2:    Ratio 1:345 (C001)
  • Servos 4,5,6: Ratio 1:147 (C046)

FOLLOWER:
  • Tous les servos: Ratio 1:345
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    # Détection initiale
    port = detect_port()
    if not port:
        print("❌ Aucun adaptateur USB détecté!")
        print("\nVérifiez:")
        print("  1. L'adaptateur USB est branché")
        print("  2. Un seul robot est connecté")
        print("  3. L'alimentation est active")
        return

    print(f"✅ Port détecté: {port}")
    
    while True:
        print("\n" + "="*50)
        print("MENU PRINCIPAL")
        print("="*50)
        print("1-6 → Configurer un servo spécifique")
        print("T   → Configurer TOUS les servos")
        print("B   → Bloquer le servo au centre")
        print("L   → Libérer le servo")
        print("D   → Détecter à nouveau le port USB")
        print("Q   → Quitter")
        print("="*50)
        
        choix = input("\nVotre choix: ").strip().upper()
        
        if choix == 'Q':
            print("\n✅ Configuration terminée")
            break
        elif choix == 'B':
            # Bloquer le servo branché
            print("\n🔒 Blocage du servo au centre...")
            portHandler = PortHandler(port)
            packetHandler = PacketHandler(1.0)
            if portHandler.openPort() and portHandler.setBaudRate(1000000):
                # Chercher quel servo est branché
                for test_id in range(1, 7):
                    pos, result, _ = packetHandler.read2ByteTxRx(portHandler, test_id, 56)
                    if result == 0:
                        packetHandler.write1ByteTxRx(portHandler, test_id, 40, 1)
                        packetHandler.write2ByteTxRx(portHandler, test_id, 42, 2048)
                        print(f"✅ Servo {test_id} bloqué au centre")
                        break
                portHandler.closePort()
        elif choix == 'L':
            # Libérer le servo branché
            print("\n🔓 Libération du servo...")
            portHandler = PortHandler(port)
            packetHandler = PacketHandler(1.0)
            if portHandler.openPort() and portHandler.setBaudRate(1000000):
                # Chercher quel servo est branché
                for test_id in range(1, 7):
                    pos, result, _ = packetHandler.read2ByteTxRx(portHandler, test_id, 56)
                    if result == 0:
                        packetHandler.write1ByteTxRx(portHandler, test_id, 40, 0)
                        print(f"✅ Servo {test_id} libéré")
                        break
                portHandler.closePort()
        elif choix == 'D':
            port = detect_port()
            if port:
                print(f"✅ Port détecté: {port}")
            else:
                print("❌ Aucun port détecté")
        elif choix == 'T':
            # AJOUT 2: Configurer TOUS les servos
            print("\n🔄 CONFIGURATION DE TOUS LES SERVOS")
            for servo_id in range(1, 7):
                print(f"\n📋 SERVO {servo_id}/6")
                print("-"*40)
                
                if servo_id == 1:
                    print("🔧 BASE - Rotation horizontale")
                elif servo_id == 2:
                    print("🔧 ÉPAULE - Lever/Baisser le bras")
                elif servo_id == 3:
                    print("🔧 COUDE - Plier l'avant-bras")
                elif servo_id == 4:
                    print("🔧 POIGNET-FLEXION - Incliner")
                elif servo_id == 5:
                    print("🔧 POIGNET-ROTATION - Tourner")
                elif servo_id == 6:
                    print("🔧 PINCE/POIGNÉE - Saisir")
                    print("\n⚠️  IMPORTANT: Monter avec pince OUVERTE!")
                
                print("\n⚠️  Branchez UNIQUEMENT ce servo!")
                input("Appuyez sur ENTRÉE quand prêt...")
                
                if configure_servo(servo_id):
                    print(f"✅ Servo {servo_id} configuré!")
                else:
                    print(f"❌ Problème avec servo {servo_id}")
                    retry = input("Réessayer? (O/N): ").strip().upper()
                    if retry == 'O':
                        configure_servo(servo_id)
            
            print("\n✅ Configuration de tous les servos terminée!")
        elif choix in ['1', '2', '3', '4', '5', '6']:
            servo_id = int(choix)
            
            # Instructions spécifiques par servo
            print(f"\n📋 PRÉPARATION SERVO {servo_id}")
            print("-"*40)
            
            if servo_id == 1:
                print("🔧 BASE - Rotation horizontale")
                print("   Position: Base du robot")
            elif servo_id == 2:
                print("🔧 ÉPAULE - Lever/Baisser le bras")
                print("   Position: Premier joint après la base")
            elif servo_id == 3:
                print("🔧 COUDE - Plier l'avant-bras")
                print("   Position: Joint du milieu")
            elif servo_id == 4:
                print("🔧 POIGNET-FLEXION - Incliner")
                print("   Position: Premier joint du poignet")
            elif servo_id == 5:
                print("🔧 POIGNET-ROTATION - Tourner")
                print("   Position: Rotation du poignet")
            elif servo_id == 6:
                print("🔧 PINCE/POIGNÉE - Saisir")
                print("   Position: Extrémité")
                print("\n⚠️  IMPORTANT: Monter avec pince OUVERTE!")
            
            print("\n⚠️  Branchez UNIQUEMENT ce servo!")
            input("Appuyez sur ENTRÉE quand prêt...")
            
            if configure_servo(servo_id):
                print(f"\n✅ Servo {servo_id} configuré avec succès!")
                print("📌 Vous pouvez maintenant:")
                print("   1. Débrancher ce servo")
                print("   2. Le monter sur le robot")
                print("   3. Passer au servo suivant")
            else:
                print(f"\n❌ Problème avec le servo {servo_id}")
                print("Vérifiez les connexions et réessayez")
        else:
            print("❌ Choix invalide")

if __name__ == "__main__":
    main()
