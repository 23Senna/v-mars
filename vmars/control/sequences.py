"""Motion recipes as data instead of copy-pasted if/elif branches.

Angles are *relative* to the cycle's base pose. The AUTO base pitch is
900° + n·360°, i.e. physically 180°, so a pitch offset of +180° ends at 0°,
+225° at 45°, +270° at 90° and +315° at 135°.
"""

from __future__ import annotations

from dataclasses import dataclass

from vmars import config


@dataclass(frozen=True)
class CorrectionProfile:
    """What the platform does in an AUTO cycle after the measurement.

    Timeline (``t`` = seconds since the cycle started)::

        t < travel_until   → move to the corrective pose, roll tumbling  ("KE …")
        t < hold_until     → hold the pose (gravity flows to thin branch) ("SET …")
        afterwards         → +360° pitch, yaw back to base, resume tumbling ("LANJUT")
    """

    pitch_offset_deg: float
    yaw_offset_deg: float
    travel_until_s: float
    hold_until_s: float
    travel_label: str
    hold_label: str
    hold_roll_speed: float = 0.0


R = config.ROLL_SPEED_CORRECTION

CORRECTION_PROFILES: dict[str, CorrectionProfile] = {
    # I-shape
    "I-A": CorrectionProfile(0.0, 0.0, 0.0, 39.0, "", "TAHAN"),
    "I-B": CorrectionProfile(180.0, 0.0, 13.0, 47.0, "KE 0°", "SET 0°"),
    # Y-shape
    "Y-C": CorrectionProfile(180.0, 90.0, 13.0, 47.0, "KE 0°", "SET 0°"),
    "Y-D-S2": CorrectionProfile(315.0, 45.0, 19.0, 53.0, "KE 135°", "SET 135°", +R),
    "Y-D-S3": CorrectionProfile(315.0, -45.0, 19.0, 53.0, "KE 135°", "SET 135°", -R),
    "Y-E-S2": CorrectionProfile(225.0, 135.0, 15.0, 49.0, "KE 45°", "SET 45°"),
    "Y-E-S3": CorrectionProfile(225.0, -135.0, 15.0, 49.0, "KE 45°", "SET 45°"),
    # T-shape
    "T-A-S2": CorrectionProfile(225.0, 135.0, 15.0, 49.0, "KE 45°", "SET 45°", +R),
    "T-A-S3": CorrectionProfile(225.0, -135.0, 15.0, 49.0, "KE 45°", "SET 45°", -R),
    "T-B-S2": CorrectionProfile(315.0, 45.0, 19.0, 53.0, "KE 135°", "SET 135°", +R),
    "T-B-S3": CorrectionProfile(315.0, -45.0, 19.0, 53.0, "KE 135°", "SET 135°", -R),
    # 3D-shape
    "3D-A": CorrectionProfile(180.0, 0.0, 13.0, 47.0, "KE 0°", "SET 0°"),
    "3D-B": CorrectionProfile(270.0, 90.0, 17.0, 51.0, "KE 90°", "SET 90°", +R),
    "3D-C": CorrectionProfile(270.0, -90.0, 17.0, 51.0, "KE 90°", "SET 90°", -R),
}


@dataclass(frozen=True)
class ManualPreset:
    """A MANUAL-mode button: wait for ``cycle_time_s`` in the tumbling cycle,
    then hold pitch/yaw for 30 s while rolling at ``roll_speed``."""

    label: str
    cycle_time_s: float
    pitch_deg: float
    yaw_deg: float
    roll_speed: float = 0.0


MANUAL_PRESETS: dict[str, tuple[ManualPreset, ...]] = {
    "I": (
        ManualPreset("GO 0°", 0.0, 0, 0),
        ManualPreset("STAY 180°", 8.0, 180, 0),
    ),
    "Y": (
        ManualPreset("P:0 Y:90", 0.0, 0, 90),
        ManualPreset("P:135 Y:45 R", 6.0, 135, 45, +R),
        ManualPreset("P:135 Y:-45 L", 6.0, 135, -45, -R),
        ManualPreset("P:45 Y:135", 2.0, 45, 135),
        ManualPreset("P:45 Y:-135", 2.0, 45, -135),
    ),
    "T": (
        ManualPreset("P:45 Y:135 R", 2.0, 45, 135, +R),
        ManualPreset("P:45 Y:-135 L", 2.0, 45, -135, -R),
        ManualPreset("P:135 Y:45 R", 6.0, 135, 45, +R),
        ManualPreset("P:135 Y:-45 L", 6.0, 135, -45, -R),
    ),
    "3D": (
        ManualPreset("P:0 Y:0", 0.0, 0, 0),
        ManualPreset("P:90 Y:90 R", 4.0, 90, 90, +R),
        ManualPreset("P:90 Y:-90 L", 4.0, 90, -90, -R),
    ),
}
