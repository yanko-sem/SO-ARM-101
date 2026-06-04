#!/usr/bin/env python3
"""
Module SEM_8_camera_config.py
Service Écoles-Médias (SEM) - DIP Genève

VERROUILLAGE MATÉRIEL DES CAMÉRAS (exposition / balance des blancs)
===================================================================

Fige les réglages caméra via v4l2-ctl pour garantir des images cohérentes
entre l'enregistrement (script 8) et le déploiement (script 12).

Un réglage PAR caméra (JSON imbriqué). La capture lance guvcview pour régler
l'image en direct, puis te laisse confirmer/corriger les valeurs lues. Chaque
contrôle est relu après application pour confirmer qu'il a bien été pris (✓/✗).
Aucune valeur n'est fabriquée silencieusement : si une caméra n'a pas de réglage
défini, le verrouillage est ignoré (il faut lancer la capture).

Séparation stricte (même principe que repos_position.json) :
  - les VALEURS sont dans ~/lerobot/calibration/camera_settings.json
  - ce module ne contient que le MÉCANISME

Pré-requis : v4l-utils (sudo apt install v4l-utils) et guvcview (sudo apt install guvcview)

Usage autonome :
    python SEM_8_camera_config.py --show
    python SEM_8_camera_config.py --capture cam_top /dev/video0
    python SEM_8_camera_config.py cam_top /dev/video0 cam_follower /dev/video2

Usage intégré (scripts 8 et 12) :
    from SEM_8_camera_config import verrouiller_camera, capturer_reglages_camera

Auteur: Service Écoles-Médias (SEM)
Version: 5.0
"""

import os
import sys
import json
import subprocess

SETTINGS_FILE = os.path.expanduser("~/lerobot/calibration/camera_settings.json")

# Interrupteurs "auto coupé" — toujours forcés (mécanisme, pas réglage réglable)
AUTO_OFF = {
    "auto_exposure": 1,                 # 1 = manuel
    "white_balance_automatic": 0,
    "exposure_dynamic_framerate": 0,
}


def _charger_tout():
    """Charge le JSON complet (toutes caméras) ; dict vide si absent/invalide."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def charger_reglages_camera(nom_camera):
    """Retourne la section nom_camera, ou None si absente.

    On ne fabrique PAS de valeurs par défaut : une exposition arbitraire
    pourrait rendre l'image noire ou saturée selon la caméra. C'est la capture
    qui crée la section.
    """
    return _charger_tout().get(nom_camera)


def _lire_controle(device, controle):
    """Lit la valeur actuelle d'un contrôle via v4l2-ctl --get-ctrl."""
    try:
        r = subprocess.run(["v4l2-ctl", "-d", device, f"--get-ctrl={controle}"],
                           capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if r.returncode == 0 and ":" in r.stdout:
        try:
            return int(r.stdout.split(":", 1)[1].strip())
        except ValueError:
            return None
    return None


def _saisir_entier(label, lu):
    """Entrée garde la valeur lue si elle existe ; si lu est None, pas de défaut
    fabriqué (taper une valeur, ou Entrée = ignorer). Redemande si saisie invalide."""
    while True:
        if lu is not None:
            rep = input(f"      {label} (lu : {lu}) — Entrée pour garder, ou tape un nombre : ").strip()
            if rep == "":
                return lu
        else:
            rep = input(f"      {label} non lisible — tape une valeur (Entrée = ignorer) : ").strip()
            if rep == "":
                return None
        try:
            return int(rep)
        except ValueError:
            print(f"      ⚠️  « {rep} » n'est pas un entier valide, réessaie.")


def _afficher_reglages(titre, reglages):
    """Affiche un bloc de réglages aligné (style script 5)."""
    print(f"\n📊 {titre} :")
    print("   " + "-" * 44)
    if not reglages:
        print("   (aucun réglage enregistré)")
    else:
        for k, v in reglages.items():
            print(f"   {k} {'.' * max(2, 34 - len(k))} {v}")
    print("   " + "-" * 44)


def afficher_reglages_enregistres():
    """Affiche tout le contenu de camera_settings.json (option --show)."""
    data = _charger_tout()
    print(f"\n📂 {SETTINGS_FILE}")
    if not data:
        print("   (fichier absent ou vide — aucun réglage enregistré)")
        return
    for cam, reglages in data.items():
        _afficher_reglages(cam, reglages)


def capturer_reglages_camera(device, nom_camera, forcer=False, titre=None):
    """Crée/met à jour la section nom_camera de camera_settings.json.

    Affiche d'abord les réglages actuellement enregistrés (référence). Si une
    section existe et forcer=False : propose [Entrée] garder / [R] refaire.
    Pour (re)définir : lance guvcview (réglage live), relit les valeurs et te
    laisse les confirmer (Entrée) ou les corriger, affiche un avant→après, puis
    demande de valider ou recommencer. Aucune valeur fabriquée ; seuls les
    contrôles présents sur la caméra sont enregistrés. Les autres caméras du
    fichier sont préservées.
    """
    entete = titre if titre else nom_camera
    data = _charger_tout()
    actuel = data.get(nom_camera)

    print("\n" + "=" * 60)
    print(f"  RÉGLAGES CAMÉRA — {entete}")
    print("=" * 60)
    _afficher_reglages("Réglages actuellement enregistrés", actuel)

    if actuel and not forcer:
        print("\n  [Entrée] : garder ces réglages")
        print("  [R]      : refaire le réglage avec guvcview")
        if input("Choix : ").strip().upper() != 'R':
            return actuel

    while True:
        print(f"\n📸 guvcview va s'ouvrir sur {device}.")
        print("   → DÉCOCHE « Auto » pour l'exposition, ajuste, puis FERME guvcview.")
        try:
            r = subprocess.run(["guvcview", "-d", device],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode != 0:
                print("   ⚠️  guvcview s'est terminé avec un code non nul — vérifie que la bonne caméra a bien été réglée.")
        except FileNotFoundError:
            print("   ⚠️  guvcview introuvable (sudo apt install guvcview) — saisis les valeurs à la main.")

        if _lire_controle(device, "auto_exposure") not in (None, 1):
            print("\n   ⚠️  La caméra semble encore en mode AUTO : l'exposition lue peut être peu fiable.")

        print("\n   Confirme ou corrige les valeurs :")
        reglages = {}
        for ctrl, val in AUTO_OFF.items():           # interrupteurs auto : seulement s'ils existent
            if _lire_controle(device, ctrl) is not None:
                reglages[ctrl] = val
        for ctrl, label in [("exposure_time_absolute", "Exposition"),
                            ("white_balance_temperature", "Balance des blancs"),
                            ("gain", "Gain")]:
            v = _saisir_entier(label, _lire_controle(device, ctrl))
            if v is not None:
                reglages[ctrl] = v

        print("\n📊 Avant  →  Après :")
        print("   " + "-" * 44)
        for k in [c for c in reglages if c not in AUTO_OFF]:
            avant = actuel.get(k, "—") if actuel else "—"
            print(f"   {k} {'.' * max(2, 30 - len(k))} {str(avant):>5}  →  {reglages[k]}")
        print("   " + "-" * 44)

        print("\n  [Entrée] : valider et enregistrer")
        print("  [R]      : recommencer le réglage")
        if input("Choix : ").strip().upper() != 'R':
            break

    data[nom_camera] = reglages
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    resume = ", ".join(f"{k}={v}" for k, v in reglages.items() if k not in AUTO_OFF)
    print(f"\n   ✅ {nom_camera} enregistrée : {resume if resume else '(aucune valeur)'}")
    return reglages


def verrouiller_camera(device, nom_camera):
    """Applique la section nom_camera à la caméra via v4l2-ctl, avec relecture.

    Chaque contrôle est réglé PUIS relu pour confirmer la prise (✓/✗).
    Si aucun réglage n'est défini pour cette caméra : ne touche à rien, prévient,
    et retourne False. Retourne True seulement si tous les contrôles sont confirmés.
    """
    reglages = charger_reglages_camera(nom_camera)
    if not reglages:
        print(f"   ⚠️  Aucun réglage défini pour {nom_camera} — verrouillage ignoré (lance la capture).")
        return False
    print(f"   {device} ({nom_camera}) :")
    ok = True
    for controle, valeur in reglages.items():
        try:
            subprocess.run(["v4l2-ctl", "-d", device, f"--set-ctrl={controle}={valeur}"],
                           capture_output=True, text=True)
        except FileNotFoundError:
            print("      ❌ v4l2-ctl introuvable (sudo apt install v4l-utils)")
            return False
        lu = _lire_controle(device, controle)
        if lu is not None and lu == int(valeur):
            print(f"      ✓ {controle} = {valeur}")
        else:
            print(f"      ✗ {controle} (demandé {valeur}, lu {lu})")
            ok = False
    return ok


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 1 and args[0] == "--show":
        # python SEM_8_camera_config.py --show
        afficher_reglages_enregistres()
    elif len(args) >= 3 and args[0] == "--capture":
        # python SEM_8_camera_config.py --capture <nom_camera> /dev/videoX
        capturer_reglages_camera(args[2], args[1], forcer=True)
    elif len(args) >= 2 and len(args) % 2 == 0:
        # python SEM_8_camera_config.py <nom> /dev/videoX [<nom> /dev/videoY ...]
        print("🔧 Verrouillage des caméras...")
        for i in range(0, len(args), 2):
            verrouiller_camera(args[i + 1], args[i])
        print("🎉 Terminé.")
    else:
        print("Usage :")
        print("  Voir      : python SEM_8_camera_config.py --show")
        print("  Capturer  : python SEM_8_camera_config.py --capture <nom> /dev/videoX")
        print("  Appliquer : python SEM_8_camera_config.py <nom> /dev/videoX [<nom> /dev/videoY ...]")
        sys.exit(1)
