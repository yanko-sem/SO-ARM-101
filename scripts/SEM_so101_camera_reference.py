#!/usr/bin/env python3
"""
Module SEM_so101_camera_reference.py
Service Écoles-Médias (SEM) - DIP Genève

RÉFÉRENCE VISUELLE CAMÉRA — OUTIL & MODULE (v7, multi-caméra)
============================================================
Fichier : SEM_so101_camera_reference.py (ex-SEM_camera_reference.py)

Double rôle (décision validée) :
  1. OUTIL autonome (menu) : mesure, référence, diagnostic, recalibrage.
  2. MODULE importé par les scripts du pipeline (étapes 5-6) — l'import
     ne déclenche ni menu ni caméra (garde __main__). API publique :
       controle_camera_avant_enregistrement(idx, nom_camera, contexte) → dict
       copier_reference_vers_meta(meta_dir) → bool (copie les DEUX caméras)
       menu_reference(idx, nom_camera) → menu complet, caméra déjà
                             identifiée, sortie [S] Étape suivante
       controle_camera_deploiement(idx, nom_camera, dossier_reference,
                             contexte) → contrôle contre la référence du
                             DATASET (étape 6, script 11) — lecture seule
     MULTI-CAMÉRA (spec validée) : nom_camera ∈ {"cam_top", "cam_follower"} ;
     chaque caméra a son PROFIL (zones, critères, sentinelle couleur) et son
     jeu de fichiers ; le code de mesure/évaluation est unique.

Calibration des caméras par référence chiffrée (voir « Spécification
Étape 0 » v1.6 et « Spécification multi-caméra » v1.0). Outil + module,
couvrant les étapes 1 à 4 + l'API de l'étape 5, pour DEUX caméras
(cam_top globale, cam_follower pince). Les zones, critères et la sentinelle
couleur dépendent du PROFIL de la caméra (dictionnaire PROFILS) :

  [1] Définition des zones  : rectangles dessinés à la souris, séquence
                              guidée selon le profil — cam_top : plateau_1
                              → plateau_2 → plateau_3 (opt.) → bol → rose ;
                              cam_follower : bois_1 → bois_2 → pince_verte.
                              Validation par surface (400 px) et, pour
                              cam_top, appartenance au masque.
  [2] Visualisation des     : image figée masquée + zones dessinées, pour
      zones actuelles         juger s'il faut les redessiner.
  [3] Mesure en direct      : métriques M1-M8 par zone — tableau initial
                              imprimé automatiquement, puis valeurs
                              recalculées toutes les 0,5 s sur le flux.
                              Touche M : nouveau tableau + stabilité M9
                              (~4 s, toutes zones plateau).
  [4] Capture de la         : référence ACTIVE = moyenne de 20 échantillons
      référence (étape 2)     sur ~4 s + images témoins (frame réelle la
                              plus représentative) + métadonnées.
                              BLOQUÉE si réglages non verrouillés (D1) ou
                              si lumière instable, sigma_t > 1,5 (D2).
  [5] Affichage de la       : métadonnées, réglages capturés, statistiques
      référence active        par zone, contrôle de caducité (masque + zones).
  [6] Diagnostic de         : verdicts 🟢/🟠/🔴 par critère (C1-C9, seuils
      conformité (étape 3)    PROVISOIRES dans le bloc SEUILS) vs la
                              référence active. Acquisition identique à la
                              capture (20 éch., ~4 s). Refusé si réglages
                              ni d'origine ni recalibrés, ou référence
                              caduque ; suspendu si sigma_t > 3.
                              Qualification écart GLOBAL / LOCAL. N'écrit rien.
  [7] Recalibrage guidé     : boucle diagnostic (même logique que [6]) +
      (étape 4)               consignes graduées → [A] ajuster via guvcview →
                              remesure, jusqu'au 🟢. À la convergence,
                              enregistre les réglages (camera_settings.json)
                              et reglages_recalibres dans la référence — le
                              diagnostic [6] les acceptera ensuite.

Règle d'interface : quand une fenêtre vidéo est OUVERTE, toutes les touches
se pressent DANS la fenêtre ; quand aucune fenêtre n'est ouverte, les
saisies se font dans le terminal. (Un input() terminal pendant qu'une
fenêtre est ouverte gèlerait la boucle d'événements HighGUI.)

Garanties (v4) :
  - Options [1] à [6] : ne créent AUCUN nouveau réglage caméra (pas de
    guvcview, pas d'écriture dans camera_settings.json). Elles peuvent
    APPLIQUER les réglages existants (application non destructive) pour
    mesurer dans les mêmes conditions que le pipeline.
  - Option [7] (recalibrage) : peut modifier camera_settings.json,
    UNIQUEMENT après action explicite de l'utilisateur via guvcview, en
    utilisant le mécanisme existant de SEM_so101_camera_config.py. Elle peut
    aussi ajouter reglages_recalibres + date_recalibrage dans la référence.
  - RÉGLAGE INITIAL : si la caméra n'a AUCUN réglage enregistré (première
    mise en service), le menu propose à son démarrage de les créer
    (guvcview, action explicite, [R]) — seule autre situation où l'outil
    écrit camera_settings.json.
  - Si le verrouillage échoue ou si la caméra est absente du fichier de
    réglages : la mesure reste autorisée comme TEST DE L'OUTIL, avec
    l'avertissement « mesures non représentatives du pipeline ».
  - Fichiers propres de l'outil, PAR caméra : zones
    (camera_reference_zones_<cam>.json) et référence active
    (camera_reference_<cam>.json + image témoin _raw.png ; _masked.png
    uniquement pour cam_top, qui a un masque).
  - API d'intégration (étape 5) : controle_camera_avant_enregistrement
    applique la politique script 8 (spec §5) et peut écrire dans le
    journal camera_reference_log.jsonl (passages 🟠 confirmés) ; un
    contrôle indisponible ne peut plus être « passé » : il se répare ([M])
    ou annule ([Q]) ; copier_reference_vers_meta copie la
    référence dans le meta/ d'un dataset (traçabilité).
  - Aucun script validé du pipeline n'est modifié par ce module lui-même.

Identification obligatoire : les index /dev/videoX ne sont pas stables.
Au lancement, l'outil demande quelle caméra travailler (G/P), affiche un
aperçu et demande une confirmation explicite. Aucune mesure n'est possible
avant confirmation. L'index n'est pas mémorisé entre les sessions.

Pré-requis : camera_mask.json (créé par le script 7) — pour cam_top
uniquement ; cam_follower mesure sur l'image entière (pas de masque).

Note d'architecture : l'état de la caméra courante (profil, fichiers) est
porté par des variables de module ; les contrôles des deux caméras doivent
rester SÉQUENTIELS (jamais deux en parallèle).

Usage :
    python SEM_so101_camera_reference.py

Auteur: Service Écoles-Médias (SEM)
Version: 8.0 (multi-caméra + déploiement étape 6 + étapes 1-4 + API étape 5 du plan « Référence visuelle caméra »)
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

import shutil

import cv2
import numpy as np

cv2.setNumThreads(1)   # cohérence avec les scripts 8 et 11

# Module partagé du pipeline (mécanisme de verrouillage caméra).
# Import tolérant, aligné sur le script 8 (except Exception : un module
# présent mais cassé ne doit pas produire un traceback au démarrage).
NOM_MODULE_CONFIG = "SEM_so101_camera_config"
try:
    from SEM_so101_camera_config import (verrouiller_camera,
                                         charger_reglages_camera,
                                         capturer_reglages_camera)
except Exception:
    try:
        from SEM_so101_8_camera_config import (verrouiller_camera,
                                               charger_reglages_camera,
                                               capturer_reglages_camera)
        NOM_MODULE_CONFIG = "SEM_so101_8_camera_config (transition)"
    except Exception:
        try:
            from SEM_8_camera_config import (verrouiller_camera,
                                             charger_reglages_camera,
                                             capturer_reglages_camera)
            NOM_MODULE_CONFIG = "SEM_8_camera_config (ancien nom)"
        except Exception:
            verrouiller_camera = None
            charger_reglages_camera = None
            capturer_reglages_camera = None
            NOM_MODULE_CONFIG = "SEM_so101_camera_config (INTROUVABLE)"

# ============================================
# CONSTANTES
# ============================================

LARGEUR, HAUTEUR = 640, 360          # résolution du pipeline (16:9)
FPS = 30                             # fps du pipeline (script 8, CONFIG['fps'])
ECHELLE_AFFICHAGE = 2                # fenêtres affichées en 1280x720

# Alignement caméra : acquisition UNIFIÉE (codec MJPG + 640x360) entre cet
# outil, l'enregistrement (script 8) et le déploiement. La référence doit être
# créée et contrôlée dans EXACTEMENT les mêmes conditions caméra que le dataset
# et l'inférence, sinon le score de conformité serait biaisé.

CALIB_DIR = Path.home() / "lerobot" / "calibration"
MASK_FILE = CALIB_DIR / "camera_mask.json"
LOG_FILE = CALIB_DIR / "camera_reference_log.jsonl"   # journal UNIQUE, entrées étiquetées par caméra

# Variables PAR CAMÉRA : (re)définies par selectionner_profil(nom_camera) —
# un jeu de fichiers/zones par caméra (spec multi-caméra §2-§3). Tout point
# d'entrée (menu, contrôle, copie) appelle selectionner_profil avant usage.
NOM_CAMERA = None
PROFIL = None
ZONES_FILE = None
REF_FILE = None
REF_RAW_PNG = None
REF_MASKED_PNG = None
SEQUENCE_ZONES = None
CONSIGNES_ZONES = None
COULEURS_ZONES = None

# Capture de la référence (étape 2)
REF_N_ECHANTILLONS = 20              # frames moyennées pour la référence
REF_SIGMA_T_MAX = 1.5                # porte de stabilité STRICTE (seuil 🟢 C9)

SEUIL_SATURE = 250                   # M7 : pixel saturé si max(R,G,B) >= 250
SEUIL_SOMBRE = 10                    # M8 : pixel très sombre si Y <= 10
SURFACE_MIN = 400                    # surface minimale d'une zone (pixels)

INTERVALLE_METRIQUES = 0.5           # s — recalcul M1-M8 (décision D3)
STABILITE_DUREE = 4.0                # s — mesure M9
STABILITE_INTERVALLE = 0.2           # s — échantillonnage M9

TOUCHES_ENTREE = (13, 10)            # codes touche Entrée (CR / LF)

# ============================================
# SEUILS DU DIAGNOSTIC (spec Étape 0 v1.3, §4) — PROVISOIRES
# À ajuster ICI pendant la campagne de figeage, sans toucher à la logique.
# Format : (seuil 🟢, seuil 🟠) — au-delà : 🔴. C8 : (seuil 🟢,) — au-delà : 🟠.
# ============================================
SEUILS = {
    "C1": (8.0, 20.0),    # |ΔY| plateau (vs référence)
    "C2": (2.0, 5.0),     # |Δratio|/ratio_réf en % (plateau, pire de R/G et B/G)
    "C3": (3.0, 6.0),     # |Δsigma_Y| plateau
    "C4": (6.0, 12.0),    # Δ_inter (homogénéité spatiale, M10)
    "C5": (0.5, 2.0),     # |Δ % saturés| bol, en points (relatif — amendement v1.3)
    "C6": (10.0, 25.0),   # |Δ médiane Y| bol
    "C7": (0.5, 3.0),     # |Δ % sombres| plateau, en points (relatif — amendement v1.3)
    "C8": (4.0,),         # |Δratio|/ratio_réf en % (rose) — jamais 🔴
    "C9": (1.5, 3.0),     # sigma_t (absolu) ; 🔴 = mesure instable, diagnostic suspendu
}
SATURATION_ABS_AVERTISSEMENT = 5.0   # % absolu bol : avertissement informatif (non bloquant)

# ============================================
# CORRESPONDANCE RÉGLAGES TECHNIQUES ↔ INTERFACE GUVCVIEW
# (noms exacts tels qu'affichés dans guvcview — base de l'aide opérateur)
# ============================================
GUVCVIEW_NOMS = {
    "exposure_time_absolute":    "Temps d'exposition, Absolu",
    "white_balance_temperature": "Balance des blancs",
    "gain":                      "Gain",
    "white_balance_automatic":   "Balance des blancs, Automatique",
    "exposure_dynamic_framerate": "Exposition, Nombre d'images par seconde dynamique",
}
# Contrôles guvcview à NE PAS toucher dans ce protocole
GUVCVIEW_INTERDITS = ["Luminosité", "Contraste", "Saturation", "Teinte",
                      "Gamma", "Netteté", "Correction de contre-jour",
                      "Fréquence de rafraîchissement"]

# ============================================
# PROFILS CAMÉRA (spec multi-caméra §2) — la fiche de CE que chaque caméra
# mesure ; le code de mesure/évaluation est identique pour toutes.
# ============================================
PROFILS = {
    "cam_top": {
        "libelle": "GLOBALE (cam_top)",
        "nom_simple": "GLOBALE",
        "masque": True,                                  # masque du script 7
        "pilotes": ["plateau_1", "plateau_2", "plateau_3"],
        "bol": True,                                     # critères C5/C6 actifs
        "sentinelle": "rose",                            # zone du critère C8
        "sentinelle_libelle": "pièce rose",
        "checklist_camera": ("Caméra cam_top en position d'enregistrement, "
                             "non déplacée depuis la création du masque"),
        "identification_aide": ("Confirme uniquement la vue GLOBALE du "
                                "plateau (pas la pince)."),
        "sequence_zones": [
            ("plateau_1", True,  (80, 200, 80)),
            ("plateau_2", True,  (80, 200, 80)),
            ("plateau_3", False, (80, 200, 80)),
            ("bol",       True,  (60, 200, 230)),
            ("rose",      True,  (180, 105, 255)),
        ],
        "consignes": {
            "plateau_1": "aplat uniforme du plateau (hors marqueurs gravés, hors ombres)",
            "plateau_2": "autre aplat du plateau, ÉLOIGNÉ de plateau_1",
            "plateau_3": "troisième aplat du plateau (optionnel)",
            "bol":       "intérieur du bol blanc vide",
            "rose":      "pièce rose fixe du Leader",
        },
    },
    "cam_follower": {
        "libelle": "PINCE (cam_follower)",
        "nom_simple": "PINCE",
        "masque": False,                                 # image entière (validé)
        "pilotes": ["bois_1", "bois_2"],
        "bol": False,                                    # pas de bol exploitable
        "sentinelle": "pince_verte",
        "sentinelle_libelle": "pince verte",
        "checklist_camera": ("Caméra cam_follower fixée sur la pince, robot "
                             "AU REPOS (la vue dépend de la pose du bras)"),
        "identification_aide": ("Confirme uniquement la vue PINCE "
                                "(gros plan : pince verte + plateau bois)."),
        "sequence_zones": [
            ("bois_1",      True, (80, 200, 80)),
            ("bois_2",      True, (80, 200, 80)),
            ("pince_verte", True, (80, 220, 120)),
        ],
        "consignes": {
            "bois_1":      "aplat du plateau bois, partie HAUTE droite (hors gravures)",
            "bois_2":      "aplat du plateau bois, partie BASSE droite, éloigné de bois_1",
            "pince_verte": "surface verte de la pince (aplat, hors trous et arêtes)",
        },
    },
}


def selectionner_profil(nom_camera, dossier_reference=None):
    """Sélectionne la caméra de travail : recharge le profil et le jeu de
    fichiers correspondants. À appeler par TOUT point d'entrée (menu,
    contrôle, capture, copie) avant d'utiliser les variables par caméra.

    dossier_reference (étape 6, déploiement) : si fourni, REF_FILE et les
    images témoins pointent vers CE dossier (le meta/ du dataset) au lieu
    de ~/lerobot/calibration — la « vérité » devient celle du dataset.
    Les autres fichiers (réglages, journal, zones locales) ne changent pas.
    Le mode déploiement n'écrit JAMAIS dans ce dossier (spec étape 6 §6)."""
    global NOM_CAMERA, PROFIL, ZONES_FILE, REF_FILE, REF_RAW_PNG, REF_MASKED_PNG
    global SEQUENCE_ZONES, CONSIGNES_ZONES, COULEURS_ZONES
    if nom_camera not in PROFILS:
        raise ValueError(f"Caméra inconnue : {nom_camera!r} "
                         f"(attendu : {', '.join(PROFILS)})")
    NOM_CAMERA = nom_camera
    PROFIL = PROFILS[nom_camera]
    base_ref = Path(dossier_reference) if dossier_reference else CALIB_DIR
    ZONES_FILE = CALIB_DIR / f"camera_reference_zones_{nom_camera}.json"
    REF_FILE = base_ref / f"camera_reference_{nom_camera}.json"
    REF_RAW_PNG = base_ref / f"camera_reference_{nom_camera}_raw.png"
    REF_MASKED_PNG = base_ref / f"camera_reference_{nom_camera}_masked.png"
    SEQUENCE_ZONES = PROFIL["sequence_zones"]
    CONSIGNES_ZONES = PROFIL["consignes"]
    COULEURS_ZONES = {nom: c for nom, _, c in SEQUENCE_ZONES}


# ============================================
# AFFICHAGE TERMINAL (style des scripts du pipeline)
# ============================================

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')


def afficher_tableau(titre, lignes):
    """Affiche un bloc aligné (style _afficher_reglages du module caméra).
    lignes : liste de tuples (label, valeur)."""
    print(f"\n📊 {titre} :")
    print("   " + "-" * 52)
    for label, valeur in lignes:
        print(f"   {label} {'.' * max(2, 36 - len(label))} {valeur}")
    print("   " + "-" * 52)


# ============================================
# IDENTIFICATION DE LA CAMÉRA (obligatoire, selon le profil sélectionné)
# ============================================

def detect_cameras():
    """Balayage des indices 0-9 (même approche que le script 7)."""
    cameras = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cameras.append(i)
        cap.release()
    return cameras


def ouvrir_camera(idx, warmup=5):
    """Ouverture commune : force 640x360, vide quelques images (warmup,
    pour éviter une image initiale instable), puis VÉRIFIE la résolution
    réellement obtenue — le masque et les zones sont en 640x360, toute
    autre résolution fausserait toutes les mesures.
    Retourne le VideoCapture prêt à l'emploi, ou None (erreur affichée)."""
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        print(f"   ❌ Impossible d'ouvrir la caméra {idx}.")
        return None
    # MJPG : acquisition UNIFIÉE avec l'enregistrement (script 8) et le
    # déploiement — la référence doit être créée/contrôlée dans EXACTEMENT
    # les mêmes conditions caméra que le dataset et l'inférence.
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, LARGEUR)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HAUTEUR)
    cap.set(cv2.CAP_PROP_FPS, FPS)   # même demande que le script 8
    fps_reel = cap.get(cv2.CAP_PROP_FPS)
    if fps_reel and abs(fps_reel - FPS) > 1:
        # Informatif seulement : le FPS rapporté par OpenCV n'est pas toujours fiable
        print(f"   ℹ️  FPS demandé {FPS}, rapporté {fps_reel:.0f}.")
    ret, frame = False, None
    for _ in range(max(1, warmup)):
        ret, frame = cap.read()
        time.sleep(0.05)
    if not ret or frame is None:
        print(f"   ❌ Caméra {idx} : lecture impossible.")
        cap.release()
        return None
    if frame.shape[:2] != (HAUTEUR, LARGEUR):
        print(f"   ❌ Caméra {idx} : résolution réelle "
              f"{frame.shape[1]}x{frame.shape[0]} au lieu de "
              f"{LARGEUR}x{HAUTEUR} — mesures impossibles "
              f"(masque et zones définis en {LARGEUR}x{HAUTEUR}).")
        cap.release()
        return None
    return cap


def identifier_camera():
    """Aperçu de chaque caméra candidate + confirmation explicite par
    touches DANS LA FENÊTRE, pour la caméra du PROFIL courant
    (selectionner_profil doit avoir été appelé). Retourne l'index
    confirmé, ou None si abandon. L'index n'est pas mémorisé."""
    print("\n🔍 Détection des caméras...")
    cameras = detect_cameras()
    if not cameras:
        print("❌ Aucune caméra détectée. Branche la caméra et relance.")
        return None
    print(f"   Caméras trouvées aux indices : {cameras}")

    print(f"\n📷 IDENTIFICATION — {PROFIL['libelle']}")
    print("   Un aperçu va s'afficher pour chaque caméra candidate.")
    print(f"   {PROFIL['identification_aide']}")
    print("   Réponds avec les touches DANS LA FENÊTRE :")
    print(f"   [Entrée] = OUI c'est la {PROFIL['nom_simple']}   [N] = suivante   [Q] = quitter")

    titre = f"Identification {PROFIL['nom_simple']}"
    i = 0
    essais = 0
    while True:
        idx = cameras[i % len(cameras)]
        cap = ouvrir_camera(idx, warmup=3)
        if cap is not None:
            ret, frame = cap.read()
            cap.release()
        else:
            ret, frame = False, None
        if not ret:
            print(f"   ⚠️  Caméra {idx} : inutilisable — caméra suivante.")
            i += 1
            essais += 1
            if essais >= 2 * len(cameras):
                print("❌ Aucune caméra utilisable en 640x360.")
                try:
                    cv2.destroyWindow(titre)
                except cv2.error:
                    pass
                return None
            continue

        print(f"   → /dev/video{idx} affichée — réponds dans la fenêtre.")
        affiche = cv2.resize(frame, (LARGEUR * ECHELLE_AFFICHAGE,
                                     HAUTEUR * ECHELLE_AFFICHAGE))
        cv2.putText(affiche,
                    f"/dev/video{idx} - {PROFIL['nom_simple']} ?  "
                    f"[Entree = OUI] [N = suivante] [Q = quitter]",
                    (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        decision = None
        while decision is None:
            cv2.imshow(titre, affiche)
            key = cv2.waitKey(20) & 0xFF
            if key in TOUCHES_ENTREE:
                decision = 'OUI'
            elif key in (ord('n'), ord('N')):
                decision = 'SUIVANTE'
            elif key in (ord('q'), ord('Q')) or key == 27:
                decision = 'QUITTER'
        if decision == 'OUI':
            cv2.destroyWindow(titre)
            cv2.waitKey(50)
            print(f"   ✅ {PROFIL['libelle']} confirmée : index {idx} (/dev/video{idx})")
            return idx
        if decision == 'QUITTER':
            cv2.destroyWindow(titre)
            cv2.waitKey(50)
            return None
        i += 1


def appliquer_reglages_pipeline(idx):
    """Applique les réglages existants de camera_settings.json à la caméra
    confirmée (verrouiller_camera, signature : device puis nom logique —
    identique aux scripts 8 et 11). Application non destructive de réglages
    déjà validés : aucun réglage n'est créé ni sauvegardé ici.

    Retourne True si tous les contrôles sont confirmés, False sinon
    (mode « mesures non représentatives du pipeline »).
    La caméra doit être LIBÉRÉE avant l'appel (cohérence avec l'ordre du
    pipeline : verrouillage avant connexion des caméras)."""
    device = f"/dev/video{idx}"
    print(f"\n🔒 Application des réglages du pipeline ({device})...")

    if not os.path.exists(device):
        print(f"   ⚠️  {device} introuvable — vérifie la correspondance index/device.")
        return False
    if verrouiller_camera is None:
        print(f"   ⚠️  Module {NOM_MODULE_CONFIG} introuvable — verrouillage impossible.")
        return False
    if charger_reglages_camera is not None and not charger_reglages_camera(NOM_CAMERA):
        print(f"   ⚠️  Aucun réglage '{NOM_CAMERA}' dans camera_settings.json.")
        print("       (Tu peux les créer depuis le menu de l'outil avec [R].)")
        return False

    return bool(verrouiller_camera(device, NOM_CAMERA))


def avertir_non_representatif():
    print("\n" + "!" * 60)
    print("!!  RÉGLAGES NON VERROUILLÉS                              !!")
    print("!!  MESURES NON REPRÉSENTATIVES DU PIPELINE               !!")
    print("!!  Utilisable UNIQUEMENT comme test de l'outil.          !!")
    print("!!  NE PAS utiliser ces mesures pour fixer ou valider     !!")
    print("!!  les seuils de la spécification.                       !!")
    print("!" * 60)


# ============================================
# MASQUE DE ZONE UTILE (créé par le script 7, lecture seule)
# ============================================

def charger_masque():
    """Lit MASK_FILE et renvoie la liste des points du polygone, ou None."""
    if not MASK_FILE.exists():
        return None
    try:
        with open(MASK_FILE, 'r') as f:
            data = json.load(f)
        return [tuple(p) for p in data["points"]]
    except Exception:
        return None


def construire_mask_image(points, width, height):
    if not points:
        # Caméra SANS masque (profil pince) : toute l'image est utile.
        return np.full((height, width), 255, dtype=np.uint8)
    """Masque binaire (uint8 0/255) à partir des points du polygone."""
    mask = np.zeros((height, width), dtype=np.uint8)
    pts = np.array(points, np.int32)
    cv2.fillPoly(mask, [pts], 255)
    return mask


# ============================================
# ZONES DE MESURE
# ============================================

def charger_zones(mask_pts, mask_img):
    """Charge ZONES_FILE avec la MÊME rigueur qu'à la création :
      - contrôle d'obsolescence : empreinte du masque identique au masque
        courant (masque refait → cadrage différent → zones caduques) ;
      - résolution de référence = 640x360 ;
      - noms autorisés uniquement, sans doublon ;
      - zones obligatoires présentes (plateau_1, plateau_2, bol, rose) ;
      - champs x, y, w, h entiers ;
      - chaque rectangle passe valider_zone() (surface, masque).
    Retourne la liste des zones, ou None (zones à redéfinir)."""
    if not ZONES_FILE.exists():
        return None
    try:
        with open(ZONES_FILE, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"⚠️  Fichier de zones illisible ({e}) — à redéfinir.")
        return None

    def caduques(raison):
        print(f"⚠️  Zones enregistrées CADUQUES : {raison}.")
        print("    À redéfinir avec l'option [1].")
        return None

    if data.get("mask_points") != [list(p) for p in mask_pts]:
        return caduques("le masque caméra a changé depuis leur définition")
    res = data.get("reference_resolution", {})
    if (res.get("width"), res.get("height")) != (LARGEUR, HAUTEUR):
        return caduques(f"résolution de référence ≠ {LARGEUR}x{HAUTEUR}")

    zones = data.get("zones", [])
    if not isinstance(zones, list) or not zones:
        return caduques("champ 'zones' absent ou invalide")
    for z in zones:
        if not isinstance(z, dict):
            return caduques("entrée de zone invalide (dictionnaire attendu)")
    noms_autorises = [nom for nom, _, _ in SEQUENCE_ZONES]
    noms_obligatoires = [nom for nom, oblig, _ in SEQUENCE_ZONES if oblig]
    noms = [z.get("nom") for z in zones]
    if len(noms) != len(set(noms)):
        return caduques("zone en double")
    for nom in noms:
        if nom not in noms_autorises:
            return caduques(f"nom de zone inconnu : '{nom}'")
    for nom in noms_obligatoires:
        if nom not in noms:
            return caduques(f"zone obligatoire manquante : '{nom}'")
    zones_valides = []
    for z in zones:
        for champ in ("x", "y", "w", "h"):
            v = z.get(champ)
            if not isinstance(v, int) or isinstance(v, bool):
                return caduques(f"zone '{z.get('nom')}' : champ {champ} non entier")
        rect = (z["x"], z["y"], z["w"], z["h"])
        ok, msg = valider_zone(rect, mask_img)
        if not ok:
            return caduques(f"zone '{z['nom']}' invalide ({msg})")
        # Liste normalisée : seuls les champs attendus sont retournés
        zones_valides.append({"nom": z["nom"], "x": z["x"], "y": z["y"],
                              "w": z["w"], "h": z["h"]})

    print(f"✅ Zones chargées et revalidées : {', '.join(noms)}")
    return zones_valides


def valider_zone(rect, mask_img):
    """Règles de validité (spec §2) : surface >= SURFACE_MIN et chaque pixel
    du rectangle dans la partie utile du masque (255).
    Retourne (ok, message)."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return False, "largeur/hauteur nulle ou négative"
    if w * h < SURFACE_MIN:
        return False, f"surface {w * h} px < {SURFACE_MIN} px minimum"
    if x < 0 or y < 0 or x + w > LARGEUR or y + h > HAUTEUR:
        return False, "rectangle hors de l'image"
    if not np.all(mask_img[y:y + h, x:x + w] == 255):
        return False, "le rectangle touche le noir numérique du masque"
    return True, "OK"


def _capturer_image_figee(idx):
    """Capture une image (640x360, résolution vérifiée, warmup appliqué)
    pour servir de fond au dessin des zones."""
    cap = ouvrir_camera(idx)
    if cap is None:
        return None
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def _dessiner_zones_sur(image, zones, echelle=1):
    """Dessine rectangles + noms des zones (coordonnées multipliées par echelle)."""
    for z in zones:
        c = COULEURS_ZONES.get(z["nom"], (255, 255, 255))
        x, y, w, h = (z["x"] * echelle, z["y"] * echelle,
                      z["w"] * echelle, z["h"] * echelle)
        cv2.rectangle(image, (x, y), (x + w, y + h), c, 2)
        cv2.putText(image, z["nom"], (x, max(15, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1)


def definir_zones(idx, mask_pts, mask_img):
    """Séquence guidée de définition des zones (spec §2).

    TOUTE l'interaction (dessin, validation, aperçu final) se fait DANS la
    fenêtre vidéo — jamais via input() pendant qu'une fenêtre est ouverte :
    un input() bloquant gèle la boucle d'événements HighGUI (fenêtre grise
    ou figée), cause du bug « l'image disparaît / ne réapparaît plus »
    observé en test. Le terminal ne sert plus qu'à l'affichage.

    Touches dans la fenêtre :
      cliquer-glisser : dessiner le rectangle de la zone annoncée
      [Entrée]        : valider le rectangle proposé / enregistrer (aperçu)
      [R]             : redessiner le rectangle / tout recommencer (aperçu)
      [P]             : passer la zone (zones optionnelles uniquement)
      [A] ou ESC      : abandonner (à l'aperçu : [A] ; ESC partout)

    Sauvegarde dans ZONES_FILE (avec empreinte du masque).
    Retourne la liste des zones, ou None si abandon."""
    print("\n" + "=" * 60)
    print("🎯 DÉFINITION DES ZONES DE MESURE")
    print("=" * 60)
    print(f"\n   Caméra : {PROFIL['libelle']}")
    print("   Scène recommandée : robots au repos, bol vide, pas de cube.")
    seq = " → ".join(nom + ("" if oblig else " (opt.)")
                     for nom, oblig, _ in SEQUENCE_ZONES)
    print(f"   Séquence : {seq}")
    print("\n   Principe : le terminal annonce chaque zone ; tout le reste se")
    print("   passe DANS la fenêtre vidéo (l'image reste visible en permanence) :")
    print("   1. dessine un rectangle en MAINTENANT le bouton gauche enfoncé,")
    print("   2. relâche : le rectangle proposé s'affiche,")
    print("   3. touche [Entrée] = valider, [R] = redessiner, ESC = abandonner.")
    print("\n   Rappels (consignes de chaque zone, spec §2) :")
    for nom_z, _, _ in SEQUENCE_ZONES:
        print(f"   - {nom_z} : {CONSIGNES_ZONES.get(nom_z, '')}")
    input("\n   Appuie sur ENTRÉE pour capturer l'image de fond...")

    frame = _capturer_image_figee(idx)
    if frame is None:
        print("❌ Impossible de capturer une image.")
        return None
    frame_masquee = cv2.bitwise_and(frame, frame, mask=mask_img)

    titre = "Definition des zones"
    etat = {"depart": None, "courant": None, "fini": None}

    def callback(event, mx, my, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            etat["depart"] = (mx, my)
            etat["courant"] = (mx, my)
            etat["fini"] = None
        elif event == cv2.EVENT_MOUSEMOVE and etat["depart"] and not etat["fini"]:
            etat["courant"] = (mx, my)
        elif event == cv2.EVENT_LBUTTONUP and etat["depart"]:
            etat["fini"] = (mx, my)

    cv2.namedWindow(titre)
    cv2.setMouseCallback(titre, callback)
    cv2.waitKey(50)

    def fermer(retour):
        cv2.destroyWindow(titre)
        cv2.waitKey(50)
        return retour

    # Touches Entrée : constante module TOUCHES_ENTREE
    e = ECHELLE_AFFICHAGE

    while True:                                  # permet « tout recommencer »
        zones = []
        for nom, obligatoire, couleur in SEQUENCE_ZONES:
            print(f"\n▶ ZONE '{nom}' — {CONSIGNES_ZONES[nom]}")
            if not obligatoire:
                print("   Zone OPTIONNELLE : touche [P] dans la fenêtre pour la passer.")
            print("   Dessine le rectangle dans la fenêtre, puis [Entrée] = valider,")
            print("   [R] = redessiner, ESC = abandonner.")

            etat["depart"] = etat["courant"] = etat["fini"] = None
            rect_candidat = None
            passer = False
            abandon = False
            while True:                          # boucle d'événements de la zone
                affiche = cv2.resize(frame_masquee, (LARGEUR * e, HAUTEUR * e))
                _dessiner_zones_sur(affiche, zones, echelle=e)

                if rect_candidat is None:
                    consigne = f"Zone : {nom} - cliquer-glisser"
                    if not obligatoire:
                        consigne += "  [P = passer]"
                    consigne += "  [ESC = abandonner]"
                    if etat["depart"] and etat["courant"] and not etat["fini"]:
                        cv2.rectangle(affiche, etat["depart"], etat["courant"],
                                      (0, 255, 255), 2)
                else:
                    x, y, w, h = rect_candidat
                    cv2.rectangle(affiche, (x * e, y * e),
                                  ((x + w) * e, (y + h) * e), couleur, 2)
                    consigne = (f"Zone : {nom} - [Entree = valider] "
                                f"[R = redessiner] [ESC = abandonner]")
                cv2.putText(affiche, consigne, (15, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.imshow(titre, affiche)
                key = cv2.waitKey(20) & 0xFF

                # Relâchement souris -> proposition de rectangle (validée)
                if rect_candidat is None and etat["fini"]:
                    (x1, y1), (x2, y2) = etat["depart"], etat["fini"]
                    rect = (min(x1, x2) // e, min(y1, y2) // e,
                            abs(x2 - x1) // e, abs(y2 - y1) // e)
                    etat["depart"] = etat["courant"] = etat["fini"] = None
                    ok, msg = valider_zone(rect, mask_img)
                    if not ok:
                        print(f"   ❌ Rectangle refusé : {msg}. Redessine-le.")
                    else:
                        rect_candidat = rect
                        x, y, w, h = rect
                        print(f"   Rectangle proposé : x={x}, y={y}, w={w}, h={h} "
                              f"({w * h} px) — [Entrée] valider / [R] redessiner.")

                if key == 27:                                    # ESC
                    abandon = True
                    break
                if (rect_candidat is None and not obligatoire
                        and key in (ord('p'), ord('P'))):
                    passer = True
                    break
                if rect_candidat is not None:
                    if key in TOUCHES_ENTREE:
                        x, y, w, h = rect_candidat
                        zones.append({"nom": nom, "x": x, "y": y, "w": w, "h": h})
                        print(f"   ✅ Zone '{nom}' validée.")
                        break
                    if key in (ord('r'), ord('R')):
                        rect_candidat = None
                        print(f"   ↩️  Zone '{nom}' : redessine le rectangle.")

            if abandon:
                print("❌ Définition des zones abandonnée.")
                return fermer(None)
            if passer:
                print(f"   ⏭️  Zone '{nom}' passée.")
                continue

        # Aperçu final — validation DANS la fenêtre
        print(f"\n   Zones définies : {', '.join(z['nom'] for z in zones)}")
        print("   Dans la fenêtre : [Entrée] = enregistrer, [R] = tout recommencer,")
        print("   [A] ou ESC = abandonner.")
        decision = None
        while decision is None:
            apercu = cv2.resize(frame_masquee, (LARGEUR * e, HAUTEUR * e))
            _dessiner_zones_sur(apercu, zones, echelle=e)
            cv2.putText(apercu, "Apercu - [Entree = enregistrer] [R = recommencer] "
                                "[A/ESC = abandonner]",
                        (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow(titre, apercu)
            key = cv2.waitKey(20) & 0xFF
            if key in TOUCHES_ENTREE:
                decision = 'V'
            elif key in (ord('r'), ord('R')):
                decision = 'R'
            elif key == 27 or key in (ord('a'), ord('A')):
                decision = 'A'

        if decision == 'A':
            print("❌ Abandon — aucune zone enregistrée.")
            return fermer(None)
        if decision == 'R':
            print("\n🔄 On recommence toutes les zones.")
            continue
        break                                    # 'V' : enregistrer

    fermer(None)
    data = {
        "camera": NOM_CAMERA,
        "reference_resolution": {"width": LARGEUR, "height": HAUTEUR},
        "mask_points": [list(p) for p in mask_pts],   # empreinte du masque
        "date": datetime.now().isoformat(timespec="seconds"),
        "zones": zones,
    }
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    with open(ZONES_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Zones sauvegardées : {ZONES_FILE}")
    return zones



# ============================================
# MÉTRIQUES (spec §3)
# ============================================

def stats_zone(frame, zone):
    """Calcule M1-M8 sur la zone (image BGR 0-255).
    Retourne un dict ; ratios à None si Ḡ < 1 (garde de la spec)."""
    x, y, w, h = zone["x"], zone["y"], zone["w"], zone["h"]
    roi = frame[y:y + h, x:x + w]
    gris = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)        # Y (BT.601, M4)

    moy_b = float(np.mean(roi[:, :, 0]))
    moy_g = float(np.mean(roi[:, :, 1]))
    moy_r = float(np.mean(roi[:, :, 2]))
    garde = moy_g >= 1.0
    return {
        "R": moy_r, "G": moy_g, "B": moy_b,                              # M1
        "r_RG": (moy_r / moy_g) if garde else None,                      # M2
        "r_BG": (moy_b / moy_g) if garde else None,                      # M3
        "Y": float(np.mean(gris)),                                       # M4
        "sigma_Y": float(np.std(gris)),                                  # M5
        "med_Y": float(np.median(gris)),                                 # M6
        "pct_satures": float(np.mean(np.max(roi, axis=2) >= SEUIL_SATURE) * 100),  # M7
        "pct_sombres": float(np.mean(gris <= SEUIL_SOMBRE) * 100),       # M8
    }


def _fmt(v, dec=1):
    return "n/a" if v is None else f"{v:.{dec}f}"


def imprimer_tableau_metriques(toutes_stats):
    """Tableau M1-M8 complet dans le terminal (une section par zone)."""
    for nom, s in toutes_stats.items():
        afficher_tableau(f"Zone {nom}", [
            ("Moyennes R / G / B (M1)", f"{s['R']:.1f} / {s['G']:.1f} / {s['B']:.1f}"),
            ("Ratio R/G (M2)", _fmt(s['r_RG'], 3)),
            ("Ratio B/G (M3)", _fmt(s['r_BG'], 3)),
            ("Luminance moyenne Y (M4)", f"{s['Y']:.1f}"),
            ("Contraste sigma_Y (M5)", f"{s['sigma_Y']:.1f}"),
            ("Mediane Y (M6)", f"{s['med_Y']:.1f}"),
            (f"% pixels satures >= {SEUIL_SATURE} (M7)", f"{s['pct_satures']:.2f} %"),
            (f"% pixels sombres Y <= {SEUIL_SOMBRE} (M8)", f"{s['pct_sombres']:.2f} %"),
        ])


def mesure_stabilite(cap, mask_img, zones):
    """M9 : stabilité temporelle de Ȳ sur ~4 s, TOUTES les zones plateau
    (spec v1.2 — une ombre fluctuante peut n'affecter qu'une zone).
    Échantillonnage toutes les ~0,2 s. Imprime moyenne / sigma_t / min / max
    par zone + avertissement si fluctuation (automatisme caméra ou lumière
    instable)."""
    zones_plateau = [z for z in zones if z["nom"] in PROFIL["pilotes"]]
    if not zones_plateau:
        print("⚠️  Aucune zone plateau définie — stabilité non mesurable.")
        return

    n_total = int(STABILITE_DUREE / STABILITE_INTERVALLE)
    print(f"\n⏱️  Mesure de stabilité (M9) : {STABILITE_DUREE:.0f} s, "
          f"{n_total} échantillons, zones {', '.join(z['nom'] for z in zones_plateau)}")
    print("   Ne touche à rien pendant la mesure...")

    echantillons = {z["nom"]: [] for z in zones_plateau}
    prochain = time.monotonic()
    for k in range(n_total):
        # On continue de lire le flux pour rester en temps réel
        while time.monotonic() < prochain:
            cap.grab()
            time.sleep(0.005)
        ret, frame = cap.read()
        prochain += STABILITE_INTERVALLE
        if not ret:
            continue
        frame_m = cv2.bitwise_and(frame, frame, mask=mask_img)
        for z in zones_plateau:
            gris = cv2.cvtColor(
                frame_m[z["y"]:z["y"] + z["h"], z["x"]:z["x"] + z["w"]],
                cv2.COLOR_BGR2GRAY)
            echantillons[z["nom"]].append(float(np.mean(gris)))
        print(f"\r   Échantillon {k + 1}/{n_total}", end="", flush=True)
    print()

    instable = False
    for nom, vals in echantillons.items():
        if len(vals) < 2:
            print(f"   ⚠️  {nom} : pas assez d'échantillons.")
            continue
        arr = np.array(vals)
        sigma_t = float(np.std(arr))
        afficher_tableau(f"Stabilité M9 — {nom} ({len(vals)} échantillons)", [
            ("Y moyen", f"{np.mean(arr):.2f}"),
            ("sigma_t", f"{sigma_t:.2f}"),
            ("min / max", f"{np.min(arr):.1f} / {np.max(arr):.1f}"),
            ("étendue max-min", f"{np.max(arr) - np.min(arr):.2f}"),
        ])
        if sigma_t > 3.0:
            instable = True
            print(f"   🔴 {nom} : sigma_t > 3 — mesure NON FIABLE.")
        elif sigma_t > 1.5:
            print(f"   🟠 {nom} : sigma_t > 1,5 — fluctuation notable.")
        else:
            print(f"   🟢 {nom} : stable.")
    if instable:
        print("\n   ⚠️  Instabilité détectée : vérifie qu'aucun automatisme caméra")
        print("      n'est actif (exposition/balance AUTO) et que la lumière est stable.")


# ============================================
# VISUALISATION DES ZONES (option [2])
# ============================================

def visualiser_zones(idx, mask_img, zones):
    """Affiche une image figée masquée avec les zones dessinées, pour juger
    s'il faut les redessiner. Fermeture : N'IMPORTE QUELLE touche DANS la
    fenêtre."""
    frame = _capturer_image_figee(idx)
    if frame is None:
        print("❌ Impossible de capturer une image.")
        return
    frame_m = cv2.bitwise_and(frame, frame, mask=mask_img)
    affiche = cv2.resize(frame_m, (LARGEUR * ECHELLE_AFFICHAGE,
                                   HAUTEUR * ECHELLE_AFFICHAGE))
    _dessiner_zones_sur(affiche, zones, echelle=ECHELLE_AFFICHAGE)
    cv2.putText(affiche, "Zones actuelles - une touche pour fermer", (15, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    titre = "Zones actuelles"
    print("\n👁️  Zones affichées — une touche DANS LA FENÊTRE pour fermer.")
    while True:
        cv2.imshow(titre, affiche)
        if (cv2.waitKey(50) & 0xFF) != 255:      # 255 = aucune touche
            break
    cv2.destroyWindow(titre)
    cv2.waitKey(50)


# ============================================
# MESURE EN DIRECT (option [3])
# ============================================

def _incruster_metriques(affiche, zones, toutes_stats):
    """Incrustation compacte par zone sur l'image affichée (échelle x2)."""
    e = ECHELLE_AFFICHAGE
    for z in zones:
        s = toutes_stats.get(z["nom"])
        if s is None:
            continue
        c = COULEURS_ZONES.get(z["nom"], (255, 255, 255))
        x, y, h = z["x"] * e, z["y"] * e, z["h"] * e
        if z["nom"] == "bol":
            l1 = f"med:{s['med_Y']:.0f} sat:{s['pct_satures']:.1f}%"
            l2 = f"Y:{s['Y']:.0f}"
        elif z["nom"] == "rose":
            l1 = f"R/G:{_fmt(s['r_RG'], 2)} B/G:{_fmt(s['r_BG'], 2)}"
            l2 = f"Y:{s['Y']:.0f}"
        else:  # plateau
            l1 = f"Y:{s['Y']:.0f} sd:{s['sigma_Y']:.1f} so:{s['pct_sombres']:.1f}%"
            l2 = f"R/G:{_fmt(s['r_RG'], 2)} B/G:{_fmt(s['r_BG'], 2)}"
        cv2.putText(affiche, l1, (x + 3, y + h + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1)
        cv2.putText(affiche, l2, (x + 3, y + h + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1)


def mesurer_en_direct(idx, mask_img, zones, verrouille):
    """Flux masqué + rectangles + métriques M1-M8 recalculées toutes les
    0,5 s (D3). Touches DANS LA FENÊTRE (cohérent avec le script 7) :
      [M] : mesure de stabilité M9 (~4 s) + tableau M1-M8 dans le terminal
      [Q] : retour au menu"""
    cap = ouvrir_camera(idx)
    if cap is None:
        return

    titre = "Mesure en direct - [M] tableau+stabilite  [Q] retour menu"
    print("\n📷 Mesure en direct — les mesures démarrent immédiatement :")
    print("   tableau initial M1-M8 ci-dessous, puis valeurs mises à jour")
    print("   en continu sur l'image (toutes les 0,5 s).")
    print("   Touches DANS LA FENÊTRE :")
    print("   [M] : nouveau tableau M1-M8 + mesure de stabilité M9 (~4 s)")
    print("   [Q] : retour au menu")
    if not verrouille:
        print("   ⚠️  MESURES NON REPRÉSENTATIVES DU PIPELINE (réglages non verrouillés)")

    toutes_stats = {}
    derniere_mesure = 0.0
    table_initiale_affichee = False
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️  Lecture caméra impossible — retour au menu.")
                break
            frame_m = cv2.bitwise_and(frame, frame, mask=mask_img)

            maintenant = time.monotonic()
            if maintenant - derniere_mesure >= INTERVALLE_METRIQUES:
                toutes_stats = {z["nom"]: stats_zone(frame_m, z) for z in zones}
                derniere_mesure = maintenant
                if not table_initiale_affichee:
                    print("\n📋 Mesure initiale (M1-M8) :")
                    imprimer_tableau_metriques(toutes_stats)
                    print("\n   (suite en continu sur l'image — [M] remesurer, [Q] menu)")
                    table_initiale_affichee = True

            affiche = cv2.resize(frame_m, (LARGEUR * ECHELLE_AFFICHAGE,
                                           HAUTEUR * ECHELLE_AFFICHAGE))
            _dessiner_zones_sur(affiche, zones, echelle=ECHELLE_AFFICHAGE)
            _incruster_metriques(affiche, zones, toutes_stats)
            if not verrouille:
                cv2.putText(affiche, "REGLAGES NON VERROUILLES - NON REPRESENTATIF",
                            (15, HAUTEUR * ECHELLE_AFFICHAGE - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow(titre, affiche)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), ord('Q')):
                break
            if key in (ord('m'), ord('M')):
                if toutes_stats:
                    print("\n📋 Métriques instantanées (M1-M8) :")
                    imprimer_tableau_metriques(toutes_stats)
                mesure_stabilite(cap, mask_img, zones)
                print("\n   (retour au flux en direct — [M] pour remesurer, [Q] pour quitter)")
    finally:
        cap.release()
        cv2.destroyWindow(titre)
        cv2.waitKey(50)


# ============================================
# CAPTURE DE LA RÉFÉRENCE (étape 2, option [4])
# ============================================

def _acquerir_echantillons(idx, mask_img, zones, n, intervalle):
    """Acquisition de n frames espacées d'`intervalle` s.
    Retourne (frames_brutes, frames_masquees, stats) ou None ;
    stats : {nom_zone: [dict M1-M8 par échantillon]}."""
    cap = ouvrir_camera(idx)
    if cap is None:
        return None
    frames, frames_m = [], []
    stats = {z["nom"]: [] for z in zones}
    prochain = time.monotonic()
    try:
        for k in range(n):
            while time.monotonic() < prochain:
                cap.grab()
                time.sleep(0.005)
            ret, frame = cap.read()
            prochain += intervalle
            if not ret:
                print("\n   ⚠️  Lecture caméra impossible pendant l'acquisition.")
                return None
            fm = cv2.bitwise_and(frame, frame, mask=mask_img)
            frames.append(frame)
            frames_m.append(fm)
            for z in zones:
                stats[z["nom"]].append(stats_zone(fm, z))
            print(f"\r   Échantillon {k + 1}/{n}", end="", flush=True)
        print()
    finally:
        cap.release()
    return frames, frames_m, stats


def _imprimer_stats_reference(stats_ref):
    """Tableaux des statistiques de référence (une section par zone)."""
    for nom, s in stats_ref.items():
        afficher_tableau(f"Référence — zone {nom}", [
            ("Moyennes R / G / B", f"{s['R']:.1f} / {s['G']:.1f} / {s['B']:.1f}"),
            ("Ratio R/G", f"{s['r_RG']:.3f}"),
            ("Ratio B/G", f"{s['r_BG']:.3f}"),
            ("Luminance moyenne Y", f"{s['Y']:.1f}"),
            ("Contraste sigma_Y", f"{s['sigma_Y']:.1f}"),
            ("Mediane Y (moy. des médianes)", f"{s['med_Y']:.1f}"),
            ("% pixels satures", f"{s['pct_satures']:.2f} %"),
            ("% pixels sombres", f"{s['pct_sombres']:.2f} %"),
            ("Stabilité sigma_t", f"{s['sigma_t']:.2f}"),
        ])


def _verifier_caducite(data, mask_pts, zones):
    """Retourne la liste des raisons de caducité d'une référence
    (liste vide = référence valide). Une référence est caduque si le
    masque OU les zones ont changé depuis sa capture : dans les deux cas,
    ses statistiques ne sont plus comparables aux mesures actuelles."""
    raisons = []
    if data.get("mask_points") != [list(p) for p in mask_pts]:
        raisons.append("le masque caméra a changé depuis la capture")
    if zones is None:
        raisons.append("les zones actuelles sont absentes ou invalides "
                       "(comparaison impossible)")
    elif data.get("zones") != zones:
        raisons.append("les zones de mesure ont changé depuis la capture")
    return raisons


def _resume_reference(data, mask_pts, zones):
    """Résumé d'une référence pour décision éclairée (garder/remplacer) :
    date, note, Y et sigma_t des plateaux, réglages capturés, statut."""
    stats = data.get("stats", {})
    plateaux = {n: s for n, s in stats.items() if n in PROFIL["pilotes"]}
    y_txt = ", ".join(f"{n}: {s.get('Y', 0):.1f}" for n, s in plateaux.items()) or "?"
    st_txt = ", ".join(f"{n}: {s.get('sigma_t', 0):.2f}" for n, s in plateaux.items()) or "?"
    raisons = _verifier_caducite(data, mask_pts, zones)
    statut = "VALIDE ✓" if not raisons else "CADUQUE ⚠️ (" + " ; ".join(raisons) + ")"
    afficher_tableau("Référence existante", [
        ("Date", data.get("date", "?")),
        ("Note", data.get("note", "") or "(vide)"),
        ("Y plateaux", y_txt),
        ("sigma_t plateaux", st_txt),
        ("Réglages caméra capturés", "oui" if data.get("reglages_camera") else "NON ⚠️"),
        ("Statut", statut),
    ])
    return raisons


def _confirmer_checklist(action):
    """Check-list de la scène de référence (spec Étape 0 §1) — affichée
    avant CHAQUE capture de référence et CHAQUE diagnostic : toute mesure
    faite hors de cette scène n'est pas comparable.
    Retourne True si l'utilisateur confirme (Entrée), False si annulation."""
    items = [
        "Robots Leader et Follower en position REPOS",
        "Bol blanc en place, VIDE",
        "Cube ABSENT du plateau",
        "Plateau en position d'enregistrement, propre, rien d'autre",
        PROFIL["checklist_camera"],
        "Les deux caméras branchées",
        "Réglages caméra verrouillés via camera_settings.json "
        "(contrôlé automatiquement par l'outil)",
        f"Résolution / FPS : {LARGEUR}x{HAUTEUR} @ {FPS} fps "
        "(contrôlé automatiquement par l'outil)",
    ]
    if PROFIL["masque"]:
        items.append("Image mesurée avec camera_mask.json appliqué "
                     "(contrôlé automatiquement par l'outil)")
    items.append("Éclairage stable (pas de mouvement, pas de nuages rapides)")
    print("\n" + "=" * 60)
    print(f"📋 CHECK-LIST SCÈNE DE RÉFÉRENCE — {PROFIL['libelle']}")
    print("=" * 60)
    for item in items:
        print(f"   – {item}")
    print(f"\n  [Entrée] : scène conforme, {action}")
    print("  [Q]      : annuler")
    while True:
        rep = input("Choix : ").strip().upper()
        if rep in ("", "Q"):
            break
        print(f"   ⚠️  Saisie '{rep}' non reconnue — Entrée ou Q.")
    return rep == ""


def capturer_reference(idx, mask_pts, mask_img, zones, verrouille):
    """Étape 2 : capture de la référence ACTIVE (option [4]).

    Décisions validées :
      D1 : capture BLOQUÉE si les réglages caméra ne sont pas verrouillés
           (le mode dégradé sert à tester l'outil, jamais à produire une
           référence officielle).
      D2 : porte de stabilité STRICTE — refus dès qu'un sigma_t plateau
           dépasse 1,5 (seuil 🟢 de C9). La référence est le point zéro du
           système : pas de zone orange avec confirmation ici.
      D3 : statistiques = MOYENNE de 20 échantillons sur ~4 s ; images
           témoins = la frame RÉELLE la plus représentative (luminance
           plateau la plus proche de la moyenne d'acquisition) — ni frame
           moyenne artificielle, ni dernière frame arbitraire.

    Sauvegarde (spec Étape 0 §6) : REF_FILE (stats par zone + sigma_t +
    copie des réglages caméra + empreinte du masque + zones + métadonnées
    + note libre), REF_RAW_PNG et REF_MASKED_PNG (frame témoin)."""
    # ----- Garde-fous (D1) -----
    if not verrouille:
        print("\n❌ Capture refusée : réglages caméra NON VERROUILLÉS.")
        print("   Une référence officielle exige les réglages du pipeline")
        print("   (camera_settings.json — règle-les depuis le menu avec [R]).")
        return

    # ----- Référence existante : résumé enrichi + [Entrée] garder / [R] refaire -----
    if REF_FILE.exists():
        try:
            with open(REF_FILE, 'r') as f:
                ancienne = json.load(f)
        except Exception:
            ancienne = None
        if ancienne:
            print("\n📂 Une référence active existe déjà :")
            raisons = _resume_reference(ancienne, mask_pts, zones)
            if raisons:
                print("   ⚠️  Cette référence est CADUQUE — remplacement recommandé ([R]).")
            print("\n  [Entrée] : garder cette référence (annuler la capture)")
            print("  [R]      : la remplacer par une nouvelle capture")
            while True:
                rep = input("Choix : ").strip().upper()
                if rep in ("", "R"):
                    break
                print(f"   ⚠️  Saisie '{rep}' non reconnue — Entrée ou R.")
            if rep != "R":
                print("   ✅ Référence conservée — capture annulée.")
                return

    # ----- Check-list de la scène (spec Étape 0 §1) -----
    if not _confirmer_checklist("lancer la capture"):
        print("   Capture annulée.")
        return

    print("\n   📝 Note libre : décris le contexte d'éclairage de cette capture.")
    print("      Elle est enregistrée dans la référence et te permettra plus")
    print("      tard de savoir dans quelles conditions elle a été prise")
    print("      (utile dès que plusieurs sessions ou références coexistent).")
    print("      Exemple : « lumière du jour, store mi-clos, plafonnier allumé »")
    note = input("   Note (Entrée pour laisser vide) : ").strip()

    # ----- Acquisition -----
    duree = REF_N_ECHANTILLONS * STABILITE_INTERVALLE
    print(f"\n⏱️  Acquisition : {REF_N_ECHANTILLONS} échantillons sur "
          f"{duree:.0f} s. Ne touche à rien...")
    res = _acquerir_echantillons(idx, mask_img, zones,
                                 REF_N_ECHANTILLONS, STABILITE_INTERVALLE)
    if res is None:
        print("❌ Capture échouée (acquisition impossible).")
        return
    frames, frames_m, stats = res

    for nom, liste in stats.items():
        if any(s["r_RG"] is None or s["r_BG"] is None for s in liste):
            print(f"\n❌ Capture refusée : zone '{nom}' trop sombre "
                  f"(ratios couleur non calculables).")
            return

    # ----- Statistiques moyennées + sigma_t par zone -----
    cles = ("R", "G", "B", "r_RG", "r_BG", "Y",
            "sigma_Y", "med_Y", "pct_satures", "pct_sombres")
    stats_ref = {}
    for nom, liste in stats.items():
        moy = {c: float(np.mean([s[c] for s in liste])) for c in cles}
        moy["sigma_t"] = float(np.std([s["Y"] for s in liste]))
        stats_ref[nom] = moy

    # ----- Porte de stabilité STRICTE (D2) -----
    instables = [(nom, s["sigma_t"]) for nom, s in stats_ref.items()
                 if nom in PROFIL["pilotes"] and s["sigma_t"] > REF_SIGMA_T_MAX]
    if instables:
        print("\n❌ Capture refusée — lumière instable pendant l'acquisition :")
        for nom, st in instables:
            print(f"   {nom} : sigma_t = {st:.2f} (maximum autorisé : "
                  f"{REF_SIGMA_T_MAX})")
        print("   Vérifie : automatismes caméra coupés ? lampe qui scintille ?")
        print("   mouvement dans la scène ? Puis recommence la capture.")
        return

    # ----- Frame témoin représentative (D3) -----
    noms_plateau = [z["nom"] for z in zones if z["nom"] in PROFIL["pilotes"]]
    y_par_frame = [float(np.mean([stats[nom][k]["Y"] for nom in noms_plateau]))
                   for k in range(len(frames))]
    cible = float(np.mean(y_par_frame))
    k_temoin = int(np.argmin([abs(y - cible) for y in y_par_frame]))

    # ----- Sauvegarde -----
    reglages = charger_reglages_camera(NOM_CAMERA) if charger_reglages_camera else None
    data = {
        "camera": NOM_CAMERA,
        "date": datetime.now().isoformat(timespec="seconds"),
        "note": note,
        "resolution": {"width": LARGEUR, "height": HAUTEUR},
        "fps_demande": FPS,
        "acquisition": {
            "n_echantillons": REF_N_ECHANTILLONS,
            "intervalle_s": STABILITE_INTERVALLE,
            "frame_temoin_index": k_temoin,
            "critere_temoin": "luminance plateau la plus proche de la moyenne",
            "porte_stabilite_sigma_t_max": REF_SIGMA_T_MAX,
        },
        "reglages_camera": reglages,
        "mask_points": [list(p) for p in mask_pts],   # empreinte du masque
        "zones": zones,
        "stats": stats_ref,
    }
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    # ----- Sauvegarde CONTRÔLÉE par temporaires et bascule finale -----
    # (pas « atomique » au sens strict : os.replace est atomique PAR fichier,
    # les trois bascules ne forment pas une transaction unique — fenêtre
    # résiduelle de quelques ms en cas de crash système entre deux replace.
    # Amélioration possible si nécessaire : images versionnées par capture_id
    # référencées dans le JSON.)
    # Sans temporaires, remplacer une référence existante pourrait laisser un
    # état incohérent (nouvelles images + ancien JSON) si l'écriture échoue.
    # Les temporaires des images gardent l'extension .png (cv2.imwrite
    # choisit l'encodeur d'après l'extension). Le JSON est basculé en
    # DERNIER : c'est le point de validation de la capture.
    tmp_raw = REF_RAW_PNG.with_name(REF_RAW_PNG.stem + "_tmp.png")
    tmp_masked = REF_MASKED_PNG.with_name(REF_MASKED_PNG.stem + "_tmp.png")
    tmp_json = REF_FILE.with_name(REF_FILE.stem + "_tmp.json")

    def _nettoyer_tmp():
        for p in (tmp_raw, tmp_masked, tmp_json):
            p.unlink(missing_ok=True)

    ok_raw = cv2.imwrite(str(tmp_raw), frames[k_temoin])
    ok_masked = (cv2.imwrite(str(tmp_masked), frames_m[k_temoin])
                 if PROFIL["masque"] else True)
    if (not ok_raw or not ok_masked or not tmp_raw.exists()
            or (PROFIL["masque"] and not tmp_masked.exists())):
        print("\n❌ Échec d'écriture des images témoins — référence NON modifiée.")
        print(f"   Vérifie les droits/espace disque sur {CALIB_DIR}")
        _nettoyer_tmp()
        return
    try:
        with open(tmp_json, 'w') as f:
            json.dump(data, f, indent=2)
        with open(tmp_json, 'r') as f:      # relecture : JSON lisible ?
            json.load(f)
    except Exception as e:
        print(f"\n❌ Échec d'écriture/relecture du JSON ({e}) — référence NON modifiée.")
        _nettoyer_tmp()
        return
    os.replace(tmp_raw, REF_RAW_PNG)
    if PROFIL["masque"]:
        os.replace(tmp_masked, REF_MASKED_PNG)
    os.replace(tmp_json, REF_FILE)          # point de validation final

    print("\n✅ Référence capturée et sauvegardée :")
    print(f"   {REF_FILE}")
    print(f"   {REF_RAW_PNG}")
    if PROFIL["masque"]:
        print(f"   {REF_MASKED_PNG}")
    print(f"   Frame témoin : échantillon {k_temoin + 1}/{len(frames)} "
          f"(le plus représentatif)")
    _imprimer_stats_reference(stats_ref)


def afficher_reference(mask_pts, zones):
    """Option [5] : affiche la référence active — métadonnées, réglages
    caméra capturés, statistiques par zone, existence des images témoins.
    Contrôle de caducité complet : masque ET zones (redessiner les zones
    rend la référence obsolète même si le masque n'a pas changé)."""
    if not REF_FILE.exists():
        print(f"\n❌ Aucune référence active ({REF_FILE}).")
        print("   Capture-la avec l'option [4].")
        return
    try:
        with open(REF_FILE, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"\n❌ Référence illisible ({e}) — recapture nécessaire (option [4]).")
        return

    print("\n📂 RÉFÉRENCE ACTIVE")
    acq = data.get("acquisition", {})
    res = data.get("resolution", {})
    idx_t = acq.get("frame_temoin_index")
    n_ech = acq.get("n_echantillons")
    temoin_txt = (f"échantillon {idx_t + 1}/{n_ech}"
                  if isinstance(idx_t, int) and isinstance(n_ech, int) else "?")
    afficher_tableau("Métadonnées", [
        ("Caméra", data.get("camera", "?")),
        ("Date", data.get("date", "?")),
        ("Note", data.get("note", "") or "(vide)"),
        ("Résolution", f"{res.get('width', '?')}x{res.get('height', '?')}"),
        ("FPS demandé", data.get("fps_demande", "?")),
        ("Échantillons moyennés", acq.get("n_echantillons", "?")),
        ("Frame témoin", temoin_txt),
    ])
    reglages = data.get("reglages_camera") or {}
    afficher_tableau("Réglages caméra d'origine (à la capture)",
                     list(reglages.items()) if reglages else [("(aucun)", "")])

    recal = data.get("reglages_recalibres") or None
    if recal:
        afficher_tableau(
            f"Réglages recalibrés (le {data.get('date_recalibrage', '?')})",
            list(recal.items()))
        print("\n   ↪ Le diagnostic [6] accepte actuellement : origine OU recalibrage.")
    else:
        print("\n   ↪ Le diagnostic [6] accepte actuellement : origine uniquement.")

    raisons = _verifier_caducite(data, mask_pts, zones)
    if raisons:
        print("\n⚠️  ATTENTION — cette référence est CADUQUE :")
        for r in raisons:
            print(f"   - {r}")
        print("   Recapture nécessaire (option [4]).")

    stats = data.get("stats", {})
    if stats:
        _imprimer_stats_reference(stats)

    print("\n   Images témoins :")
    # La caméra pince n'a pas de masque → pas d'image _masked (c'est normal).
    chemins = [REF_RAW_PNG] + ([REF_MASKED_PNG] if PROFIL["masque"] else [])
    for chemin in chemins:
        etat = "présent ✓" if chemin.exists() else "MANQUANT ❌"
        print(f"   {chemin.name} {'.' * max(2, 42 - len(chemin.name))} {etat}")
    if not all(c.exists() for c in chemins):
        print("   ⚠️  Référence INCOMPLÈTE (image témoin manquante) — recapture recommandée.")


# ============================================
# DIAGNOSTIC DE CONFORMITÉ (étape 3, option [6])
# ============================================

def _verdict_3(valeur, seuil_vert, seuil_orange):
    """Verdict 🟢/🟠/🔴 d'une valeur d'écart contre ses deux seuils."""
    if valeur <= seuil_vert:
        return "🟢"
    if valeur <= seuil_orange:
        return "🟠"
    return "🔴"


_SEVERITE = {"🟢": 0, "🟠": 1, "🔴": 2}


_CLES_STATS = ("R", "G", "B", "r_RG", "r_BG", "Y",
               "sigma_Y", "med_Y", "pct_satures", "pct_sombres")


def _mesurer_zones(idx, mask_img, zones, n=REF_N_ECHANTILLONS):
    """Acquisition de n échantillons et moyenne par zone (+ sigma_t).
    Retourne le dict {zone: stats moyennées}, ou None si échec/zone sombre."""
    res = _acquerir_echantillons(idx, mask_img, zones, n, STABILITE_INTERVALLE)
    if res is None:
        return None
    _, _, stats = res
    for nom, liste in stats.items():
        if any(s["r_RG"] is None or s["r_BG"] is None for s in liste):
            print(f"\n❌ Mesure impossible : zone '{nom}' trop sombre "
                  f"(ratios couleur non calculables).")
            return None
    cour = {}
    for nom, liste in stats.items():
        moy = {c: float(np.mean([s[c] for s in liste])) for c in _CLES_STATS}
        moy["sigma_t"] = float(np.std([s["Y"] for s in liste]))
        cour[nom] = moy
    return cour


def _evaluer_conformite(cour, refs, zones):
    """Évaluation PURE (aucun affichage, aucune mesure) des critères C1-C9.
    Retourne (resultats, global_v) où resultats est la liste
    (code, libellé, verdict, texte) et global_v le pire verdict.
    Si C9 = 🔴 (mesure instable), retourne ([...C9...], '🔴') sans C1-C8 :
    l'appelant suspend alors le diagnostic."""
    noms_plateau = [z["nom"] for z in zones if z["nom"] in PROFIL["pilotes"]]

    sigmas = {n: cour[n]["sigma_t"] for n in noms_plateau}
    pire_sigma = max(sigmas.values())
    v9 = _verdict_3(pire_sigma, *SEUILS["C9"])
    res_c9 = ("C9", "Stabilité temporelle", v9,
              f"sigma_t max = {pire_sigma:.2f} "
              f"(seuils {SEUILS['C9'][0]}/{SEUILS['C9'][1]})")
    if v9 == "🔴":
        return [res_c9], "🔴"

    def pire_plateau(fn):
        valeurs = {n: fn(n) for n in noms_plateau}
        nom = max(valeurs, key=valeurs.get)
        return valeurs[nom], nom

    def ecart_ratio_pct(nom):
        r, c = refs[nom], cour[nom]
        return max(abs(c["r_RG"] - r["r_RG"]) / r["r_RG"],
                   abs(c["r_BG"] - r["r_BG"]) / r["r_BG"]) * 100

    e1, z1 = pire_plateau(lambda n: abs(cour[n]["Y"] - refs[n]["Y"]))
    e2, z2 = pire_plateau(ecart_ratio_pct)
    e3, z3 = pire_plateau(lambda n: abs(cour[n]["sigma_Y"] - refs[n]["sigma_Y"]))
    d_i = [cour[n]["Y"] - refs[n]["Y"] for n in noms_plateau]
    e4 = max(d_i) - min(d_i)
    e7, z7 = pire_plateau(lambda n: abs(cour[n]["pct_sombres"] - refs[n]["pct_sombres"]))
    sent = PROFIL["sentinelle"]
    e8 = max(abs(cour[sent]["r_RG"] - refs[sent]["r_RG"]) / refs[sent]["r_RG"],
             abs(cour[sent]["r_BG"] - refs[sent]["r_BG"]) / refs[sent]["r_BG"]) * 100

    resultats = [
        ("C1", "Luminosité zones pilotes", _verdict_3(e1, *SEUILS["C1"]),
         f"|ΔY| = {e1:.1f} (seuils {SEUILS['C1'][0]}/{SEUILS['C1'][1]} ; pire : {z1})"),
        ("C2", "Balance des blancs", _verdict_3(e2, *SEUILS["C2"]),
         f"Δratio = {e2:.1f} % (seuils {SEUILS['C2'][0]}/{SEUILS['C2'][1]} % ; pire : {z2})"),
        ("C3", "Contraste zones pilotes", _verdict_3(e3, *SEUILS["C3"]),
         f"|Δsigma_Y| = {e3:.1f} (seuils {SEUILS['C3'][0]}/{SEUILS['C3'][1]} ; pire : {z3})"),
        ("C4", "Homogénéité spatiale", _verdict_3(e4, *SEUILS["C4"]),
         f"Δ_inter = {e4:.1f} (seuils {SEUILS['C4'][0]}/{SEUILS['C4'][1]})"),
    ]
    if PROFIL["bol"]:
        e5 = abs(cour["bol"]["pct_satures"] - refs["bol"]["pct_satures"])
        e6 = abs(cour["bol"]["med_Y"] - refs["bol"]["med_Y"])
        resultats.append(("C5", "Saturation bol", _verdict_3(e5, *SEUILS["C5"]),
            f"|Δsat| = {e5:.2f} pt (seuils {SEUILS['C5'][0]}/{SEUILS['C5'][1]} pt)"))
        resultats.append(("C6", "Luminosité bol", _verdict_3(e6, *SEUILS["C6"]),
            f"|Δmed| = {e6:.1f} (seuils {SEUILS['C6'][0]}/{SEUILS['C6'][1]})"))
    resultats.append(("C7", "Pixels sombres pilotes", _verdict_3(e7, *SEUILS["C7"]),
        f"|Δsombres| = {e7:.2f} pt (seuils {SEUILS['C7'][0]}/{SEUILS['C7'][1]} pt ; pire : {z7})"))
    resultats.append(("C8", f"Couleur {PROFIL['sentinelle_libelle']}",
        "🟢" if e8 <= SEUILS["C8"][0] else "🟠",
        f"Δratio = {e8:.1f} % (seuil {SEUILS['C8'][0]} % ; plafonné à orange)"))
    resultats.append(res_c9)
    global_v = max((v for _, _, v, _ in resultats), key=lambda v: _SEVERITE[v])
    return resultats, global_v


def _afficher_rapport(resultats, global_v, cour, refs, zones, ref_date):
    """Rapport terminal complet d'un diagnostic (sans boîte noire)."""
    print("\n" + "=" * 60)
    print("🩺 DIAGNOSTIC DE CONFORMITÉ — vs référence du", ref_date)
    print("=" * 60)
    afficher_tableau("Diagnostic par critère", [
        (f"{code} {libelle}", f"{verdict}  {texte}")
        for code, libelle, verdict, texte in resultats
    ])
    print("\n📊 Détail par zone (courant / référence / écart) :")
    for z in zones:
        n = z["nom"]
        c, r = cour[n], refs[n]
        afficher_tableau(f"Zone {n}", [
            ("Y", f"{c['Y']:.1f} / {r['Y']:.1f} / {c['Y'] - r['Y']:+.1f}"),
            ("R/G", f"{c['r_RG']:.3f} / {r['r_RG']:.3f} / {c['r_RG'] - r['r_RG']:+.3f}"),
            ("B/G", f"{c['r_BG']:.3f} / {r['r_BG']:.3f} / {c['r_BG'] - r['r_BG']:+.3f}"),
            ("sigma_Y", f"{c['sigma_Y']:.1f} / {r['sigma_Y']:.1f} / {c['sigma_Y'] - r['sigma_Y']:+.1f}"),
            ("% saturés", f"{c['pct_satures']:.2f} / {r['pct_satures']:.2f} / {c['pct_satures'] - r['pct_satures']:+.2f}"),
            ("% sombres", f"{c['pct_sombres']:.2f} / {r['pct_sombres']:.2f} / {c['pct_sombres'] - r['pct_sombres']:+.2f}"),
            ("médiane Y", f"{c['med_Y']:.1f} / {r['med_Y']:.1f} / {c['med_Y'] - r['med_Y']:+.1f}"),
            ("sigma_t", f"{c['sigma_t']:.2f}"),
        ])
    print("\n" + "=" * 60)
    print(f"  VERDICT GLOBAL : {global_v}")
    print("=" * 60)
    _qualifier_ecart(resultats, global_v, cour)


def _qualifier_ecart(resultats, global_v, cour):
    """Qualification GLOBAL/LOCAL (spec §4) + avertissement saturation."""
    v = {code: verdict for code, _, verdict, _ in resultats}
    if (v.get("C1", "🟢") != "🟢" or v.get("C2", "🟢") != "🟢") and v.get("C4", "🟢") == "🟢":
        print("  ↪ Écart GLOBAL : toutes les zones dérivent ensemble —")
        print("    rattrapable par réglage caméra (exposition, gain,")
        print("    balance des blancs) ou par l'éclairage général.")
    if v.get("C4", "🟢") != "🟢" or v.get("C7", "🟢") != "🟢":
        print("  ↪ Écart LOCAL : géométrie de la lumière (ombre portée,")
        print("    soleil rasant, reflet) — NON rattrapable par la caméra,")
        print("    agir sur la pièce (store, lampe, position).")
    if global_v == "🟢":
        print("  ↪ Conditions conformes à la référence.")
    if PROFIL["bol"] and cour["bol"]["pct_satures"] > SATURATION_ABS_AVERTISSEMENT:
        print(f"\n  ℹ️  Saturation absolue du bol : "
              f"{cour['bol']['pct_satures']:.1f} % > "
              f"{SATURATION_ABS_AVERTISSEMENT:.0f} % — perte d'information")
        print("     possible (contours fusionnés). Informatif, non bloquant.")


def _afficher_instable(cour, zones, texte_c9):
    """Affichage du cas MESURE INSTABLE (C9 🔴), détaillé par zone plateau
    (principe « pas de boîte noire »). Partagé par [6] et [7]."""
    print("\n🔴 MESURE INSTABLE — diagnostic SUSPENDU (aucun verdict rendu).")
    print(f"   {texte_c9}")
    for z in zones:
        if z["nom"] in PROFIL["pilotes"]:
            print(f"   {z['nom']} : sigma_t = {cour[z['nom']]['sigma_t']:.2f} "
                  f"(seuils {SEUILS['C9'][0]}/{SEUILS['C9'][1]})")
    print("   Vérifie : automatismes caméra coupés ? lampe qui scintille ?")
    print("   mouvement dans la scène ? Puis recommence.")


def _afficher_action_recommandee(resultats, global_v, cour, refs, zones):
    """Bloc ACTION RECOMMANDÉE de l'option [6] : traduit le verdict en
    consigne opérateur (« quoi faire maintenant »).
    [6] = diagnostic + ORIENTATION (vers [7] ou vers une action physique) ;
    le mode d'emploi guvcview détaillé (valeurs, contrôles interdits)
    appartient à [7], là où l'action se fait — il n'est PAS dupliqué ici."""
    v = {code: verdict for code, _, verdict, _ in resultats}
    noms_plateau = [z["nom"] for z in zones if z["nom"] in PROFIL["pilotes"]]
    local = v.get("C4", "🟢") != "🟢" or v.get("C7", "🟢") != "🟢"

    print("\n" + "=" * 60)
    print("🛠️  ACTION RECOMMANDÉE")
    print("=" * 60)

    if global_v == "🟢":
        print("🟢 Conditions conformes. Aucune action nécessaire.")
        return

    if local:
        print("Écart LOCAL détecté (lumière non uniforme sur la scène).")
        print("Ne lance PAS guvcview en priorité : aucun réglage caméra ne")
        print("corrige une ombre, un reflet ou un soleil rasant.")
        print("\nAction conseillée :")
        print("1. Corrige physiquement la scène : ombre portée, reflet,")
        print("   objet parasite, soleil direct, lampe trop proche.")
        print("2. Relance le diagnostic [6].")
        if (v.get("C1", "🟢") != "🟢" or v.get("C2", "🟢") != "🟢"
                or v.get("C5", "🟢") != "🟢" or v.get("C6", "🟢") != "🟢"):
            print("3. Si un écart global subsiste ensuite : lance le")
            print("   recalibrage guidé [7].")
        return

    # Écart GLOBAL (orange ou rouge) : cause probable + sens
    dY = float(np.mean([cour[n]["Y"] - refs[n]["Y"] for n in noms_plateau]))
    dRG = float(np.mean([cour[n]["r_RG"] - refs[n]["r_RG"] for n in noms_plateau]))
    dBG = float(np.mean([cour[n]["r_BG"] - refs[n]["r_BG"] for n in noms_plateau]))
    chaude = dRG > 0 or dBG < 0

    if global_v == "🟠":
        print("🟠 Conditions non conformes, mais probablement corrigeables.")
    else:
        print("🔴 Conditions trop éloignées de la référence.")

    print("\nCause probable :")
    if v.get("C1", "🟢") != "🟢" or v.get("C6", "🟢") != "🟢":
        print(f"- Image globalement trop {'CLAIRE' if dY > 0 else 'SOMBRE'} "
              f"(ΔY moyen plateau : {dY:+.1f}).")
    if v.get("C2", "🟢") != "🟢" or v.get("C8", "🟢") != "🟢":
        print(f"- Dominante {'CHAUDE (rougeâtre)' if chaude else 'FROIDE (bleutée)'}.")
    if v.get("C5", "🟢") != "🟢":
        print("- Bol saturé (reflet ou surexposition).")
    if v.get("C3", "🟢") != "🟢":
        print("- Contraste du plateau modifié (souvent lié à la luminosité).")

    print("\nAction conseillée :")
    print("1. Lance l'option [7] « Recalibrer pour REVENIR à la référence ».")
    print("2. Ne redessine PAS les zones.")
    print("3. Ne recapture PAS de nouvelle référence.")
    print("4. Suis l'aide guvcview de [7] (contrôles exacts, valeurs")
    print("   d'essai) jusqu'à retrouver un verdict 🟢.")
    if global_v == "🔴":
        print("5. Si [7] ne ramène pas au 🟢 : vérifie la scène (caméra")
        print("   déplacée ? éclairage radicalement différent ?) avant")
        print("   d'envisager une recapture de référence [4].")
    if v.get("C9", "🟢") == "🟠":
        print("\nℹ️  Mesure légèrement fluctuante (C9 🟠) : vérifie la")
        print("   stabilité de la lumière avant/pendant le recalibrage.")


def _verifier_reference_et_reglages(mask_pts, zones):
    """Garde-fous de comparabilité partagés entre l'option [6] et l'API
    d'intégration (étape 5) : référence existante, lisible, non caduque,
    réglages actuels = origine OU recalibrage validé, statistiques
    complètes. Ne vérifie PAS le verrouillage (garanti par l'appelant).
    Retourne (ref, refs, erreurs) — erreurs est une liste de lignes,
    vide si tout est conforme (ref/refs valent alors les données)."""
    if not REF_FILE.exists():
        return None, None, [f"aucune référence active ({REF_FILE})",
                            "capture-la d'abord (outil, option [4])"]
    try:
        with open(REF_FILE, 'r') as f:
            ref = json.load(f)
    except Exception as e:
        return None, None, [f"référence illisible ({e})"]
    raisons = _verifier_caducite(ref, mask_pts, zones)
    if raisons:
        lignes = ["la référence est CADUQUE :"]
        lignes += [f"- {r}" for r in raisons]
        lignes.append("recapture nécessaire (outil, option [4])")
        return None, None, lignes
    ref_regl = ref.get("reglages_camera") or None
    if not ref_regl:
        return None, None, ["la référence ne contient pas de réglages caméra "
                            "— recapture nécessaire (outil, option [4])"]
    # Réglages acceptés : origine OU dernier recalibrage validé 🟢 (étape 4)
    # — dans les deux cas, prouvés reproduire l'image de référence.
    actuels = charger_reglages_camera(NOM_CAMERA) if charger_reglages_camera else None
    recal = ref.get("reglages_recalibres") or None
    if actuels != ref_regl and actuels != recal:
        lignes = ["les réglages caméra actuels ne correspondent ni aux réglages",
                  "d'origine de la référence, ni à un recalibrage validé.",
                  "Le diagnostic mesurerait « lumière + réglages », ininterprétable.",
                  "Contrôles divergents (actuel ≠ origine) :"]
        for k in sorted(set(list((actuels or {}).keys()) + list(ref_regl.keys()))):
            va = (actuels or {}).get(k, "—")
            vr = ref_regl.get(k, "—")
            if va != vr:
                lignes.append(f"- {k} : {va} ≠ {vr}")
        lignes.append("→ restaure des réglages connus, recalibre (option [7]),")
        lignes.append("  ou recapture une référence (option [4])")
        return None, None, lignes
    refs = ref.get("stats", {})
    for z in zones:
        if z["nom"] not in refs:
            return None, None, [f"zone '{z['nom']}' absente des statistiques "
                                "de la référence — recapture nécessaire"]
    return ref, refs, []


def diagnostic_conformite(idx, mask_pts, mask_img, zones, verrouille):
    """Étape 3 : diagnostic ponctuel de conformité vs la référence active
    (option [6]). Acquisition identique à la capture (20 échantillons,
    ~4 s) pour une comparabilité maximale.

    Garde-fous (comparabilité) :
      - réglages verrouillés ET identiques à ceux stockés dans la
        référence (un camera_settings.json modifié puis verrouillé
        mesurerait « lumière + réglages », ininterprétable) ;
      - référence existante, lisible, NON caduque (masque + zones) ;
      - check-list de la scène confirmée.

    Ordre d'évaluation :
      1. C9 d'abord : sigma_t plateau > 3 → MESURE INSTABLE, diagnostic
         suspendu (aucun verdict) ; entre 1,5 et 3 → C9 🟠 signalé.
      2. C1-C8 contre la référence, pire-des-zones par critère,
         C8 plafonné à 🟠. Score global = pire critère.
      3. Rapport terminal complet (« pas de boîte noire ») + qualification
         écart GLOBAL (rattrapable par réglage) / LOCAL (agir sur la pièce)
         + avertissement informatif si saturation absolue bol > 5 %.

    Le diagnostic n'écrit RIEN (D3) : la journalisation appartient à
    l'intégration au script 8 (étape 5)."""
    # ----- Garde-fous -----
    if not verrouille:
        print("\n❌ Diagnostic refusé : réglages caméra NON VERROUILLÉS.")
        return
    ref, refs, erreurs = _verifier_reference_et_reglages(mask_pts, zones)
    if erreurs:
        print("\n❌ Diagnostic refusé :")
        for ligne in erreurs:
            print(f"   {ligne}")
        return

    # ----- Check-list (même scène que la référence) -----
    if not _confirmer_checklist("lancer le diagnostic"):
        print("   Diagnostic annulé.")
        return

    # ----- Acquisition (identique à la capture) -----
    duree = REF_N_ECHANTILLONS * STABILITE_INTERVALLE
    print(f"\n⏱️  Acquisition : {REF_N_ECHANTILLONS} échantillons sur "
          f"{duree:.0f} s. Ne touche à rien...")
    cour = _mesurer_zones(idx, mask_img, zones)
    if cour is None:
        print("❌ Diagnostic échoué (acquisition impossible).")
        return

    resultats, global_v = _evaluer_conformite(cour, refs, zones)

    # C9 d'abord : la mesure est-elle fiable ?
    if global_v == "🔴" and len(resultats) == 1:   # seul C9 présent = instable
        _afficher_instable(cour, zones, resultats[0][3])
        return

    _afficher_rapport(resultats, global_v, cour, refs, zones,
                      ref.get("date", "?"))
    _afficher_action_recommandee(resultats, global_v, cour, refs, zones)


# ============================================
# RECALIBRAGE GUIDÉ (étape 4, option [7])
# ============================================

def _afficher_aide_guvcview(resultats, cour, refs, zones):
    """Aide opérateur : traduit le diagnostic C1-C9 en actions concrètes
    dans guvcview, avec les NOMS EXACTS des contrôles de l'interface, les
    valeurs actuelles et un exemple d'essai. Ne modifie aucun réglage.

    Logique des sens (identique à l'évaluation) :
      - trop clair/sombre : moyenne des ΔY plateau (C1), Δmédiane bol (C6) ;
      - dominante : ΔR/G > 0 ou ΔB/G < 0 → chaude ; inverse → froide ;
      - C4/C7 hors vert : écart LOCAL, priorité à la correction physique ;
      - C5 hors vert : reflet/surexposition du bol, physique d'abord."""
    v = {code: verdict for code, _, verdict, _ in resultats}
    noms_plateau = [z["nom"] for z in zones if z["nom"] in PROFIL["pilotes"]]
    actuels = (charger_reglages_camera(NOM_CAMERA)
               if charger_reglages_camera else None) or {}
    expo = actuels.get("exposure_time_absolute")
    wb = actuels.get("white_balance_temperature")
    gain = actuels.get("gain")

    print("\n" + "=" * 60)
    print("🎛️  AIDE GUVCVIEW — QUE FAUT-IL TOUCHER ?")
    print("=" * 60)

    # ----- Diagnostic résumé -----
    dY = float(np.mean([cour[n]["Y"] - refs[n]["Y"] for n in noms_plateau]))
    dRG = float(np.mean([cour[n]["r_RG"] - refs[n]["r_RG"] for n in noms_plateau]))
    dBG = float(np.mean([cour[n]["r_BG"] - refs[n]["r_BG"] for n in noms_plateau]))
    lum_hors_vert = v.get("C1", "🟢") != "🟢" or v.get("C6", "🟢") != "🟢"
    coul_hors_vert = v.get("C2", "🟢") != "🟢" or v.get("C8", "🟢") != "🟢"
    local = v.get("C4", "🟢") != "🟢" or v.get("C7", "🟢") != "🟢"
    sat = v.get("C5", "🟢") != "🟢"
    chaude = dRG > 0 or dBG < 0

    print("\nDiagnostic résumé :")
    if lum_hors_vert:
        print(f"- Image globalement trop {'CLAIRE' if dY > 0 else 'SOMBRE'}.")
    if coul_hors_vert:
        print(f"- Dominante {'CHAUDE (rougeâtre)' if chaude else 'FROIDE (bleutée)'}.")
    if sat:
        print("- Bol saturé ou reflet trop fort.")
    if local:
        print("- Éclairage NON homogène : correction caméra insuffisante.")
    else:
        print("- Éclairage homogène : correction caméra possible.")

    # ----- Écart LOCAL : priorité absolue, avant tout réglage -----
    if local:
        print("\n⚠️  ÉCART LOCAL DÉTECTÉ — ne se corrige PAS avec guvcview.")
        print("   Corrige d'abord physiquement la lumière :")
        print("   ombre portée, reflet, soleil rasant, lampe trop proche,")
        print("   objet parasite dans la scène. Ensuite seulement, remesure.")
        if not (lum_hors_vert or coul_hors_vert or sat):
            print("\nAucune action caméra proposée : corrige d'abord")
            print("physiquement la lumière, puis [Entrée] pour remesurer.")
            return False        # écart purement local → [A] non proposé

    # ----- Actions dans guvcview -----
    blocs = []
    if lum_hors_vert:
        sens = "diminuer" if dY > 0 else "augmenter"
        b = [f"{GUVCVIEW_NOMS['exposure_time_absolute']}",
             "   Réglage technique : exposure_time_absolute",
             f"   Valeur actuelle : {expo if expo is not None else '?'}",
             f"   Action conseillée : {sens}"]
        if isinstance(expo, int):
            pas = max(5, round(expo * 0.1))
            cible = expo - pas if dY > 0 else expo + pas
            b.append(f"   Exemple d'essai : {expo} → {cible}")
        if dY > 0:
            b.append(f"   Gain (valeur actuelle : {gain if gain is not None else '?'}) :"
                     " diminuer seulement si > 0")
        else:
            b.append(f"   Gain (valeur actuelle : {gain if gain is not None else '?'}) :"
                     " augmenter seulement si l'exposition ne suffit pas")
        b.append("   Ne touche PAS au curseur « Luminosité ».")
        blocs.append(b)
    if coul_hors_vert:
        sens = "diminuer" if chaude else "augmenter"
        b = [f"{GUVCVIEW_NOMS['white_balance_temperature']}",
             "   Réglage technique : white_balance_temperature",
             f"   Valeur actuelle : {wb if wb is not None else '?'}",
             f"   Action conseillée : {sens}"]
        if isinstance(wb, int):
            cible = wb - 100 if chaude else wb + 100
            b.append(f"   Exemple d'essai : {wb} → {cible}")
        b.append("   Laisse « Balance des blancs, Automatique » désactivée.")
        if not lum_hors_vert:
            b.append("   NB : balance des blancs et exposition INTERAGISSENT")
            b.append(f"   (ΔY plateau actuel : {dY:+.1f}, seuil 🟢 : ±{SEUILS['C1'][0]:.0f}).")
            b.append("   Si l'image dérive en luminosité, retouche légèrement")
            b.append(f"   « {GUVCVIEW_NOMS['exposure_time_absolute']} » "
                     f"(valeur actuelle : {expo if expo is not None else '?'}).")
        blocs.append(b)
    if sat:
        blocs.append(["Bol saturé / reflet — priorité au physique :",
                      "   1. supprimer le reflet (déplacer/atténuer la lumière)",
                      f"   2. si nécessaire seulement : diminuer "
                      f"« {GUVCVIEW_NOMS['exposure_time_absolute']} »",
                      "   Ne touche pas à « Luminosité », « Contraste » ni « Gamma »."])

    if blocs:
        print("\nDans guvcview, contrôles à ajuster (par ordre de priorité) :")
        for i, b in enumerate(blocs, 1):
            print(f"\n{i}. {b[0]}")
            for ligne in b[1:]:
                print(ligne)
    elif not local:
        print("\nAucune action caméra requise par le diagnostic.")

    # ----- Contrôles interdits + rappels -----
    print("\nNe touche pas à :")
    for nom in GUVCVIEW_INTERDITS:
        print(f"- {nom}")
    print("\nRappels :")
    print(f"- « {GUVCVIEW_NOMS['white_balance_automatic']} » doit rester désactivée.")
    print(f"- « {GUVCVIEW_NOMS['exposure_dynamic_framerate']} » doit rester désactivée.")
    print("- « Exposition automatique » doit rester en mode manuel.")
    return True                 # [A] proposé (action caméra ou cas mixte)


def _ecrire_recalibrage_reference(reglages):
    """Inscrit reglages_recalibres + date dans la référence (écriture
    contrôlée via temporaire). Retourne True si OK."""
    try:
        with open(REF_FILE, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"   ❌ Référence illisible ({e}) — recalibrage non enregistré.")
        return False
    data["reglages_recalibres"] = reglages
    data["date_recalibrage"] = datetime.now().isoformat(timespec="seconds")
    tmp = REF_FILE.with_name(REF_FILE.stem + "_tmp.json")
    try:
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        with open(tmp, 'r') as f:
            json.load(f)
    except Exception as e:
        print(f"   ❌ Écriture du recalibrage échouée ({e}).")
        tmp.unlink(missing_ok=True)
        return False
    os.replace(tmp, REF_FILE)
    return True


def recalibrage_guide(idx, mask_pts, mask_img, zones, verrouille, ecrire_reference=True):
    """Étape 4 : recalibrage guidé interactif (option [7]).

    Le diagnostic [6] exige des réglages égaux à ceux de la référence ; le
    recalibrage est précisément l'opération qui MODIFIE les réglages pour
    que l'IMAGE retrouve les statistiques de la référence quand la lumière
    a changé. Ce qui fait foi pour le modèle est l'image, pas les réglages.

    Boucle : diagnostic complet (20 éch., même logique que [6], D2) →
    consignes graduées (jamais d'ordre aveugle) → [A] ajuster (guvcview,
    caméra libérée puis réglages ré-appliqués) / [Entrée] remesurer /
    [Q] abandonner. À la convergence 🟢, propose le verrouillage :
    sauvegarde des réglages dans camera_settings.json (déjà fait par
    capturer_reglages_camera) + reglages_recalibres dans la référence."""
    if not REF_FILE.exists():
        print(f"\n❌ Recalibrage refusé : aucune référence active ({REF_FILE}).")
        print("   Capture-la d'abord (option [4]).")
        return
    try:
        with open(REF_FILE, 'r') as f:
            ref = json.load(f)
    except Exception as e:
        print(f"\n❌ Recalibrage refusé : référence illisible ({e}).")
        return
    raisons = _verifier_caducite(ref, mask_pts, zones)
    if raisons:
        print("\n❌ Recalibrage refusé : la référence est CADUQUE :")
        for r in raisons:
            print(f"   - {r}")
        print("   Recapture nécessaire (option [4]).")
        return
    refs = ref.get("stats", {})
    for z in zones:
        if z["nom"] not in refs:
            print(f"\n❌ Recalibrage impossible : zone '{z['nom']}' absente des")
            print("   statistiques de la référence — recapture nécessaire.")
            return
    if capturer_reglages_camera is None or verrouiller_camera is None:
        print(f"\n❌ Recalibrage impossible : module {NOM_MODULE_CONFIG} indisponible.")
        return

    device = f"/dev/video{idx}"
    if not _confirmer_checklist("lancer le recalibrage guidé"):
        print("   Recalibrage annulé.")
        return

    print("\n🔧 RECALIBRAGE GUIDÉ — l'outil mesure et conseille, tu ajustes.")
    while True:
        duree = REF_N_ECHANTILLONS * STABILITE_INTERVALLE
        print(f"\n⏱️  Mesure : {REF_N_ECHANTILLONS} échantillons sur "
              f"{duree:.0f} s. Ne touche à rien...")
        cour = _mesurer_zones(idx, mask_img, zones)
        if cour is None:
            print("❌ Mesure impossible — recalibrage interrompu.")
            return
        resultats, global_v = _evaluer_conformite(cour, refs, zones)

        action_camera = True       # défaut : instable (guvcview peut servir
                                   # à couper un automatisme) et cas 🟢 + [A]
        if global_v == "🔴" and len(resultats) == 1:
            _afficher_instable(cour, zones, resultats[0][3])
            print("   Stabilise la lumière avant d'ajuster les réglages.")
        else:
            afficher_tableau("Diagnostic par critère", [
                (f"{code} {libelle}", f"{verdict}  {texte}")
                for code, libelle, verdict, texte in resultats
            ])
            print(f"\n  VERDICT GLOBAL : {global_v}")
            _qualifier_ecart(resultats, global_v, cour)

            if global_v == "🟢":
                print("\n✅ CONVERGENCE : conditions conformes à la référence.")
                print("  [Entrée] : verrouiller ces réglages (recalibrage validé)")
                print("  [A]      : ajuster encore   [Q] : quitter sans verrouiller")
                rep = input("Choix : ").strip().upper()
                if rep == "":
                    actuels = (charger_reglages_camera(NOM_CAMERA)
                               if charger_reglages_camera else None)
                    if not actuels:
                        print("   ⚠️  Réglages actuels illisibles — non enregistrés.")
                        return
                    if not ecrire_reference:
                        # Mode déploiement (D3) : la référence du dataset
                        # est en LECTURE SEULE — réglages locaux + journal
                        # suffisent, le verdict mesuré fait foi.
                        print("   ℹ️  Mode déploiement : référence du dataset non modifiée.")
                    elif _ecrire_recalibrage_reference(actuels):
                        print("   ✅ Recalibrage enregistré dans la référence")
                        print("      (reglages_recalibres). Le diagnostic [6]")
                        print("      acceptera désormais ces réglages.")
                    return
                if rep == "Q":
                    print("   Recalibrage quitté sans verrouillage.")
                    return
                # 'A' → on retombe dans la phase d'ajustement ci-dessous
            action_camera = _afficher_aide_guvcview(resultats, cour, refs, zones)

        if action_camera:
            print("\n  [A]      : ajuster les réglages (guvcview)")
        else:
            print()
        print("  [Entrée] : remesurer sans ajuster")
        print("  [Q]      : abandonner le recalibrage")
        while True:
            rep = input("Choix : ").strip().upper()
            if rep in ("", "Q") or (rep == "A" and action_camera):
                break
            if rep == "A":
                print("   ⚠️  [A] non proposé ici : écart purement LOCAL —")
                print("   corrige la pièce, puis [Entrée] pour remesurer.")
            else:
                print(f"   ⚠️  Saisie '{rep}' non reconnue.")
        if rep == "Q":
            print("   Recalibrage abandonné.")
            return
        if rep == "A":
            # guvcview a besoin d'un accès exclusif au device : aucune
            # caméra OpenCV n'est ouverte ici (les mesures libèrent la
            # leur). capturer_reglages_camera retourne le dict capturé, ou
            # None si l'utilisateur annule (cas fichier corrompu) : le garde
            # « if not apres » ci-dessous couvre None comme un dict vide. On
            # compare ensuite avant/après pour détecter une absence d'ajustement.
            avant = charger_reglages_camera(NOM_CAMERA) if charger_reglages_camera else None
            apres = capturer_reglages_camera(device, NOM_CAMERA, forcer=True,
                                             titre=f"RECALIBRAGE — {PROFIL['libelle']}")
            if not apres:
                print("   ❌ Aucun réglage capturé — recalibrage inchangé.")
                continue
            if apres == avant:
                print("   ℹ️  Réglages inchangés (rien ajusté) — nouvelle mesure.")
            print("\n🔒 Application des nouveaux réglages...")
            if not verrouiller_camera(device, NOM_CAMERA):
                print("   ❌ Impossible d'appliquer les réglages — "
                      "recalibrage interrompu.")
                return
        # [Entrée] ou après ajustement → la boucle remesure


# ============================================
# API D'INTÉGRATION AU PIPELINE (étape 5 — script 8)
# Fonctions PUBLIQUES importables :
#   from SEM_so101_camera_reference import (
#       controle_camera_avant_enregistrement, copier_reference_vers_meta)
# ============================================

def _journaliser_evenement(contexte, verdict, resultats, decision, note=""):
    """Ajoute une ligne JSON au journal camera_reference_log.jsonl
    (spec §5 : une ligne par événement — date, caméra, critères hors
    zone verte avec leurs valeurs, décision de l'utilisateur).
    Retourne True si l'écriture a réussi."""
    entree = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "camera": NOM_CAMERA,
        "contexte": contexte,
        "verdict": verdict,
        "decision": decision,
        "criteres_hors_vert": {
            code: {"verdict": v, "detail": texte}
            for code, _, v, texte in resultats if v != "🟢"
        },
    }
    if note:
        entree["note"] = note
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        print(f"   ⚠️  Journalisation impossible ({e}) — {LOG_FILE}")
        return False


def copier_reference_vers_meta(meta_dir):
    """API publique (traçabilité, spec multi-caméra §3/§6) : copie dans le
    meta/ d'un dataset les références des DEUX caméras (celles qui
    existent), avec leurs images témoins. Le meta/ devient leur exemplaire
    de vérité. Retourne True si au moins une référence a été copiée et
    qu'aucune copie n'a échoué."""
    try:
        meta = Path(meta_dir)
        meta.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"   ❌ Dossier meta inaccessible ({e}).")
        return False
    profil_avant = NOM_CAMERA
    ok_global = True
    copiees = 0
    for nom in PROFILS:
        selectionner_profil(nom)
        if not REF_FILE.exists():
            print(f"   ℹ️  Pas de référence pour {nom} — ignorée.")
            continue
        try:
            shutil.copy2(REF_FILE, meta / REF_FILE.name)
            if REF_RAW_PNG.exists():
                shutil.copy2(REF_RAW_PNG, meta / REF_RAW_PNG.name)
            if PROFILS[nom]["masque"] and REF_MASKED_PNG.exists():
                shutil.copy2(REF_MASKED_PNG, meta / REF_MASKED_PNG.name)
            print(f"   ✅ Référence {nom} copiée dans {meta}")
            copiees += 1
        except Exception as e:
            print(f"   ❌ Copie de la référence {nom} échouée ({e}).")
            ok_global = False
    if profil_avant:
        selectionner_profil(profil_avant)
    if copiees == 0:
        print("   ⚠️  Aucune référence à copier.")
        return False
    return ok_global


def controle_camera_avant_enregistrement(idx, nom_camera="cam_top", contexte=""):
    """API publique (étape 5, multi-caméra) — enveloppe : exécute le
    contrôle de la caméra nom_camera ; si l'utilisateur choisit [M], ouvre
    le menu COMPLET de référence de CETTE caméra (sans re-reconnaissance)
    puis REVÉRIFIE depuis le début (la référence ou les réglages ont pu
    changer dans le menu).
    Voir _controle_une_passe pour le déroulé et le dict retourné."""
    while True:
        res = _controle_une_passe(idx, nom_camera, contexte)
        if isinstance(res, dict) and res.get("verdict") == "MENU":
            executer_menu(idx, nom_camera, mode_integre=True)
            continue
        return res


def _controle_une_passe(idx, nom_camera, contexte=""):
    """API publique (étape 5) — appelée par le script 8 AVANT une session
    ou un bloc d'épisodes. PRÉ-REQUIS : les caméras du script appelant
    sont LIBÉRÉES (règle validée : contrôle uniquement entre les blocs ;
    ce module ouvre et ferme sa propre capture, puis la libère).

    Déroulé : chargement masque + zones + référence → garde-fous de
    comparabilité (les mêmes que l'option [6]) → check-list de la scène →
    verrouillage des réglages → mesure (20 éch., ~4 s) → rapport complet
    + ACTION RECOMMANDÉE → politique script 8 (spec §5) :
      🟢 → autorisé ;
      🟠 → autorisé après CONFIRMATION explicite, écart JOURNALISÉ ;
      🔴 → BLOQUÉ par défaut, recalibrage guidé proposé immédiatement ;
      mesure instable → traitée comme 🔴 (remesurer après stabilisation).
    Contrôle INDISPONIBLE (masque/zones/référence absents, module config
    introuvable, mesure impossible) : PAS de continuation à l'aveugle —
    [M] ouvre le menu pour réparer (réglages/zones/référence), [Q] annule.

    Retourne un dict (clés et valeurs en français) :
      verdict  : "🟢" | "🟠" | "🔴" | "INSTABLE" | "INDISPONIBLE" | "ANNULÉ"
      autorise : True si l'enregistrement peut commencer
      decision : "auto" | "confirme_orange" | "recalibre_puis_vert"
                 | "menu" | "annule"
      criteres : {code: verdict} (vide si indisponible/annulé)
      date, contexte"""

    def _resultat(verdict, autorise, decision, criteres=None):
        return {"verdict": verdict, "autorise": autorise,
                "decision": decision, "criteres": dict(criteres or {}),
                "date": datetime.now().isoformat(timespec="seconds"),
                "contexte": contexte}

    def _indisponible(lignes):
        print("\n⚠️  CONTRÔLE CAMÉRA INDISPONIBLE :")
        for ligne in lignes:
            print(f"   {ligne}")
        print("\n  [M] : ouvrir le MENU de référence (créer/réparer la")
        print("        référence — même caméra, sans re-reconnaissance)")
        print("  [Q] : annuler")
        # Choix A (validé) : pas de « continuer sans contrôle ». Un contrôle
        # indisponible se RÉPARE ([M] : réglages, zones, référence) ou
        # ANNULE ([Q]) — l'enregistrement n'est jamais autorisé à l'aveugle.
        while True:
            rep = input("Choix : ").strip().upper()
            if rep in ("M", "Q"):
                break
            print(f"   ⚠️  Saisie '{rep}' non reconnue — M ou Q.")
        if rep == "M":
            return _resultat("MENU", False, "menu")
        return _resultat("INDISPONIBLE", False, "annule")

    selectionner_profil(nom_camera)
    print("\n" + "=" * 60)
    print(f"📷 CONTRÔLE CAMÉRA — {PROFIL['libelle']} — {contexte or 'session'}")
    print("=" * 60)

    if verrouiller_camera is None or charger_reglages_camera is None:
        return _indisponible([f"module {NOM_MODULE_CONFIG} introuvable"])
    if PROFIL["masque"]:
        mask_pts = charger_masque()
        if not mask_pts:
            return _indisponible([f"masque introuvable ou illisible ({MASK_FILE})"])
    else:
        mask_pts = []          # caméra sans masque : image entière utile
    mask_img = construire_mask_image(mask_pts, LARGEUR, HAUTEUR)
    zones = charger_zones(mask_pts, mask_img)
    if not zones:
        return _indisponible([f"zones absentes ou invalides ({ZONES_FILE})",
                              "définis-les avec l'outil (option [1])"])
    ref, refs, erreurs = _verifier_reference_et_reglages(mask_pts, zones)
    if erreurs:
        return _indisponible(erreurs)

    if not _confirmer_checklist("lancer le contrôle caméra"):
        print("   Contrôle annulé.")
        return _resultat("ANNULÉ", False, "annule")

    if not appliquer_reglages_pipeline(idx):
        return _indisponible(["verrouillage des réglages impossible "
                              "(voir messages ci-dessus)"])

    recalibre = False
    while True:
        duree = REF_N_ECHANTILLONS * STABILITE_INTERVALLE
        print(f"\n⏱️  Mesure : {REF_N_ECHANTILLONS} échantillons sur "
              f"{duree:.0f} s. Ne touche à rien...")
        cour = _mesurer_zones(idx, mask_img, zones)
        if cour is None:
            return _indisponible(["mesure impossible (caméra/acquisition)"])
        resultats, global_v = _evaluer_conformite(cour, refs, zones)
        criteres = {code: v for code, _, v, _ in resultats}

        # Mesure instable : traitée comme 🔴 pour le script 8 (spec §5)
        if global_v == "🔴" and len(resultats) == 1:
            _afficher_instable(cour, zones, resultats[0][3])
            print("\n   Politique script 8 : mesure instable = bloqué.")
            print("  [E] : remesurer (après stabilisation de la lumière)")
            print("  [Q] : annuler l'enregistrement")
            while True:
                rep = input("Choix : ").strip().upper()
                if rep in ("E", "Q"):
                    break
                print(f"   ⚠️  Saisie '{rep}' non reconnue — E ou Q.")
            if rep == "E":
                continue
            return _resultat("INSTABLE", False, "annule", criteres)

        _afficher_rapport(resultats, global_v, cour, refs, zones,
                          ref.get("date", "?"))
        _afficher_action_recommandee(resultats, global_v, cour, refs, zones)

        if global_v == "🟢":
            print("\n✅ Conditions conformes — enregistrement autorisé.")
            return _resultat("🟢", True,
                             "recalibre_puis_vert" if recalibre else "auto",
                             criteres)

        if global_v == "🟠":
            print("\n🟠 Politique script 8 : autorisé après CONFIRMATION "
                  "explicite (journalisé).")
            print("  [Entrée] : continuer l'enregistrement (écart journalisé)")
            print("  [R]      : recalibrer d'abord (recommandé)")
            print("  [M]      : ouvrir le menu de référence")
            print("  [Q]      : annuler l'enregistrement")
            while True:
                rep = input("Choix : ").strip().upper()
                if rep in ("", "R", "M", "Q"):
                    break
                print(f"   ⚠️  Saisie '{rep}' non reconnue.")
            if rep == "M":
                return _resultat("MENU", False, "menu", criteres)
            if rep == "":
                _journaliser_evenement(contexte, "🟠", resultats,
                                       "confirme_orange")
                print("   ✅ Écart journalisé — enregistrement autorisé.")
                return _resultat("🟠", True, "confirme_orange", criteres)
            if rep == "Q":
                return _resultat("🟠", False, "annule", criteres)
        else:  # 🔴
            print("\n🔴 Politique script 8 : BLOQUÉ par défaut — "
                  "recalibrer d'abord.")
            print("  [R] : recalibrage guidé (recommandé)")
            print("  [M] : ouvrir le menu de référence")
            print("  [Q] : annuler l'enregistrement")
            while True:
                rep = input("Choix : ").strip().upper()
                if rep in ("R", "M", "Q"):
                    break
                print(f"   ⚠️  Saisie '{rep}' non reconnue — R, M ou Q.")
            if rep == "M":
                return _resultat("MENU", False, "menu", criteres)
            if rep == "Q":
                return _resultat("🔴", False, "annule", criteres)

        # [R] depuis 🟠 ou 🔴 : recalibrage guidé puis nouvelle mesure
        recalibrage_guide(idx, mask_pts, mask_img, zones, True)
        recalibre = True
        # La référence a pu recevoir reglages_recalibres : recharger
        ref, refs, erreurs = _verifier_reference_et_reglages(mask_pts, zones)
        if erreurs:
            return _indisponible(erreurs)


def controle_camera_deploiement(idx, nom_camera, dossier_reference=None,
                                contexte="déploiement"):
    """API publique (étape 6) — appelée par le SCRIPT 11 au démarrage du
    déploiement, pour UNE caméra, contre la référence du DATASET.

    dossier_reference : le meta/ du dataset d'entraînement (résolution via
    train_config.json, faite par le script 11). None = références locales
    (mode LEGACY explicite, décision D1 — le script 11 journalise).

    Différences avec le contrôle d'enregistrement (spec étape 6) :
      - zones et masque lus DANS la référence elle-même (autosuffisante),
        pas dans les fichiers locaux — comparaison exacte avec le dataset ;
      - garde des réglages ASSOUPLIE (D2) : divergence = information, le
        verdict MESURÉ décide ; le verrouillage matériel doit réussir ;
      - pas de [M] ni de check-list (le robot est déjà au repos, piloté
        par le script 11) ; recalibrage [R] sans écriture dans la
        référence (D3) ;
      - politique : 🟢 auto ; 🟠 [Entrée]/[R]/[Q] ; 🔴 [R]/[Q] ;
        instable [E]/[Q].

    Retourne le même dict que le contrôle d'enregistrement.
    GARANTIE : aucune écriture dans dossier_reference."""
    selectionner_profil(nom_camera, dossier_reference)
    try:
        return _deploiement_une_passe(idx, contexte)
    finally:
        # Ne jamais laisser fuiter les chemins du dataset vers la suite
        selectionner_profil(nom_camera)


def _deploiement_une_passe(idx, contexte):
    def _resultat(verdict, autorise, decision, criteres=None):
        return {"verdict": verdict, "autorise": autorise,
                "decision": decision, "criteres": criteres or {},
                "date": datetime.now().isoformat(timespec="seconds"),
                "contexte": contexte}

    def _indisponible(lignes):
        print("\n⚠️  CONTRÔLE DÉPLOIEMENT INDISPONIBLE :")
        for ligne in lignes:
            print(f"   {ligne}")
        print("\n  [Q] : seul choix — corriger puis relancer le déploiement")
        input("  [Entrée] pour continuer... ")
        return _resultat("INDISPONIBLE", False, "annule")

    print("\n" + "=" * 60)
    print(f"📷 CONTRÔLE DÉPLOIEMENT — {PROFIL['libelle']} — {contexte}")
    print("=" * 60)
    print(f"   Référence : {REF_FILE}")

    if verrouiller_camera is None or charger_reglages_camera is None:
        return _indisponible([f"module {NOM_MODULE_CONFIG} introuvable"])

    # Référence du dataset : AUTOSUFFISANTE (stats + zones + masque)
    try:
        with open(REF_FILE, 'r') as f:
            ref = json.load(f)
    except Exception as e:
        return _indisponible([f"référence illisible ({e})"])
    refs = ref.get("stats", {})
    zones = ref.get("zones", [])
    if not refs or not zones:
        return _indisponible(["référence incomplète (stats ou zones absentes)"])
    mask_pts = ref.get("mask_points") or []
    if PROFIL["masque"] and not mask_pts:
        return _indisponible(["référence sans points de masque (cam_top)"])
    mask_img = construire_mask_image(mask_pts, LARGEUR, HAUTEUR)

    # D2 : réglages divergents = INFORMATION (le verdict mesuré décide) ;
    # le VERROUILLAGE matériel, lui, doit réussir (sinon arrêt).
    actuels = charger_reglages_camera(NOM_CAMERA) or {}
    attendus = ref.get("reglages_recalibres") or ref.get("reglages_camera") or {}
    differences = sorted(k for k in set(actuels) | set(attendus)
                         if actuels.get(k) != attendus.get(k))
    if differences:
        print("\nℹ️  Réglages courants ≠ réglages de la référence du dataset :")
        for k in differences:
            print(f"   {k:32s} {actuels.get(k, '—')} (référence : {attendus.get(k, '—')})")
        print("   → C'est la MESURE qui décide (D2) ; recalibre si le verdict l'exige.")
    if not actuels:
        return _indisponible(["aucun réglage local enregistré pour cette caméra",
                              "règle-la d'abord (outil de référence, [R])"])
    if not appliquer_reglages_pipeline(idx):
        return _indisponible(["verrouillage des réglages impossible "
                              "(voir messages ci-dessus) — D2 : le "
                              "verrouillage matériel doit réussir"])

    recalibre = False
    while True:
        duree = REF_N_ECHANTILLONS * STABILITE_INTERVALLE
        print(f"\n⏱️  Mesure : {REF_N_ECHANTILLONS} échantillons sur "
              f"{duree:.0f} s. Ne touche à rien...")
        cour = _mesurer_zones(idx, mask_img, zones)
        if cour is None:
            return _indisponible(["mesure impossible (caméra/acquisition)"])
        resultats, global_v = _evaluer_conformite(cour, refs, zones)
        criteres = {code: v for code, _, v, _ in resultats}

        if global_v == "🔴" and len(resultats) == 1:
            _afficher_instable(cour, zones, resultats[0][3])
            print("\n   Mesure instable = bloqué (stabilise la lumière).")
            print("  [E] : remesurer   [Q] : quitter le déploiement")
            while True:
                rep = input("Choix : ").strip().upper()
                if rep in ("E", "Q"):
                    break
                print(f"   ⚠️  Saisie '{rep}' non reconnue — E ou Q.")
            if rep == "E":
                continue
            return _resultat("INSTABLE", False, "annule", criteres)

        _afficher_rapport(resultats, global_v, cour, refs, zones,
                          ref.get("date", "?"))
        _afficher_action_recommandee(resultats, global_v, cour, refs, zones)

        if global_v == "🟢":
            print("\n✅ Conditions conformes au dataset — déploiement autorisé.")
            return _resultat("🟢", True,
                             "recalibre_puis_vert" if recalibre else "auto",
                             criteres)

        if global_v == "🟠":
            print("\n🟠 Écart modéré avec le dataset : performance possible")
            print("   mais non garantie.")
            print("  [Entrée] : continuer le déploiement (écart journalisé)")
            print("  [R]      : recalibrer vers la référence du dataset")
            print("  [Q]      : quitter")
            while True:
                rep = input("Choix : ").strip().upper()
                if rep in ("", "R", "Q"):
                    break
                print(f"   ⚠️  Saisie '{rep}' non reconnue.")
            if rep == "":
                _journaliser_evenement(contexte, "🟠", resultats,
                                       "confirme_orange")
                print("   ✅ Écart journalisé — déploiement autorisé.")
                return _resultat("🟠", True, "confirme_orange", criteres)
            if rep == "Q":
                return _resultat("🟠", False, "annule", criteres)
        else:  # 🔴
            print("\n🔴 Conditions trop éloignées du dataset — pas de passage")
            print("   en force (le modèle verrait des images inconnues).")
            print("  [R] : recalibrage guidé vers la référence du dataset")
            print("  [Q] : quitter")
            while True:
                rep = input("Choix : ").strip().upper()
                if rep in ("R", "Q"):
                    break
                print(f"   ⚠️  Saisie '{rep}' non reconnue — R ou Q.")
            if rep == "Q":
                return _resultat("🔴", False, "annule", criteres)

        # [R] : recalibrage guidé, SANS écriture dans la référence (D3)
        recalibrage_guide(idx, mask_pts, mask_img, zones, True,
                          ecrire_reference=False)
        recalibre = True


# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main():
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║   RÉFÉRENCE VISUELLE CAMÉRA — OUTIL & MODULE (v7)        ║
║     Service Écoles-Médias (SEM) — DIP Genève             ║
╚══════════════════════════════════════════════════════════╝
    """)
    print("Étapes 1-4 du plan « Référence visuelle caméra » :")
    print("options [1] à [6] : mesure, référence et diagnostic, sans")
    print("création de réglage caméra ; option [7] : recalibrage guidé,")
    print("pouvant modifier camera_settings.json après action explicite")
    print("via guvcview. Aucun script validé du pipeline n'est modifié.")

    # 1) Choix de la caméra de travail
    print("\nQuelle caméra veux-tu travailler ?")
    print("  [G] GLOBALE (cam_top)")
    print("  [P] PINCE (cam_follower)")
    while True:
        rep_cam = input("Choix : ").strip().upper()
        if rep_cam in ("G", "P"):
            break
        print(f"   ⚠️  Saisie '{rep_cam}' non reconnue — G ou P.")
    nom_camera = "cam_top" if rep_cam == "G" else "cam_follower"
    selectionner_profil(nom_camera)

    # 2) Identification obligatoire de la caméra (index non mémorisé)
    idx = identifier_camera()
    if idx is None:
        print("\n👋 Fin (caméra non confirmée).")
        return

    executer_menu(idx, nom_camera, mode_integre=False)


def menu_reference(idx, nom_camera="cam_top"):
    """API publique : ouvre le menu COMPLET de l'outil pour la caméra
    nom_camera, DÉJÀ identifiée à l'index idx (aucune re-reconnaissance).
    Utilisé par le script 8 — appelé une fois par caméra.
    La sortie est [S] Étape suivante (et non Quitter) : au retour de
    cette fonction, le script appelant poursuit son déroulement normal.
    PRÉ-REQUIS : la caméra idx est LIBÉRÉE par l'appelant."""
    executer_menu(idx, nom_camera, mode_integre=True)


def executer_menu(idx, nom_camera, mode_integre=False):
    """Boucle du menu principal pour la caméra nom_camera (index idx).
    mode_integre=False : outil autonome — sortie [Q] Quitter.
    mode_integre=True  : intégré au script 8 — sortie [S] Étape suivante."""
    selectionner_profil(nom_camera)
    # Application des réglages du pipeline (caméra libérée avant,
    # rouverte ensuite par chaque fonction de mesure — D1/D2)
    verrouille = appliquer_reglages_pipeline(idx)

    # Réglages NON VERROUILLÉS — QUELLE QUE SOIT la cause (aucun réglage,
    # réglages présents mais verrouillage échoué) : porte de RÉPARATION.
    # Sans verrouillage, [4]/[6]/[7] resteront indisponibles dans le menu
    # (mode TEST limité : [1][2][3][5] seulement).
    if not verrouille and capturer_reglages_camera is not None:
        deja = bool(charger_reglages_camera(NOM_CAMERA)) \
            if charger_reglages_camera is not None else False
        if deja:
            print(f"\n⚠️  Des réglages existent pour {PROFIL['libelle']} mais le")
            print("   VERROUILLAGE A ÉCHOUÉ (voir messages ci-dessus).")
            print("\n  [R]      : refaire les réglages avec guvcview puis verrouiller")
        else:
            print(f"\n⚠️  Aucun réglage enregistré pour {PROFIL['libelle']}.")
            print("   Une référence officielle exige des réglages connus et")
            print("   verrouillés. C'est le RÉGLAGE INITIAL : une seule fois,")
            print("   avec guvcview.")
            print("\n  [R]      : régler maintenant avec guvcview (recommandé)")
        print("  [Entrée] : continuer en mode TEST limité ([1][2][3][5] seulement)")
        while True:
            rep_init = input("Choix : ").strip().upper()
            if rep_init in ("R", ""):
                break
            print(f"   ⚠️  Saisie '{rep_init}' non reconnue — R ou Entrée.")
        if rep_init == "R":
            capturer_reglages_camera(f"/dev/video{idx}", NOM_CAMERA,
                                     forcer=True,
                                     titre=f"RÉGLAGES — {PROFIL['libelle']}")
            verrouille = appliquer_reglages_pipeline(idx)
            if not verrouille:
                print("   ❌ Verrouillage toujours impossible — mode TEST limité.")

    if not verrouille:
        avertir_non_representatif()

    # Masque : obligatoire pour la caméra globale (script 7) ; la pince
    # mesure sur l'image entière (spec multi-caméra, validé).
    if PROFIL["masque"]:
        mask_pts = charger_masque()
        if mask_pts is None:
            print(f"\n❌ Masque introuvable ou illisible : {MASK_FILE}")
            print("   Crée d'abord le masque avec le script 7 :")
            print("   python SEM_so101_7_teleoperation_camera.py")
            if mode_integre:
                print("   (Le menu de référence n'est pas utilisable sans masque.)")
            return
        print(f"\n✅ Masque chargé : {len(mask_pts)} points")
    else:
        mask_pts = []
        print(f"\nℹ️  {PROFIL['libelle']} : pas de masque — image entière mesurée.")
    mask_img = construire_mask_image(mask_pts, LARGEUR, HAUTEUR)

    # Zones existantes (obsolescence + revalidation complète)
    zones = charger_zones(mask_pts, mask_img)

    # Menu principal (options 1-7 + sortie selon le mode)
    touche_sortie = 'S' if mode_integre else 'Q'
    while True:
        print("\n" + "=" * 60)
        print(f"  MENU PRINCIPAL — {PROFIL['libelle']}")
        print("=" * 60)
        etat_zones = (f"{len(zones)} zones définies" if zones
                      else "AUCUNE zone définie (commencer par [1])")
        etat_regl = "verrouillés ✓" if verrouille else "NON VERROUILLÉS ⚠️"
        etat_ref = "AUCUNE"
        if REF_FILE.exists():
            try:
                with open(REF_FILE, 'r') as f:
                    etat_ref = json.load(f).get("date", "illisible")
            except Exception:
                etat_ref = "illisible ⚠️"
        print(f"  Caméra : {NOM_CAMERA} (/dev/video{idx})   "
              f"Réglages : {etat_regl}")
        print(f"  Zones : {etat_zones}   Référence active : {etat_ref}")
        print()
        print("  [1] Définir / redessiner les zones")
        print("  [2] Visualiser les zones actuelles")
        print("  [3] Mesurer en direct (M1-M8 + stabilité M9)")
        if verrouille:
            print("  [4] Créer / remplacer la référence (scène standard requise)")
            print("  [5] Afficher la référence active")
            print("  [6] Diagnostic de conformité (vs référence active)")
            print("  [7] Recalibrer pour REVENIR à la référence (ajuster jusqu'à 🟢)")
        else:
            print("  [5] Afficher la référence active")
            print("  ([4] référence, [6] diagnostic, [7] recalibrage : INDISPONIBLES")
            print("   tant que les réglages ne sont pas verrouillés)")
            print("  [R] Régler la caméra avec guvcview puis verrouiller")
        if mode_integre:
            print("  [S] Étape suivante — poursuivre l'enregistrement")
        else:
            print("  [Q] Quitter")
        choix = input("\nChoix : ").strip().upper()

        if not verrouille and choix in ('4', '6', '7'):
            print("⚠️  Indisponible : réglages non verrouillés — utilise [R].")
            continue
        if not verrouille and choix == 'R':
            if capturer_reglages_camera is None:
                print(f"⚠️  Module {NOM_MODULE_CONFIG} introuvable — réglage impossible.")
                continue
            capturer_reglages_camera(f"/dev/video{idx}", NOM_CAMERA,
                                     forcer=True,
                                     titre=f"RÉGLAGES — {PROFIL['libelle']}")
            verrouille = appliquer_reglages_pipeline(idx)
            print("   " + ("✅ Réglages verrouillés." if verrouille
                           else "❌ Verrouillage toujours impossible."))
            continue

        if choix == '1':
            nouvelles = definir_zones(idx, mask_pts, mask_img)
            if nouvelles:
                zones = nouvelles
        elif choix == '2':
            if not zones:
                print("⚠️  Définis d'abord les zones (option [1]).")
                continue
            visualiser_zones(idx, mask_img, zones)
        elif choix == '3':
            if not zones:
                print("⚠️  Définis d'abord les zones (option [1]).")
                continue
            mesurer_en_direct(idx, mask_img, zones, verrouille)
        elif choix == '4':
            if not zones:
                print("⚠️  Définis d'abord les zones (option [1]).")
                continue
            capturer_reference(idx, mask_pts, mask_img, zones, verrouille)
        elif choix == '5':
            afficher_reference(mask_pts, zones)
        elif choix == '6':
            if not zones:
                print("⚠️  Définis d'abord les zones (option [1]).")
                continue
            diagnostic_conformite(idx, mask_pts, mask_img, zones, verrouille)
        elif choix == '7':
            if not zones:
                print("⚠️  Définis d'abord les zones (option [1]).")
                continue
            recalibrage_guide(idx, mask_pts, mask_img, zones, verrouille)
        elif choix == touche_sortie:
            if mode_integre:
                print("\n➡️  Étape suivante — retour au script d'enregistrement.")
            else:
                print("\n👋 Fin.")
            break
        else:
            print("⚠️  Choix non reconnu.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Interruption (CTRL+C) — fermeture propre.")
        cv2.destroyAllWindows()
        sys.exit(0)
