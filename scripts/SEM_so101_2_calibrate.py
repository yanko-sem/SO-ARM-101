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

def clear_screen():
    """Efface l'écran"""
    os.system('clear')

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

def afficher_comparaison_calibration(anciennes, nouvelles):
    """Tableau comparatif ancien → nouveau (MIN/CENTRE/MAX/Amplitude) par servo."""
    def _paire(av, nv, champ):
        a = str(av[champ]) if av else "—"
        n = str(nv[champ]) if nv else "—"
        return f"{a} → {n}"
    print("\n" + "="*84)
    print("COMPARAISON DE CALIBRATION  (ancien → nouveau)")
    print("="*84)
    print(f"{'ID':<4} {'Nom':<16} {'MIN':<14} {'CENTRE':<14} {'MAX':<14} {'Amplitude':<14}")
    print("-"*84)
    for i in range(1, 7):
        key = f"servo_{i}"
        av = anciennes.get(key)
        nv = nouvelles.get(key)
        print(f"{i:<4} {SERVO_NAMES[i]:<16} {_paire(av,nv,'min'):<14} {_paire(av,nv,'center'):<14} {_paire(av,nv,'max'):<14} {_paire(av,nv,'amplitude'):<14}")
    print("="*84)

def etat_calibration(robot_type):
    """État du fichier de calibration d'un bras : 'complet', 'incomplet' ou 'absent'."""
    cal = charger_calibration(robot_type)
    if not cal:
        return "absent"
    if all(f"servo_{i}" in cal for i in range(1, 7)):
        return "complet"
    return "incomplet"

# Libellés d'état affichés au menu principal (un par bras).
_LIBELLE_ETAT = {
    "complet": "✅ complet",
    "incomplet": "⚠️ incomplet",
    "absent": "⬜ non vérifié",
}

def afficher_etat_calibrations():
    """Affiche l'état courant des calibrations Follower et Leader."""
    ef = etat_calibration("FOLLOWER")
    el = etat_calibration("LEADER")
    print(f"État : Follower {_LIBELLE_ETAT[ef]}")
    print(f"       Leader   {_LIBELLE_ETAT[el]}")

def afficher_recap_final():
    """Récapitulatif final de l'état des deux fichiers de calibration."""
    print("\n" + "="*60)
    print("RÉCAPITULATIF FINAL DES CALIBRATIONS")
    print("="*60)
    for robot_type in ("FOLLOWER", "LEADER"):
        etat = etat_calibration(robot_type)
        presence = "absente" if etat == "absent" else "présente"
        completude = {"complet": "complète", "incomplet": "incomplète", "absent": "—"}[etat]
        print(f"  {robot_type.capitalize():<9}: {presence} · {completude}")
    print("="*60)

def connecter_robot(robot_type):
    """Détecte le port, demande la confirmation de rôle, ouvre la connexion.

    Le script ne pouvant PAS identifier physiquement quel bras est branché (les deux
    SO-ARM 101 sont identiques), une confirmation explicite de l'opérateur sert de
    garde-fou humain. Retourne (portHandler, packetHandler) en cas de succès, sinon
    (None, None).
    """
    PORT = detect_port()
    if not PORT:
        print("❌ Connexion au robot impossible.")
        print("\nVérifiez :")
        print("  1. Câble USB branché (un seul adaptateur à la fois)")
        print("  2. Alimentation connectée (5V ou 12V selon le bras)")
        print("  3. Interrupteur ON")
        return None, None

    print(f"✅ Port détecté: {PORT}")

    rep = input(f"\n⚠️  Confirmez-vous que le bras branché est bien le {robot_type} ? [O/N] : ").strip().upper()
    if rep != 'O':
        print("↩️  Calibration annulée — retour au menu principal.")
        return None, None

    BAUDRATE = 1000000
    portHandler = PortHandler(PORT)
    packetHandler = PacketHandler(1.0)

    if not portHandler.openPort():
        print("❌ Impossible d'ouvrir le port")
        return None, None
    if not portHandler.setBaudRate(BAUDRATE):
        print("❌ Impossible de configurer le baudrate")
        portHandler.closePort()
        return None, None

    print("✅ Connexion établie")
    return portHandler, packetHandler

def liberer_et_fermer(packetHandler, portHandler):
    """Libère les 6 servos (best-effort) puis ferme le port. Toujours sûr à appeler."""
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

def session_bras(robot_type):
    """Calibration d'un bras : connexion, menu servo, libération garantie.

    Retourne l'ensemble (set) des IDs de servos calibrés AU COURS DE CETTE SESSION.
    Le menu servo est inchangé, à une exception près : l'option de sortie est
    [R] Retour au menu principal (elle ne quitte plus le programme). La libération
    des 6 servos est garantie à la fin (bloc finally), AVANT tout débranchement.
    """
    portHandler, packetHandler = connecter_robot(robot_type)
    if portHandler is None:
        return set()

    servos_session = set()
    try:
        calibration = charger_calibration(robot_type)
        if calibration:
            print("📁 Calibration existante chargée")
            afficher_tableau_calibration(calibration)

        while True:
            print("\n" + "="*60)
            print(f"MENU SERVO — {robot_type}")
            print("="*60)
            print("1-6 → Calibrer un servo spécifique")
            print("  T → Calibrer TOUS les servos")
            print("  V → Voir calibration actuelle")
            print("  R → Retour au menu principal")
            print("="*60)

            choix = input("\nVotre choix: ").strip().upper()

            if choix == 'R':
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
                        print(f"❌ Servo {servo_id} : calibration annulée, rien n'est sauvegardé pour ce servo. Séquence interrompue.")
                        print("ℹ️ Les servos déjà validés avant cet échec restent sauvegardés.")
                        break

                    calibration[f"servo_{servo_id}"] = result
                    servos_session.add(servo_id)

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
                servos_session.add(servo_id)

                # SAUVEGARDE IMMÉDIATE
                sauvegarder_calibration(calibration, robot_type)
                print(f"💾 Calibration du servo {servo_id} sauvegardée!")
            else:
                print("❌ Choix invalide")
    finally:
        liberer_et_fermer(packetHandler, portHandler)

    return servos_session

def calibrer_bras_sequence(robot_type):
    """Calibration complète d'un bras (mode [1], sans menu) — écriture différée.

    Les 6 servos sont calibrés EN MÉMOIRE : le fichier de calibration n'est PAS
    modifié pendant la séquence. Après les 6, un tableau ancien → nouveau est
    affiché, puis :
      [O] valider  -> écriture du fichier, avertissement, relâchement
      [N] refaire  -> on recommence les 6 (fichier toujours intact)
      [A] abandon  -> fichier intact (ancienne calibration conservée)
    Toute interruption ou tout échec laisse l'ancienne calibration intacte.
    Retourne True si la calibration a été validée et écrite, False sinon.
    """
    portHandler, packetHandler = connecter_robot(robot_type)
    if portHandler is None:
        return False

    valide = False
    libere = False
    try:
        anciennes = charger_calibration(robot_type)

        # Valeurs actuellement enregistrées (AVANT)
        if anciennes:
            print("\n📋 Calibration actuellement enregistrée pour ce bras :")
            afficher_tableau_calibration(anciennes)
        else:
            print("\nℹ️  Aucune calibration enregistrée pour ce bras (première fois).")

        while True:
            nouvelles = dict(anciennes)  # copie de travail (fichier non touché)
            interrompu = False
            print("\n🔄 CALIBRATION DES 6 SERVOS (en mémoire, non enregistrée pour l'instant)")
            for servo_id in range(1, 7):
                result = calibrer_servo(packetHandler, portHandler,
                                      servo_id, SERVO_NAMES[servo_id])
                if result is None:
                    print(f"❌ Servo {servo_id} : calibration annulée. Séquence interrompue.")
                    print("ℹ️ Rien n'est enregistré : l'ancienne calibration est conservée.")
                    interrompu = True
                    break
                nouvelles[f"servo_{servo_id}"] = result
                print(f"✅ Servo {servo_id} mesuré (en mémoire).")

            if interrompu:
                break  # bras non finalisé ; fichier intact

            print("\n✅ MESURE DES 6 SERVOS TERMINÉE")
            afficher_comparaison_calibration(anciennes, nouvelles)

            while True:
                print("\n[O] Valider et enregistrer  |  [N] Recommencer les 6 servos  |  [A] Abandonner (conserver l'ancienne)")
                rep = input("Votre choix : ").strip().upper()
                if rep in ("O", "N", "A"):
                    break
                print("❌ Choix invalide : tapez O, N ou A.")

            if rep == 'O':
                sauvegarder_calibration(nouvelles, robot_type)
                print("💾 Calibration enregistrée.")
                valide = True
                break
            if rep == 'A':
                print("↩️  Abandon — l'ancienne calibration est conservée (aucune écriture).")
                break
            # rep == 'N'
            print("↩️  On recommence la calibration des 6 servos (fichier inchangé).")

        # Avertissement AVANT relâchement (anti-chute), puis relâchement
        print("\n" + "="*60)
        print("⚠️  Les servos vont être RELÂCHÉS : le bras ne tiendra plus seul.")
        print("    Tenez le bras ou posez-le en position sûre.")
        input("    Appuyez sur [ENTRÉE] pour relâcher les servos...")
        liberer_et_fermer(packetHandler, portHandler)
        libere = True
    finally:
        if not libere:
            liberer_et_fermer(packetHandler, portHandler)

    return valide

def flux_complet():
    """Calibration complète des deux bras : Follower puis Leader (écriture différée par bras, validée sur le tableau final). Follower bloquant ; Leader non finalisé = avertissement non fatal."""
    print("\n" + "="*60)
    print("ÉTAPE 1/2 — Calibration du FOLLOWER (obligatoire)")
    print("="*60)
    print("Le Follower est le bras enregistré dans le dataset et utilisé")
    print("au déploiement autonome. Cette calibration est OBLIGATOIRE.")
    input("\n➡️  Branchez UNIQUEMENT le Follower, puis appuyez sur [ENTRÉE]...")

    if not calibrer_bras_sequence("FOLLOWER"):
        print("\n↩️  Calibration du Follower non finalisée (abandon ou interruption).")
        print("   L'ancienne calibration, si elle existait, est conservée.")
        print("   Retour au menu principal.")
        return

    print("\n✅ Follower validé et enregistré.")

    print("\n" + "="*60)
    print("ÉTAPE 2/2 — Calibration du LEADER (obligatoire pour la calibration complète)")
    print("="*60)
    print("Le Leader n'est pas utilisé au déploiement autonome, mais il sert")
    print("à la téléopération et à l'enregistrement des démonstrations.")
    input("\n➡️  Débranchez le Follower. Branchez UNIQUEMENT le Leader. Puis [ENTRÉE]...")

    if not calibrer_bras_sequence("LEADER"):
        print("\n⚠️ Calibration du Leader non finalisée (abandon ou interruption).")
        print("   Le Follower (bras critique) reste validé et enregistré.")
        print("   Relancez [1] pour refaire la séquence complète, ou utilisez [2] pour terminer uniquement le Leader.")
        return

    print("\n✅ Leader validé et enregistré.")
    print("\n✅ Calibration complète Follower + Leader terminée.")

def flux_un_seul_bras():
    """Recalibration de maintenance d'un seul bras (granularité libre : 1 à 6 servos)."""
    print("\n🤖 Quel bras recalibrer ?")
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

    input(f"\n➡️  Branchez UNIQUEMENT le {robot_type}, puis appuyez sur [ENTRÉE]...")
    session_bras(robot_type)

def main():
    clear_screen()

    print("""
╔══════════════════════════════════════════════════════════╗
║     CALIBRATION SO-ARM 101                              ║
║     Service Ecoles Médias                               ║
╚══════════════════════════════════════════════════════════╝

Ce script calibre les limites de mouvement de chaque servo.
Mode [1] (complet) : les valeurs sont enregistrées après validation du tableau final.
Mode [2] (ciblé)   : chaque servo validé est sauvegardé immédiatement.

Parcours recommandé : Follower d'abord (obligatoire), Leader ensuite.
Un seul bras branché à la fois.
""")

    while True:
        print("\n" + "="*60)
        print("MENU PRINCIPAL")
        print("="*60)
        afficher_etat_calibrations()
        print("-"*60)
        print("  [1] Calibration complète (Follower puis Leader) — recommandé")
        print("  [2] Recalibrer un seul bras (Follower OU Leader)")
        print("  [Q] Quitter")
        print("="*60)

        choix = input("\nVotre choix: ").strip().upper()

        if choix == 'Q':
            break
        elif choix == '1':
            flux_complet()
        elif choix == '2':
            flux_un_seul_bras()
        else:
            print("❌ Choix invalide")

    afficher_recap_final()
    print("\n✅ Script de calibration terminé")

if __name__ == "__main__":
    main()
