#!/usr/bin/env python3
"""
Script SEM_so101_9_dataset.py
Service Écoles-Médias (SEM) - DIP Genève

PRÉPARATION COMPLÈTE DU DATASET POUR L'ENTRAÎNEMENT
====================================================

Prépare, en un seul geste, le dataset destiné à l'entraînement (script 10) :
  1. Analyse + validation des données source (script 8) — fail-closed.
  2. Consolidation des 5 positions dans un dossier TEMPORAIRE.
  3. Finalisation : info.json complet, tasks.jsonl, episodes.jsonl, episodes_stats.jsonl,
     conversion H.264 (navigateur), vérification frames vidéo/parquet.
  4. Bascule ATOMIQUE vers le dataset final UNIQUEMENT si les étapes critiques réussissent.
  5. Visualisation LeRobot optionnelle — désormais intégrée ici (ancienne étape de visualisation séparée).

Entrée : ~/.cache/huggingface/lerobot/local/so101_pick_place/position_X_*/
Sortie : ~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated/

Auteur: Service Écoles-Médias (SEM)
Version: 2.2 (préparation complète du dataset + visualisation intégrée)
"""

import os
import sys
import json
import shutil
import subprocess
import threading
import webbrowser
import urllib.request
import time
from pathlib import Path
from datetime import datetime

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

POSITIONS = {
    1: {"nom": "Centre", "dossier": "position_1_centre"},
    2: {"nom": "Libre", "dossier": "position_2_libre"},
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
# Dossier TEMPORAIRE : la consolidation + finalisation s'y font intégralement,
# puis bascule atomique vers OUTPUT_BASE seulement si tout a réussi. Garantit
# qu'un échec en cours de route ne détruit jamais le dataset final existant.
TMP_BASE = Path(os.path.expanduser(
    "~/.cache/huggingface/lerobot/local/so101_pick_place_consolidated_tmp"
))

LEROBOT_DIR = Path(os.path.expanduser("~/lerobot"))
FPS = 30
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 360

# Colonnes de DONNÉES obligatoires dans les parquets source. Les colonnes de
# métadonnées (timestamp, frame_index, episode_index, index, task_index) sont
# (re)générées à la consolidation, donc non exigées en entrée.
COLONNES_DATA_REQUISES = ["observation.state", "action"]
# Jeu complet attendu dans les parquets FINAUX (données + métadonnées régénérées).
COLONNES_FINALES_REQUISES = COLONNES_DATA_REQUISES + [
    "timestamp", "frame_index", "episode_index", "index", "task_index"
]
# Dimension attendue de observation.state et action (6 servos du SO-ARM 101).
DIM_STATE_ACTION = 6

# ============================================
# FONCTIONS — ANALYSE & VALIDATION SOURCE
# ============================================

def clear_screen():
    os.system('clear')


def analyser_source():
    """Analyse les données source et retourne (inventaire, total_episodes,
    total_frames, donnees_erreurs). donnees_erreurs liste les parquets source
    invalides : colonne de DONNÉES manquante, parquet vide, forme ≠ (n, 6), ou
    valeurs non numériques / non finies (NaN/Inf) — dataset inexploitable."""
    inventaire = {}
    total_episodes = 0
    total_frames = 0
    donnees_erreurs = []

    for pos_id, pos_info in POSITIONS.items():
        pos_path = SOURCE_BASE / pos_info['dossier']
        data_path = pos_path / "data" / "chunk-000"

        episodes = []
        if data_path.exists():
            parquet_files = sorted(data_path.glob("episode_*.parquet"))
            for pf in parquet_files:
                try:
                    df = pd.read_parquet(pf)
                    manquantes = [c for c in COLONNES_DATA_REQUISES if c not in df.columns]
                    if manquantes:
                        donnees_erreurs.append(
                            f"Position {pos_id}, {pf.name} : colonne(s) manquante(s) {manquantes}")
                    elif len(df) == 0:
                        donnees_erreurs.append(
                            f"Position {pos_id}, {pf.name} : parquet vide (0 ligne)")
                    else:
                        # Forme (n, 6), numérique et fini, pour observation.state et action.
                        for col in COLONNES_DATA_REQUISES:
                            try:
                                arr = np.asarray(df[col].tolist(), dtype=np.float32)
                            except (ValueError, TypeError):
                                donnees_erreurs.append(
                                    f"Position {pos_id}, {pf.name} : '{col}' non numérique ou de longueur variable")
                                continue
                            if arr.ndim != 2 or arr.shape[1] != DIM_STATE_ACTION:
                                donnees_erreurs.append(
                                    f"Position {pos_id}, {pf.name} : '{col}' forme {arr.shape} ≠ (n, {DIM_STATE_ACTION})")
                            elif not np.isfinite(arr).all():
                                donnees_erreurs.append(
                                    f"Position {pos_id}, {pf.name} : '{col}' contient des valeurs non finies (NaN/Inf)")
                    episodes.append({
                        'file': pf,
                        'frames': len(df),
                        'episode_idx_original': int(pf.stem.split('_')[1])
                    })
                    total_frames += len(df)
                except Exception as e:
                    print(f"  ⚠️  Erreur lecture {pf.name}: {e}")
                    donnees_erreurs.append(f"Position {pos_id}, {pf.name} : illisible ({e})")

        inventaire[pos_id] = {
            'nom': pos_info['nom'],
            'dossier': pos_info['dossier'],
            'path': pos_path,
            'episodes': episodes,
            'count': len(episodes)
        }
        total_episodes += len(episodes)

    return inventaire, total_episodes, total_frames, donnees_erreurs


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
    """Vérifie que les deux vidéos existent pour chaque épisode. Retourne la liste
    des manques (une vidéo absente pour un épisode existant = corruption)."""
    erreurs = []
    for pos_id, info in inventaire.items():
        pos_path = info['path']
        for ep in info['episodes']:
            idx = ep['episode_idx_original']
            fname = f"episode_{idx:06d}.mp4"
            vid_top = pos_path / "videos" / "chunk-000" / f"observation.images.{CAM_TOP}" / fname
            if not vid_top.exists():
                erreurs.append(f"Position {pos_id}, épisode {idx}: {CAM_TOP} manquant")
            vid_fol = pos_path / "videos" / "chunk-000" / f"observation.images.{CAM_FOLLOWER}" / fname
            if not vid_fol.exists():
                erreurs.append(f"Position {pos_id}, épisode {idx}: {CAM_FOLLOWER} manquant")
    return erreurs


# ============================================
# CONSOLIDATION (vers un dossier de destination)
# ============================================

def consolider(inventaire, dest_base):
    """Fusionne toutes les positions dans dest_base (dossier TEMPORAIRE).
    Fail-closed : si une vidéo source attendue est absente au moment de la copie,
    la consolidation est annulée (return False). Retourne True sinon."""
    data_out = dest_base / "data" / "chunk-000"
    video_top_out = dest_base / "videos" / "chunk-000" / f"observation.images.{CAM_TOP}"
    video_fol_out = dest_base / "videos" / "chunk-000" / f"observation.images.{CAM_FOLLOWER}"
    meta_out = dest_base / "meta"

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

            df['episode_index'] = new_idx
            df['task_index'] = task_index
            df['index'] = range(global_frame_idx, global_frame_idx + len(df))
            df['frame_index'] = range(len(df))
            df['timestamp'] = [i / FPS for i in range(len(df))]

            df.to_parquet(dst_parquet, index=False)

            # 2. Copier les vidéos — fail-closed si une source attendue est absente.
            orig_fname = f"episode_{orig_idx:06d}.mp4"
            new_fname = f"episode_{new_idx:06d}.mp4"

            src_vid_top = pos_path / "videos" / "chunk-000" / f"observation.images.{CAM_TOP}" / orig_fname
            src_vid_fol = pos_path / "videos" / "chunk-000" / f"observation.images.{CAM_FOLLOWER}" / orig_fname
            if not src_vid_top.exists() or not src_vid_fol.exists():
                manque = CAM_TOP if not src_vid_top.exists() else CAM_FOLLOWER
                print(f"\n  ❌ Vidéo {manque} absente pour position {pos_id} épisode {orig_idx}"
                      f" — consolidation annulée (dataset incomplet).")
                return False
            shutil.copy2(src_vid_top, video_top_out / new_fname)
            shutil.copy2(src_vid_fol, video_fol_out / new_fname)

            episodes_metadata.append({
                "episode_index": new_idx,
                "tasks": [task_desc],
                "length": num_frames
            })

            global_frame_idx += num_frames
            global_episode_idx += 1
            print(f"  ✅ Position {pos_id} ({info['nom']:8}) ep {orig_idx} → épisode {new_idx:3d} ({num_frames} frames)")

    # 4. Générer info.json (format basé sur lerobot/svla_so101_pickplace)
    motor_names = [
        "shoulder_pan", "shoulder_lift", "elbow_flex",
        "wrist_flex", "wrist_roll", "gripper"
    ]
    video_info = {
        "video.fps": FPS, "video.height": 360, "video.width": 640,
        "video.channels": 3, "video.codec": "mp4v", "video.pix_fmt": "yuv420p",
        "video.is_depth_map": False, "has_audio": False
    }
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
            "action": {"dtype": "float32", "shape": [6], "names": motor_names},
            "observation.state": {"dtype": "float32", "shape": [6], "names": motor_names},
            f"observation.images.{CAM_TOP}": {
                "dtype": "video", "shape": [360, 640, 3],
                "names": ["height", "width", "channels"],
                "info": dict(video_info)
            },
            f"observation.images.{CAM_FOLLOWER}": {
                "dtype": "video", "shape": [360, 640, 3],
                "names": ["height", "width", "channels"],
                "info": dict(video_info)
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

    # 5. tasks.jsonl
    with open(meta_out / "tasks.jsonl", 'w') as f:
        for task_desc, task_idx in sorted(tasks_set.items(), key=lambda x: x[1]):
            f.write(json.dumps({"task_index": task_idx, "task": task_desc}) + "\n")

    # 6. episodes.jsonl
    with open(meta_out / "episodes.jsonl", 'w') as f:
        for ep_meta in episodes_metadata:
            f.write(json.dumps(ep_meta) + "\n")

    # 7. Traçabilité de consolidation
    trace = {
        "created": datetime.now().isoformat(),
        "source": str(SOURCE_BASE),
        "output": str(OUTPUT_BASE),
        "total_episodes": global_episode_idx,
        "total_frames": global_frame_idx,
        "positions": {
            str(pos_id): {"nom": info['nom'], "episodes": info['count']}
            for pos_id, info in inventaire.items()
        }
    }
    with open(meta_out / "consolidation_trace.json", 'w') as f:
        json.dump(trace, f, indent=2)

    return True


# ============================================
# FINALISATION (opère sur un dataset donné)
# ============================================

def completer_info_json(dataset_path):
    """Ajoute les champs manquants dans info.json pour la compatibilité LeRobot."""
    info_file = dataset_path / "meta" / "info.json"
    if not info_file.exists():
        return False

    with open(info_file) as f:
        info = json.load(f)

    modifie = False
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
        print("  ✅ info.json mis à jour")
    else:
        print("  ✅ info.json complet")
    return True


def generer_episodes_stats(dataset_path):
    """Génère meta/episodes_stats.jsonl (requis par LeRobot v2.1).
    Valide d'abord la présence des colonnes obligatoires dans CHAQUE parquet ;
    refuse (return False) si une colonne manque (dataset inexploitable). Les stats
    images utilisent volontairement les valeurs standard ImageNet (backbone ACT
    pré-entraîné) — choix DOCUMENTÉ, non recalculé sans preuve LeRobot/ACT contraire."""
    stats_file = dataset_path / "meta" / "episodes_stats.jsonl"
    data_dir = dataset_path / "data" / "chunk-000"
    parquets = sorted(data_dir.glob("*.parquet"))

    if not parquets:
        print("  ❌ Aucun fichier parquet trouvé")
        return False

    # Validation stricte des colonnes obligatoires AVANT tout calcul.
    for pf in parquets:
        cols = set(pd.read_parquet(pf, columns=None).columns)
        manquantes = [c for c in COLONNES_FINALES_REQUISES if c not in cols]
        if manquantes:
            print(f"  ❌ {pf.name} : colonne(s) obligatoire(s) manquante(s) {manquantes}")
            print("     Dataset inexploitable pour l'entraînement — génération des stats annulée.")
            return False

    print("\n📊 Génération de episodes_stats.jsonl...")
    stats_lines = []
    for pf in parquets:
        ep_idx = int(pf.stem.split('_')[1])
        df = pd.read_parquet(pf)

        ep_stats = {"episode_index": ep_idx, "stats": {}}

        states = np.array(df['observation.state'].tolist(), dtype=np.float32)
        ep_stats["stats"]["observation.state"] = {
            "mean": states.mean(axis=0).tolist(),
            "std": states.std(axis=0).tolist(),
            "min": states.min(axis=0).tolist(),
            "max": states.max(axis=0).tolist(),
            "count": [len(df)]
        }

        actions = np.array(df['action'].tolist(), dtype=np.float32)
        ep_stats["stats"]["action"] = {
            "mean": actions.mean(axis=0).tolist(),
            "std": actions.std(axis=0).tolist(),
            "min": actions.min(axis=0).tolist(),
            "max": actions.max(axis=0).tolist(),
            "count": [len(df)]
        }

        # Stats images : valeurs standard ImageNet (choix délibéré, cf. docstring).
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

    with open(stats_file, 'w') as f:
        for line in stats_lines:
            f.write(json.dumps(line) + "\n")

    print(f"\n  ✅ episodes_stats.jsonl généré ({len(stats_lines)} épisodes)")
    return True


def mettre_a_jour_codec_info_json(dataset_path):
    """Met à jour video.codec ('mp4v' → 'h264') dans info.json après conversion H.264.
    Idempotent : ne modifie que les champs encore à 'mp4v'. LeRobot décode d'après le
    flux réel, donc non bloquant, mais une métadonnée fausse n'a pas lieu d'être."""
    info_file = dataset_path / "meta" / "info.json"
    if not info_file.exists():
        return
    with open(info_file) as f:
        info = json.load(f)
    modifie = False
    for spec in info.get("features", {}).values():
        if isinstance(spec, dict) and spec.get("dtype") == "video":
            vinfo = spec.get("info", {})
            if vinfo.get("video.codec") == "mp4v":
                vinfo["video.codec"] = "h264"
                modifie = True
    if modifie:
        with open(info_file, 'w') as f:
            json.dump(info, f, indent=2)
        print("  🔧 info.json : video.codec mis à jour (mp4v → h264)")


def convertir_videos_h264(dataset_path):
    """Convertit les vidéos en H.264 (compatibilité navigateur). Retourne un statut
    explicite : 'ok' (tout converti ou déjà fait), 'non_fait' (ffmpeg absent),
    'echec' (au moins une conversion a échoué)."""
    vid_dir = dataset_path / "videos" / "chunk-000"
    if not vid_dir.exists():
        return "non_fait"

    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
        if result.returncode != 0:
            print("  ⚠️  ffmpeg non disponible — vidéos non converties")
            return "non_fait"
    except FileNotFoundError:
        print("  ⚠️  ffmpeg non trouvé — vidéos non converties")
        return "non_fait"

    marker = dataset_path / "meta" / ".h264_converted"
    if marker.exists():
        print("  ✅ Vidéos déjà converties en H.264")
        mettre_a_jour_codec_info_json(dataset_path)
        return "ok"

    print("\n🎬 Conversion des vidéos en H.264 (compatibilité navigateur)...")
    mp4_files = list(vid_dir.rglob("*.mp4"))
    total = len(mp4_files)

    # TOUT-OU-RIEN : on convertit d'abord tout vers des fichiers temporaires SANS
    # toucher aux originaux ; on ne remplace les originaux que si TOUTES les
    # conversions réussissent. Sinon le dataset reste uniformément en mp4v (jamais
    # un état mixte h264/mp4v).
    convertis = []  # liste de (tmp_file, mp4_file) convertis avec succès
    erreurs = 0
    for i, mp4_file in enumerate(mp4_files):
        tmp_file = mp4_file.with_suffix('.tmp.mp4')
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp4_file),
             "-c:v", "libx264", "-preset", "fast", "-crf", "23",
             "-pix_fmt", "yuv420p", str(tmp_file)],
            capture_output=True
        )
        if result.returncode == 0:
            convertis.append((tmp_file, mp4_file))
            print(f"  ✅ [{i+1}/{total}] {mp4_file.parent.name}/{mp4_file.name}")
        else:
            if tmp_file.exists():
                tmp_file.unlink()
            erreurs += 1
            print(f"  ❌ [{i+1}/{total}] {mp4_file.name} — échec conversion")

    if erreurs:
        # Annulation : on supprime les temporaires réussis, AUCUN original n'est modifié.
        for tmp_file, _ in convertis:
            if tmp_file.exists():
                tmp_file.unlink()
        print(f"\n  ❌ {erreurs}/{total} échec(s) — AUCUN original modifié "
              f"(dataset laissé en mp4v ; relancez pour réessayer).")
        return "echec"

    # Toutes les conversions ont réussi : on remplace les originaux d'un seul tenant.
    # Encadré : un échec d'E/S ici laisserait TMP en état mixte → arrêt propre (le
    # dataset final n'étant pas encore basculé, l'ancien dataset reste intact).
    try:
        for tmp_file, mp4_file in convertis:
            tmp_file.replace(mp4_file)
    except Exception as e:
        print(f"\n  ❌ Remplacement vidéo interrompu ({e}) — dataset temporaire incohérent.")
        return "echec_remplacement"
    marker.touch()
    mettre_a_jour_codec_info_json(dataset_path)
    print(f"\n  ✅ {total} vidéos converties en H.264")
    return "ok"


def verifier_frames_video(dataset_path):
    """Vérifie que chaque vidéo a la bonne résolution (640×360) ET autant de frames
    que son parquet. Retourne (etat, detail) avec etat dans {"ok", "incoherences",
    "non_verifie"} : « non vérifié » (ffprobe absent) n'est PAS « OK »."""
    print("\n🔍 Vérification résolution + frames vidéo vs parquet...")

    try:
        r = subprocess.run(["ffprobe", "-version"], capture_output=True)
        if r.returncode != 0:
            print("  ⚠️  ffprobe non disponible — vérification NON effectuée.")
            return "non_verifie", None
    except FileNotFoundError:
        print("  ⚠️  ffprobe non trouvé — vérification NON effectuée.")
        return "non_verifie", None

    def compter_frames(video_path):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                 "-show_entries", "stream=nb_read_frames",
                 "-of", "default=nokey=1:noprint_wrappers=1", str(video_path)],
                capture_output=True, text=True
            )
            return int(r.stdout.strip())
        except (ValueError, FileNotFoundError):
            return None

    def dimensions_video(video_path):
        """Retourne (largeur, hauteur) via ffprobe, ou None si illisible."""
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height",
                 "-of", "csv=s=x:p=0", str(video_path)],
                capture_output=True, text=True
            )
            w, h = r.stdout.strip().split('x')
            return int(w), int(h)
        except (ValueError, FileNotFoundError):
            return None

    parquets = sorted((dataset_path / "data" / "chunk-000").glob("*.parquet"))
    incoherences = 0
    non_comptees = 0
    for pf in parquets:
        ep_idx = int(pf.stem.split('_')[1])
        n_parquet = len(pd.read_parquet(pf))
        fname = f"episode_{ep_idx:06d}.mp4"
        for cam in [CAM_TOP, CAM_FOLLOWER]:
            vid = dataset_path / "videos" / "chunk-000" / f"observation.images.{cam}" / fname
            if not vid.exists():
                print(f"  ❌ Épisode {ep_idx:3d} ({cam}) : vidéo manquante")
                incoherences += 1
                continue
            dims = dimensions_video(vid)
            if dims is None:
                print(f"  ⚠️  Épisode {ep_idx:3d} ({cam}) : dimensions vidéo non vérifiables")
                non_comptees += 1
            elif dims != (VIDEO_WIDTH, VIDEO_HEIGHT):
                print(f"  ❌ Épisode {ep_idx:3d} ({cam}) : résolution {dims[0]}×{dims[1]} ≠ {VIDEO_WIDTH}×{VIDEO_HEIGHT} attendue")
                incoherences += 1
            n_video = compter_frames(vid)
            if n_video is None:
                print(f"  ⚠️  Épisode {ep_idx:3d} ({cam}) : comptage de frames impossible")
                non_comptees += 1
            elif n_video != n_parquet:
                print(f"  ❌ Épisode {ep_idx:3d} ({cam}) : {n_video} frames vidéo ≠ {n_parquet} lignes parquet")
                incoherences += 1

    if incoherences > 0:
        print(f"  ❌ {incoherences} incohérence(s) — à examiner avant l'entraînement.")
        return "incoherences", incoherences
    if non_comptees > 0:
        print(f"  ⚠️  {non_comptees} vidéo(s) non comptée(s) — vérification incomplète.")
        return "non_verifie", non_comptees
    print(f"  ✅ Résolution 640×360 et frames = parquet pour tous les épisodes ({len(parquets)})")
    return "ok", 0


def afficher_resume(info, dataset_path):
    """Affiche le résumé du dataset préparé."""
    n_parquet = len(list((dataset_path / "data" / "chunk-000").glob("*.parquet")))
    total_size = sum(f.stat().st_size for f in dataset_path.rglob("*") if f.is_file())
    if total_size > 1024 * 1024 * 1024:
        size_str = f"{total_size / (1024**3):.1f} GB"
    elif total_size > 1024 * 1024:
        size_str = f"{total_size / (1024**2):.0f} MB"
    else:
        size_str = f"{total_size / 1024:.0f} KB"

    meta_files = []
    for f in ["info.json", "episodes.jsonl", "tasks.jsonl", "episodes_stats.jsonl"]:
        status = "✅" if (dataset_path / "meta" / f).exists() else "❌"
        meta_files.append(f"  {status} {f}")

    print(f"""
╔══════════════════════════════════════════════════════════╗
║          DATASET PRÉPARÉ — RÉSUMÉ                        ║
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


# ============================================
# BASCULE ATOMIQUE & RAPPORT
# ============================================

def nettoyer_tmp():
    """Supprime le dossier temporaire s'il existe (best-effort)."""
    if TMP_BASE.exists():
        try:
            shutil.rmtree(TMP_BASE)
        except Exception as e:
            print(f"  ⚠️  Nettoyage du dossier temporaire impossible ({e}).")


def basculer_vers_final():
    """Remplace OUTPUT_BASE par TMP_BASE de façon aussi atomique que possible :
    l'ancien dataset n'est supprimé qu'au tout dernier moment, puis TMP est renommé.
    Retourne True si la bascule a réussi."""
    try:
        if OUTPUT_BASE.exists():
            ancien = OUTPUT_BASE.with_name(OUTPUT_BASE.name + "_old")
            if ancien.exists():
                shutil.rmtree(ancien)
            OUTPUT_BASE.rename(ancien)            # met l'ancien de côté
            try:
                TMP_BASE.rename(OUTPUT_BASE)       # installe le nouveau
            except Exception:
                ancien.rename(OUTPUT_BASE)         # rollback si le renommage échoue
                raise
            # Le nouveau dataset est installé : le nettoyage de l'ancien est
            # best-effort et ne doit JAMAIS faire échouer une bascule réussie.
            try:
                shutil.rmtree(ancien)
            except Exception as e:
                print(f"  ⚠️  Ancien dataset non supprimé ({ancien.name}) : {e}"
                      f" — suppression manuelle possible, le nouveau dataset est en place.")
        else:
            TMP_BASE.rename(OUTPUT_BASE)
        return True
    except Exception as e:
        print(f"  ❌ Bascule vers le dataset final impossible ({e}).")
        return False


def afficher_rapport_final(h264_status, frames_status):
    """Rapport à états DISTINCTS : on ne déclare jamais « tout prêt » d'un bloc."""
    map_h264 = {
        "ok": "✅ vidéos en H.264 (visualisation navigateur OK)",
        "non_fait": "⚠️  non faite (ffmpeg absent) — vidéos encore en mp4v, visualisation navigateur indisponible",
        "echec": "❌ conversion échouée — vidéos conservées en mp4v, relance possible",
    }
    map_frames = {
        "ok": "✅ frames vidéo = lignes parquet (vérifié)",
        "non_verifie": "⚠️  NON vérifiée (ffprobe absent, dimensions illisibles ou comptage impossible)",
        "incoherences": "❌ incohérences détectées",
    }
    print("\n" + "=" * 60)
    print("  RAPPORT DE PRÉPARATION DU DATASET")
    print("=" * 60)
    print(f"  • Consolidation + métadonnées v2.1 : ✅ (info.json, tasks, episodes, episodes_stats)")
    print(f"  • Conversion H.264 (navigateur) : {map_h264.get(h264_status, h264_status)}")
    print(f"  • Vérification frames vidéo/parquet : {map_frames.get(frames_status, frames_status)}")
    print("-" * 60)
    print(f"  📂 Dataset final : {OUTPUT_BASE}")
    print("  ℹ️  Métadonnées complètes pour l'entraînement (script 10).")
    print("     La lecture vidéo dépend de votre backend LeRobot : un essai avec le")
    print("     script 10 confirme la compatibilité (mp4v vs H.264).")
    print("=" * 60)


# ============================================
# VISUALISATION (optionnelle)
# ============================================

def ouvrir_navigateur_quand_pret(url, timeout=30.0, interval=0.5):
    """Attend que le serveur local réponde avant d'ouvrir le navigateur."""
    debut = time.time()
    while time.time() - debut < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1):
                webbrowser.open(url)
                return
        except Exception:
            time.sleep(interval)
    print(f"⚠️  Le navigateur n'a pas été ouvert automatiquement : serveur non joignable après {timeout:.0f} s.")
    print(f"   Ouvrez manuellement : {url}")


def lancer_visualisation():
    """Lance l'outil de visualisation officiel LeRobot sur le dataset final."""
    script_path = LEROBOT_DIR / "lerobot" / "scripts" / "visualize_dataset_html.py"
    if not script_path.exists():
        print(f"\n❌ Script de visualisation introuvable :\n   {script_path}")
        return

    url = "http://127.0.0.1:9090"
    print("\n🌐 Lancement de la visualisation LeRobot...")
    print(f"   Le navigateur par défaut s'ouvrira automatiquement (sinon : {url}).")
    print("   Appuyez sur Ctrl+C dans le terminal pour arrêter.\n")

    threading.Thread(target=ouvrir_navigateur_quand_pret, args=(url,), daemon=True).start()
    try:
        subprocess.run(
            [sys.executable, str(script_path),
             "--repo-id", "local/so101_pick_place_consolidated",
             "--tolerance-s", "1.0"],
            cwd=str(LEROBOT_DIR)
        )
    except KeyboardInterrupt:
        print("\n\n✅ Serveur de visualisation arrêté.")


# ============================================
# ORCHESTRATION
# ============================================

def dataset_final_pret():
    """Heuristique (pas une validation complète) : OUTPUT_BASE ressemble-t-il à un
    dataset déjà préparé ? Sert à proposer le raccourci visualisation."""
    meta = OUTPUT_BASE / "meta"
    for f in ["info.json", "episodes_stats.jsonl", "tasks.jsonl", "episodes.jsonl"]:
        if not (meta / f).exists():
            return False
    return any((OUTPUT_BASE / "data" / "chunk-000").glob("*.parquet"))


def preparer_dataset():
    """Pipeline complet : analyse → validation → consolidation (TMP) → finalisation
    → bascule atomique → rapport. Retourne True si un dataset final a été produit."""
    if not SOURCE_BASE.exists():
        print(f"❌ Dossier source introuvable :\n   {SOURCE_BASE}")
        print("\n   Lancez d'abord le script 8 pour enregistrer des épisodes.")
        return False

    print("🔍 Analyse des données source...")
    inventaire, total_episodes, total_frames, donnees_erreurs = analyser_source()

    if total_episodes == 0:
        print("\n❌ Aucun épisode trouvé. Enregistrez d'abord des épisodes avec le script 8.")
        return False

    afficher_inventaire(inventaire, total_episodes, total_frames)

    # Fail-closed : parquets source invalides (colonnes, vide, forme, NaN/Inf).
    if donnees_erreurs:
        print(f"\n❌ {len(donnees_erreurs)} parquet(s) source invalide(s) :")
        for err in donnees_erreurs[:10]:
            print(f"   • {err}")
        if len(donnees_erreurs) > 10:
            print(f"   ... et {len(donnees_erreurs) - 10} autres")
        print("   Préparation annulée (dataset inexploitable pour l'entraînement).")
        return False

    # Fail-closed : vidéos manquantes pour des épisodes existants.
    print("\n🔍 Vérification des vidéos...")
    erreurs_videos = verifier_videos(inventaire)
    if erreurs_videos:
        print(f"\n❌ {len(erreurs_videos)} vidéo(s) manquante(s) pour des épisodes existants :")
        for err in erreurs_videos[:10]:
            print(f"   • {err}")
        if len(erreurs_videos) > 10:
            print(f"   ... et {len(erreurs_videos) - 10} autres")
        print("   Préparation annulée (dataset incomplet).")
        return False
    print("  ✅ Toutes les vidéos sont présentes")

    # Pas de blocage sur le NOMBRE d'épisodes : un dataset réduit (peu d'épisodes
    # par position) est un usage pédagogique légitime. On signale seulement les
    # positions à 0 épisode (risque d'oubli après renommage, ex. position_2_libre)
    # et on demande une confirmation explicite — sans empêcher quoi que ce soit.
    positions_vides = [(pid, info['nom']) for pid, info in inventaire.items() if info['count'] == 0]
    if positions_vides:
        print("\n⚠️  Position(s) SANS épisode — absente(s) du dataset final :")
        for pid, nom in positions_vides:
            print(f"   • Position {pid} ({nom}) : 0 épisode")
        n_ok = sum(1 for v in inventaire.values() if v['count'] > 0)
        print(f"   Le dataset contiendra {n_ok}/{len(inventaire)} positions, {total_episodes} épisodes.")
        if input("   Confirmer la préparation ainsi ? [O/N] : ").strip().upper() != 'O':
            print("   Préparation annulée.")
            return False

    print(f"\n📦 Le dataset préparé sera créé dans :\n   {OUTPUT_BASE}")
    print(f"   (construction temporaire : {TMP_BASE.name})")
    input("\nAppuyez sur ENTRÉE pour lancer la préparation...")

    # Construction dans le dossier temporaire (atomicité).
    nettoyer_tmp()
    ok_consol = consolider(inventaire, TMP_BASE)
    if not ok_consol:
        nettoyer_tmp()
        print("\n❌ Consolidation annulée — dataset final inchangé.")
        return False

    # Finalisation (sur le dossier temporaire).
    completer_info_json(TMP_BASE)
    if not generer_episodes_stats(TMP_BASE):
        nettoyer_tmp()
        print("\n❌ Finalisation impossible (statistiques) — dataset final inchangé.")
        return False

    h264_status = convertir_videos_h264(TMP_BASE)
    if h264_status == "echec_remplacement":
        nettoyer_tmp()
        print("\n❌ Conversion vidéo interrompue (remplacement) — préparation annulée"
              " (dataset final inchangé).")
        return False
    frames_status, _ = verifier_frames_video(TMP_BASE)

    # Incohérences frames/parquet = corruption structurelle → arrêt dur en mode normal.
    if frames_status == "incoherences":
        nettoyer_tmp()
        print("\n❌ Incohérences frames/parquet détectées — préparation annulée "
              "(dataset final inchangé).")
        return False

    # Bascule atomique vers le dataset final.
    if not basculer_vers_final():
        nettoyer_tmp()
        print("\n❌ Bascule impossible — dataset final inchangé.")
        return False

    # Résumé + rapport à états distincts.
    info_file = OUTPUT_BASE / "meta" / "info.json"
    with open(info_file) as f:
        info = json.load(f)
    afficher_resume(info, OUTPUT_BASE)
    afficher_rapport_final(h264_status, frames_status)
    return True


def verifier_moteur_parquet():
    """Préflight : pandas a besoin d'un moteur Parquet (pyarrow ou fastparquet)
    pour lire/écrire les .parquet. Vérifié explicitement au démarrage pour éviter
    un échec obscur en pleine préparation."""
    for moteur in ("pyarrow", "fastparquet"):
        try:
            __import__(moteur)
            return
        except ImportError:
            continue
    print("\n❌ Moteur Parquet manquant : pandas ne peut ni lire ni écrire les .parquet.")
    print("   → Installe pyarrow (recommandé) :  pip install pyarrow")
    sys.exit(1)


def main():
    clear_screen()
    verifier_moteur_parquet()
    print("""
╔══════════════════════════════════════════════════════════╗
║     SEM — PRÉPARATION DATASET SO-ARM 101                 ║
║     Service Écoles-Médias — DIP Genève                   ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Entrée intelligente : si un dataset final préparé existe déjà, proposer
    # d'aller directement à la visualisation plutôt que de tout reconstruire.
    if dataset_final_pret():
        print(f"ℹ️  Un dataset préparé existe déjà :\n   {OUTPUT_BASE}")
        print("\n  [P] Préparer à nouveau (reconsolider depuis le script 8)")
        print("  [V] Visualiser directement le dataset existant")
        print("  [Q] Quitter")
        choix = input("\n  Votre choix : ").strip().upper()
        if choix == 'V':
            lancer_visualisation()
            return
        if choix != 'P':
            print("\n✅ Rien à faire.")
            return

    if not preparer_dataset():
        return

    # Visualisation optionnelle.
    print("\n" + "=" * 55)
    print("  V — Lancer la visualisation dans le navigateur")
    print("  Q — Quitter (prochaine étape : entraînement)")
    print("=" * 55)
    choix = input("\n  Votre choix : ").strip().upper()
    if choix == 'V':
        lancer_visualisation()
    else:
        print("\n✅ Préparation terminée.")
        print("🚀 Prochaine étape :")
        print("   python SEM_so101_10_train.py")


if __name__ == "__main__":
    main()
