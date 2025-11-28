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
    
    # Commande pour configurer le servo
    cmd = [
        'python', 'lerobot/scripts/configure_motor.py',
        '--port', port,
        '--brand', 'feetech',
        '--model', 'sts3215',
        '--baudrate', '1000000',
        '--ID', str(servo_id)
    ]
    
    try:
        # Exécution de la commande
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Servo {servo_id} configuré avec succès")
            
            # Test de mouvement
            print("\n🔄 Test de mouvement...")
            from dynamixel_sdk import *
            
            portHandler = PortHandler(port)
            packetHandler = PacketHandler(1.0)
            
            if portHandler.openPort() and portHandler.setBaudRate(1000000):
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
                
                # Désactiver le servo
                packetHandler.write1ByteTxRx(portHandler, servo_id, 40, 0)
                portHandler.closePort()
                
                print("✅ Test terminé - Servo opérationnel")
            return True
        else:
            print(f"❌ Erreur lors de la configuration")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
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
        print("1 → Configurer Servo 1 (BASE)")
        print("2 → Configurer Servo 2 (ÉPAULE)")
        print("3 → Configurer Servo 3 (COUDE)")
        print("4 → Configurer Servo 4 (POIGNET-FLEXION)")
        print("5 → Configurer Servo 5 (POIGNET-ROTATION)")
        print("6 → Configurer Servo 6 (PINCE/POIGNÉE)")
        print("-"*50)
        print("D → Détecter à nouveau le port USB")
        print("Q → Quitter")
        print("="*50)
        
        choix = input("\nVotre choix: ").strip().upper()
        
        if choix == 'Q':
            print("\n✅ Configuration terminée")
            break
        elif choix == 'D':
            port = detect_port()
            if port:
                print(f"✅ Port détecté: {port}")
            else:
                print("❌ Aucun port détecté")
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