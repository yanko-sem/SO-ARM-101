#!/usr/bin/env python3
"""
Script SEM_so101_10_train.py
Service Écoles-Médias (SEM) - DIP Genève

ENTRAÎNEMENT DU MODÈLE ACT POUR SO-ARM 101
============================================

Ce script lance l'entraînement d'une politique ACT
(Action Chunking with Transformers) sur le dataset consolidé.

Matériel de référence : Quadro RTX 4000 (8 Go VRAM). CPU possible, mais beaucoup plus lent.
Dataset : so101_pick_place_consolidated (50 épisodes, 2 caméras)

Auteur: Service Écoles-Médias (SEM)
Version: 1.1
"""

import os
import sys
import json
import subprocess
import shutil
import re
from pathlib import Path
from datetime import datetime

# Auto-activation de l'environnement lerobot si nécessaire
try:
    import torch
except ImportError:
    lerobot_python = os.path.expanduser("~/miniconda3/envs/lerobot/bin/python3")
    if os.path.exists(lerobot_python):
        print("\n🔧 Activation automatique de l'environnement lerobot...")
        subprocess.call([lerobot_python] + sys.argv)
        sys.exit(0)
    else:
        print("❌ Environnement lerobot non trouvé!")
        print("Solution: conda activate lerobot")
        sys.exit(1)

# ============================================
# CONFIGURATION
# ============================================

DATASET_PATH = Path(os.path.expanduser(
    "~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated"
))

LEROBOT_DIR = Path(os.path.expanduser("~/lerobot"))

TRAIN_SCRIPT = LEROBOT_DIR / "lerobot" / "scripts" / "train.py"

# Base commune des modèles nommés (registre local). Chaque modèle est un
# sous-dossier de TRAIN_BASE contenant sa propre structure LeRobot
# (checkpoints/<step>/pretrained_model). OUTPUT_DIR est déterminé APRÈS le
# choix du modèle (voir selectionner_ou_creer_modele et main) : il reste None
# tant qu'aucun modèle n'a été choisi.
TRAIN_BASE = LEROBOT_DIR / "outputs" / "train"

OUTPUT_DIR = None

# Paramètres d'entraînement optimisés pour la machine GPU de référence (Quadro
# RTX 4000, 8 Go VRAM) ; utilisables aussi sur CPU, avec des temps beaucoup plus longs.
TRAINING_CONFIGS = {
    "standard": {
        "nom": "Standard (recommandé)",
        "description": "100k steps, batch 4 — ~4-6h sur Quadro RTX 4000",
        "batch_size": 4,
        "steps": 100000,
        "save_freq": 10000,
        "log_freq": 100,
        "chunk_size": 50,
        "n_action_steps": 15,
    },
    "rapide": {
        "nom": "Rapide (test)",
        "description": "10k steps, batch 4 — ~30min, pour vérifier que tout fonctionne",
        "batch_size": 4,
        "steps": 10000,
        "save_freq": 2000,
        "log_freq": 100,
        "chunk_size": 50,
        "n_action_steps": 15,
    },
    "intermediaire": {
        "nom": "Intermédiaire",
        "description": "50k steps, batch 4 — ~2-3h, souvent suffisant",
        "batch_size": 4,
        "steps": 50000,
        "save_freq": 5000,
        "log_freq": 100,
        "chunk_size": 50,
        "n_action_steps": 15,
    },
    "intensif": {
        "nom": "Intensif",
        "description": "200k steps, batch 4 — ~8-12h, si 100k insuffisant",
        "batch_size": 4,
        "steps": 200000,
        "save_freq": 20000,
        "log_freq": 100,
        "chunk_size": 50,
        "n_action_steps": 15,
    },
}

# ============================================
# FONCTIONS
# ============================================

def clear_screen():
    os.system('clear')


NOM_MODELE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def nom_modele_valide(nom):
    """Vrai si `nom` respecte la convention sûre [a-z0-9_-], non vide.

    On REFUSE (sans réécrire) tout nom hors convention : une espace, un accent,
    un '/' ou un '.' casserait le chemin du dossier modèle. Le nom est libre
    par ailleurs (aucun préfixe imposé)."""
    return bool(nom) and NOM_MODELE_RE.match(nom) is not None


def checkpoint_chargeable(cp):
    """Vrai si le checkpoint `cp` (dossier d'un pas, ex. .../checkpoints/002000)
    est RÉELLEMENT chargeable par ACTPolicy.from_pretrained() : son
    pretrained_model/ contient config.json ET model.safetensors (les deux
    fichiers que from_pretrained consomme). Un checkpoint partiel est écarté."""
    pm = cp / "pretrained_model"
    return (pm.is_dir()
            and (pm / "config.json").exists()
            and (pm / "model.safetensors").exists())


def lister_modeles():
    """Liste triée des dossiers de modèles VALIDES sous TRAIN_BASE.

    Un modèle est valide s'il contient au moins un checkpoint RÉELLEMENT
    chargeable : un dossier checkpoints/<step>/pretrained_model contenant
    config.json ET model.safetensors — les deux fichiers que
    ACTPolicy.from_pretrained() consomme (config du policy + poids). Le filtre
    est STRUCTUREL (pas basé sur le nom) ; un checkpoint partiel/incomplet est
    ignoré."""
    if not TRAIN_BASE.exists():
        return []
    modeles = []
    for d in sorted(TRAIN_BASE.iterdir()):
        if not d.is_dir():
            continue
        ckpt = d / "checkpoints"
        if ckpt.is_dir() and any(
                checkpoint_chargeable(cp) for cp in ckpt.iterdir()):
            modeles.append(d)
    return modeles


def selectionner_ou_creer_modele():
    """Choix du modèle à entraîner (registre local de modèles nommés).

    - Liste les modèles existants (pour les reprendre, prolonger ou remplacer).
    - Permet de créer un nouveau modèle nommé.
    Retourne le NOM du modèle (dossier = TRAIN_BASE/<nom>), ou None si l'on
    quitte. Nom libre dans [a-z0-9_-], aucun préfixe imposé, aucun défaut : la
    saisie est explicite (fail-closed : pas d'état caché, pas de réécriture)."""
    while True:
        modeles = lister_modeles()

        print("\n" + "=" * 60)
        print("📂 MODÈLE À ENTRAÎNER")
        print("=" * 60)

        if modeles:
            print(f"\n📋 Modèles existants ({len(modeles)}) :")
            for i, d in enumerate(modeles, start=1):
                n_ok = sum(1 for cp in (d / "checkpoints").iterdir()
                           if checkpoint_chargeable(cp))
                print(f"   [{i:>2}]  {d.name:<32} ({n_ok} checkpoint(s))")
        else:
            print("\n   (aucun modèle existant pour l'instant)")

        print("\n   [C] Créer un nouveau modèle")
        print("   [Q] Quitter")
        choix = input("\n→ Votre choix (numéro, C ou Q) : ").strip()

        if choix.upper() == "Q":
            return None

        if choix.upper() == "C":
            nom = input(
                "\n   Nom du nouveau modèle (a-z, 0-9, '-', '_') : ").strip()
            if not nom_modele_valide(nom):
                print("\n   ❌ Nom refusé. Autorisé : a-z, 0-9, '-', '_' "
                      "(sans espace ni accent) ; le nom doit commencer par une "
                      "lettre ou un chiffre.")
                input("   Appuyez sur ENTRÉE pour réessayer...")
                continue
            cible = TRAIN_BASE / nom
            if cible.exists():
                # Le dossier existe déjà (modèle complet OU partiel/échoué). On
                # NE bloque PAS : on retourne ce nom pour que
                # reprendre_entrainement() propose reprendre / prolonger /
                # remplacer / autre modèle / quitter — y compris pour un dossier
                # incomplet sans checkpoint reprenable. Sinon un dossier partiel
                # bloquerait définitivement ce nom (impasse).
                print(f"\n   ℹ️  « {nom} » existe déjà — reprise ou remplacement "
                      "proposés à l'étape suivante.")
            return nom

        if choix.isdigit() and 1 <= int(choix) <= len(modeles):
            return modeles[int(choix) - 1].name

        print("\n   ❌ Choix invalide.")
        input("   Appuyez sur ENTRÉE pour réessayer...")


def verifier_prerequis():
    """Vérifie que tout est prêt pour l'entraînement"""
    print("\n🔍 Vérification des prérequis...")
    erreurs = []

    # 1. CUDA — GPU fortement recommandé mais NON obligatoire. Sans CUDA,
    #    l'entraînement tourne sur CPU (beaucoup plus lent). LeRobot bascule
    #    lui-même device/AMP si besoin ; le script transmet déjà device=cpu
    #    et use_amp=false plus bas.
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"  ✅ GPU : {gpu_name} ({vram:.1f} Go VRAM)")
    else:
        print("  ⚠️  Pas de GPU CUDA détecté — l'entraînement utilisera le CPU.")
        print("      C'est possible, mais BEAUCOUP plus lent. GPU NVIDIA fortement recommandé.")
        print("      (Les durées indiquées dans les profils sont des estimations sur GPU.)")

    # 2. Dataset
    info_file = DATASET_PATH / "meta" / "info.json"
    if info_file.exists():
        # Lecture fail-closed : un info.json corrompu doit produire une erreur
        # propre dans la liste, jamais un traceback Python.
        info = None
        try:
            with open(info_file) as f:
                info = json.load(f)
        except Exception as e:
            erreurs.append(f"info.json illisible : {e}")

        if info is not None:
            episodes = info.get('total_episodes', 0)
            frames = info.get('total_frames', 0)
            print(f"  ✅ Dataset : {episodes} épisodes, {frames} frames")

            # Préflight : un dataset déclaré vide ne doit pas lancer l'entraînement.
            if episodes <= 0 or frames <= 0:
                erreurs.append(
                    f"Dataset vide : total_episodes={episodes}, total_frames={frames}"
                )

            # Afficher les features réellement détectées (caméras, état, action)
            # pour confirmer d'un coup d'œil la cohérence du dataset.
            features = info.get('features', {})
            cameras = sorted(k for k in features if k.startswith("observation.images."))
            print(f"  ✅ Caméras détectées : {len(cameras)}")
            for cle_cam in cameras:
                print(f"       • {cle_cam}  (shape {features[cle_cam].get('shape', '?')})")

            # Vérification bloquante : les deux caméras attendues doivent être présentes
            # (noms définis dans le script 8 : cam_top + cam_follower).
            for cle_attendue in ("observation.images.cam_top", "observation.images.cam_follower"):
                if cle_attendue not in features:
                    erreurs.append(f"Caméra attendue manquante : {cle_attendue}")

            for cle in ("observation.state", "action"):
                if cle in features:
                    print(f"  ✅ {cle}  (shape {features[cle].get('shape', '?')})")
                else:
                    erreurs.append(f"Feature manquante dans le dataset : {cle}")

        # Préflight de structure sur disque (garde-fou runtime, indépendant du
        # contenu d'info.json) : au moins un parquet et les deux dossiers vidéo
        # attendus. Le script 9 reste responsable de la validation lourde
        # (frames, durées, résolution) ; ici on échoue proprement si le dataset
        # a été déplacé, amputé ou mal reconstruit depuis la consolidation.
        if not list((DATASET_PATH / "data").glob("**/*.parquet")):
            erreurs.append("Aucun fichier parquet trouvé dans le dataset consolidé")

        videos_root = DATASET_PATH / "videos"
        for cam in ("cam_top", "cam_follower"):
            cle_cam = f"observation.images.{cam}"
            # Tolérant à la numérotation des chunks (videos/chunk-XXX/<cle>)
            # comme à une disposition à plat éventuelle (videos/<cle>).
            if not list(videos_root.glob(f"*/{cle_cam}")) and not (videos_root / cle_cam).exists():
                erreurs.append(f"Dossier vidéo manquant : {cle_cam}")
    else:
        erreurs.append(f"Dataset introuvable : {DATASET_PATH}")

    # 3. Stats
    stats_file = DATASET_PATH / "meta" / "episodes_stats.jsonl"
    if stats_file.exists():
        print(f"  ✅ Statistiques : episodes_stats.jsonl présent")
    else:
        erreurs.append("episodes_stats.jsonl manquant — lancez le script 9")

    # 4. Script d'entraînement
    if TRAIN_SCRIPT.exists():
        print(f"  ✅ Script LeRobot : train.py trouvé")
    else:
        erreurs.append(f"Script d'entraînement introuvable : {TRAIN_SCRIPT}")

    # 5. PyTorch
    print(f"  ✅ PyTorch : {torch.__version__}")
    if torch.cuda.is_available():
        print(f"  ✅ CUDA : {torch.version.cuda}")

    # 6. PyAV — requis car la commande impose --dataset.video_backend=pyav.
    # Sans ce contrôle, l'échec n'apparaîtrait que tardivement dans LeRobot.
    try:
        import av
        print(f"  ✅ PyAV : {av.__version__}")
    except ImportError:
        erreurs.append("PyAV manquant — requis car --dataset.video_backend=pyav")

    # 7. Espace disque (fail-closed : ~/lerobot doit exister avant disk_usage,
    # sinon shutil.disk_usage lèverait FileNotFoundError au lieu d'un message).
    if not LEROBOT_DIR.exists():
        erreurs.append(f"Dossier LeRobot introuvable : {LEROBOT_DIR}")
    else:
        free_space = shutil.disk_usage(str(LEROBOT_DIR)).free / (1024**3)
        if free_space < 5:
            erreurs.append(f"Espace disque insuffisant : {free_space:.1f} Go (minimum 5 Go)")
        else:
            print(f"  ✅ Espace disque : {free_space:.1f} Go disponibles")

    return erreurs


def afficher_menu_config():
    """Affiche le menu de sélection de la configuration"""
    print(f"""
╔══════════════════════════════════════════════════════════╗
║          CONFIGURATION D'ENTRAÎNEMENT                    ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  1. {TRAINING_CONFIGS['rapide']['nom']:40}     ║
║     {TRAINING_CONFIGS['rapide']['description']:51} ║
║                                                          ║
║  2. {TRAINING_CONFIGS['intermediaire']['nom']:40}     ║
║     {TRAINING_CONFIGS['intermediaire']['description']:51} ║
║                                                          ║
║  3. {TRAINING_CONFIGS['standard']['nom']:40}     ║
║     {TRAINING_CONFIGS['standard']['description']:51} ║
║                                                          ║
║  4. {TRAINING_CONFIGS['intensif']['nom']:40}     ║
║     {TRAINING_CONFIGS['intensif']['description']:51} ║
║                                                          ║
║  Q. Quitter                                              ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

    choix = input("  Votre choix [1/2/3/4/Q] : ").strip().upper()

    if choix == '1':
        return "rapide"
    elif choix == '2':
        return "intermediaire"
    elif choix == '3':
        return "standard"
    elif choix == '4':
        return "intensif"
    else:
        return None


def ajouter_inhibition_systeme(cmd):
    """Protège l'entraînement contre veille, extinction et inactivité si systemd-inhibit existe.

    systemd-inhibit ne nécessite normalement pas de mot de passe utilisateur.
    Si l'outil n'est pas disponible, on lance la commande normale avec un avertissement.
    """
    inhibit = shutil.which("systemd-inhibit")
    if inhibit is None:
        print("⚠️  systemd-inhibit introuvable : entraînement lancé sans protection veille/extinction.")
        return cmd

    return [
        inhibit,
        "--what=sleep:shutdown:idle",
        "--why=Entraînement LeRobot ACT en cours",
        "--mode=block",
    ] + cmd


def charger_params_sem():
    """Charge sem_training_params.json sans jamais bloquer la reprise.

    Ce fichier est informatif pour l'interface SEM. La reprise LeRobot fiable
    utilise le train_config.json du checkpoint, pas ce fichier. S'il est absent,
    vide ou corrompu, on l'ignore proprement.
    """
    params_file = OUTPUT_DIR / "sem_training_params.json"
    if not params_file.exists():
        return None
    try:
        with open(params_file) as f:
            return json.load(f)
    except Exception as e:
        print(f"   ⚠️  sem_training_params.json illisible — ignoré ({e})")
        return None


def checkpoint_pour_reprise(checkpoints):
    """Retourne le checkpoint à reprendre : priorité à 'last', sinon dernier checkpoint valide trié.

    Un checkpoint est considéré reprenable seulement s'il contient
    pretrained_model/train_config.json, requis par la version actuelle de LeRobot.
    """
    checkpoints_dir = OUTPUT_DIR / "checkpoints"
    last = checkpoints_dir / "last"
    if last.exists() and (last / "pretrained_model" / "train_config.json").exists():
        return last

    checkpoints_valides = [
        cp for cp in checkpoints
        if (cp / "pretrained_model" / "train_config.json").exists()
    ]
    if checkpoints_valides:
        # Tri par valeur entière (et non alphabétique) : sinon "50000" passerait
        # après "200000" et la reprise repartirait d'un checkpoint plus ancien.
        checkpoints_valides.sort(
            key=lambda cp: int(cp.name) if cp.name.isdigit() else -1
        )
        return checkpoints_valides[-1]
    return None


def lancer_entrainement(config_key, effacer_ancien=False):
    """Lance l'entraînement avec la configuration choisie"""
    config = TRAINING_CONFIGS[config_key]

    print(f"\n🚀 Lancement de l'entraînement : {config['nom']}")
    print(f"   Steps : {config['steps']}")
    print(f"   Batch size : {config['batch_size']}")
    print(f"   Chunk size : {config['chunk_size']}")
    print(f"   Checkpoints : tous les {config['save_freq']} steps")
    print(f"   Sortie : {OUTPUT_DIR}")

    # Construire la commande
    cmd = [
        sys.executable,
        str(TRAIN_SCRIPT),
        "--dataset.repo_id=local/so101_pick_place_consolidated",
        "--dataset.video_backend=pyav",
        f"--policy.type=act",
        f"--policy.device={'cuda' if torch.cuda.is_available() else 'cpu'}",
        f"--policy.use_amp={'true' if torch.cuda.is_available() else 'false'}",
        f"--policy.chunk_size={config['chunk_size']}",
        f"--policy.n_action_steps={config['n_action_steps']}",
        f"--output_dir={OUTPUT_DIR}",
        f"--batch_size={config['batch_size']}",
        f"--steps={config['steps']}",
        f"--save_freq={config['save_freq']}",
        f"--log_freq={config['log_freq']}",
        f"--save_checkpoint=true",
        f"--wandb.enable=false",
        f"--eval_freq=0",
    ]

    print(f"\n📋 Commande :")
    print(f"   {' '.join(cmd[1:])}")

    # Confirmation
    duree_ref = config['description'].split('—')[1].strip()
    if torch.cuda.is_available():
        print(f"\n⏱️  Durée estimée : {duree_ref}")
    else:
        print(f"\n⏱️  Durée estimée (sur GPU de référence) : {duree_ref}")
        print("   Sur CPU : non estimée, probablement beaucoup plus longue.")
    print(f"   L'entraînement peut être interrompu avec Ctrl+C")
    print(f"   Les checkpoints sont sauvegardés régulièrement\n")

    choix = input("   Lancer ? [O/N] : ").strip().upper()
    if choix != 'O':
        print("   Annulé.")
        return False

    # Remplacement d'un modèle existant : suppression UNIQUEMENT après cette
    # confirmation finale ET une confirmation forte (saisie de SUPPRIMER).
    # Fail-closed : toute autre saisie annule sans rien supprimer. LeRobot
    # refuse un output_dir déjà existant pour un entraînement neuf
    # (FileExistsError) : la suppression est donc nécessaire, mais jamais
    # silencieuse.
    if effacer_ancien and OUTPUT_DIR.exists():
        print(f"\n⚠️  REMPLACEMENT du modèle : {OUTPUT_DIR}")
        print("   Cette opération SUPPRIME définitivement ce modèle et tous ses checkpoints.")
        conf = input("   Tapez SUPPRIMER (en majuscules) pour confirmer, ou ENTRÉE pour annuler : ").strip()
        if conf != "SUPPRIMER":
            print("   Annulé — modèle existant conservé.")
            return False
        print(f"\n🗑️  Suppression du modèle existant : {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
        print("   ✅ Modèle existant supprimé.")

    # Lancer
    print("\n" + "=" * 60)
    print("  ENTRAÎNEMENT EN COURS")
    print("  Ctrl+C pour interrompre (les checkpoints sont sauvegardés)")
    print("=" * 60 + "\n")

    start_time = datetime.now()

    def _ecrire_params_sem():
        # Métadonnées SEM écrites DANS le dossier du modèle, une fois celui-ci
        # créé par LeRobot. On n'écrit jamais avant le lancement : un output_dir
        # non vide ferait échouer un entraînement neuf. Informatif uniquement.
        if not OUTPUT_DIR.exists():
            return
        params = {
            "config": config_key,
            "params": config,
            "dataset": str(DATASET_PATH),
            "started_at": start_time.isoformat(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
            "output_dir": str(OUTPUT_DIR),
        }
        try:
            with open(OUTPUT_DIR / "sem_training_params.json", 'w') as f:
                json.dump(params, f, indent=2)
        except Exception as e:
            print(f"   ⚠️  Écriture de sem_training_params.json impossible — ignoré ({e})")

    try:
        cmd_exec = ajouter_inhibition_systeme(cmd)
        result = subprocess.run(cmd_exec, cwd=str(LEROBOT_DIR))
        _ecrire_params_sem()

        end_time = datetime.now()
        duration = end_time - start_time

        if result.returncode == 0:
            print(f"\n✅ Entraînement terminé avec succès !")
            print(f"   Durée : {duration}")
            print(f"   Modèle sauvegardé dans : {OUTPUT_DIR}")
            afficher_checkpoints()
            return True
        else:
            print(f"\n❌ L'entraînement s'est terminé avec une erreur (code {result.returncode})")
            return False

    except KeyboardInterrupt:
        _ecrire_params_sem()
        end_time = datetime.now()
        duration = end_time - start_time
        print(f"\n\n⚠️  Entraînement interrompu par l'utilisateur")
        print(f"   Durée : {duration}")
        print(f"   Les checkpoints sauvegardés restent disponibles :")
        afficher_checkpoints()
        return False


def afficher_checkpoints():
    """Affiche les checkpoints disponibles"""
    checkpoints_dir = OUTPUT_DIR / "checkpoints"
    if not checkpoints_dir.exists():
        print("   Aucun checkpoint trouvé")
        return

    checkpoints = sorted(checkpoints_dir.glob("*/"))
    if checkpoints:
        print(f"\n  📁 Checkpoints disponibles ({len(checkpoints)}) :")
        for cp in checkpoints:
            # Vérifier la taille
            size = sum(f.stat().st_size for f in cp.rglob("*") if f.is_file())
            size_mb = size / (1024**2)
            print(f"     • {cp.name} ({size_mb:.0f} MB)")

        print(f"\n  🚀 Pour déployer le modèle :")
        print(f"     python SEM_so101_11_deploy.py")
    else:
        print("   Aucun checkpoint trouvé")



def steps_du_checkpoint(checkpoint):
    """Retourne le nombre de steps atteint par un checkpoint.
    Résout 'last' (lien symbolique) vers le dossier réel (ex. 200000).
    Si 'last' est un VRAI dossier (pas un lien), retombe sur le plus grand
    checkpoint numérique voisin."""
    nom = checkpoint.name
    if nom.isdigit():
        return int(nom)
    try:
        cible = checkpoint.resolve().name
        if cible.isdigit():
            return int(cible)
    except Exception:
        pass
    if nom == "last":
        try:
            numeriques = [
                int(cp.name)
                for cp in checkpoint.parent.iterdir()
                if cp.is_dir() and cp.name.isdigit()
            ]
            if numeriques:
                return max(numeriques)
        except Exception:
            pass
    return None


def profils_superieurs(step_actuel):
    """Retourne les profils dont le nombre de steps dépasse strictement step_actuel,
    triés par steps croissants. Liste de tuples (steps, save_freq, nom)."""
    return sorted(
        (
            (cfg["steps"], cfg["save_freq"], cfg["nom"])
            for cfg in TRAINING_CONFIGS.values()
            if cfg["steps"] > step_actuel
        ),
        key=lambda t: t[0],
    )


def reprendre_entrainement():
    """Vérifie si un entraînement précédent existe et peut être repris.

    Retourne :
      - "done" si une reprise a été lancée ou si l'utilisateur quitte ;
      - "new" si l'utilisateur demande un nouvel entraînement ;
      - "none" si aucun ancien dossier n'existe.
    """
    if not OUTPUT_DIR.exists():
        return "none"

    checkpoints_dir = OUTPUT_DIR / "checkpoints"

    if not checkpoints_dir.exists():
        print(f"\n⚠️  Dossier d'entraînement existant mais non reprenable :")
        print(f"   {OUTPUT_DIR}")
        print("   Aucun dossier checkpoints/ n'a été trouvé.")
        print("\n  N — Remplacer ce modèle (supprime l'existant, confirmation forte requise)")
        print("  A — Choisir un autre modèle")
        print("  Q — Quitter")
        choix = input("\n  Votre choix : ").strip().upper()
        if choix == 'N':
            print("\n⚠️  Remplacement demandé : l'ancien dossier sera supprimé seulement après confirmation forte (SUPPRIMER) au lancement.")
            return "new"
        elif choix == 'A':
            return "reselect"
        sys.exit(0)

    checkpoints = sorted([cp for cp in checkpoints_dir.glob("*/") if cp.is_dir()])
    checkpoints_valides = [
        cp for cp in checkpoints
        if (cp / "pretrained_model" / "train_config.json").exists()
    ]

    if not checkpoints_valides:
        print(f"\n⚠️  Dossier checkpoints présent mais aucun checkpoint reprenable trouvé :")
        print(f"   {checkpoints_dir}")
        print("   Aucun fichier pretrained_model/train_config.json n'a été trouvé.")
        print("\n  N — Remplacer ce modèle (supprime l'existant, confirmation forte requise)")
        print("  A — Choisir un autre modèle")
        print("  V — Voir les dossiers checkpoints")
        print("  Q — Quitter")
        choix = input("\n  Votre choix : ").strip().upper()
        if choix == 'N':
            print("\n⚠️  Remplacement demandé : l'ancien dossier sera supprimé seulement après confirmation forte (SUPPRIMER) au lancement.")
            return "new"
        elif choix == 'A':
            return "reselect"
        elif choix == 'V':
            afficher_checkpoints()
            input("\nAppuyez sur ENTRÉE...")
            return reprendre_entrainement()
        sys.exit(0)

    checkpoint_resume = checkpoint_pour_reprise(checkpoints_valides)
    if checkpoint_resume is None:
        print("\n❌ Aucun checkpoint avec train_config.json n'est disponible pour la reprise.")
        return "done"

    config_path = checkpoint_resume / "pretrained_model" / "train_config.json"

    print(f"\n📂 Entraînement précédent détecté :")
    print(f"   Checkpoint de reprise : {checkpoint_resume.name}")
    print(f"   Config de reprise     : {config_path}")

    # Afficher les paramètres SEM précédents si le fichier existe et est lisible.
    # Ce fichier est informatif : la reprise utilise le train_config.json du checkpoint.
    params = charger_params_sem()
    if params:
        print(f"   Configuration SEM : {params.get('config', '?')}")
        print(f"   Démarré le        : {params.get('started_at', '?')}")

    print(f"\n  R — Reprendre l'entraînement")
    print(f"  P — Prolonger l'entraînement (reprendre et augmenter le nombre de steps)")
    print(f"  N — Remplacer ce modèle (supprime l'existant, confirmation forte requise)")
    print(f"  A — Choisir un autre modèle")
    print(f"  V — Voir les checkpoints")
    print(f"  Q — Quitter")

    choix = input("\n  Votre choix : ").strip().upper()

    if choix == 'R':
        cmd = [
            sys.executable,
            str(TRAIN_SCRIPT),
            f"--config_path={config_path}",
            "--resume=true",
        ]

        print(f"\n🔄 Reprise de l'entraînement depuis {checkpoint_resume.name}...")
        print(f"   Ctrl+C pour interrompre\n")

        try:
            cmd_exec = ajouter_inhibition_systeme(cmd)
            result = subprocess.run(cmd_exec, cwd=str(LEROBOT_DIR))
            if result.returncode != 0:
                print(f"\n❌ La reprise s'est terminée avec une erreur (code {result.returncode})")
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Entraînement interrompu")
            afficher_checkpoints()

        return "done"

    elif choix == 'P':
        step_actuel = steps_du_checkpoint(checkpoint_resume)
        if step_actuel is None:
            print("\n❌ Impossible de déterminer le nombre de steps déjà atteint pour ce checkpoint.")
            input("\nAppuyez sur ENTRÉE...")
            return reprendre_entrainement()

        cibles = profils_superieurs(step_actuel)
        if not cibles:
            print(f"\n⚠️  Le checkpoint est déjà à {step_actuel} steps : aucun profil supérieur disponible (maximum 200000).")
            input("\nAppuyez sur ENTRÉE...")
            return reprendre_entrainement()

        print(f"\n📈 Prolongation depuis {step_actuel} steps. Cibles disponibles :")
        for i, (steps_cible, _sf, nom_cible) in enumerate(cibles, start=1):
            print(f"  {i} — {nom_cible} : {steps_cible} steps")
        print("  Q — Annuler")

        sel = input("\n  Votre choix : ").strip().upper()
        if sel == 'Q' or not sel.isdigit() or not (1 <= int(sel) <= len(cibles)):
            print("\n  Annulé.")
            return reprendre_entrainement()

        steps_cible, save_freq_cible, nom_cible = cibles[int(sel) - 1]

        print(f"\n  Reprise depuis {checkpoint_resume.name} (step {step_actuel})")
        print(f"  → Prolongation jusqu'à {steps_cible} steps ({nom_cible})")
        print(f"  → Checkpoints tous les {save_freq_cible} steps")
        confirm = input("\n  Lancer la prolongation ? [O/N] : ").strip().upper()
        if confirm != 'O':
            print("\n  Annulé.")
            return reprendre_entrainement()

        cmd = [
            sys.executable,
            str(TRAIN_SCRIPT),
            f"--config_path={config_path}",
            "--resume=true",
            f"--steps={steps_cible}",
            f"--save_freq={save_freq_cible}",
        ]

        print(f"\n🔄 Prolongation depuis {checkpoint_resume.name} jusqu'à {steps_cible} steps...")
        print(f"   Ctrl+C pour interrompre\n")

        try:
            cmd_exec = ajouter_inhibition_systeme(cmd)
            result = subprocess.run(cmd_exec, cwd=str(LEROBOT_DIR))
            if result.returncode != 0:
                print(f"\n❌ La prolongation s'est terminée avec une erreur (code {result.returncode})")
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Entraînement interrompu")
            afficher_checkpoints()

        return "done"

    elif choix == 'N':
        print("\n⚠️  Remplacement demandé : l'ancien dossier sera supprimé seulement après confirmation forte (SUPPRIMER) au lancement.")
        return "new"

    elif choix == 'A':
        return "reselect"

    elif choix == 'V':
        afficher_checkpoints()
        input("\nAppuyez sur ENTRÉE...")
        return reprendre_entrainement()

    else:
        sys.exit(0)


# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main():
    global OUTPUT_DIR
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     SEM — ENTRAÎNEMENT ACT SO-ARM 101                    ║
║     Service Écoles-Médias — DIP Genève                   ║
╚══════════════════════════════════════════════════════════╝
    """)

    # 1. Vérifier les prérequis
    erreurs = verifier_prerequis()
    if erreurs:
        print(f"\n❌ Prérequis manquants :")
        for err in erreurs:
            print(f"   • {err}")
        return

    # 2. Choix du modèle (registre local de modèles nommés) puis, si le modèle
    #    existe déjà, proposition de reprise / prolongation / remplacement.
    while True:
        nom_modele = selectionner_ou_creer_modele()
        if nom_modele is None:
            print("\n✅ Entraînement annulé.")
            return
        OUTPUT_DIR = TRAIN_BASE / nom_modele

        decision = reprendre_entrainement()
        if decision == "reselect":
            continue
        if decision == "done":
            return
        break

    effacer_ancien = (decision == "new")

    # 3. Menu de configuration
    config_key = afficher_menu_config()
    if config_key is None:
        print("\n✅ Entraînement annulé.")
        return

    # 4. Lancer
    lancer_entrainement(config_key, effacer_ancien=effacer_ancien)


if __name__ == "__main__":
    main()
