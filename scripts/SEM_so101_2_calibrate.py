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
    """Détection du port du robot (fail-closed).

    On TESTE chaque port candidat en interrogeant le servo 1 : seul un vrai robot
    répond. On collecte TOUS les ports qui répondent. S'il y en a exactement un, on
    le retourne. S'il y en a plusieurs (Leader ET Follower branchés, par ex.), on
    REFUSE et on demande de n'en garder qu'un — sinon on risquerait de piloter le
    mauvais bras avant même le choix L/F.
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
        print("   Débranchez tous les adaptateurs sauf celui du bras à utiliser.")
    return None

# Noms des servos (source unique, partagee par la calibration et le tableau)
SERVO_NAMES = {
    1: "BASE",
    2: "ÉPAULE",
    3: "COUDE",
    4: "POIGNET-FLEXION",
    5: "POIGNET-ROTATION",
    6: "PINCE/POIGNÉE",
}

# Amplitude minimale acceptee (ticks). En dessous, la calibration est consideree
# invalide (MIN/MAX trop proches -> calibration mecaniquement fausse et division
# par zero possible en aval lors de la conversion ticks -> %). Seuil coherent
# avec le depannage du guide Phase 3 (amplitude < 500 = probleme).
MIN_AMPLITUDE = 500

# ----------------------------------------------------------------------------
# Politique de gestion des erreurs (calibration) :
# Certains servos Feetech peuvent renvoyer un statut interne non nul (error)
# tout en conservant une position parfaitement lisible. En calibration, seul
# l'echec de communication (result != COMM_SUCCESS) bloque ; le statut interne
# est affiche en avertissement, sans interrompre la calibration. La cause du
# statut reste a identifier sur la table de controle Feetech STS3215 (hors
# urgence). NB : regle LOCALE a la calibration, NON generalisee aux scripts
# de mouvement (teleoperation, enregistrement, deploiement).
# ----------------------------------------------------------------------------
def ecrire_1byte(packetHandler, portHandler, servo_id, registre, valeur, action):
    """Ecriture 1 octet. Bloque uniquement sur une vraie panne de communication.

    result != COMM_SUCCESS -> echec de communication (bloquant).
    error  != 0            -> statut interne non nul renvoye par le servo :
                              commande transmise, cause NON identifiee. Non
                              bloquant, signale pour surveillance.
    """
    result, error = packetHandler.write1ByteTxRx(portHandler, servo_id, registre, valeur)
    if result != COMM_SUCCESS:
        print(f"  ❌ Échec communication ({action}, servo {servo_id})")
        return False
    if error != 0:
        print(f"  ⚠️ Servo {servo_id} : statut interne non nul ({action}, code {error}) — à surveiller, non bloquant")
    return True

def lire_position(packetHandler, portHandler, servo_id):
    """Lecture de la position (registre 56). Retourne (position, ok).

    Seule une vraie panne de communication (result) invalide la lecture.
    Un statut interne non nul (error) est signale mais la position est
    conservee : la cause n'est PAS presumee ici, elle reste a identifier.
    """
    pos, result, error = packetHandler.read2ByteTxRx(portHandler, servo_id, 56)
    if result != COMM_SUCCESS:
        return None, False
    if error != 0:
        print(f"  ⚠️ Servo {servo_id} : statut interne non nul (code {error}) — position conservée, à identifier")
    return pos, True

def centrage_doux(packetHandler, portHandler, servo_id, pos_min, pos_max):
    """Centre le servo avec un mouvement fluide.

    Retourne True si la commande finale vers le centre a ete acquittee, False sinon.
    """
    centre = (pos_min + pos_max) // 2
    pos_actuelle, ok = lire_position(packetHandler, portHandler, servo_id)
    if not ok:
        # Position de depart inconnue : on commande directement le centre (sans rampe)
        print("  ⚠️ Position de départ illisible — recentrage direct vers le centre")
        result, error = packetHandler.write2ByteTxRx(portHandler, servo_id, 42, centre)
        return result == COMM_SUCCESS and error == 0

    print(f"  🔄 Centrage fluide vers {centre}...")

    # Mouvement sinusoïdal pour la fluidité
    steps = 50
    final_ok = True
    for step in range(steps + 1):
        t = step / steps
        # Courbe sinusoïdale
        smooth_t = (1 - math.cos(t * math.pi)) / 2
        pos = int(pos_actuelle + (centre - pos_actuelle) * smooth_t)
        result, error = packetHandler.write2ByteTxRx(portHandler, servo_id, 42, pos)
        if step == steps:  # on verifie au moins la commande finale (sur le centre)
            final_ok = (result == COMM_SUCCESS and error == 0)
        time.sleep(1.5 / steps)  # 1.5 secondes au total

    return final_ok

def calibrer_servo(packetHandler, portHandler, servo_id, servo_name):
    """Calibre un servo individuellement.

    Retourne le dict de calibration, ou None si une operation critique echoue
    (lecture de position ou desactivation du couple) -> dans ce cas, RIEN ne doit
    etre sauvegarde par l'appelant.
    """
    print(f"\n{'='*60}")
    print(f"CALIBRATION DU SERVO {servo_id} - {servo_name}")
    print(f"{'='*60}")

    # Activer le servo (couple)
    activation_ok = ecrire_1byte(packetHandler, portHandler, servo_id, 40, 1, "activation couple")

    # Lire position actuelle (verifiee)
    pos_actuelle, ok = lire_position(packetHandler, portHandler, servo_id)
    if not ok:
        print("  ❌ Lecture de la position impossible — calibration annulée")
        if activation_ok:
            ecrire_1byte(packetHandler, portHandler, servo_id, 40, 0, "libération couple")
        return None
    print(f"Position actuelle: {pos_actuelle}")

    # Relacher pour manipulation manuelle — VERIFIE : ne jamais annoncer "LIBRE"
    # si le couple n'a pas reellement ete coupe (risque mecanique).
    if not ecrire_1byte(packetHandler, portHandler, servo_id, 40, 0, "libération couple"):
        print("  ❌ Le couple n'a PAS pu être désactivé — NE manipulez PAS le servo. Calibration annulée")
        return None

    print("\n⚠️  Le servo est maintenant LIBRE")

    print("\n📋 Instructions:")
    print("1. Bougez MANUELLEMENT le servo à sa position MINIMALE")
    print("2. Maintenez la position et appuyez sur ENTRÉE")
    input("\n➡️  Position MIN prête? [ENTRÉE]")

    # Lire position MIN (verifiee)
    pos_min, ok = lire_position(packetHandler, portHandler, servo_id)
    if not ok:
        print("  ❌ Lecture de la position MIN impossible — calibration annulée")
        ecrire_1byte(packetHandler, portHandler, servo_id, 40, 0, "libération couple")
        return None
    print(f"✅ Position MIN enregistrée: {pos_min}")

    print("\n3. Bougez MANUELLEMENT le servo à sa position MAXIMALE")
    print("4. Maintenez la position et appuyez sur ENTRÉE")
    input("\n➡️  Position MAX prête? [ENTRÉE]")

    # Lire position MAX (verifiee)
    pos_max, ok = lire_position(packetHandler, portHandler, servo_id)
    if not ok:
        print("  ❌ Lecture de la position MAX impossible — calibration annulée")
        ecrire_1byte(packetHandler, portHandler, servo_id, 40, 0, "libération couple")
        return None
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

    # Refus d'une amplitude invalide (MIN/MAX trop proches) : ne rien sauvegarder.
    if amplitude < MIN_AMPLITUDE:
        print(f"  ❌ Amplitude trop faible ({amplitude} < {MIN_AMPLITUDE}) — calibration annulée")
        print("  Recommencez en définissant des limites MIN/MAX réellement distinctes et sûres.")
        ecrire_1byte(packetHandler, portHandler, servo_id, 40, 0, "libération couple")
        return None

    # Réactiver le couple pour le recentrage. Si l'activation echoue, on NE jette PAS
    # la calibration (MIN/MAX sont valides) : on saute le recentrage en avertissant.
    # Fail-closed : le servo n'est MAINTENU bloqué au centre que si le recentrage est
    # CONFIRMÉ (facilite la suite). Sinon il est libéré — jamais bloqué dans une pose
    # non maîtrisée, jamais d'annonce "au centre" trompeuse. Libération de tous les
    # servos garantie à la sortie (bloc finally).
    if ecrire_1byte(packetHandler, portHandler, servo_id, 40, 1, "activation couple"):
        if centrage_doux(packetHandler, portHandler, servo_id, pos_min, pos_max):
            print(f"🔒 Servo {servo_id} centré et maintenu bloqué (facilite la suite)")
        else:
            print(f"⚠️ Servo {servo_id} : recentrage non confirmé — servo libéré")
            ecrire_1byte(packetHandler, portHandler, servo_id, 40, 0, "libération couple")
    else:
        print(f"⚠️ Servo {servo_id} : couple non réactivé, recentrage ignoré (calibration conservée)")

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

    # Sauvegarder (ecriture atomique : .tmp puis remplacement, evite un fichier corrompu si interruption)
    tmp_filename = filename + ".tmp"
    with open(tmp_filename, 'w') as f:
        json.dump(calibration, f, indent=2)
    os.replace(tmp_filename, filename)

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
    print(f"{'ID':<4} {'Nom':<16} {'MIN':<8} {'CENTRE':<8} {'MAX':<8} {'Amplitude':<10}")
    print("-"*80)

    for i in range(1, 7):
        key = f"servo_{i}"
        if key in calibration:
            cal = calibration[key]
            print(f"{i:<4} {SERVO_NAMES[i]:<16} {cal['min']:<8} {cal['center']:<8} {cal['max']:<8} {cal['amplitude']:<10}")
        else:
            print(f"{i:<4} {SERVO_NAMES[i]:<16} {'---':<8} {'---':<8} {'---':<8} {'---':<10}")

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
        print("❌ Connexion au robot impossible.")
        print("\nVérifiez :")
        print("  1. Câble USB branché (un seul adaptateur à la fois)")
        print("  2. Alimentation connectée (5V ou 12V selon le bras)")
        print("  3. Interrupteur ON")
        return

    print(f"✅ Port détecté: {PORT}")

    # Choix du robot - UN SEUL ! (choix explicite : pas de defaut silencieux vers Leader)
    print("\n🤖 Quel robot calibrer ?")
    print("  [L] LEADER")
    print("  [F] FOLLOWER")

    robot_type = None
    while robot_type is None:
        choix_robot = input("\nVotre choix [L/F] : ").strip().upper()
        if choix_robot == 'L':
            robot_type = "LEADER"
        elif choix_robot == 'F':
            robot_type = "FOLLOWER"
        else:
            print("❌ Choix invalide : tapez L ou F")

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
        portHandler.closePort()
        return

    print("✅ Connexion établie")

    try:
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
                                          servo_id, SERVO_NAMES[servo_id])
                    if result is None:
                        print(f"❌ Servo {servo_id} : calibration annulée, rien n'est sauvegardé. Séquence interrompue.")
                        break

                    calibration[f"servo_{servo_id}"] = result

                    # SAUVEGARDE APRÈS CHAQUE SERVO
                    sauvegarder_calibration(calibration, robot_type)
                    print(f"💾 Servo {servo_id} sauvegardé!")
                else:
                    print("\n✅ CALIBRATION COMPLÈTE TERMINÉE")

                afficher_tableau_calibration(calibration)

            elif choix in ['1', '2', '3', '4', '5', '6']:
                servo_id = int(choix)
                result = calibrer_servo(packetHandler, portHandler,
                                      servo_id, SERVO_NAMES[servo_id])
                if result is None:
                    print("❌ Calibration annulée : rien n'est sauvegardé")
                    continue

                calibration[f"servo_{servo_id}"] = result

                # SAUVEGARDE IMMÉDIATE
                sauvegarder_calibration(calibration, robot_type)
                print(f"💾 Calibration du servo {servo_id} sauvegardée!")
            else:
                print("❌ Choix invalide")
    finally:
        # Liberation finale GARANTIE (meme en cas d'exception ou d'interruption).
        # Chaque ecriture est best-effort pour garantir que closePort() soit toujours atteint.
        print("\n🏁 Libération des servos...")
        for i in range(1, 7):
            try:
                packetHandler.write1ByteTxRx(portHandler, i, 40, 0)
            except Exception:
                pass
        try:
            portHandler.closePort()
        except Exception:
            pass
        print("\n✅ Calibration terminée")
        print(f"📁 Fichier: ~/lerobot/calibration/{robot_type.lower()}_calibration.json")

if __name__ == "__main__":
    main()
