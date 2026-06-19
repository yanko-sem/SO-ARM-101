#!/usr/bin/env python3
"""
Module SEM_so101_camera_config.py
Service Écoles-Médias (SEM) - DIP Genève

VERROUILLAGE MATÉRIEL DES CAMÉRAS (exposition / balance des blancs)
===================================================================

Fige les réglages caméra via v4l2-ctl pour garantir des images cohérentes
entre l'enregistrement (script 8) et le déploiement (script 11).

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
    python SEM_so101_camera_config.py --show
    python SEM_so101_camera_config.py --capture cam_top /dev/video0
    python SEM_so101_camera_config.py cam_top /dev/video0 cam_follower /dev/video2

Usage intégré (scripts 8 et 11) :
    from SEM_so101_camera_config import verrouiller_camera, capturer_reglages_camera

Auteur: Service Écoles-Médias (SEM)
Version: 5.1
"""

import os
import sys
import json
import time
import subprocess

SETTINGS_FILE = os.path.expanduser("~/lerobot/calibration/camera_settings.json")

# Interrupteurs "auto coupé" — toujours forcés (mécanisme, pas réglage réglable)
AUTO_OFF = {
    "auto_exposure": 1,                 # 1 = manuel
    "white_balance_automatic": 0,
    "exposure_dynamic_framerate": 0,
}


def _lire_fichier_settings():
    """Lit camera_settings.json en distinguant trois cas :
      ('absent', {})    : fichier inexistant (cas normal au 1er lancement) ;
      ('ok', data)      : fichier lu, JSON valide et de type dict ;
      ('corrompu', {})  : fichier présent mais illisible / non-JSON / non-dict.
    Distinguer 'corrompu' de 'absent' évite d'écraser silencieusement un fichier
    abîmé — et donc de perdre les réglages des autres caméras."""
    if not os.path.exists(SETTINGS_FILE):
        return 'absent', {}
    try:
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)
    except Exception:
        return 'corrompu', {}
    if not isinstance(data, dict):
        return 'corrompu', {}
    return 'ok', data


def _charger_tout():
    """Charge le JSON complet (toutes caméras) ; dict vide si absent OU corrompu.
    Pour distinguer les deux cas, utiliser _lire_fichier_settings()."""
    return _lire_fichier_settings()[1]


def charger_reglages_camera(nom_camera):
    """Retourne la section nom_camera SI c'est un dictionnaire non vide,
    sinon None (section absente, vide, ou de type invalide).

    On ne fabrique PAS de valeurs par défaut : une exposition arbitraire
    pourrait rendre l'image noire ou saturée selon la caméra. C'est la capture
    qui crée la section.
    """
    section = _charger_tout().get(nom_camera)
    return section if isinstance(section, dict) and section else None


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
    elif not isinstance(reglages, dict):
        print(f"   ⚠️  section invalide ({type(reglages).__name__}) — ignorée")
    else:
        for k, v in reglages.items():
            print(f"   {k} {'.' * max(2, 34 - len(k))} {v}")
    print("   " + "-" * 44)


def afficher_reglages_enregistres():
    """Affiche tout le contenu de camera_settings.json (option --show)."""
    etat, data = _lire_fichier_settings()
    print(f"\n📂 {SETTINGS_FILE}")
    if etat == 'corrompu':
        print("   ⚠️  fichier présent mais illisible/corrompu.")
        print("   → Relance une capture pour le régénérer, ou inspecte-le manuellement.")
        return
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
    etat, data = _lire_fichier_settings()
    if etat == 'corrompu':
        # Fichier présent mais illisible : NE PAS l'écraser en silence (on
        # perdrait les réglages des AUTRES caméras). On sauvegarde l'ancien
        # fichier puis on repart à neuf, après confirmation explicite.
        print(f"\n   ⚠️  {SETTINGS_FILE} est illisible (corrompu).")
        print("       Repartir d'un fichier vierge fera perdre les réglages des AUTRES caméras.")
        if input("       Sauvegarder l'ancien fichier et continuer ? [o/N] : ").strip().lower() != 'o':
            print("   Capture annulée (fichier corrompu laissé tel quel).")
            return None
        sauvegarde = SETTINGS_FILE + ".corrupt." + time.strftime("%Y%m%d_%H%M%S")
        try:
            os.rename(SETTINGS_FILE, sauvegarde)
            print(f"   Ancien fichier sauvegardé sous : {sauvegarde}")
        except Exception as e:
            print(f"   ❌ Sauvegarde impossible ({e}).")
            print("   Capture annulée pour ne pas écraser un fichier corrompu non sauvegardé.")
            return None
        data = {}
    actuel = data.get(nom_camera)
    if actuel is not None and not isinstance(actuel, dict):
        print(f"   ⚠️  Section '{nom_camera}' invalide dans camera_settings.json — elle sera remplacée.")
        actuel = None

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
    Si le fichier est corrompu ou qu'aucun réglage VALIDE n'est défini pour cette
    caméra : ne touche à rien, prévient, et retourne False. Retourne True seulement
    si tous les contrôles sont confirmés.
    """
    etat, data = _lire_fichier_settings()
    if etat == 'corrompu':
        print(f"   ⚠️  {SETTINGS_FILE} illisible/corrompu — verrouillage {nom_camera} "
              f"ignoré (relance la capture pour le régénérer).")
        return False
    reglages = data.get(nom_camera)
    if not isinstance(reglages, dict) or not reglages:
        print(f"   ⚠️  Aucun réglage valide pour {nom_camera} — verrouillage ignoré (lance la capture).")
        return False
    print(f"   {device} ({nom_camera}) :")
    ok = True
    for controle, valeur in reglages.items():
        try:
            valeur_int = int(valeur)
        except (TypeError, ValueError):
            print(f"      ✗ {controle} : valeur invalide dans camera_settings.json ({valeur!r})")
            ok = False
            continue
        try:
            subprocess.run(["v4l2-ctl", "-d", device, f"--set-ctrl={controle}={valeur_int}"],
                           capture_output=True, text=True)
        except FileNotFoundError:
            print("      ❌ v4l2-ctl introuvable (sudo apt install v4l-utils)")
            return False
        lu = _lire_controle(device, controle)
        if lu is not None and lu == valeur_int:
            print(f"      ✓ {controle} = {valeur_int}")
        else:
            print(f"      ✗ {controle} (demandé {valeur_int}, lu {lu})")
            ok = False
    return ok


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 1 and args[0] == "--show":
        # python SEM_so101_camera_config.py --show
        afficher_reglages_enregistres()
    elif len(args) >= 3 and args[0] == "--capture":
        # python SEM_so101_camera_config.py --capture <nom_camera> /dev/videoX
        capturer_reglages_camera(args[2], args[1], forcer=True)
    elif len(args) >= 2 and len(args) % 2 == 0:
        # python SEM_so101_camera_config.py <nom> /dev/videoX [<nom> /dev/videoY ...]
        print("🔧 Verrouillage des caméras...")
        for i in range(0, len(args), 2):
            verrouiller_camera(args[i + 1], args[i])
        print("🎉 Terminé.")
    else:
        print("Usage :")
        print("  Voir      : python SEM_so101_camera_config.py --show")
        print("  Capturer  : python SEM_so101_camera_config.py --capture <nom> /dev/videoX")
        print("  Appliquer : python SEM_so101_camera_config.py <nom> /dev/videoX [<nom> /dev/videoY ...]")
        sys.exit(1)
