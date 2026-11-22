# Smart Workout Tracker

**USC EE 250 — Final Project | Fall 2026**

**Team:** Leah Moore and Firuz Farhodov

## Overview

A wrist-worn IoT workout assistant designed to automatically count exercise repetitions, monitor heart rate, and estimate when a user is ready to begin their next set.

The system combines motion sensing, physiological sensing, real-time signal processing, and wireless communication to provide feedback during resistance training.

## System Architecture

The project consists of two main nodes:

**1. ESP32-S3 — Sensor Node**
- MPU6050 accelerometer and gyroscope for motion tracking
- MAX30102 PPG sensor for heart-rate monitoring
- I²C communication with both sensors
- Planned Wi-Fi/MQTT communication with the host

**2. MacBook — Host Node**
- Python-based sensor data processing
- IMU visualization and repetition detection
- Exercise set and rest tracking
- MQTT data reception
- Planned heart-rate recovery and readiness feedback

**Data flow:**

`MPU6050 + MAX30102 → ESP32-S3 → Wi-Fi/MQTT → Python Host → Workout Feedback`

## Hardware

| Component | Purpose |
|---|---|
| ESP32-S3 DevKitC-1 | Sensor acquisition and wireless communication |
| MPU6050 (GY-521) | 3-axis acceleration and angular velocity |
| MAX30102 | Optical PPG measurements for heart-rate estimation |
| MacBook | Data processing and visualization |
| 3D-printed enclosure | Planned wrist-mounted sensor housing |

### Planned I²C Connections

| Sensor Pin | ESP32-S3 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO 8 |
| SCL | GPIO 9 |

## Software

### ESP32 Firmware — `main/`

Written in C using ESP-IDF v6.0.2.

The initial firmware includes an I²C scanner using the ESP-IDF master driver API.

### Host Software — `host/`

Written in Python.

Current source files include:

| File | Purpose |
|---|---|
| `detect_reps.py` | Repetition detection |
| `track_workout.py` | Workout state tracking |
| `plot_imu.py` | IMU data visualization |
| `simulate_imu.py` | Synthetic IMU data generation |
| `replay_live.py` | Simulated live data replay |
| `mqtt_workout.py` | MQTT workout data handling |
| `plot_style.py` | Shared plotting utilities |
| `test_*.py` | Automated tests |

See `host/README.md` for detailed host-side documentation and usage.

## Setup

### ESP32 Firmware

Requirements:
- ESP-IDF v6.0.2
- ESP32-S3 development board
- USB data cable

From the project root:

```bash
. ~/.espressif/v6.0.2/esp-idf/export.sh
idf.py set-target esp32s3
idf.py build
idf.py flash monitor
```

The ESP-IDF environment path may differ between computers. The target only needs to be set when initially configuring the project or changing targets.

### Python Host

Python 3 is required.

Refer to `host/README.md` for individual script commands, test instructions, and dependency setup.

MQTT-specific dependencies are listed in `host/requirements-mqtt.txt`.

## Development Progress

### Verified

- [x] ESP-IDF development environment configured
- [x] ESP32-S3 firmware successfully compiled
- [x] Firmware successfully flashed to ESP32-S3
- [x] I²C scanner runs and produces serial output
- [x] MPU6050 header pins soldered
- [x] GitHub repository initialized

### Implemented in Source — Validation Pending

- [ ] Python IMU visualization
- [ ] Synthetic motion data generation
- [ ] Repetition detection
- [ ] Workout state tracking
- [ ] Live data replay
- [ ] MQTT host-side processing

### Planned

- [ ] Connect MPU6050 and verify I²C address
- [ ] Acquire real six-axis motion data
- [ ] Validate rep detection against actual exercise repetitions
- [ ] Integrate MAX30102 and estimate heart rate
- [ ] Establish end-to-end ESP32-to-host MQTT communication
- [ ] Implement recovery/readiness estimation
- [ ] Build a real-time workout dashboard
- [ ] Complete wearable enclosure and system testing

## Testing and Validation

The project will be evaluated using manually counted exercise repetitions, sensor recordings, and end-to-end communication tests.

Planned evaluation metrics include:
- Rep-count accuracy
- False-positive and missed-repetition counts
- Exercise/rest state detection
- Heart-rate signal quality
- Communication reliability and latency

## AI-Assisted Development

ChatGPT and OpenAI Codex have been used to assist with project planning, software development, debugging, and documentation.

## Next Steps

1. Connect and validate the MPU6050 hardware.
2. Record real wrist-motion data during bicep curls.
3. Test and refine the rep-detection pipeline.
4. Integrate PPG measurements and MQTT communication.
5. Complete the recovery algorithm and dashboard.

**Final submission deadline: December 7, 2026.**