#!/usr/bin/env python3
"""
Script SEM_so101_1_configure.py
Service Ecoles Médias - Configuration des servos SO-ARM 101

Ce script attribue à chaque servo son ID, teste son mouvement, puis le place
au centre (2048) et le bloque pour le montage.

Il rappelle les ratios mécaniques du Leader et du Follower (aide au montage),
mais ne les modifie pas : le ratio dépend du modèle physique du servo.
"""

import sys
import os
import time

# Ajout du chemin LeRobot pour les imports
sys.path.append(os.path.expanduser('~/lerobot'))

from dynamixel_sdk import *

def detect_port():
    """Détection automatique du port USB"""
    ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']
    for port in ports:
        if os.path.exists(port):
            return port
    return None

def configure_servo(servo_id):
    """Configure directement un servo Feetech STS3215 via dynamixel_sdk."""
    port = detect_port()
    if not port:
        print("❌ Aucun port USB détecté!")
        return False

    print(f"\n{'='*50}")
    print(f"Configuration du Servo {servo_id}")
    print(f"Port: {port}")
    print(f"{'='*50}")

    # Configuration directe via dynamixel_sdk
    # (l'outil officiel équivalent est lerobot/scripts/configure_motor.py).
    portHandler = None
    try:
        portHandler = PortHandler(port)
        packetHandler = PacketHandler(1.0)

        if not portHandler.openPort():
            print("❌ Impossible d'ouvrir le port")
            return False

        if not portHandler.setBaudRate(1000000):
            print("❌ Impossible de configurer le baudrate")
            portHandler.closePort()
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
            print("  - L'alimentation est connectée (5V ou 12V selon le bras)")
            portHandler.closePort()
            return False

        # 2. CHANGEMENT D'ID si nécessaire
        if id_actuel != servo_id:
            print(f"\n📝 Configuration de l'ID...")
            print(f"  ID actuel: {id_actuel}")
            print(f"  Nouvel ID: {servo_id}")

            # Feetech STS3215 : l'ID est au registre 5 et l'EEPROM est verrouillée.
            # Il faut déverrouiller (registre LOCK 55 = 0), écrire l'ID, puis reverrouiller (= 1).
            packetHandler.write1ByteTxRx(portHandler, id_actuel, 55, 0)        # déverrouille l'EEPROM
            time.sleep(0.05)
            packetHandler.write1ByteTxRx(portHandler, id_actuel, 5, servo_id)  # écrit le nouvel ID (registre 5)
            time.sleep(0.2)
            packetHandler.write1ByteTxRx(portHandler, servo_id, 55, 1)         # reverrouille l'EEPROM (au nouvel ID)
            time.sleep(0.05)

            # Vérifier que le servo répond bien au nouvel ID (seul test fiable)
            pos, result, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
            if result == 0:
                print(f"  ✅ ID changé : le servo répond maintenant à l'ID {servo_id}")
            else:
                print("  ❌ L'ID n'a pas changé (le servo ne répond pas au nouvel ID)")
                # Sécurité EEPROM : reverrouiller, que le servo soit resté à l'ancien
                # ID ou passé au nouveau (l'autre tentative est un no-op inoffensif).
                for relock_id in (servo_id, id_actuel):
                    try:
                        packetHandler.write1ByteTxRx(portHandler, relock_id, 55, 1)
                    except Exception:
                        pass
                print("  Débranchez/rebranchez le servo et réessayez")
                portHandler.closePort()
                return False
        else:
            print(f"✅ Le servo a déjà l'ID {servo_id}")

        # 3. VÉRIFICATION de la configuration
        print("\n📋 Vérification de la configuration...")

        # Lire l'ID pour confirmer (registre 5, table Feetech)
        id_lu, result, _ = packetHandler.read1ByteTxRx(portHandler, servo_id, 5)
        if result == 0 and id_lu == servo_id:
            print(f"  ✅ ID: {id_lu} [SAUVEGARDÉ]")
        else:
            print("  ❌ Problème avec l'ID")
            portHandler.closePort()
            return False

        # Lire le baudrate (registre 6, table Feetech)
        baud_reg, result, _ = packetHandler.read1ByteTxRx(portHandler, servo_id, 6)
        if result == 0:
            print(f"  ℹ️ Baudrate registre: {baud_reg} (0 = 1Mbps)")
        else:
            print("  ⚠️ Baudrate non relu correctement")

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
        if portHandler is not None:
            try:
                portHandler.closePort()
            except Exception:
                pass
        return False

def main():
    # Effacer l'écran au début
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
            if portHandler.openPort():
                if portHandler.setBaudRate(1000000):
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
            if portHandler.openPort():
                if portHandler.setBaudRate(1000000):
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
            # Configurer TOUS les servos
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
