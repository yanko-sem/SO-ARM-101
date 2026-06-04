# 🤖 SO-ARM 101 — Educational Robotics, AI & Imitation Learning

<p align="center">
  <strong>Build, teleoperate, train and deploy a robot capable of learning a gesture from demonstration.</strong>
</p>

<p align="center">
  <img src="assets/so-arm101-demo.gif" alt="SO-ARM 101 demo - imitation learning" width="800">
</p>

<p align="center">
  <em>Image/GIF to add: pick-and-place demonstration of the Follower after training.</em>
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

> 🇫🇷 [Français](README.md) | 🇬🇧 **English**

---

## 🎯 Project Goal

**SO-ARM 101 - Educational Robotics Project** is a complete, reproducible and pedagogical pipeline for exploring modern robotics with AI.

The project trains a robotic arm to perform an object manipulation task through **learning from demonstration** (*Imitation Learning*): a human guides a **Leader** arm, a **Follower** arm reproduces the gesture, demonstrations are recorded with two cameras, then an ACT (*Action Chunking Transformers*) model learns to execute the task autonomously.

Developed by the **Service Écoles-Médias (SEM)** of the **Department of Public Education (DIP), Geneva**, this project aims to make robotic AI concrete, observable and experimentally accessible in an educational context.

### Why this project matters

- 🎓 **Designed for education**: a clear, phase-by-phase progression suitable for teaching.
- 🛠️ **DIY and turnkey**: from software setup to autonomous deployment.
- 🤖 **Concrete AI**: imitation learning, datasets, training and inference on a real robot.
- 📷 **Two cameras**: global view + gripper-mounted view.
- 🔁 **Reproducible**: scripts, guides, calibration, masks, camera settings and checkpoints.
- 🚀 **Modern**: based on LeRobot, PyTorch, Dynamixel SDK and ACT.

---

## 👥 Who is this project for?

| Audience | What the project provides |
| :--- | :--- |
| **Teachers** | A complete sequence for teaching robotics, programming, AI and experimental methodology. |
| **Students / advanced learners** | A hands-on project to understand the full chain: sensors → data → model → action. |
| **Educational institutions** | A structured foundation for workshops, demonstrators, training sessions or interdisciplinary projects. |
| **Makers / developers** | An open-source robotics pipeline to adapt, improve or extend. |

---

## 🧠 What you will build

By the end of the workflow, you will have a system capable of:

1. configuring and testing the servomotors;
2. calibrating the mechanical limits of both arms;
3. teleoperating a Follower arm with a Leader arm;
4. filming the scene with two cameras;
5. recording a demonstration dataset;
6. consolidating and checking the data;
7. training an ACT model;
8. deploying the model so the robot acts autonomously.

The reference task is intentionally simple and educational: **pick up a cube from one of five positions and drop it into a box**.

---

## 📋 Overview of the Phases

### ✅ Complete pipeline available

- **Phase 1**: Complete installation of the LeRobot environment
- **Phase 2**: Servo configuration (IDs, testing, centering and mounting)
- **Phase 3**: Movement limit calibration
- **Phase 4**: Testing and manual control
- **Phase 5**: Teleoperation configuration
- **Phase 6**: Leader → Follower teleoperation
- **Phase 7**: Teleoperation with cameras and useful-area mask definition
- **Phase 8**: Dataset recording for imitation learning (2 cameras)
- **Phase 9**: Dataset consolidation
- **Phase 10**: Dataset video checking and conversion
- **Phase 11**: ACT model training (*Action Chunking Transformers*)
- **Phase 12**: Autonomous deployment of the trained model

### 🚀 Possible extensions

- classroom scenarios;
- new manipulation tasks;
- dataset improvement;
- model comparison;
- web interface for control or visualization;
- English version of the project.

---

## 🔧 Hardware Configuration

### Required hardware

- 2× SO-ARM 101 arms (**Leader** + **Follower**)
- 2× Feetech or Waveshare USB adapters
- 2× power supplies depending on the kit used
- 12× Feetech STS3215 servos
- 2× USB cameras (`cam_top` + `cam_follower`)
- 1× PC running Ubuntu 22.04 or 24.04
- (Optional) NVIDIA GPU to speed up training

### Servo configuration

**Leader** — human control arm

- Servos 1,3: 1:191 ratio (C044)
- Servo 2: 1:345 ratio (C001)
- Servos 4,5,6: 1:147 ratio (C046)

**Follower** — arm that learns and acts

- All servos: 1:345 ratio (identical)

---

## ⚡ Main Script Workflow

This section provides a high-level overview of the general order of the scripts. It does not replace the detailed guides: each phase requires hardware checks, operator choices and safety steps.

```bash
# Activate the environment
conda activate lerobot

# Go to the SEM scripts directory
cd ~/lerobot/Scripts_SEM/scripts

# Configure the servos
python SEM_so101_1_configure.py

# Calibrate the arms
python SEM_so101_2_calibrate.py

# Teleoperation with cameras
python SEM_so101_7_teleoperation_camera.py

# Record the dataset
python SEM_so101_8_record_dataset.py

# Consolidate, check, train and deploy
python SEM_so101_9_dataset.py
python SEM_so101_10_visualize_dataset.py
python SEM_so101_11_train.py
python SEM_so101_12_deploy.py
```

For a complete and safe installation, follow the detailed guides in the `Guides/` folder.

---

## 📚 Phase-by-Phase Usage Guide

### Phase 1: LeRobot Installation

```bash
# Follow the full guide: Guides/SEM_SO101_Phase1.md
# Key points: Python 3.10, PyTorch, Dynamixel SDK, ffmpeg
# USB permissions: sudo usermod -a -G dialout $USER
# Camera permissions: sudo usermod -a -G video $USER
# Camera tools: v4l-utils and guvcview
```

### Phase 2: Servo Configuration

```bash
cd ~/lerobot/Scripts_SEM/scripts
python SEM_so101_1_configure.py

# Configure each servo with its ID (1-6)
# One servo at a time, movement test included
# Options: T = configure all 6 servos, B = lock, L = release, D = detect port
```

### Phase 3: Calibration

```bash
python SEM_so101_2_calibrate.py

# Defines the min/max limits of each servo
# Automatically saves to ~/lerobot/calibration/
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
# COPY/MIRROR configuration per servo
python SEM_so101_5_config_teleoperation.py

# Simultaneous Leader → Follower control
python SEM_so101_6_teleoperation.py
```

### Phase 6: Cameras

```bash
# Teleoperation with video feedback and useful-area mask creation
python SEM_so101_7_teleoperation_camera.py

# The mask is shared with phases 8 and 12
# File: ~/lerobot/calibration/camera_mask.json
```

### Phase 7: Dataset Recording

```bash
# Recording with 2 cameras (cam_top + cam_follower)
python SEM_so101_8_record_dataset.py

# Task: pick up a cube and drop it into a box
# 5 positions × 10 episodes = 50 demonstrations
# Output format: LeRobotDataset v2.1
# Camera settings are captured and locked to ensure training/deployment consistency
```

### Phase 8: Consolidation and Visualization

```bash
# Merge the 5 positions into a unified dataset
python SEM_so101_9_dataset.py

# Consolidated dataset used later for training
```

### Phase 9: Video Checking and Conversion

```bash
# Check the dataset and convert videos to H.264 if necessary
python SEM_so101_10_visualize_dataset.py

# Goal: ensure video compatibility with LeRobot training
```

### Phase 10: ACT Model Training

```bash
# Launch training
python SEM_so101_11_train.py

# The script uses the consolidated dataset
# Training can be resumed from an existing checkpoint
# CPU training is possible, NVIDIA GPU recommended
```

### Phase 11: Autonomous Deployment

```bash
# Deploy the trained ACT model
python SEM_so101_12_deploy.py

# The Follower acts autonomously using both cameras
# The mask and camera settings are reapplied to remain consistent with the dataset
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
│   └── SEM_SO101_Phase7.md
├── README.md
└── scripts
    ├── __pycache__
    ├── SEM_8_camera_config.py
    ├── SEM_so101_10_visualize_dataset.py
    ├── SEM_so101_11_train.py
    ├── SEM_so101_12_deploy.py
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

**Note:** The `~/lerobot/calibration/` folder is created automatically by the scripts. It contains, among others, `leader_calibration.json`, `follower_calibration.json`, `repos_position.json`, `camera_mask.json` and `camera_settings.json`.

---

## 🧪 Data Quality and Safety

This project is not just about “making a robot move”. It focuses on **dataset quality**, because an imitation model learns directly from demonstrations.

The SEM scripts include several safeguards:

- strict consistency between recording and deployment;
- shared mask for the global camera;
- exposure / white balance / gain locking;
- verification of both camera streams;
- serial read checks during recording;
- safe return-to-rest behavior;
- emergency stop without automatic return movement.

---

## 🔧 Troubleshooting

| Problem | Solution |
|----------|----------|
| USB port not detected | Check the `dialout` group (see Phase 1) |
| Servo does not respond | Check power supply and 3-pin cables |
| Calibration lost | Run script 2 again |
| Sudden movement | Check calibration, rest position and teleoperation mode |
| Import error | `conda activate lerobot` |
| Script does not start | Check Python 3.10 environment |
| Camera not detected | Check the `video` group and test with `v4l2-ctl --list-devices` |
| Camera settings impossible | Check `v4l2-ctl --version` and `guvcview --version` |
| Empty videos | Check `ffmpeg -version` and both camera connections |
| Inconsistent dataset | Check mask, camera settings, 640×360 resolution and two-camera synchronization |
| Frequent “instant skipped” messages | Check cables, power supply and serial bus stability |

---

## 📊 Technical Specifications

### STS3215 Servos

- Protocol: Dynamixel v1.0
- Baudrate: 1,000,000 bps
- Range: 0-4095 (0°-360°)
- Center: 2048
- Torque: 15 kg.cm

### Performance

- Control frequency: 30-50 Hz
- Smooth movements: 100 steps
- Teleoperation latency: < 50 ms
- Autonomous deployment: around 30 Hz

### Cameras (Phases 7, 8 and 12)

- Resolution: 640 × 360 pixels (16:9)
- FPS: 30 frames per second
- Video format: MP4, then H.264 conversion if necessary
- Global camera: `cam_top`
- Gripper camera: `cam_follower`
- Locked settings: exposure, white balance, gain
- Useful-area mask applied to the global camera

---

## 🌐 Resources

### Documentation

- [LeRobot GitHub](https://github.com/huggingface/lerobot)
- [SO-ARM Wiki](https://wiki.seeedstudio.com/guide_so-arm_100)
- [Feetech Robotics](https://www.feetechrc.com/)

### Useful keywords

`SO-ARM 101` · `LeRobot` · `Imitation Learning` · `Action Chunking Transformers` · `ACT` · `Educational robotics` · `Robotics dataset` · `PyTorch` · `Dynamixel SDK` · `Feetech STS3215`

---

## 🤝 Contributing

Contributions are welcome:

- guide improvements;
- bug fixes;
- new educational scenarios;
- script improvements;
- English translation;
- visuals, diagrams or videos;
- adaptation to other robotic tasks.

---

## 👥 Contributors

- Yanko Michel — Service Écoles-Médias (SEM), Geneva
- Claude AI — Development assistant
- ChatGPT — Assistance with auditing, documentation and structuring

---

## 📝 License

![Creative Commons License](https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png)

This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.

**You are free to:**

- Share — copy and redistribute the material in any medium or format
- Adapt — remix, transform and build upon the material

**Under the following terms:**

- Attribution — Give appropriate credit and indicate changes
- NonCommercial
- ShareAlike

---

<p align="center">
  <strong>A project designed to make intelligent robotics visible, hands-on and teachable.</strong>
</p>

<p align="center">
  Service Écoles-Médias (SEM) — Department of Public Education (DIP), Geneva
</p>

**Last updated: 2026-06-04**
