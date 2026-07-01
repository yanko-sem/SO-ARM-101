#!/usr/bin/env python3
"""
SEM_so101_camera_auto.py
Service Écoles-Médias (SEM) - DIP Genève

CAMÉRA — EXPOSITION AUTO PUIS FIGÉE + CONTRÔLE IMAGE SIMPLE
==========================================================

Module autonome de gestion caméra pour le script 8. Il ne dépend que de
v4l2-ctl et d'un moyen de lire des frames.

Deux fonctions publiques :

  regler_exposition_auto_puis_figee(index, nom, lire_frame, duree_stab=4.0)
      Laisse l'exposition automatique s'adapter à la lumière du moment pendant
      quelques secondes, puis la FIGE pour toute la séance (bascule en manuel
      SANS réécrire l'exposition/WB : le pilote garde la valeur convergée), coupe
      le framerate dynamique et règle le secteur à 50 Hz (Genève). Ainsi l'image
      s'ajuste une fois à l'éclairage réel, puis ne dérive plus pendant
      l'enregistrement. FAIL-CLOSED : toute écriture v4l2 ratée est listée et met
      ok=False. Retourne une preuve structurée.

  controle_image_simple(lire_frame, nom, largeur, hauteur, masque_path=None,
                        est_globale=False)
      Plancher physique GLOBAL : UNE mesure par caméra (la GLOBALE dans la zone
      utile du masque ; jamais de sous-zones sémantiques, de Δ, ni de couleur d'objet) :
      image lisible, bonne résolution, ni noire ni cramée, stable, masque présent
      si requis. Mesure quelques indicateurs globaux et rend un verdict simple
      🟢 / 🟠 / 🔴 avec un message en français pour l'opérateur.

`lire_frame` est un appelable SANS argument qui renvoie une frame BGR (numpy) ou
None — typiquement la méthode de lecture de la caméra déjà ouverte par le script
(p. ex. ThreadedCamera.async_read). Le réglage s'applique sur le flux DÉJÀ actif :
pas de réouverture après le figeage (sinon certaines webcams réinitialisent
l'auto).

Auteur : Service Écoles-Médias (SEM)   —   Version : 1.1
"""

import re
import time
import json
import subprocess
from pathlib import Path

import numpy as np
import cv2

# --- valeurs v4l2 (relevées sur les caméras Innomaker du projet) ---
AUTO_EXPO_AUTO, AUTO_EXPO_MANUEL = 3, 1     # 3 = Aperture Priority, 1 = Manual
WB_AUTO, WB_MANUEL = 1, 0
PLF_50HZ = 1                                # power_line_frequency : 1 = 50 Hz (Genève)

# ============================================================================
#  SEUILS OPÉRATIONNELS — plancher physique GLOBAL, validés pour la phase.
#  Les cas limites restent 🟠 (décision opérateur sur image live) ; 🔴 ne bloque
#  que les échecs francs. Aucun seuil par zone/objet ni de Δ : mesures globales.
#  Repères validés : captures lum 88→221 OK ; GLOBALE zone utile extrême = 33.4% clairs (🟠).
# ============================================================================
PIX_SOMBRE = 20          # un pixel est "très sombre" si gris < 20
PIX_CLAIR  = 225         # un pixel est "très clair" si gris > 225
                         # (225 et non 250 : la GLOBALE plafonne ~230 sans saturer)

LUM_NOIR_REFUS   = 15.0  # 🔴 image quasi noire si luminosité moyenne <
LUM_SOMBRE_AVERT = 60.0  # 🟠 image sombre si luminosité moyenne <
LUM_CLAIR_AVERT  = 210.0 # 🟠 image très claire si luminosité moyenne > (pince extrême 220.6 → 🟠)

PCT_CLAIR_AVERT  = 25.0  # 🟠 si % pixels très clairs >
PCT_CLAIR_REFUS  = 90.0  # 🔴 PINCE (plein cadre) : cramé si quasi toute l'image est claire (pince extrême 65.3% reste OK)
# La GLOBALE est mesurée dans la ZONE UTILE (masque = le plateau), qui doit rester
# bien exposée : tolérance de sur-exposition plus STRICTE que la pince.
# Repères zone utile validés OK : globale extrême = 33.4% de clairs (reste 🟠).
PCT_CLAIR_REFUS_GLOBALE = 45.0  # 🔴 GLOBALE (zone utile) : plateau cramé si % pixels très clairs >
PCT_SOMBRE_AVERT = 25.0  # 🟠 si % pixels très sombres >
PCT_SOMBRE_REFUS = 60.0  # 🔴 image massivement écrasée si % pixels très sombres >

STAB_AMPL_REFUS  = 25.0  # 🔴 flux instable si amplitude de luminosité (frames) >


# ============================================================================
#  HELPERS v4l2
# ============================================================================
def _lire_ctrl(device, controle):
    """Lit un contrôle (int|None), robuste aux menus type '1 (Manual Mode)'."""
    try:
        r = subprocess.run(["v4l2-ctl", "-d", device, f"--get-ctrl={controle}"],
                           capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if r.returncode == 0 and ":" in r.stdout:
        m = re.search(r"-?\d+", r.stdout.split(":", 1)[1])
        if m:
            return int(m.group())
    return None


def _ecrire_ctrl(device, controle, valeur):
    """Écrit un contrôle puis le relit pour confirmer. True si confirmé."""
    try:
        subprocess.run(["v4l2-ctl", "-d", device, f"--set-ctrl={controle}={int(valeur)}"],
                       capture_output=True, text=True)
    except FileNotFoundError:
        return False
    return _lire_ctrl(device, controle) == int(valeur)


def _luminosite(frame):
    """Luminosité moyenne (0-255) en niveaux de gris."""
    return float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))


# ============================================================================
#  EXPOSITION : AUTO PUIS FIGÉE
# ============================================================================
def regler_exposition_auto_puis_figee(index, nom, lire_frame, duree_stab=4.0):
    """Laisse l'exposition s'ajuster automatiquement à la lumière, puis la FIGE,
    sur la caméra /dev/video{index}, le flux étant DÉJÀ
    actif (lire_frame fournit des frames pour faire converger l'auto).

    FAIL-CLOSED : chaque écriture v4l2 critique est vérifiée. Retourne :
        {
          "ok": bool,                 # True si aucune écriture critique ratée
          "echecs": [str, ...],       # contrôles non confirmés
          "auto_expo", "wb_auto",     # contrôles RELUS après le figeage
          "dyn_fps", "plf",
          "expo", "wb",               # (expo peut être périmé : ne pas s'y fier)
          "lum": float|None,          # luminosité moyenne après le figeage
        }
    """
    device = f"/dev/video{index}"
    echecs = []

    # secteur 50 Hz (anti-scintillement) d'abord
    if not _ecrire_ctrl(device, "power_line_frequency", PLF_50HZ):
        echecs.append("power_line_frequency=1 (50 Hz)")

    # 1) auto activée
    if not _ecrire_ctrl(device, "auto_exposure", AUTO_EXPO_AUTO):
        echecs.append("auto_exposure=3 (activer auto)")
    if not _ecrire_ctrl(device, "white_balance_automatic", WB_AUTO):
        echecs.append("white_balance_automatic=1 (activer auto WB)")

    # 2) convergence : on garde le flux actif pendant duree_stab.
    #    On COMPTE les frames réellement lues : sans flux actif, l'auto ne peut
    #    pas converger → le réglage ne serait pas réellement appliqué.
    nb_frames = 0
    t0 = time.time()
    while time.time() - t0 < duree_stab:
        if lire_frame() is not None:
            nb_frames += 1
        time.sleep(0.03)
    if nb_frames == 0:
        echecs.append("aucune frame lue pendant la convergence (flux caméra inactif)")

    # 3) bascule en manuel SANS réécrire expo/WB (le pilote fige la valeur trouvée)
    if not _ecrire_ctrl(device, "auto_exposure", AUTO_EXPO_MANUEL):
        echecs.append("auto_exposure=1 (couper auto)")
    if not _ecrire_ctrl(device, "white_balance_automatic", WB_MANUEL):
        echecs.append("white_balance_automatic=0 (couper auto WB)")
    if _lire_ctrl(device, "exposure_dynamic_framerate") is not None:
        if not _ecrire_ctrl(device, "exposure_dynamic_framerate", 0):
            echecs.append("exposure_dynamic_framerate=0")

    # 4) mesure témoin + relecture des contrôles (preuve du réglage)
    frame = lire_frame()
    if frame is None:
        echecs.append("frame témoin finale absente (flux caméra inactif)")
    lum = _luminosite(frame) if frame is not None else None
    return {
        "ok": not echecs,
        "echecs": echecs,
        "auto_expo": _lire_ctrl(device, "auto_exposure"),
        "wb_auto":   _lire_ctrl(device, "white_balance_automatic"),
        "dyn_fps":   _lire_ctrl(device, "exposure_dynamic_framerate"),
        "plf":       _lire_ctrl(device, "power_line_frequency"),
        "expo":      _lire_ctrl(device, "exposure_time_absolute"),
        "wb":        _lire_ctrl(device, "white_balance_temperature"),
        "lum":       lum,
    }


# ============================================================================
#  CONTRÔLE IMAGE SIMPLE (plancher physique global + retour lumière)
# ============================================================================
def _charger_masque(masque_path, largeur, hauteur):
    """Construit le masque binaire (255 = zone utile) depuis le JSON polygone.
    Met à l'échelle si la résolution de référence diffère. Retourne un
    np.uint8 (hauteur, largeur), ou None si le fichier est illisible/invalide."""
    try:
        d = json.load(open(masque_path))
        pts = np.array(d["points"], dtype=np.float64)
        ref = d.get("reference_resolution", {})
        rw = ref.get("width", largeur)
        rh = ref.get("height", hauteur)
        if (rw, rh) != (largeur, hauteur):
            pts[:, 0] *= largeur / rw
            pts[:, 1] *= hauteur / rh
        m = np.zeros((hauteur, largeur), dtype=np.uint8)
        cv2.fillPoly(m, [pts.astype(np.int32)], 255)
        return m if np.any(m) else None
    except Exception:
        return None


def controle_image_simple(lire_frame, nom, largeur, hauteur,
                          masque_path=None, est_globale=False):
    """Plancher physique GLOBAL + retour lumière à l'opérateur. Aucune zone
    sémantique, aucun Δ, aucune couleur d'objet : UNE seule mesure globale par
    caméra, mais calculée sur le BON périmètre :
      - GLOBALE (est_globale=True) : image brute mesurée UNIQUEMENT dans la zone
        utile du masque (le plateau réellement enregistré). Le pourtour n'est pas
        compté : sinon un plateau cramé serait noyé dans un pourtour plus sombre.
      - PINCE : image brute mesurée en plein cadre (pas de masque).
    Le seuil de sur-exposition 🔴 est plus strict pour la GLOBALE (zone utile).
    Retourne : {"verdict", "bloquant", "message", "mesures"}.
    """
    def _res(verdict, message, mesures):
        return {"verdict": verdict, "bloquant": verdict == "🔴",
                "message": message, "mesures": mesures}

    # Périmètre de mesure : masque pour la GLOBALE, plein cadre pour la PINCE.
    masque = None
    if est_globale:
        if masque_path is None or not Path(masque_path).exists():
            return _res("🔴", "masque GLOBALE absent — relance la préparation", {})
        masque = _charger_masque(masque_path, largeur, hauteur)
        if masque is None:
            return _res("🔴", "masque GLOBALE illisible — relance la préparation", {})

    def _sel(gris):
        """Pixels à mesurer : zone utile (masque) pour la GLOBALE, sinon tout."""
        if masque is not None and gris.shape[:2] == masque.shape[:2]:
            return gris[masque > 0]
        return gris.ravel()

    # collecte de quelques frames (~0.6 s) pour mesurer la stabilité, sur le
    # périmètre choisi (zone utile pour la GLOBALE).
    lums, derniere = [], None
    t0 = time.time()
    while time.time() - t0 < 0.6:
        f = lire_frame()
        if f is not None:
            derniere = f
            lums.append(float(np.mean(_sel(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)))))
        time.sleep(0.05)

    if derniere is None or not lums:
        return _res("🔴", "image absente — vérifie le branchement de la caméra", {})

    # résolution réelle
    h, w = derniere.shape[:2]
    if not (w == largeur and h == hauteur):
        return _res("🔴", f"résolution {w}x{h} au lieu de {largeur}x{hauteur}",
                    {"resolution_ok": False})

    gris = cv2.cvtColor(derniere, cv2.COLOR_BGR2GRAY)
    sel = _sel(gris)
    lum = float(np.mean(lums))
    pct_sombres = float(np.mean(sel < PIX_SOMBRE) * 100.0)
    pct_clairs = float(np.mean(sel > PIX_CLAIR) * 100.0)
    stabilite = float(max(lums) - min(lums))
    perimetre = "zone utile" if masque is not None else "plein cadre"
    mesures = {"lum": round(lum, 1), "pct_sombres": round(pct_sombres, 1),
               "pct_clairs": round(pct_clairs, 1), "stabilite": round(stabilite, 2),
               "resolution_ok": True, "perimetre": perimetre}

    # Seuil de sur-exposition 🔴 propre à chaque caméra (justifié : la GLOBALE est
    # mesurée sur le plateau, la PINCE en plein cadre naturellement plus clair).
    pct_clair_refus = PCT_CLAIR_REFUS_GLOBALE if est_globale else PCT_CLAIR_REFUS

    # --- 🔴 blocages (image inexploitable) ---
    if lum < LUM_NOIR_REFUS:
        return _res("🔴", "image quasi noire — ajoute de la lumière puis relance le réglage d'exposition", mesures)
    if pct_clairs > pct_clair_refus:
        return _res("🔴", "plateau/image cramé(e) — réduis la lumière puis relance le réglage d'exposition", mesures)
    if pct_sombres > PCT_SOMBRE_REFUS:
        return _res("🔴", "image massivement trop sombre — ajoute de la lumière puis relance le réglage d'exposition", mesures)
    if stabilite > STAB_AMPL_REFUS:
        return _res("🔴", "image instable (clignote) — vérifie l'éclairage et le 50 Hz", mesures)

    # --- 🟠 avertissements (exploitable, mais à surveiller) ---
    if lum < LUM_SOMBRE_AVERT:
        return _res("🟠", "image un peu sombre — ajoute de la lumière, ou continue si elle te paraît correcte", mesures)
    if lum > LUM_CLAIR_AVERT:
        return _res("🟠", "image très claire — réduis la lumière, ou continue si elle te paraît correcte", mesures)
    if pct_clairs > PCT_CLAIR_AVERT:
        return _res("🟠", "des zones très claires apparaissent — surveille la sur-exposition", mesures)
    if pct_sombres > PCT_SOMBRE_AVERT:
        return _res("🟠", "des zones très sombres apparaissent — surveille le sous-éclairage", mesures)

    # --- 🟢 ---
    return _res("🟢", "lumière OK", mesures)


def texte_verdict(nom, res):
    """Ligne prête à afficher, ex. : 'GLOBALE : 🟢 lumière OK  (zone utile : lum=... clairs=...%)'."""
    m = res.get("mesures", {})
    details = ""
    if m:
        peri = m.get("perimetre")
        peri = f"{peri} : " if peri else ""
        details = (f"   ({peri}lum={m.get('lum')}, clairs={m.get('pct_clairs')}%, "
                   f"sombres={m.get('pct_sombres')}%, stab={m.get('stabilite')})")
    return f"{nom} : {res['verdict']} {res['message']}{details}"
