#!/usr/bin/env python3
"""
Script SEM_so101_2_calibrate.py
Service Ecoles Médias - Calibration des servos SO-ARM 101

Ce script permet de calibrer les limites min/max de chaque servo
et sauvegarde automatiquement après chaque calibration.
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

def detect_port():
    """Détection automatique du port USB"""
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']:
        if os.path.exists(port):
            return port
    return None

def centrage_doux(packetHandler, portHandler, servo_id, pos_min, pos_max):
    """Centre le servo avec un mouvement fluide"""
    centre = (pos_min + pos_max) // 2
    pos_actuelle, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)

    print(f"  🔄 Centrage fluide vers {centre}...")

    # Mouvement sinusoïdal pour la fluidité
    steps = 50
    for step in range(steps + 1):
        t = step / steps
        # Courbe sinusoïdale
        smooth_t = (1 - math.cos(t * math.pi)) / 2
        pos = int(pos_actuelle + (centre - pos_actuelle) * smooth_t)
        packetHandler.write2ByteTxRx(portHandler, servo_id, 42, pos)
        time.sleep(1.5 / steps)  # 1.5 secondes au total

    return centre

def calibrer_servo(packetHandler, portHandler, servo_id, servo_name):
    """Calibre un servo individuellement"""
    print(f"\n{'='*60}")
    print(f"CALIBRATION DU SERVO {servo_id} - {servo_name}")
    print(f"{'='*60}")

    # Activer le servo
    packetHandler.write1ByteTxRx(portHandler, servo_id, 40, 1)

    # Lire position actuelle
    pos_actuelle, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
    print(f"Position actuelle: {pos_actuelle}")

    # Relâcher pour manipulation manuelle
    print("\n⚠️  Le servo est maintenant LIBRE")
    packetHandler.write1ByteTxRx(portHandler, servo_id, 40, 0)

    print("\n📋 Instructions:")
    print("1. Bougez MANUELLEMENT le servo à sa position MINIMALE")
    print("2. Maintenez la position et appuyez sur ENTRÉE")
    input("\n➡️  Position MIN prête? [ENTRÉE]")

    # Lire position MIN
    pos_min, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
    print(f"✅ Position MIN enregistrée: {pos_min}")

    print("\n3. Bougez MANUELLEMENT le servo à sa position MAXIMALE")
    print("4. Maintenez la position et appuyez sur ENTRÉE")
    input("\n➡️  Position MAX prête? [ENTRÉE]")

    # Lire position MAX
    pos_max, _, _ = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
    print(f"✅ Position MAX enregistrée: {pos_max}")

    # Vérification cohérence
    if pos_max <= pos_min:
        print("⚠️  ATTENTION: MAX <= MIN, inversion automatique")
        pos_min, pos_max = pos_max, pos_min

    # Calcul du centre et amplitude
    centre = (pos_min + pos_max) // 2
    amplitude = pos_max - pos_min

    print(f"\n📊 Résumé calibration:")
    print(f"  • MIN: {pos_min}")
    print(f"  • MAX: {pos_max}")
    print(f"  • CENTRE: {centre}")
    print(f"  • Amplitude: {amplitude}")

    # Réactiver et centrer avec mouvement fluide
    packetHandler.write1ByteTxRx(portHandler, servo_id, 40, 1)
    centrage_doux(packetHandler, portHandler, servo_id, pos_min, pos_max)

    print(f"✅ Servo {servo_id} centré")

    # Désactiver le servo
    packetHandler.write1ByteTxRx(portHandler, servo_id, 40, 0)

    return {
        "min": pos_min,
        "max": pos_max,
        "center": centre,
        "amplitude": amplitude
    }

def sauvegarder_calibration(calibration, robot_type):
    """Sauvegarde la calibration dans un fichier JSON"""
    # Créer le dossier si nécessaire (nouveau chemin)
    calib_dir = os.path.expanduser("~/lerobot/calibration")
    os.makedirs(calib_dir, exist_ok=True)

    # Nom du fichier selon le robot
    filename = f"{calib_dir}/{robot_type.lower()}_calibration.json"

    # Sauvegarder
    with open(filename, 'w') as f:
        json.dump(calibration, f, indent=2)

    print(f"\n💾 Calibration sauvegardée: {filename}")

def charger_calibration(robot_type):
    """Charge une calibration existante"""
    filename = os.path.expanduser(f"~/lerobot/calibration/{robot_type.lower()}_calibration.json")

    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def afficher_tableau_calibration(calibration):
    """Affiche un tableau récapitulatif de la calibration"""
    print("\n" + "="*80)
    print("TABLEAU RÉCAPITULATIF DE CALIBRATION")
    print("="*80)
    print(f"{'ID':<4} {'Nom':<15} {'MIN':<8} {'CENTRE':<8} {'MAX':<8} {'Amplitude':<10}")
    print("-"*80)

    servo_names = {
        1: "BASE",
        2: "ÉPAULE",
        3: "COUDE",
        4: "POIGNET-F",
        5: "POIGNET-R",
        6: "PINCE/POIGNÉE"
    }

    for i in range(1, 7):
        key = f"servo_{i}"
        if key in calibration:
            cal = calibration[key]
            print(f"{i:<4} {servo_names[i]:<15} {cal['min']:<8} {cal['center']:<8} {cal['max']:<8} {cal['amplitude']:<10}")
        else:
            print(f"{i:<4} {servo_names[i]:<15} {'---':<8} {'---':<8} {'---':<8} {'---':<10}")

    print("="*80)

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║     CALIBRATION SO-ARM 101                              ║
║     Service Ecoles Médias                               ║
╚══════════════════════════════════════════════════════════╝

Ce script calibre les limites de mouvement de chaque servo.
IMPORTANT: La calibration est SAUVEGARDÉE après chaque servo!
""")

    # Détection du port
    PORT = detect_port()
    if not PORT:
        print("❌ Aucun adaptateur USB détecté!")
        print("\nVérifiez :")
        print("  1. Câble USB branché")
        print("  2. Alimentation 12V connectée")
        print("  3. Interrupteur ON")
        return

    print(f"✅ Port détecté: {PORT}")

    # Choix du robot - UN SEUL !
    print("\n🤖 Quel robot calibrer ?")
    print("  [L] LEADER")
    print("  [F] FOLLOWER")

    choix_robot = input("\nVotre choix : ").strip().upper()

    if choix_robot == 'F':
        robot_type = "FOLLOWER"
    else:
        robot_type = "LEADER"  # Par défaut

    print(f"\n✅ Calibration du {robot_type}")

    # Charger calibration existante si disponible
    calibration = charger_calibration(robot_type)
    if calibration:
        print("📁 Calibration existante chargée")
        afficher_tableau_calibration(calibration)

    # Connexion - UN SEUL PORT !
    BAUDRATE = 1000000
    portHandler = PortHandler(PORT)
    packetHandler = PacketHandler(1.0)

    if not portHandler.openPort():
        print("❌ Impossible d'ouvrir le port")
        return

    if not portHandler.setBaudRate(BAUDRATE):
        print("❌ Impossible de configurer le baudrate")
        return

    print("✅ Connexion établie")

    servo_names = {
        1: "BASE",
        2: "ÉPAULE",
        3: "COUDE",
        4: "POIGNET-FLEXION",
        5: "POIGNET-ROTATION",
        6: "PINCE" if robot_type == "FOLLOWER" else "POIGNÉE"
    }

    while True:
        print("\n" + "="*60)
        print("MENU PRINCIPAL")
        print("="*60)
        print("1-6 → Calibrer un servo spécifique")
        print("  T → Calibrer TOUS les servos")
        print("  V → Voir calibration actuelle")
        print("  Q → Quitter")
        print("="*60)

        choix = input("\nVotre choix: ").strip().upper()

        if choix == 'Q':
            break
        elif choix == 'V':
            afficher_tableau_calibration(calibration)
        elif choix == 'T':
            # Calibrer tous les servos
            print("\n🔄 CALIBRATION COMPLÈTE")
            for servo_id in range(1, 7):
                result = calibrer_servo(packetHandler, portHandler,
                                      servo_id, servo_names[servo_id])
                calibration[f"servo_{servo_id}"] = result

                # SAUVEGARDE APRÈS CHAQUE SERVO
                sauvegarder_calibration(calibration, robot_type)
                print(f"💾 Servo {servo_id} sauvegardé!")

            print("\n✅ CALIBRATION COMPLÈTE TERMINÉE")
            afficher_tableau_calibration(calibration)

        elif choix in ['1', '2', '3', '4', '5', '6']:
            servo_id = int(choix)
            result = calibrer_servo(packetHandler, portHandler,
                                  servo_id, servo_names[servo_id])
            calibration[f"servo_{servo_id}"] = result

            # SAUVEGARDE IMMÉDIATE
            sauvegarder_calibration(calibration, robot_type)
            print(f"💾 Calibration du servo {servo_id} sauvegardée!")
        else:
            print("❌ Choix invalide")

    # Libération finale
    print("\n🏁 Libération des servos...")
    for i in range(1, 7):
        packetHandler.write1ByteTxRx(portHandler, i, 40, 0)

    portHandler.closePort()
    print("\n✅ Calibration terminée")
    print(f"📁 Fichier: ~/lerobot/calibration/{robot_type.lower()}_calibration.json")

if __name__ == "__main__":
    main()
