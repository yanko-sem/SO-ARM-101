#!/usr/bin/env python3
"""
Script SEM_so101_5_config_teleoperation.py
Configuration des modes COPIE/MIROIR pour chaque servo
Avec test fluide de connexion et centrage parallele
"""
import sys, os, time, json, math, select

# Auto-activation de l'environnement lerobot si necessaire
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

# Noms des servos (source unique)
SERVO_NAMES = {1: "BASE", 2: "ÉPAULE", 3: "COUDE",
               4: "POIGNET-F", 5: "POIGNET-R", 6: "PINCE"}

# Amplitude minimale exigee d'une calibration pour etre exploitable (meme seuil que scripts 2/3/4)
MIN_AMPLITUDE = 500

# Fichier externe centralisant la position repos (partage entre tous les scripts)
REPOS_FILE = os.path.expanduser("~/lerobot/calibration/repos_position.json")

def clear_screen():
    os.system('clear')

def detect_ports():
    """Détecte les ports des robots (liste).

    Teste chaque port candidat en interrogeant le servo 1 : ne garde que les
    ports qui répondent au protocole servo (= robots). Les autres périphériques
    série (téléphone en charge, etc.) sont ignorés. Le robot doit être alimenté.
    Ici on RETOURNE une liste (la téléopération a besoin des deux robots) ;
    l'identification guidée s'appuie sur le nombre exact de ports attendus.
    """
    BAUDRATE = 1000000
    ports = []
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']:
        if not os.path.exists(port):
            continue
        ph = PortHandler(port)
        pk = PacketHandler(1.0)
        try:
            if ph.openPort() and ph.setBaudRate(BAUDRATE):
                _, result, _ = pk.read2ByteTxRx(ph, 1, 56)
                if result == COMM_SUCCESS:
                    ports.append(port)
        except Exception:
            # Périphérique série qui se comporte mal : on l'ignore proprement
            pass
        finally:
            try:
                ph.closePort()
            except Exception:
                pass
    return ports

# ----------------------------------------------------------------------------
# Politique de gestion des erreurs (lecture de position) :
# Certains servos Feetech peuvent renvoyer un octet de statut interne non nul
# tout en conservant une position parfaitement lisible. Seul l'echec de
# communication (result != COMM_SUCCESS) invalide la lecture ; l'octet de
# statut interne est ignore (tolere silencieusement, contexte teleoperation).
# Cause a identifier sur la table de controle Feetech STS3215 (hors urgence).
# Regle limitee aux LECTURES ; ecritures/mouvements traites au cas par cas.
# ----------------------------------------------------------------------------
def lire_position(packet, port, servo_id):
    """Lecture de la position (registre 56). Retourne (position, ok).

    Seule une vraie panne de communication (result) invalide la lecture.
    L'octet de statut interne du servo est ignore (tolere silencieusement,
    contexte teleoperation) : la position reste valide ; la cause de ce
    statut n'est PAS presumee ici, elle reste a identifier.
    """
    pos, result, _ = packet.read2ByteTxRx(port, servo_id, 56)
    if result != COMM_SUCCESS:
        return None, False
    return pos, True

def cleanup_ports(lp=None, fp=None, lk=None, fk=None, release=True):
    """Nettoyage best-effort, idempotent et tolérant aux initialisations partielles.
    Libère les servos (si les handlers existent) puis ferme les ports ouverts.
    Ne lève jamais d'exception (appelable dans un finally ou avant un retour d'échec)."""
    if release:
        for pk, ph in ((lk, lp), (fk, fp)):
            if pk is not None and ph is not None:
                for i in range(1, 7):
                    try:
                        pk.write1ByteTxRx(ph, i, 40, 0)
                    except Exception:
                        pass
    for ph in (lp, fp):
        if ph is not None:
            try:
                ph.closePort()
            except Exception:
                pass

def charger_calibration(robot_type):
    """Charge la calibration d'un robot (ou None si absente)."""
    calib_file = os.path.expanduser(f"~/lerobot/calibration/{robot_type}_calibration.json")
    if os.path.exists(calib_file):
        try:
            with open(calib_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    return None

def calibration_complete(calibration):
    """Vrai uniquement si les 6 servos sont calibres avec une plage exploitable
    (presents, min/max/center numeriques, amplitude >= MIN_AMPLITUDE, min<=center<=max).
    Meme exigence que le script 4. En telleoperation, sans calibration valide le
    mapping retomberait sur 0-4095 -> risque de butees sur le Follower piloté."""
    if not calibration:
        return False
    for i in range(1, 7):
        key = f"servo_{i}"
        if key not in calibration:
            return False
        cal = calibration[key]
        min_v = cal.get("min")
        max_v = cal.get("max")
        center_v = cal.get("center")
        if not isinstance(min_v, (int, float)) or not isinstance(max_v, (int, float)):
            return False
        if max_v - min_v < MIN_AMPLITUDE:
            return False
        if not isinstance(center_v, (int, float)):
            return False
        if not (min_v <= center_v <= max_v):
            return False
    return True

def charger_repos_pct():
    """Charge la position repos (% par servo) depuis le fichier externe.
    Retourne (dict {1:%,...}, origine) ou origine vaut 'custom' ou 'default'.
    Valide le contenu (6 servos, numeriques, [0,100]) ; le fallback par defaut
    est ANNONCE par l'appelant (jamais silencieux)."""
    defaut = {1: 50, 2: 10, 3: 88, 4: 76, 5: 50, 6: 11}
    if not os.path.exists(REPOS_FILE):
        return defaut, "default"
    try:
        with open(REPOS_FILE, 'r') as f:
            data = json.load(f)
        repos = {int(k): float(v) for k, v in data.items()}
        for i in range(1, 7):
            if i not in repos or not (0.0 <= repos[i] <= 100.0):
                return defaut, "default"
        return repos, "custom"
    except Exception:
        return defaut, "default"

def valider_servos_miroir(data):
    """Valide une valeur 'servos_miroir' : liste d'entiers 1-6, sans doublon.
    Retourne la liste triee, ou None si invalide. Une liste vide est VALIDE
    (configuration tout-COPIE)."""
    if not isinstance(data, list):
        return None
    vus = set()
    for v in data:
        # bool est un sous-type de int : on l'exclut explicitement
        if isinstance(v, bool) or not isinstance(v, int):
            return None
        if v < 1 or v > 6 or v in vus:
            return None
        vus.add(v)
    return sorted(vus)

def charger_servos_miroir_fichier(path):
    """Lit un fichier de config telleop et renvoie la liste servos_miroir validee,
    ou None si le fichier est illisible / mal forme / invalide."""
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict) or 'servos_miroir' not in data:
        return None
    return valider_servos_miroir(data['servos_miroir'])

def _cible_ticks(calib, servo_id, pct):
    """Convertit un pourcentage en ticks (calibration garantie valide au demarrage)."""
    min_val = calib[f'servo_{servo_id}']['min']
    max_val = calib[f'servo_{servo_id}']['max']
    return int(min_val + (max_val - min_val) * pct / 100)

def _est_en_repos_1robot(packet, port, calib, repos_pct, tolerance_pct=5):
    """True si le robot est proche de la position repos (tous les servos).
    False si au moins un servo en est eloigne. None si une lecture echoue
    (etat indetermine -> l'appelant doit annuler la sequence)."""
    for i in range(1, 7):
        pos, ok = lire_position(packet, port, i)
        if not ok:
            return None
        min_val = calib[f'servo_{i}']['min']
        max_val = calib[f'servo_{i}']['max']
        pct_actuel = (pos - min_val) / (max_val - min_val) * 100 if max_val > min_val else 50
        if abs(pct_actuel - repos_pct.get(i, 50)) > tolerance_pct:
            return False
    return True

def mouvement_fluide(packet, port, servo, debut, fin, duree=1.5):
    """Mouvement fluide entre deux positions (interpolation cosinus)."""
    steps = int(duree * 50)
    for i in range(steps + 1):
        t = i / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        pos = int(debut + (fin - debut) * smooth)
        packet.write2ByteTxRx(port, servo, 42, pos)
        time.sleep(duree / steps)

def mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, servos, duree=2.0):
    """Déplace les servos indiqués sur Leader ET Follower vers cibles_pct (%).
    Lectures de départ vérifiées : retourne None si une lecture échoue (mouvement
    annulé), True sinon."""
    pos_l, pos_f = {}, {}
    for s in servos:
        p, ok = lire_position(lk, lp, s)
        if not ok:
            print(f"❌ Lecture Leader servo {s} impossible — mouvement annulé")
            return None
        pos_l[s] = p
        p, ok = lire_position(fk, fp, s)
        if not ok:
            print(f"❌ Lecture Follower servo {s} impossible — mouvement annulé")
            return None
        pos_f[s] = p
    cible_l, cible_f = {}, {}
    for s in servos:
        cible_l[s] = _cible_ticks(cl, s, cibles_pct[s])
        cible_f[s] = _cible_ticks(cf, s, cibles_pct[s])
    steps = 100
    for step in range(steps + 1):
        t = step / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        for s in servos:
            lk.write2ByteTxRx(lp, s, 42, int(pos_l[s] + (cible_l[s] - pos_l[s]) * smooth))
            fk.write2ByteTxRx(fp, s, 42, int(pos_f[s] + (cible_f[s] - pos_f[s]) * smooth))
        time.sleep(duree / steps)
    return True

def aller_a_position_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, duree=2.0):
    """Déplace Leader ET Follower vers cibles_pct (%) via la séquence sûre
    (servo 4 en l'air d'abord, etc.), appliquée à l'identique aux deux robots.
    Lectures vérifiées partout : retourne None si une lecture critique échoue
    (mouvement annulé), True sinon."""
    # Activer tous les servos
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 1)
        fk.write1ByteTxRx(fp, i, 40, 1)

    repos_pct, _ = charger_repos_pct()

    # --- Phase 0 (conditionnelle, par robot) ---
    pos4_l, ok = lire_position(lk, lp, 4)
    if not ok:
        print("❌ Lecture Leader servo 4 impossible — mouvement annulé")
        return None
    if pos4_l > 2700:
        etat = _est_en_repos_1robot(lk, lp, cl, repos_pct)
        if etat is None:
            print("❌ État repos Leader indéterminé — mouvement annulé")
            return None
        if not etat:
            pos2_l, ok = lire_position(lk, lp, 2)
            if not ok:
                print("❌ Lecture Leader servo 2 impossible — mouvement annulé")
                return None
            # 1027 ticks : cible de dégagement empirique de l'installation (alignée
            # avec les scripts 4 et 6 ; seuil 2700 idem). Réglage matériel volontaire,
            # à calibrer un jour sur les 3 scripts ensemble si le matériel change.
            mouvement_fluide(lk, lp, 2, pos2_l, min(pos2_l, 1027), duree)

    pos4_f, ok = lire_position(fk, fp, 4)
    if not ok:
        print("❌ Lecture Follower servo 4 impossible — mouvement annulé")
        return None
    if pos4_f > 2700:
        etat = _est_en_repos_1robot(fk, fp, cf, repos_pct)
        if etat is None:
            print("❌ État repos Follower indéterminé — mouvement annulé")
            return None
        if not etat:
            pos2_f, ok = lire_position(fk, fp, 2)
            if not ok:
                print("❌ Lecture Follower servo 2 impossible — mouvement annulé")
                return None
            mouvement_fluide(fk, fp, 2, pos2_f, min(pos2_f, 1027), duree)

    # --- Phase 1 : servo 4 -> 20% sur les deux robots ---
    if mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, {4: 20}, [4], duree) is None:
        return None
    # --- Phase 2 : servos 1,2,3,5,6 en parallèle ---
    if mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, [1, 2, 3, 5, 6], duree) is None:
        return None
    # --- Phase 3 : servo 4 -> cible finale ---
    if mouvement_parallele_2robots(lk, lp, fk, fp, cl, cf, cibles_pct, [4], duree) is None:
        return None
    return True

def test_connexion_fluide(packet, port, robot_name, calib):
    """Test fluide de connexion : fait bouger la pince (servo 6) pour confirmer
    visuellement le bon robot. La calibration est GARANTIE valide (validée au
    démarrage) — pas de fallback brut. Retourne False si la lecture échoue."""
    print(f"\n  🔄 Test de connexion {robot_name}...")

    # Activer le servo 6
    packet.write1ByteTxRx(port, 6, 40, 1)

    centre = calib['servo_6']['center']
    min_val = calib['servo_6']['min']
    max_val = calib['servo_6']['max']
    amplitude = max_val - min_val
    pos_25 = int(min_val + amplitude * 0.25)
    pos_75 = int(min_val + amplitude * 0.75)

    pos_actuelle, ok = lire_position(packet, port, 6)
    if not ok:
        print(f"  ❌ Lecture servo 6 impossible sur {robot_name}")
        return False

    # Séquence fluide : Actuel -> Centre -> 25% -> 75% -> Centre
    print("     → Centre...")
    mouvement_fluide(packet, port, 6, pos_actuelle, centre, 1.0)
    print("     → Fermé (45°)...")
    mouvement_fluide(packet, port, 6, centre, pos_25, 0.8)
    print("     → Ouvert (90°)...")
    mouvement_fluide(packet, port, 6, pos_25, pos_75, 1.2)
    print("     → Centre...")
    mouvement_fluide(packet, port, 6, pos_75, centre, 0.8)

    print(f"  ✅ {robot_name} connecté et testé")
    return True

def identification_guidee_fluide(calib_l, calib_f):
    """Identifie Leader et Follower avec test fluide. Les calibrations (déjà
    chargées et validées) sont passées en argument. Détection STRICTE : exactement
    1 port après le Leader, exactement 2 après le Follower. Chaque échec ferme
    proprement les ports déjà ouverts (cleanup_ports) avant de retourner.
    Retourne (True, lp, lk, fp, fk) ou (False, None, None, None, None)."""
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     IDENTIFICATION LEADER/FOLLOWER                      ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Init pour le nettoyage en cas d'exception interne : sans ça, le port Leader
    # ouvert localement fuiterait (main ne le connaît pas tant que la fonction
    # n'a pas retourné, donc son finally ne peut pas le fermer).
    lp = fp = lk = fk = None
    try:
        # Débrancher tout
        ports = detect_ports()
        while len(ports) > 0:
            print("⚠️  Débranchez tous les robots")
            input("   Entrée quand fait...")
            ports = detect_ports()

        # LEADER
        print("\n🔌 Branchez le LEADER")
        input("   Entrée quand branché...")

        time.sleep(1)
        ports = detect_ports()
        if len(ports) != 1:
            print(f"❌ Attendu exactement 1 robot après branchement du Leader, détecté : {len(ports)}.")
            print("   Débranchez tout et recommencez (un seul adaptateur pour le Leader).")
            return False, None, None, None, None

        leader_port = ports[0]
        print(f"✅ LEADER détecté sur {leader_port}")

        lp = PortHandler(leader_port)
        lk = PacketHandler(1.0)
        if not lp.openPort() or not lp.setBaudRate(1000000):
            print("❌ Erreur connexion Leader")
            cleanup_ports(lp, None, lk, None)
            return False, None, None, None, None

        if not test_connexion_fluide(lk, lp, "LEADER", calib_l):
            cleanup_ports(lp, None, lk, None)
            return False, None, None, None, None

        if input("\nPince du LEADER bougée? [O/N]: ").strip().upper() != 'O':
            cleanup_ports(lp, None, lk, None)
            return False, None, None, None, None

        # FOLLOWER
        print("\n🔌 Branchez le FOLLOWER (gardez Leader branché)")
        input("   Entrée quand branché...")

        time.sleep(1)
        ports = detect_ports()
        if len(ports) != 2:
            print(f"❌ Attendu exactement 2 robots après branchement du Follower, détecté : {len(ports)}.")
            cleanup_ports(lp, None, lk, None)
            return False, None, None, None, None

        follower_port = ports[1] if ports[0] == leader_port else ports[0]
        print(f"✅ FOLLOWER détecté sur {follower_port}")

        fp = PortHandler(follower_port)
        fk = PacketHandler(1.0)
        if not fp.openPort() or not fp.setBaudRate(1000000):
            print("❌ Erreur connexion Follower")
            cleanup_ports(lp, fp, lk, fk)
            return False, None, None, None, None

        if not test_connexion_fluide(fk, fp, "FOLLOWER", calib_f):
            cleanup_ports(lp, fp, lk, fk)
            return False, None, None, None, None

        if input("\nPince du FOLLOWER bougée? [O/N]: ").strip().upper() != 'O':
            cleanup_ports(lp, fp, lk, fk)
            return False, None, None, None, None

        print("\n✅ Identification réussie!")
        return True, lp, lk, fp, fk

    except BaseException:
        # Exception ou CTRL+C avant le retour : fermer les ports ouverts localement
        cleanup_ports(lp, fp, lk, fk)
        raise

def centrage_parallele(lk, lp, fk, fp, cl, cf):
    """Centre tous les servos EN PARALLÈLE de manière fluide (les deux robots).
    Lectures vérifiées : retourne False si une position de départ est illisible
    (centrage annulé), True sinon."""
    print("\n🎯 Centrage simultané des robots...")

    # Activer tous les servos
    for i in range(1, 7):
        lk.write1ByteTxRx(lp, i, 40, 1)
        fk.write1ByteTxRx(fp, i, 40, 1)

    # Lire positions actuelles (vérifiées)
    pos_l, pos_f = {}, {}
    for i in range(1, 7):
        p, ok = lire_position(lk, lp, i)
        if not ok:
            print(f"❌ Lecture Leader servo {i} impossible — centrage annulé")
            return False
        pos_l[i] = p
        p, ok = lire_position(fk, fp, i)
        if not ok:
            print(f"❌ Lecture Follower servo {i} impossible — centrage annulé")
            return False
        pos_f[i] = p

    duree = 2.0
    steps = int(duree * 50)
    for step in range(steps + 1):
        t = step / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        for i in range(1, 7):
            centre_l = cl[f'servo_{i}']['center']
            lk.write2ByteTxRx(lp, i, 42, int(pos_l[i] + (centre_l - pos_l[i]) * smooth))
            centre_f = cf[f'servo_{i}']['center']
            fk.write2ByteTxRx(fp, i, 42, int(pos_f[i] + (centre_f - pos_f[i]) * smooth))
        time.sleep(duree / steps)

    print("✅ Robots centrés")
    return True

def recentrer_servo(lk, lp, fk, fp, cl, cf, servo, steps):
    """Recentre UN servo sur Leader et Follower (mouvement fluide). Lectures de
    départ vérifiées : retourne False si une position est illisible (aucun
    mouvement n'est lancé depuis une valeur douteuse), True sinon."""
    pos_l, ok = lire_position(lk, lp, servo)
    if not ok:
        print(f"❌ Lecture Leader servo {servo} impossible — recentrage annulé")
        return False
    pos_f, ok = lire_position(fk, fp, servo)
    if not ok:
        print(f"❌ Lecture Follower servo {servo} impossible — recentrage annulé")
        return False
    centre_l = cl[f'servo_{servo}']['center']
    centre_f = cf[f'servo_{servo}']['center']
    for i in range(steps + 1):
        t = i / steps
        smooth = (1 - math.cos(t * math.pi)) / 2
        lk.write2ByteTxRx(lp, servo, 42, int(pos_l + (centre_l - pos_l) * smooth))
        fk.write2ByteTxRx(fp, servo, 42, int(pos_f + (centre_f - pos_f) * smooth))
        time.sleep(0.02)
    return True

def mapper(pos_l, servo_id, cl, cf, miroir=False):
    """Mapping proportionnel Leader -> Follower (calibration garantie valide),
    avec option miroir et bornage de sortie sur les limites Follower."""
    ml = cl[f'servo_{servo_id}']['min']
    Ml = cl[f'servo_{servo_id}']['max']
    mf = cf[f'servo_{servo_id}']['min']
    Mf = cf[f'servo_{servo_id}']['max']

    ratio = (pos_l - ml) / (Ml - ml) if Ml > ml else 0.5
    ratio = max(0, min(1, ratio))

    if miroir:
        ratio = 1 - ratio

    return int(max(mf, min(Mf, int(mf + ratio * (Mf - mf)))))

def choisir_mode():
    """Choix explicite de la disposition (boucle jusqu'à C ou F)."""
    print("\n[C]ôte à côte ou [F]ace à face ?")
    while True:
        c = input("Choix [C/F] : ").strip().upper()
        if c == 'C':
            return "cote", "CÔTÉ À CÔTÉ"
        if c == 'F':
            return "face", "FACE À FACE"
        print("❌ Choix invalide : tapez C ou F")

def choisir_copie_miroir(servo):
    """Choix explicite COPIE/MIROIR pour un servo (boucle jusqu'à C ou M)."""
    print(f"\n\nServo {servo}: [C]opie ou [M]iroir ?")
    while True:
        c = input("Choix [C/M] : ").strip().upper()
        if c == 'C':
            return 'C'
        if c == 'M':
            return 'M'
        print("❌ Choix invalide : tapez C ou M")

def charger_config_initiale(mode_key):
    """Pour le SCRIPT 5 : lit la config existante (si présente et valide) afin
    d'afficher l'état 'avant'. Config absente = NORMAL (premier lancement, tout
    COPIE). Config présente mais mal formée = avertissement, on repart en tout
    COPIE (l'utilisateur reconfigure puis écrase le fichier)."""
    config = {i: "C" for i in range(1, 7)}
    file_config = os.path.expanduser(f"~/lerobot/calibration/teleoperation_config_{mode_key}.json")
    if not os.path.exists(file_config):
        return config  # premier lancement : tout COPIE
    miroir = charger_servos_miroir_fichier(file_config)
    if miroir is None:
        print("⚠️  Configuration existante illisible ou mal formée — départ en tout COPIE.")
        return config
    for s in miroir:
        config[s] = "M"
    return config

def main():
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     CONFIGURATION TÉLÉOPÉRATION SO-ARM 101              ║
╚══════════════════════════════════════════════════════════╝
    """)

    # --- Calibration OBLIGATOIRE des DEUX robots, validée AVANT tout matériel ---
    calib_l = charger_calibration('leader')
    calib_f = charger_calibration('follower')
    if not calibration_complete(calib_l):
        print("❌ Calibration Leader absente, incomplète ou invalide — faites la Phase 3.")
        return
    if not calibration_complete(calib_f):
        print("❌ Calibration Follower absente, incomplète ou invalide — faites la Phase 3.")
        return

    lp = fp = lk = fk = None
    urgence = False

    try:
        # Identification guidée (calibrations déjà validées)
        ok, lp, lk, fp, fk = identification_guidee_fluide(calib_l, calib_f)
        if not ok:
            print("❌ Identification échouée")
            return
        cl, cf = calib_l, calib_f
        print("\n📡 Connexions établies avec succès")

        # Choix mode explicite
        mode_key, mode_name = choisir_mode()

        # Config existante (script 5 : absente = OK, mal formée = avertie)
        file_config = os.path.expanduser(f"~/lerobot/calibration/teleoperation_config_{mode_key}.json")
        config = charger_config_initiale(mode_key)

        # Afficher config actuelle AVANT le centrage
        print(f"\n📊 Configuration actuelle {mode_name} :")
        print("-" * 35)
        for i in range(1, 7):
            val = "MIROIR" if config[i] == "M" else "COPIE"
            print(f"  Servo {i} ({SERVO_NAMES[i]:10}) : {val}")
        print("-" * 35)

        # Centrage parallèle (vérifié)
        input("\nEntrée pour centrer les robots...")
        if not centrage_parallele(lk, lp, fk, fp, cl, cf):
            print("❌ Centrage impossible (lecture servo) — arrêt.")
            return

        print("\n⚠️  Vous pouvez maintenant tenir le LEADER")
        time.sleep(2)

        # Test de chaque servo
        new_config = {}
        for servo in range(1, 7):
            clear_screen()
            print(f"TEST SERVO {servo}/6 : {SERVO_NAMES[servo]}")
            print("=" * 40)

            # Libérer SEULEMENT le servo testé (Leader), Follower actif
            lk.write1ByteTxRx(lp, servo, 40, 0)
            fk.write1ByteTxRx(fp, servo, 40, 1)

            # MODE COPIE (live) — lecture vérifiée, cycle ignoré si échec
            print("\n📋 MODE COPIE")
            print("Bougez le Leader maintenant")
            print("Appuyez ENTRÉE pour passer en miroir")
            while True:
                pos_l, ok = lire_position(lk, lp, servo)
                if ok:
                    pos_f = mapper(pos_l, servo, cl, cf, miroir=False)
                    fk.write2ByteTxRx(fp, servo, 42, pos_f)
                    print(f"L:{pos_l:4} → F:{pos_f:4} [COPIE]  ", end="\r")
                if sys.stdin in select.select([sys.stdin], [], [], 0.02)[0]:
                    input()
                    break
                time.sleep(0.02)

            # Transition : recentrer avant le miroir (lectures vérifiées)
            print("\n🔄 Recentrage pour transition...")
            lk.write1ByteTxRx(lp, servo, 40, 1)
            fk.write1ByteTxRx(fp, servo, 40, 1)
            if not recentrer_servo(lk, lp, fk, fp, cl, cf, servo, 40):
                print("❌ Recentrage impossible — arrêt sécurisé.")
                return

            # Libérer le Leader pour le test miroir
            lk.write1ByteTxRx(lp, servo, 40, 0)

            # MODE MIROIR (live) — lecture vérifiée, cycle ignoré si échec
            print("\n📋 MODE MIROIR")
            print("Bougez le Leader maintenant")
            print("Appuyez ENTRÉE pour choisir")
            while True:
                pos_l, ok = lire_position(lk, lp, servo)
                if ok:
                    pos_f = mapper(pos_l, servo, cl, cf, miroir=True)
                    fk.write2ByteTxRx(fp, servo, 42, pos_f)
                    print(f"L:{pos_l:4} → F:{pos_f:4} [MIROIR] ", end="\r")
                if sys.stdin in select.select([sys.stdin], [], [], 0.02)[0]:
                    input()
                    break
                time.sleep(0.02)

            # CHOIX explicite
            new_config[servo] = choisir_copie_miroir(servo)

            # Recentrer et bloquer ce servo (lectures vérifiées)
            lk.write1ByteTxRx(lp, servo, 40, 1)
            fk.write1ByteTxRx(fp, servo, 40, 1)
            if not recentrer_servo(lk, lp, fk, fp, cl, cf, servo, 75):
                print("❌ Recentrage impossible — arrêt sécurisé.")
                return

        # VALIDATION
        clear_screen()
        print(f"VALIDATION {mode_name}")
        print("=" * 40)
        for i in range(1, 7):
            old = "MIROIR" if config[i] == 'M' else "COPIE"
            new = "MIROIR" if new_config[i] == 'M' else "COPIE"
            print(f"Servo {i} ({SERVO_NAMES[i]:10}): {old:6} → {new:6}")

        # Sauvegarde (choix explicite V/Q)
        print("\n[V] Sauver, [Q] Annuler")
        while True:
            choix = input("Choix [V/Q] : ").strip().upper()
            if choix in ('V', 'Q'):
                break
            print("❌ Choix invalide : tapez V ou Q")

        if choix == 'V':
            servos_miroir = sorted([s for s, m in new_config.items() if m == 'M'])
            save_data = {"mode": mode_name, "servos_miroir": servos_miroir}
            os.makedirs(os.path.expanduser("~/lerobot/calibration"), exist_ok=True)
            # Sauvegarde atomique : .tmp puis os.replace
            tmp = file_config + ".tmp"
            with open(tmp, 'w') as f:
                json.dump(save_data, f, indent=2)
            os.replace(tmp, file_config)
            print("✅ Configuration sauvegardée !")
            print(f"📁 Fichier : {file_config}")
            print(f"📋 Servos en miroir : {servos_miroir}")
            print("🔗 Cette configuration sera utilisée par le script 6 de téléopération")
        else:
            print("↩️  Configuration NON sauvegardée (annulée).")

        # Position repos finale avant libération (fallback annoncé)
        print("\n🏁 Position repos avant libération...")
        repos_pct, origine = charger_repos_pct()
        if origine == "default":
            print("⚠️  repos_position.json absent ou invalide — position de repos PAR DÉFAUT utilisée.")
        if aller_a_position_2robots(lk, lp, fk, fp, cl, cf, repos_pct, duree=2.0) is None:
            print("⚠️  Retour repos incomplet (lecture servo) — vérifiez la posture des robots.")

        print("\n⚠️  Assurez-vous de tenir les robots")
        time.sleep(2)

    except KeyboardInterrupt:
        urgence = True
        print("\n🛑 Interruption (CTRL+C) — libération immédiate, aucun retour repos.")
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
    finally:
        # Nettoyage GARANTI : libération best-effort + fermeture des ports
        cleanup_ports(lp, fp, lk, fk, release=True)
        if urgence:
            print("\n✅ Arrêt d'urgence terminé (aucun retour repos).")
        else:
            print("\n✅ Configuration terminée !")

if __name__ == "__main__":
    main()
