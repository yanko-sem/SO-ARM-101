#!/usr/bin/env python3
"""
Script SEM_so101_11_train.py
Service Écoles-Médias (SEM) - DIP Genève

ENTRAÎNEMENT DU MODÈLE ACT POUR SO-ARM 101
============================================

Ce script lance l'entraînement d'une politique ACT
(Action Chunking with Transformers) sur le dataset consolidé.

Matériel cible : Quadro RTX 4000 (8 Go VRAM)
Dataset : so101_pick_place_consolidated (50 épisodes, 2 caméras)

Auteur: Service Écoles-Médias (SEM)
Version: 1.0
"""

import os
import sys
import json
import subprocess
import shutil
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

OUTPUT_DIR = LEROBOT_DIR / "outputs" / "train" / "act_so101_pick_place"

# Paramètres d'entraînement optimisés pour Quadro RTX 4000 (8 Go VRAM)
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


def verifier_prerequis():
    """Vérifie que tout est prêt pour l'entraînement"""
    print("\n🔍 Vérification des prérequis...")
    erreurs = []

    # 1. CUDA
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"  ✅ GPU : {gpu_name} ({vram:.1f} Go VRAM)")
    else:
        erreurs.append("CUDA non disponible — entraînement GPU impossible")

    # 2. Dataset
    info_file = DATASET_PATH / "meta" / "info.json"
    if info_file.exists():
        with open(info_file) as f:
            info = json.load(f)
        episodes = info.get('total_episodes', 0)
        frames = info.get('total_frames', 0)
        print(f"  ✅ Dataset : {episodes} épisodes, {frames} frames")

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
    else:
        erreurs.append(f"Dataset introuvable : {DATASET_PATH}")

    # 3. Stats
    stats_file = DATASET_PATH / "meta" / "episodes_stats.jsonl"
    if stats_file.exists():
        print(f"  ✅ Statistiques : episodes_stats.jsonl présent")
    else:
        erreurs.append("episodes_stats.jsonl manquant — lancez le script 10")

    # 4. Script d'entraînement
    if TRAIN_SCRIPT.exists():
        print(f"  ✅ Script LeRobot : train.py trouvé")
    else:
        erreurs.append(f"Script d'entraînement introuvable : {TRAIN_SCRIPT}")

    # 5. PyTorch
    print(f"  ✅ PyTorch : {torch.__version__}")
    if torch.cuda.is_available():
        print(f"  ✅ CUDA : {torch.version.cuda}")

    # 6. Espace disque
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
    params_file = Path(__file__).parent / "sem_training_params.json"
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
        f"--policy.device=cuda",
        f"--policy.use_amp=true",
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
    print(f"\n⏱️  Durée estimée : {config['description'].split('—')[1].strip()}")
    print(f"   L'entraînement peut être interrompu avec Ctrl+C")
    print(f"   Les checkpoints sont sauvegardés régulièrement\n")

    choix = input("   Lancer ? [O/N] : ").strip().upper()
    if choix != 'O':
        print("   Annulé.")
        return False

    # Si l'utilisateur a demandé un nouvel entraînement, on supprime l'ancien
    # uniquement après cette confirmation finale. Cela évite de perdre
    # un ancien modèle/checkpoint si l'utilisateur annule au menu suivant.
    if effacer_ancien and OUTPUT_DIR.exists():
        print(f"\n🗑️  Suppression de l'ancien entraînement : {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
        print("   ✅ Ancien entraînement supprimé.")

    # Sauvegarder les paramètres (à côté du script, pas dans output_dir)
    params = {
        "config": config_key,
        "params": config,
        "dataset": str(DATASET_PATH),
        "started_at": datetime.now().isoformat(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "output_dir": str(OUTPUT_DIR),
    }
    script_dir = Path(__file__).parent
    with open(script_dir / "sem_training_params.json", 'w') as f:
        json.dump(params, f, indent=2)

    # Lancer
    print("\n" + "=" * 60)
    print("  ENTRAÎNEMENT EN COURS")
    print("  Ctrl+C pour interrompre (les checkpoints sont sauvegardés)")
    print("=" * 60 + "\n")

    start_time = datetime.now()

    try:
        cmd_exec = ajouter_inhibition_systeme(cmd)
        result = subprocess.run(cmd_exec, cwd=str(LEROBOT_DIR))

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
        last = checkpoints[-1]
        print(f"     python SEM_so101_12_deploy.py")
    else:
        print("   Aucun checkpoint trouvé")



def steps_du_checkpoint(checkpoint):
    """Retourne le nombre de steps atteint par un checkpoint.
    Résout 'last' (lien symbolique) vers le dossier réel (ex. 200000)."""
    nom = checkpoint.name
    if nom.isdigit():
        return int(nom)
    try:
        cible = checkpoint.resolve().name
        if cible.isdigit():
            return int(cible)
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
        print("\n  N — Nouvel entraînement (écrase l'ancien après confirmation finale)")
        print("  Q — Quitter")
        choix = input("\n  Votre choix : ").strip().upper()
        if choix == 'N':
            print("\n⚠️  Nouvel entraînement demandé : l'ancien dossier sera supprimé seulement après confirmation finale du lancement.")
            return "new"
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
        print("\n  N — Nouvel entraînement (écrase l'ancien après confirmation finale)")
        print("  V — Voir les dossiers checkpoints")
        print("  Q — Quitter")
        choix = input("\n  Votre choix : ").strip().upper()
        if choix == 'N':
            print("\n⚠️  Nouvel entraînement demandé : l'ancien dossier sera supprimé seulement après confirmation finale du lancement.")
            return "new"
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
    print(f"  N — Nouvel entraînement (écrase l'ancien après confirmation finale)")
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
        print("\n⚠️  Nouvel entraînement demandé : l'ancien dossier sera supprimé seulement après confirmation finale du lancement.")
        return "new"

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

    # 2. Vérifier si un entraînement précédent existe
    decision = reprendre_entrainement()
    if decision == "done":
        return

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
