"""Central configuration for V-MARS.

Every tunable number lives here so that the control code reads like a
description of the process instead of a wall of magic numbers.

Deployment-specific values (database credentials, serial ports) are read from
environment variables. A ``.env`` file in the working directory or the project
root is loaded automatically (see ``.env.example``); real environment variables
always win over the file.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
ASSETS_DIR = PACKAGE_DIR / "assets"


def _load_dotenv() -> None:
    """Minimal ``.env`` loader (KEY=VALUE lines, ``#`` comments).

    Kept dependency-free on purpose: the Orange Pi image should not need extra
    pip packages just to read four settings.
    """
    for candidate in (Path.cwd() / ".env", PROJECT_ROOT / ".env"):
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))
        return


_load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# ─────────────────────────────────────────────────────────────────────────────
# Database (PostgreSQL)
# ─────────────────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "dbname": _env("VMARS_DB_NAME", "rotation_platform"),
    "user": _env("VMARS_DB_USER", "postgres"),
    "password": _env("VMARS_DB_PASSWORD", ""),
    "host": _env("VMARS_DB_HOST", "localhost"),
    "port": _env("VMARS_DB_PORT", "5432"),
}
DB_HISTORY_PAGE_SIZE = 100

# ─────────────────────────────────────────────────────────────────────────────
# Serial ports & I2C
# ─────────────────────────────────────────────────────────────────────────────
ESP32_PORT = _env("VMARS_ESP32_PORT", "/dev/ttyS2")
ESP32_BAUDRATE = 115200

JRT_S1_PORT = _env("VMARS_JRT_S1_PORT", "/dev/ttyUSB0")
JRT_S2_PORT = _env("VMARS_JRT_S2_PORT", "/dev/ttyUSB1")
JRT_BAUDRATE = 19200

I2C_BUS = 1
MPU6050_ADDRESS = 0x68
SHT31_ADDRESS = 0x44

# ─────────────────────────────────────────────────────────────────────────────
# Stepper geometry (pitch, yaw and roll share the same drive ratio)
# ─────────────────────────────────────────────────────────────────────────────
STEPS_PER_REV = 2832.0
STEPS_PER_DEGREE = STEPS_PER_REV / 360.0

ROLL_SPEED_TUMBLING = 600.0       # steps/s while tumbling
ROLL_SPEED_CORRECTION = 150.0     # steps/s (+right / -left) during a feedback hold

# ─────────────────────────────────────────────────────────────────────────────
# Timing
# ─────────────────────────────────────────────────────────────────────────────
CONTROL_PERIOD_MS = 100           # motion state machine tick
UI_PERIOD_MS = 1000               # countdown / graph / drying tick
GRAPH_WINDOW_POINTS = 60          # samples kept on the live plots
NUDGE_ROLL_DURATION_MS = 500      # how long a roll nudge runs

# ─────────────────────────────────────────────────────────────────────────────
# AUTO mode sequence (seconds)
# ─────────────────────────────────────────────────────────────────────────────
AUTO_INITIAL_PHASE_S = 40.0       # free tumbling before the first measurement
AUTO_ROLL_STOP_S = 32.0           # roll + yaw stop here inside the initial phase
AUTO_SENSOR_PRERESET_S = 38.0     # clear stale readings just before 1st cycle
AUTO_CYCLE_S = 60.0               # measure → correct → continue
AUTO_MEASURE_WINDOW_S = 5.0       # "UKUR" phase length
AUTO_MEASURE_SETTLE_S = 1.0       # laser readings ignored for the first second
AUTO_CYCLE_RESET_S = 0.5          # readings cleared in the first 0.5 s of a cycle
AUTO_TUMBLE_RATE_DEG_S = 22.5     # pitch/yaw rate during the initial phase
AUTO_BASE_PITCH_DEG = 900.0       # pitch at the first measurement (≡ 180°)
AUTO_YAW_BASE_DEG = 720.0         # yaw after the initial phase (non-I shapes)
AUTO_IMU_ANGLE_TOLERANCE_DEG = 10.0
AUTO_IMU_STABLE_WINDOW_S = (1.0, 3.0)

# ─────────────────────────────────────────────────────────────────────────────
# MANUAL mode sequence
# ─────────────────────────────────────────────────────────────────────────────
MANUAL_CYCLE_S = 8.0
MANUAL_TUMBLE_RATE_DEG_S = 45.0
MANUAL_STAY_DURATION_S = 30.0
MANUAL_IMU_ANGLE_TOLERANCE_DEG = 5.0

# ─────────────────────────────────────────────────────────────────────────────
# Shapes
# ─────────────────────────────────────────────────────────────────────────────
SHAPES = ("I", "T", "Y", "3D")
SHAPE_BRANCH_COUNT = {"I": 1, "T": 2, "Y": 2, "3D": 3}
SHAPE_IMAGES = {
    "I": "I-hmi.png",
    "T": "T-hmi.png",
    "Y": "Y-hmi.png",
    "3D": "3D-hmi.png",
}
LOGO_IMAGE = "logov-removebg-preview.png"

# Pitch angles (mod 360) at which the IMU is sampled.
CRUCIAL_ANGLES = {
    "I": (0, 180),
    "T": (45, 135, 180),
    "Y": (0, 45, 135, 180),
    "3D": (0, 90, 180, 270),
}

# ─────────────────────────────────────────────────────────────────────────────
# Sensors
# ─────────────────────────────────────────────────────────────────────────────
IMU_PITCH_OFFSET_DEG = -173.0     # mounting offset of the MPU-6050
IMU_AUTO_ZERO_ON_START = False    # see docs/REFACTORING_NOTES.md
IMU_POLL_S = 0.05
IMU_LOG_EVERY_N = 10

TEMP_POLL_S = 0.5
TEMP_WARNING_C = 24.0
TEMP_CRITICAL_C = 20.0

JRT_SHOT_INTERVAL_S = 10.0        # one single-shot per sensor per interval
JRT_REPLY_TIMEOUT_S = 2.0
JRT_VALID_MAX_MM = 1000           # readings must be 0 < d < this
JRT_PLAUSIBLE_MAX_MM = 100_000    # anything beyond 100 m is a glitch
JRT_S1_START_DELAY_S = 1.0        # staggered first shot
JRT_S2_START_DELAY_S = 2.0
