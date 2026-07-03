# 🤖 SO-ARM 101 — Educational Robotics, AI & Imitation Learning

<p align="center">
  <strong>Build, teleoperate, train, and deploy a robot that can learn a motion by demonstration.</strong>
</p>

<p align="center">
  <a href="#-main-script-workflow">Main script workflow</a> •
  <a href="#-phase-by-phase-usage-guide">Project phases</a> •
  <a href="#-complete-file-structure">Structure</a> •
  <a href="#-resources">Resources</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10-blue">
  <img alt="Ubuntu" src="https://img.shields.io/badge/Ubuntu-22.04%20%7C%2024.04-orange">
  <img alt="LeRobot" src="https://img.shields.io/badge/LeRobot-Imitation%20Learning-purple">
  <img alt="License" src="https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey">
</p>

> 🇬🇧 **English** | 🇫🇷 [Français](README.md)

---

## 🎯 Project Goal

**SO-ARM 101 - Educational Robotics Project** is a complete, reproducible, and educational pipeline for exploring modern robotics with AI.

The project makes it possible to train a robotic arm to perform an object-manipulation task through **learning by demonstration** (*Imitation Learning*): a human guides a **Leader** arm, a **Follower** arm reproduces the motion, the demonstrations are recorded with two cameras, and an ACT (*Action Chunking Transformers*) model then learns to perform the task autonomously.

Developed by the **Service Écoles-Médias (SEM)**, part of Geneva's **Department of Public Instruction (DIP)**, this project aims to make AI-driven robotics concrete, observable, and open to experimentation in an educational setting.

### Why Is This Project Interesting?

- 🎓 **Designed for education**: a clear, phase-by-phase progression suited to teaching.
- 🛠️ **DIY and turnkey**: from software setup to autonomous deployment.
- 🤖 **Hands-on AI**: imitation learning, dataset, training, and inference on a real robot.
- 📷 **Two cameras**: a global view plus a gripper-mounted camera view.
- 🔁 **Reproducible**: scripts, guides, calibration, masks, **camera setup (auto exposure, then frozen for the session) + image check**, and checkpoints.
- 🚀 **Modern**: built on LeRobot, PyTorch, the Dynamixel SDK, and ACT.

---

## 👥 Who Is This Project For?

| Audience | What the project offers |
| :--- | :--- |
| **Teachers** | A complete sequence for teaching robotics, programming, AI, and the experimental method. |
| **Students / advanced learners** | A hands-on project for understanding the full chain: sensors → data → model → action. |
| **Educational institutions** | A structured foundation for building workshops, demonstrators, training courses, or interdisciplinary projects. |
| **Makers / developers** | An open-source robotics pipeline to adapt, improve, or extend. |

---

## 🧠 What You Will Build

By the end of the journey, you will have a system that can:

1. configure and test the servomotors;
2. calibrate the mechanical limits of both arms;
3. teleoperate a Follower arm with a Leader arm;
4. film the scene with two cameras;
5. record a dataset of demonstrations;
6. consolidate and verify the data;
7. train an ACT model;
8. deploy the model so the robot acts on its own.

The reference task is deliberately simple and educational: **pick up a hexagonal prism (labeled "cube" in the dataset) from one of five positions and place it in a box**.

---

## 📋 Phases Overview

### ✅ Complete Pipeline Available

- **Phase 1**: Full installation of the LeRobot environment
- **Phase 2**: Servo configuration (IDs, testing, centering, and assembly)
- **Phase 3**: Calibration of movement limits
- **Phase 4**: Testing and manual control
- **Phase 5**: Leader → Follower teleoperation (configuration + real-time teleoperation)
- **Phase 6**: Teleoperation with cameras and definition of the working-area mask
- **Phase 7**: Dataset recording for imitation learning (2 cameras)
- **Phase 8**: Dataset consolidation and verification (statistics, video conversion, visualization)
- **Phase 9**: ACT model training (*Action Chunking Transformers*)
- **Phase 10**: Autonomous deployment of the trained model

### 🚀 Possible Extensions

- classroom teaching scenarios;
- new manipulation tasks;
- dataset improvements;
- model comparisons;
- a web interface for control or visualization;
- versions in additional languages.

---

## 🔧 Hardware Setup

### Required Hardware

- 2× SO-ARM 101 arms (**Leader** + **Follower**)
- 2× Feetech or Waveshare USB adapters
- 2× Power supplies depending on the kit used
- 12× Feetech STS3215 servos
- 2× USB cameras (`cam_top` + `cam_follower`)
- 1× PC running Ubuntu 22.04 or 24.04
- NVIDIA GPU strongly recommended for training (≥ 8 GB VRAM) — CPU possible but much slower

### Servo Configuration

**Leader** — human control arm

- Servos 1, 3: ratio 1:191 (C044)
- Servo 2: ratio 1:345 (C001)
- Servos 4, 5, 6: ratio 1:147 (C046)

**Follower** — the arm that learns and acts

- All servos: ratio 1:345 (identical)

---

## ⚡ Main Script Workflow

This section gives a high-level view of the general script order. It does not replace the detailed guides: each phase requires hardware checks, operator decisions, and safety steps.

```bash
# Activate the environment
conda activate lerobot

# Go to the SEM scripts
cd ~/lerobot/Scripts_SEM/scripts

# Configure the servos
python SEM_so101_1_configure.py

# Calibrate the arms
python SEM_so101_2_calibrate.py

# Teleoperation with cameras
python SEM_so101_7_teleoperation_camera.py

# Record the dataset
python SEM_so101_8_record_dataset.py

# Consolidate, verify, train, deploy
python SEM_so101_9_dataset.py
python SEM_so101_10_train.py
python SEM_so101_11_deploy.py
```

For a complete and safe installation, follow the detailed guides in the `Guides/` folder.

---

## 📚 Phase-by-Phase Usage Guide

> **Note:** the educational phases sometimes group several scripts. Phase numbers therefore do not always match the Python file numbers (for example, Phase 5 uses scripts 5 and 6).

### Phase 1: LeRobot Installation

```bash
# Follow the complete guide: Guides/SEM_SO101_Phase1.md
# Key points: Python 3.10, PyTorch, Dynamixel SDK, ffmpeg
# USB permissions: sudo usermod -a -G dialout $USER
# Camera permissions: sudo usermod -a -G video $USER
# Camera tools: v4l-utils (v4l2-ctl); guvcview optional
```

### Phase 2: Servo Configuration

```bash
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_1_configure.py

# Configures each servo with its ID (1-6)
# One servo at a time, movement test included
# Options: T = configure all 6 servos, B = lock, L = release, D = detect the port
```

### Phase 3: Calibration

```bash
python SEM_so101_2_calibrate.py

# Sets the min/max limits of each servo
# Automatically saved to ~/lerobot/calibration/
```

### Phase 4: Testing and Manual Control

```bash
# Real-time monitoring
python SEM_so101_3_monitor.py

# Manual control (unified Leader/Follower script)
python SEM_so101_4_control.py
```

### Phase 5: Teleoperation

```bash
# Per-servo COPY/MIRROR configuration
python SEM_so101_5_config_teleoperation.py

# Simultaneous Leader → Follower control
python SEM_so101_6_teleoperation.py
```

### Phase 6: Cameras

```bash
# Teleoperation with video feedback and creation of the working-area mask
python SEM_so101_7_teleoperation_camera.py

# The mask is shared with phases 7 and 10
# File: ~/lerobot/calibration/camera_mask.json
```

### Phase 7: Dataset Recording

```bash
# Recording with 2 cameras (cam_top + cam_follower)
python SEM_so101_8_record_dataset.py

# Task: Pick up a hexagonal prism (labeled "cube" in the dataset) and place it in a box
# 5 positions × 10 episodes = 50 demonstrations
# Output format: LeRobotDataset v2.1
# Camera check: exposure and white balance are auto-adjusted, then frozen at
# startup (global camera, then gripper camera), with an image-quality check
# before each recording block to ensure usable images
```

### Phase 8: Consolidation and Visualization

```bash
# Script 9 — merge the 5 positions into a unified dataset,
# verify the dataset, generate statistics,
# convert the videos to H.264, and visualize in the browser
python SEM_so101_9_dataset.py

# Consolidated and verified dataset, ready for training
```

### Phase 9: ACT Model Training

```bash
# Launch training
python SEM_so101_10_train.py

# The script uses the consolidated dataset
# Training can be resumed from an existing checkpoint
# NVIDIA GPU strongly recommended (≥ 8 GB VRAM); CPU possible but much slower
```

### Phase 10: Autonomous Deployment

```bash
# Deploy the trained ACT model
python SEM_so101_11_deploy.py

# The Follower acts autonomously from the two cameras
# Mask reapplied + two-camera check: exposure auto-adjusted to the room
# lighting, then frozen, followed by an image-quality check
# Controls: P = pause, R = return to rest + stop model, Enter = restart, Q = quit
```

---

## 📁 Complete File Structure

```
/home/prof/lerobot/Scripts_SEM
├── Guides
│   ├── README.md
│   ├── SEM_SO101_Phase1.md
│   ├── SEM_SO101_Phase2.md
│   ├── SEM_SO101_Phase3.md
│   ├── SEM_SO101_Phase4.md
│   ├── SEM_SO101_Phase5.md
│   ├── SEM_SO101_Phase6.md
│   ├── SEM_SO101_Phase7.md
│   ├── SEM_SO101_Phase8.md
│   ├── SEM_SO101_Phase9.md
│   └── SEM_SO101_Phase10.md
├── Hardware
│   └── 3D models (STL) and hardware files
├── README.md
└── scripts
    ├── __pycache__
    ├── SEM_so101_camera_auto.py
    ├── SEM_so101_10_train.py
    ├── SEM_so101_11_deploy.py
    ├── SEM_so101_1_configure.py
    ├── SEM_so101_2_calibrate.py
    ├── SEM_so101_3_monitor.py
    ├── SEM_so101_4_control.py
    ├── SEM_so101_5_config_teleoperation.py
    ├── SEM_so101_6_teleoperation.py
    ├── SEM_so101_7_teleoperation_camera.py
    ├── SEM_so101_8_record_dataset.py
    ├── SEM_so101_9_dataset.py
    └── Version_26_05_26
```

**Note:** The `~/lerobot/calibration/` folder is created automatically by the scripts. It notably contains `leader_calibration.json`, `follower_calibration.json`, `repos_position.json`, and `camera_mask.json`.

---

## 🧪 Data Quality and Safety

This project is not just about "making a robot move." It emphasizes **dataset quality**, because an imitation model learns directly from the demonstrations.

The SEM scripts include several safeguards:

- strict consistency between recording and deployment;
- a shared mask for the global camera;
- **image check of both cameras**: auto-then-frozen exposure (and white balance), then an image (lighting) check before each recording block and at deployment;
- verification of both camera streams;
- monitoring of serial reads and writes during recording;
- safe return to the rest position;
- emergency stop with no automatic return movement.

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| USB port not detected | Check the `dialout` group (see Phase 1) |
| Servo not responding | Check power supply and 3-pin cables |
| Lost calibration | Re-run script 2 |
| Jerky movement | Check calibration, rest position, and teleoperation mode |
| Import error | `conda activate lerobot` |
| Script won't start | Check the Python 3.10 environment |
| Camera not detected | Check the `video` group and test with `v4l2-ctl --list-devices` |
| Camera exposure adjustment fails | Check `v4l2-ctl --version` (`v4l-utils` package) |
| Empty videos | Check `ffmpeg -version` and that both cameras are connected |
| Inconsistent dataset | Check the mask, camera exposure setup, image quality, 640×360 resolution, and synchronization of both cameras |
| Frequent "instant ignoré" (skipped timestep) messages | Check cables, power supply, and serial-bus stability |

---

## 📊 Technical Specifications

### STS3215 Servos

- Protocol: Dynamixel v1.0
- Baud rate: 1,000,000 bps
- Range: 0-4095 (0°-360°)
- Center: 2048
- Torque: 15 kg·cm

### Performance

- Control frequency: 30-50 Hz
- Smooth movements: 100 steps
- Teleoperation latency: < 50 ms
- Autonomous deployment: approximately 30 Hz

### Cameras (Phases 6, 7 and 10)

- Resolution: 640 × 360 pixels (16:9)
- FPS: 30 frames/second
- Video format: MP4, then H.264 conversion if needed
- Global camera: `cam_top`
- Gripper camera: `cam_follower`
- Auto-then-frozen exposure (and white balance) per session
- Working-area mask applied to the global camera
- Image check of both cameras (usable lighting, `SEM_so101_camera_auto.py` module)

---

## 🌐 Resources

### Documentation

- [LeRobot GitHub](https://github.com/huggingface/lerobot)
- [SO-ARM Wiki](https://wiki.seeedstudio.com/guide_so-arm_100)
- [Feetech Robotics](https://www.feetechrc.com/)

### Useful Keywords

`SO-ARM 101` · `LeRobot` · `Imitation Learning` · `Action Chunking Transformers` · `ACT` · `Educational robotics` · `Robotics dataset` · `PyTorch` · `Dynamixel SDK` · `Feetech STS3215`

---

## 🤝 Contributing

Contributions are welcome:

- improving the guides;
- bug fixes;
- new educational scenarios;
- script improvements;
- translations into additional languages;
- adding visuals, diagrams, or videos;
- adapting the project to other robotic tasks.

---

## 👥 Contributors

- Yanko Michel — Service Écoles-Médias (SEM), Geneva
- Claude AI — Development assistant
- ChatGPT — Audit, documentation, and structuring assistance

---

## 📝 License

![Creative Commons License](https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png)

This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.

**You are free to:**

- Share — copy and redistribute the material
- Adapt — remix, transform, and build upon the material

**Under the following terms:**

- Attribution — credit the work and indicate any changes
- NonCommercial
- ShareAlike

---

<p align="center">
  <strong>A project to make intelligent robotics visible, hands-on, and teachable.</strong>
</p>

<p align="center">
  Service Écoles-Médias (SEM) — Department of Public Instruction (DIP), Geneva
</p>

**Last updated: see `CHANGELOG.md`**
