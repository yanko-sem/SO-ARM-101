#!/usr/bin/env python3
"""
Script SEM_so101_9_consolidate_dataset.py
Service Écoles-Médias (SEM) - DIP Genève

CONSOLIDATION DU DATASET POUR L'ENTRAÎNEMENT
=============================================

Ce script fusionne les 5 dossiers de positions créés par le script 8
en un seul dataset unifié au format LeRobotDataset v2.1,
compatible avec la commande lerobot-train.

Entrée : ~/.cache/huggingface/lerobot/local/so101_pick_place/position_X_*/
Sortie : ~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/

Auteur: Service Écoles-Médias (SEM)
Version: 1.0
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

# Module de référence visuelle caméra (étape 5, décision Q3) : à la
# consolidation, la référence et le journal sont copiés dans le meta/ du
# dataset, qui devient leur exemplaire de vérité. Import protégé et NON
# bloquant : consolider un dataset existant doit rester possible sans le
# module (avertissement de traçabilité incomplète à la place).
try:
    from SEM_so101_camera_reference import copier_reference_vers_meta
    from SEM_so101_camera_reference import LOG_FILE as CAMERA_REF_LOG
    CAMERA_REF_AVAILABLE = True
except Exception:
    copier_reference_vers_meta = None
    CAMERA_REF_LOG = None
    CAMERA_REF_AVAILABLE = False

# Auto-activation de l'environnement lerobot si nécessaire
try:
    import pandas as pd
except ImportError:
    import subprocess
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

POSITIONS = {
    1: {"nom": "Centre", "dossier": "position_1_centre"},
    2: {"nom": "Bas", "dossier": "position_2_bas"},
    3: {"nom": "Haut", "dossier": "position_3_haut"},
    4: {"nom": "Gauche", "dossier": "position_4_gauche"},
    5: {"nom": "Droite", "dossier": "position_5_droite"},
}

CAM_TOP = "cam_top"
CAM_FOLLOWER = "cam_follower"

SOURCE_BASE = Path(os.path.expanduser(
    "~/.cache/huggingface/lerobot/local/so101_pick_place"
))

OUTPUT_BASE = Path(os.path.expanduser(
    "~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated"
))

FPS = 30

# ============================================
# FONCTIONS
# ============================================

def clear_screen():
    os.system('clear')


def analyser_source():
    """Analyse les données source et retourne un inventaire"""
    inventaire = {}
    total_episodes = 0
    total_frames = 0

    for pos_id, pos_info in POSITIONS.items():
        pos_path = SOURCE_BASE / pos_info['dossier']
        data_path = pos_path / "data" / "chunk-000"

        episodes = []
        if data_path.exists():
            parquet_files = sorted(data_path.glob("episode_*.parquet"))
            for pf in parquet_files:
                try:
                    df = pd.read_parquet(pf)
                    episodes.append({
                        'file': pf,
                        'frames': len(df),
                        'episode_idx_original': int(pf.stem.split('_')[1])
                    })
                    total_frames += len(df)
                except Exception as e:
                    print(f"  ⚠️  Erreur lecture {pf.name}: {e}")

        inventaire[pos_id] = {
            'nom': pos_info['nom'],
            'dossier': pos_info['dossier'],
            'path': pos_path,
            'episodes': episodes,
            'count': len(episodes)
        }
        total_episodes += len(episodes)

    return inventaire, total_episodes, total_frames


def afficher_inventaire(inventaire, total_episodes, total_frames):
    """Affiche l'inventaire des données source"""
    print("\n📊 INVENTAIRE DES DONNÉES SOURCE")
    print("=" * 55)

    for pos_id, info in inventaire.items():
        status = "✅" if info['count'] >= 10 else ("◐" if info['count'] > 0 else "○")
        print(f"  {status} Position {pos_id} ({info['nom']:8}) : {info['count']:2} épisodes")
        if info['episodes']:
            frames_list = [e['frames'] for e in info['episodes']]
            print(f"     Frames: {min(frames_list)}-{max(frames_list)} par épisode")

    print("-" * 55)
    print(f"  Total : {total_episodes} épisodes | {total_frames} frames")
    print(f"  Source : {SOURCE_BASE}")
    print("=" * 55)


def verifier_videos(inventaire):
    """Vérifie que les vidéos existent pour chaque épisode"""
    erreurs = []

    for pos_id, info in inventaire.items():
        pos_path = info['path']
        for ep in info['episodes']:
            idx = ep['episode_idx_original']
            fname = f"episode_{idx:06d}.mp4"

            # Vérifier cam_top
            vid_top = pos_path / "videos" / "chunk-000" / f"observation.images.{CAM_TOP}" / fname
            if not vid_top.exists():
                erreurs.append(f"Position {pos_id}, épisode {idx}: {CAM_TOP} manquant")

            # Vérifier cam_follower
            vid_fol = pos_path / "videos" / "chunk-000" / f"observation.images.{CAM_FOLLOWER}" / fname
            if not vid_fol.exists():
                erreurs.append(f"Position {pos_id}, épisode {idx}: {CAM_FOLLOWER} manquant")

    return erreurs


def consolider(inventaire, total_episodes, total_frames):
    """Fusionne toutes les positions en un seul dataset"""

    # Préparer le dossier de sortie
    if OUTPUT_BASE.exists():
        print(f"\n⚠️  Le dossier de sortie existe déjà :")
        print(f"   {OUTPUT_BASE}")
        choix = input("   [E]craser ou [A]nnuler ? ").strip().upper()
        if choix != 'E':
            print("   Annulé.")
            return False
        shutil.rmtree(OUTPUT_BASE)

    # Créer l'arborescence
    data_out = OUTPUT_BASE / "data" / "chunk-000"
    video_top_out = OUTPUT_BASE / "videos" / "chunk-000" / f"observation.images.{CAM_TOP}"
    video_fol_out = OUTPUT_BASE / "videos" / "chunk-000" / f"observation.images.{CAM_FOLLOWER}"
    meta_out = OUTPUT_BASE / "meta"

    data_out.mkdir(parents=True, exist_ok=True)
    video_top_out.mkdir(parents=True, exist_ok=True)
    video_fol_out.mkdir(parents=True, exist_ok=True)
    meta_out.mkdir(parents=True, exist_ok=True)

    print("\n🔄 Consolidation en cours...")

    global_episode_idx = 0
    global_frame_idx = 0
    episodes_metadata = []
    tasks_set = {}

    for pos_id, info in inventaire.items():
        if info['count'] == 0:
            continue

        pos_path = info['path']
        task_desc = f"Prendre le cube à la position {info['nom']} et le déposer dans la boîte"

        # Enregistrer la tâche
        if task_desc not in tasks_set:
            tasks_set[task_desc] = len(tasks_set)
        task_index = tasks_set[task_desc]

        for ep in info['episodes']:
            orig_idx = ep['episode_idx_original']
            new_idx = global_episode_idx
            num_frames = ep['frames']

            # 1. Copier et renuméroter le Parquet
            src_parquet = ep['file']
            dst_parquet = data_out / f"episode_{new_idx:06d}.parquet"

            df = pd.read_parquet(src_parquet)

            # Mettre à jour les index
            df['episode_index'] = new_idx
            df['task_index'] = task_index
            df['index'] = range(global_frame_idx, global_frame_idx + len(df))
            df['frame_index'] = range(len(df))

            # Normaliser les timestamps (exactement 1/FPS entre chaque frame)
            df['timestamp'] = [i / FPS for i in range(len(df))]

            df.to_parquet(dst_parquet, index=False)

            # 2. Copier les vidéos
            orig_fname = f"episode_{orig_idx:06d}.mp4"
            new_fname = f"episode_{new_idx:06d}.mp4"

            # cam_top
            src_vid_top = pos_path / "videos" / "chunk-000" / f"observation.images.{CAM_TOP}" / orig_fname
            if src_vid_top.exists():
                shutil.copy2(src_vid_top, video_top_out / new_fname)

            # cam_follower
            src_vid_fol = pos_path / "videos" / "chunk-000" / f"observation.images.{CAM_FOLLOWER}" / orig_fname
            if src_vid_fol.exists():
                shutil.copy2(src_vid_fol, video_fol_out / new_fname)

            # 3. Metadata épisode
            episodes_metadata.append({
                "episode_index": new_idx,
                "tasks": [task_desc],
                "length": num_frames
            })

            global_frame_idx += num_frames
            global_episode_idx += 1

            # Progression
            print(f"  ✅ Position {pos_id} ({info['nom']:8}) ep {orig_idx} → épisode {new_idx:3d} ({num_frames} frames)")

    # 4. Générer info.json (format basé sur lerobot/svla_so101_pickplace)
    motor_names = [
        "shoulder_pan", "shoulder_lift", "elbow_flex",
        "wrist_flex", "wrist_roll", "gripper"
    ]

    info_json = {
        "codebase_version": "v2.1",
        "robot_type": "so101_follower",
        "total_episodes": global_episode_idx,
        "total_frames": global_frame_idx,
        "total_tasks": len(tasks_set),
        "total_videos": global_episode_idx * 2,
        "total_chunks": 1,
        "chunks_size": 1000,
        "fps": FPS,
        "splits": {"train": f"0:{global_episode_idx}"},
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
        "features": {
            "action": {
                "dtype": "float32",
                "shape": [6],
                "names": motor_names
            },
            "observation.state": {
                "dtype": "float32",
                "shape": [6],
                "names": motor_names
            },
            f"observation.images.{CAM_TOP}": {
                "dtype": "video",
                "shape": [360, 640, 3],
                "names": ["height", "width", "channels"],
                "info": {
                    "video.fps": FPS,
                    "video.height": 360,
                    "video.width": 640,
                    "video.channels": 3,
                    "video.codec": "mp4v",
                    "video.pix_fmt": "yuv420p",
                    "video.is_depth_map": False,
                    "has_audio": False
                }
            },
            f"observation.images.{CAM_FOLLOWER}": {
                "dtype": "video",
                "shape": [360, 640, 3],
                "names": ["height", "width", "channels"],
                "info": {
                    "video.fps": FPS,
                    "video.height": 360,
                    "video.width": 640,
                    "video.channels": 3,
                    "video.codec": "mp4v",
                    "video.pix_fmt": "yuv420p",
                    "video.is_depth_map": False,
                    "has_audio": False
                }
            },
            "timestamp": {"dtype": "float32", "shape": [1], "names": None},
            "frame_index": {"dtype": "int64", "shape": [1], "names": None},
            "episode_index": {"dtype": "int64", "shape": [1], "names": None},
            "index": {"dtype": "int64", "shape": [1], "names": None},
            "task_index": {"dtype": "int64", "shape": [1], "names": None}
        }
    }

    with open(meta_out / "info.json", 'w') as f:
        json.dump(info_json, f, indent=2)

    # 5. Générer tasks.jsonl
    with open(meta_out / "tasks.jsonl", 'w') as f:
        for task_desc, task_idx in sorted(tasks_set.items(), key=lambda x: x[1]):
            f.write(json.dumps({"task_index": task_idx, "task": task_desc}) + "\n")

    # 6. Générer episodes.jsonl
    with open(meta_out / "episodes.jsonl", 'w') as f:
        for ep_meta in episodes_metadata:
            f.write(json.dumps(ep_meta) + "\n")

    # 7. Sauvegarder un fichier de traçabilité
    trace = {
        "created": datetime.now().isoformat(),
        "source": str(SOURCE_BASE),
        "output": str(OUTPUT_BASE),
        "total_episodes": global_episode_idx,
        "total_frames": global_frame_idx,
        "positions": {
            str(pos_id): {
                "nom": info['nom'],
                "episodes": info['count']
            }
            for pos_id, info in inventaire.items()
        }
    }
    with open(meta_out / "consolidation_trace.json", 'w') as f:
        json.dump(trace, f, indent=2)

    # 8. Traçabilité « Référence visuelle caméra » (étape 5, décision Q3) :
    #    copie de la référence active (JSON + image témoin masquée) et du
    #    journal des passages 🟠 dans le meta/ du dataset consolidé — le
    #    déploiement s'y rattachera via le train_config.json du checkpoint.
    if CAMERA_REF_AVAILABLE:
        print("\n📷 Traçabilité caméra → meta/ ...")
        copier_reference_vers_meta(meta_out)
        if CAMERA_REF_LOG is not None and Path(CAMERA_REF_LOG).exists():
            try:
                shutil.copy2(CAMERA_REF_LOG, meta_out / Path(CAMERA_REF_LOG).name)
                print(f"   ✅ Journal copié : {Path(CAMERA_REF_LOG).name}")
            except Exception as e:
                print(f"   ⚠️  Copie du journal impossible ({e}).")
        else:
            print("   ℹ️  Aucun journal de passages 🟠 (normal si tout était 🟢).")
    else:
        print("\n⚠️  Module SEM_so101_camera_reference indisponible — référence")
        print("   caméra NON copiée dans le meta/ (traçabilité incomplète).")

    return True


def afficher_resultat():
    """Affiche le résumé du dataset consolidé"""
    info_file = OUTPUT_BASE / "meta" / "info.json"
    if not info_file.exists():
        print("❌ Aucun dataset consolidé trouvé")
        return

    with open(info_file) as f:
        info = json.load(f)

    # Compter les fichiers
    n_parquet = len(list((OUTPUT_BASE / "data" / "chunk-000").glob("*.parquet")))
    n_vid_top = len(list((OUTPUT_BASE / "videos" / "chunk-000" / f"observation.images.{CAM_TOP}").glob("*.mp4")))
    n_vid_fol = len(list((OUTPUT_BASE / "videos" / "chunk-000" / f"observation.images.{CAM_FOLLOWER}").glob("*.mp4")))

    # Taille totale
    total_size = sum(f.stat().st_size for f in OUTPUT_BASE.rglob("*") if f.is_file())
    if total_size > 1024 * 1024 * 1024:
        size_str = f"{total_size / (1024**3):.1f} GB"
    elif total_size > 1024 * 1024:
        size_str = f"{total_size / (1024**2):.0f} MB"
    else:
        size_str = f"{total_size / 1024:.0f} KB"

    print(f"""
╔══════════════════════════════════════════════════════════╗
║          DATASET CONSOLIDÉ — RÉSUMÉ                      ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  📊 Épisodes : {info['total_episodes']:4d}                                ║
║  🎬 Frames   : {info['total_frames']:6d}                              ║
║  📹 Vidéos   : {n_vid_top} (cam_top) + {n_vid_fol} (cam_follower)         ║
║  📄 Parquet  : {n_parquet} fichiers                           ║
║  💾 Taille   : {size_str:10}                            ║
║  🎯 Tâches   : {info['total_tasks']}                                    ║
║  ⚡ FPS      : {info['fps']}                                     ║
║                                                          ║
║  📁 Chemin : {str(OUTPUT_BASE)[:42]}  ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

    # Lister les tâches
    tasks_file = OUTPUT_BASE / "meta" / "tasks.jsonl"
    if tasks_file.exists():
        print("  📋 Tâches enregistrées :")
        with open(tasks_file) as f:
            for line in f:
                task = json.loads(line)
                print(f"     {task['task_index']}: {task['task']}")
        print()


# ============================================
# PROGRAMME PRINCIPAL
# ============================================

def main():
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════╗
║     SEM — CONSOLIDATION DATASET SO-ARM 101               ║
║     Service Écoles-Médias — DIP Genève                   ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Vérifier que la source existe
    if not SOURCE_BASE.exists():
        print(f"❌ Dossier source introuvable :")
        print(f"   {SOURCE_BASE}")
        print(f"\n   Lancez d'abord le script 8 pour enregistrer des épisodes.")
        return

    # Analyser
    print("🔍 Analyse des données source...")
    inventaire, total_episodes, total_frames = analyser_source()

    if total_episodes == 0:
        print("\n❌ Aucun épisode trouvé. Enregistrez d'abord des épisodes avec le script 8.")
        return

    afficher_inventaire(inventaire, total_episodes, total_frames)

    # Vérifier les vidéos
    print("\n🔍 Vérification des vidéos...")
    erreurs = verifier_videos(inventaire)
    if erreurs:
        print(f"\n⚠️  {len(erreurs)} vidéo(s) manquante(s) :")
        for err in erreurs[:10]:
            print(f"   • {err}")
        if len(erreurs) > 10:
            print(f"   ... et {len(erreurs) - 10} autres")
        choix = input("\nContinuer quand même ? [O/N] : ").strip().upper()
        if choix != 'O':
            return
    else:
        print("  ✅ Toutes les vidéos sont présentes")

    # Confirmer
    print(f"\n📦 Le dataset consolidé sera créé dans :")
    print(f"   {OUTPUT_BASE}")
    input("\nAppuyez sur ENTRÉE pour lancer la consolidation...")

    # Consolider
    if consolider(inventaire, total_episodes, total_frames):
        print("\n✅ Consolidation terminée !")
        afficher_resultat()

        print("🚀 Prochaine étape :")
        print(f"   python SEM_so101_10_visualize_dataset.py")
    else:
        print("\n❌ Consolidation annulée.")


if __name__ == "__main__":
    main()
