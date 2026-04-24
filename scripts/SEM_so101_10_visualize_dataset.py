#!/usr/bin/env python3
"""
Script SEM_so101_10_visualize_dataset.py
Service Écoles-Médias (SEM) - DIP Genève

VÉRIFICATION ET VISUALISATION DU DATASET
==========================================

Ce script :
1. Vérifie l'intégrité du dataset consolidé
2. Génère le fichier episodes_stats.jsonl (requis par LeRobot v2.1)
3. Lance l'outil officiel de visualisation LeRobot dans le navigateur

Auteur: Service Écoles-Médias (SEM)
Version: 1.0
"""

import os
import sys
import json
import subprocess
import math
from pathlib import Path

# Auto-activation de l'environnement lerobot si nécessaire
try:
    import pandas as pd
    import numpy as np
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

CAM_TOP = "cam_top"
CAM_FOLLOWER = "cam_follower"

# ============================================
# FONCTIONS
# ============================================

def clear_screen():
    os.system('clear')


def verifier_dataset():
    """Vérifie l'intégrité du dataset consolidé"""
    print("\n🔍 Vérification du dataset consolidé...")
    erreurs = []

    # Vérifier les dossiers
    for dossier in ["data/chunk-000", "videos/chunk-000", "meta"]:
        chemin = DATASET_PATH / dossier
        if not chemin.exists():
            erreurs.append(f"Dossier manquant: {dossier}")

    # Vérifier info.json
    info_file = DATASET_PATH / "meta" / "info.json"
    if not info_file.exists():
        erreurs.append("meta/info.json manquant")
        return erreurs, None

    with open(info_file) as f:
        info = json.load(f)

    total_episodes = info.get('total_episodes', 0)

    # Vérifier les parquets
    parquets = sorted((DATASET_PATH / "data" / "chunk-000").glob("*.parquet"))
    if len(parquets) != total_episodes:
        erreurs.append(f"Parquets: {len(parquets)} trouvés, {total_episodes} attendus")

    # Vérifier les vidéos
    for cam in [CAM_TOP, CAM_FOLLOWER]:
        vid_dir = DATASET_PATH / "videos" / "chunk-000" / f"observation.images.{cam}"
        if vid_dir.exists():
            vids = list(vid_dir.glob("*.mp4"))
            if len(vids) != total_episodes:
                erreurs.append(f"Vidéos {cam}: {len(vids)} trouvées, {total_episodes} attendues")
        else:
            erreurs.append(f"Dossier vidéo manquant: {cam}")

    # Vérifier episodes.jsonl
    episodes_file = DATASET_PATH / "meta" / "episodes.jsonl"
    if not episodes_file.exists():
        erreurs.append("meta/episodes.jsonl manquant")

    # Vérifier tasks.jsonl
    tasks_file = DATASET_PATH / "meta" / "tasks.jsonl"
    if not tasks_file.exists():
        erreurs.append("meta/tasks.jsonl manquant")

    if not erreurs:
        print(f"  ✅ Structure correcte ({total_episodes} épisodes)")
    else:
        for err in erreurs:
            print(f"  ❌ {err}")

    return erreurs, info


def completer_info_json():
    """Ajoute les champs manquants dans info.json pour la compatibilité LeRobot"""
    info_file = DATASET_PATH / "meta" / "info.json"
    if not info_file.exists():
        return False

    with open(info_file) as f:
        info = json.load(f)

    modifie = False

    # Champs requis par LeRobot v2.1
    champs_requis = {
        "chunks_size": 1000,
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
    }

    for champ, valeur in champs_requis.items():
        if champ not in info:
            info[champ] = valeur
            print(f"  🔧 Ajouté dans info.json : {champ}")
            modifie = True

    # Colonnes de métadonnées requises dans features
    colonnes_meta = {
        "timestamp": {"dtype": "float32", "shape": [1]},
        "frame_index": {"dtype": "int64", "shape": [1]},
        "episode_index": {"dtype": "int64", "shape": [1]},
        "index": {"dtype": "int64", "shape": [1]},
        "task_index": {"dtype": "int64", "shape": [1]}
    }

    if "features" in info:
        for col, spec in colonnes_meta.items():
            if col not in info["features"]:
                info["features"][col] = spec
                print(f"  🔧 Ajouté dans features : {col}")
                modifie = True

    if modifie:
        with open(info_file, 'w') as f:
            json.dump(info, f, indent=2)
        print(f"  ✅ info.json mis à jour")
    else:
        print(f"  ✅ info.json complet")

    return True


def generer_episodes_stats():
    """Génère le fichier episodes_stats.jsonl requis par LeRobot v2.1"""
    stats_file = DATASET_PATH / "meta" / "episodes_stats.jsonl"

    if stats_file.exists():
        print(f"\n📊 episodes_stats.jsonl existe déjà")
        choix = input("   [R]egénérer ou [G]arder ? ").strip().upper()
        if choix != 'R':
            print("   → Fichier conservé")
            return True

    print("\n📊 Génération de episodes_stats.jsonl...")

    data_dir = DATASET_PATH / "data" / "chunk-000"
    parquets = sorted(data_dir.glob("*.parquet"))

    if not parquets:
        print("  ❌ Aucun fichier parquet trouvé")
        return False

    stats_lines = []

    for pf in parquets:
        ep_idx = int(pf.stem.split('_')[1])
        df = pd.read_parquet(pf)

        ep_stats = {"episode_index": ep_idx, "stats": {}}

        # Calculer les stats pour observation.state
        if 'observation.state' in df.columns:
            states = np.array(df['observation.state'].tolist(), dtype=np.float32)
            ep_stats["stats"]["observation.state"] = {
                "mean": states.mean(axis=0).tolist(),
                "std": states.std(axis=0).tolist(),
                "min": states.min(axis=0).tolist(),
                "max": states.max(axis=0).tolist(),
                "count": [len(df)]
            }

        # Calculer les stats pour action
        if 'action' in df.columns:
            actions = np.array(df['action'].tolist(), dtype=np.float32)
            ep_stats["stats"]["action"] = {
                "mean": actions.mean(axis=0).tolist(),
                "std": actions.std(axis=0).tolist(),
                "min": actions.min(axis=0).tolist(),
                "max": actions.max(axis=0).tolist(),
                "count": [len(df)]
            }

        # Stats pour les caméras (valeurs ImageNet standard)
        num_frames = len(df)
        for cam in [f"observation.images.{CAM_TOP}", f"observation.images.{CAM_FOLLOWER}"]:
            ep_stats["stats"][cam] = {
                "mean": [[[0.485]], [[0.456]], [[0.406]]],
                "std": [[[0.229]], [[0.224]], [[0.225]]],
                "min": [[[0.0]], [[0.0]], [[0.0]]],
                "max": [[[1.0]], [[1.0]], [[1.0]]],
                "count": [num_frames]
            }

        stats_lines.append(ep_stats)
        print(f"  ✅ Épisode {ep_idx:3d} — {len(df)} frames, "
              f"state range [{states.min():.0f}-{states.max():.0f}]")

    # Écrire le fichier
    with open(stats_file, 'w') as f:
        for line in stats_lines:
            f.write(json.dumps(line) + "\n")

    print(f"\n  ✅ episodes_stats.jsonl généré ({len(stats_lines)} épisodes)")
    return True


def afficher_resume(info):
    """Affiche le résumé du dataset"""
    # Compter les fichiers
    n_parquet = len(list((DATASET_PATH / "data" / "chunk-000").glob("*.parquet")))

    # Taille totale
    total_size = sum(f.stat().st_size for f in DATASET_PATH.rglob("*") if f.is_file())
    if total_size > 1024 * 1024 * 1024:
        size_str = f"{total_size / (1024**3):.1f} GB"
    elif total_size > 1024 * 1024:
        size_str = f"{total_size / (1024**2):.0f} MB"
    else:
        size_str = f"{total_size / 1024:.0f} KB"

    # Vérifier les fichiers meta
    meta_files = []
    for f in ["info.json", "episodes.jsonl", "tasks.jsonl", "episodes_stats.jsonl"]:
        status = "✅" if (DATASET_PATH / "meta" / f).exists() else "❌"
        meta_files.append(f"  {status} {f}")

    print(f"""
╔══════════════════════════════════════════════════════════╗
║          DATASET CONSOLIDÉ — RÉSUMÉ                      ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  📊 Épisodes : {info.get('total_episodes', '?'):4}                                ║
║  🎬 Frames   : {info.get('total_frames', '?'):6}                              ║
║  📄 Parquet  : {n_parquet} fichiers                           ║
║  💾 Taille   : {size_str:10}                            ║
║  🎯 Tâches   : {info.get('total_tasks', '?')}                                    ║
║  ⚡ FPS      : {info.get('fps', '?')}                                     ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")
    print("  📋 Fichiers de métadonnées :")
    for mf in meta_files:
        print(f"     {mf}")
    print()


def convertir_videos_h264():
    """Convertit les vidéos mp4v en H.264 pour la compatibilité navigateur"""
    vid_dir = DATASET_PATH / "videos" / "chunk-000"
    if not vid_dir.exists():
        return

    # Tester si ffmpeg est disponible
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
        if result.returncode != 0:
            print("  ⚠️  ffmpeg non disponible — vidéos non converties")
            return
    except FileNotFoundError:
        print("  ⚠️  ffmpeg non trouvé — vidéos non converties")
        return

    # Vérifier si la conversion a déjà été faite
    marker = DATASET_PATH / "meta" / ".h264_converted"
    if marker.exists():
        print("  ✅ Vidéos déjà converties en H.264")
        return

    print("\n🎬 Conversion des vidéos en H.264 (compatibilité navigateur)...")

    mp4_files = list(vid_dir.rglob("*.mp4"))
    total = len(mp4_files)

    for i, mp4_file in enumerate(mp4_files):
        tmp_file = mp4_file.with_suffix('.tmp.mp4')
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(mp4_file),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                str(tmp_file)
            ],
            capture_output=True
        )
        if result.returncode == 0:
            tmp_file.replace(mp4_file)
            print(f"  ✅ [{i+1}/{total}] {mp4_file.parent.name}/{mp4_file.name}")
        else:
            if tmp_file.exists():
                tmp_file.unlink()
            print(f"  ❌ [{i+1}/{total}] {mp4_file.name} — échec conversion")

    # Marquer comme converti
    marker.touch()
    print(f"\n  ✅ {total} vidéos converties en H.264")


def lancer_visualisation():
    """Lance l'outil de visualisation officiel LeRobot"""
    script_path = LEROBOT_DIR / "lerobot" / "scripts" / "visualize_dataset_html.py"

    if not script_path.exists():
        print(f"\n❌ Script de visualisation introuvable :")
        print(f"   {script_path}")
        return

    print("\n🌐 Lancement de la visualisation LeRobot...")
    print("   Le navigateur devrait s'ouvrir automatiquement.")
    print("   Sinon, ouvrez : http://127.0.0.1:9090")
    print("   Appuyez sur Ctrl+C dans le terminal pour arrêter.\n")

    try:
        subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--repo-id", "local/so101_pick_place_consolidated",
                "--tolerance-s", "1.0"
            ],
            cwd=str(LEROBOT_DIR)
        )
    except KeyboardInterrupt:
        print("\n\n✅ Serveur de visualisation arrêté.")


# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main():
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     SEM — VISUALISATION DATASET SO-ARM 101               ║
║     Service Écoles-Médias — DIP Genève                   ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Vérifier que le dataset existe
    if not DATASET_PATH.exists():
        print(f"❌ Dataset consolidé introuvable :")
        print(f"   {DATASET_PATH}")
        print(f"\n   Lancez d'abord le script 9 pour consolider le dataset.")
        return

    # 1. Vérification d'intégrité
    erreurs, info = verifier_dataset()
    if erreurs:
        print(f"\n⚠️  {len(erreurs)} problème(s) détecté(s).")
        choix = input("Continuer quand même ? [O/N] : ").strip().upper()
        if choix != 'O':
            return

    # 2. Afficher le résumé
    if info:
        afficher_resume(info)

    # 3. Compléter info.json si nécessaire
    completer_info_json()

    # 4. Générer episodes_stats.jsonl
    if not generer_episodes_stats():
        print("\n❌ Impossible de générer les statistiques. Arrêt.")
        return

    # 5. Convertir vidéos en H.264 si nécessaire
    convertir_videos_h264()

    # 6. Menu
    print("\n" + "=" * 55)
    print("  Que souhaitez-vous faire ?")
    print("=" * 55)
    print("  V — Lancer la visualisation dans le navigateur")
    print("  Q — Quitter")
    print("=" * 55)

    choix = input("\n  Votre choix : ").strip().upper()

    if choix == 'V':
        lancer_visualisation()
    else:
        print("\n✅ Vérification terminée.")
        print("🚀 Prochaine étape :")
        print(f"   python SEM_so101_11_train.py")


if __name__ == "__main__":
    main()
