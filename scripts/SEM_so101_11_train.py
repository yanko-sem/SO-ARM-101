#!/usr/bin/env python3
"""
Script SEM_so101_11_train.py
Service Écoles-Médias (SEM) - DIP Genève

ENTRAÎNEMENT DU MODÈLE ACT POUR SO-ARM 101
============================================

Ce script lance l'entraînement d'une politique ACT
(Action Chunking with Transformers) sur le dataset consolidé.

Matériel cible : Quadro RTX 4000 (8 Go VRAM)
Dataset : so101_pick_place_consolidated (51 épisodes, 2 caméras)

Auteur: Service Écoles-Médias (SEM)
Version: 1.0
"""

import os
import sys
import json
import subprocess
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
    "intensif": {
        "nom": "Intensif (qualité max)",
        "description": "200k steps, batch 4 — ~8-12h, meilleure qualité",
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
    import shutil
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
║  2. {TRAINING_CONFIGS['standard']['nom']:40}     ║
║     {TRAINING_CONFIGS['standard']['description']:51} ║
║                                                          ║
║  3. {TRAINING_CONFIGS['intensif']['nom']:40}     ║
║     {TRAINING_CONFIGS['intensif']['description']:51} ║
║                                                          ║
║  Q. Quitter                                              ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

    choix = input("  Votre choix [1/2/3/Q] : ").strip().upper()

    if choix == '1':
        return "rapide"
    elif choix == '2':
        return "standard"
    elif choix == '3':
        return "intensif"
    else:
        return None


def lancer_entrainement(config_key):
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
        result = subprocess.run(cmd, cwd=str(LEROBOT_DIR))

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


def reprendre_entrainement():
    """Vérifie si un entraînement précédent peut être repris"""
    checkpoints_dir = OUTPUT_DIR / "checkpoints"
    if not checkpoints_dir.exists():
        return False

    checkpoints = sorted(checkpoints_dir.glob("*/"))
    if not checkpoints:
        return False

    last = checkpoints[-1]
    print(f"\n📂 Entraînement précédent détecté :")
    print(f"   Dernier checkpoint : {last.name}")

    # Charger les params précédents
    params_file = Path(__file__).parent / "sem_training_params.json"
    if params_file.exists():
        with open(params_file) as f:
            params = json.load(f)
        print(f"   Configuration : {params.get('config', '?')}")
        print(f"   Démarré le : {params.get('started_at', '?')}")

    print(f"\n  R — Reprendre l'entraînement")
    print(f"  N — Nouvel entraînement (écrase l'ancien)")
    print(f"  V — Voir les checkpoints")
    print(f"  Q — Quitter")

    choix = input("\n  Votre choix : ").strip().upper()

    if choix == 'R':
        # Reprendre avec le même config
        if params_file.exists():
            config_key = params.get('config', 'standard')
        else:
            config_key = 'standard'

        config = TRAINING_CONFIGS[config_key]
        cmd = [
            sys.executable,
            str(TRAIN_SCRIPT),
            "--dataset.repo_id=local/so101_pick_place_consolidated",
            "--dataset.video_backend=pyav",
            f"--policy.type=act",
            f"--policy.device=cuda",
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
            f"--resume=true",
        ]

        print(f"\n🔄 Reprise de l'entraînement ({config['nom']})...")
        print(f"   Ctrl+C pour interrompre\n")

        try:
            subprocess.run(cmd, cwd=str(LEROBOT_DIR))
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Entraînement interrompu")
            afficher_checkpoints()

        return True

    elif choix == 'N':
        return False  # Continue vers le menu normal

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
    if reprendre_entrainement():
        return

    # 3. Menu de configuration
    config_key = afficher_menu_config()
    if config_key is None:
        print("\n✅ Entraînement annulé.")
        return

    # 4. Lancer
    lancer_entrainement(config_key)


if __name__ == "__main__":
    main()
