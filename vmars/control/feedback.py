"""Thickness computation and the shape-specific feedback decision.

Pure functions — no Qt, no hardware — so the decision table can be unit-tested.
"""

from __future__ import annotations

from typing import Sequence

Thickness = tuple[float, float, float]


def compute_thickness(baseline_mm: Sequence[float], distances_mm: Sequence[float]) -> Thickness:
    """Hydrogel thickness = bare-stick distance − coated distance (never < 0).

    A point without a reading or without a calibration baseline reports 0.
    """
    values = []
    for base, dist in zip(baseline_mm, distances_mm):
        thickness = max(0.0, base - dist) if dist > 0 and base > 0 else 0.0
        values.append(round(thickness, 2))
    return values[0], values[1], values[2]


def has_invalid_point(thickness: Thickness, connected: Sequence[bool]) -> bool:
    """A connected sensor reporting 0 mm means the reading equals the bare
    stick — the measurement must be repeated."""
    return any(is_on and value <= 0.0 for value, is_on in zip(thickness, connected))


def decide_condition(shape: str, thickness: Thickness) -> tuple[str, str]:
    """Pick the corrective pose for the thinnest branch.

    Returns ``(condition_code, human_readable_reason)``. The code selects a
    :data:`vmars.control.sequences.CORRECTION_PROFILES` entry; an empty code
    means "no correction, keep tumbling".
    """
    s1, s2, s3 = thickness
    min_val = min(s1, s2, s3)
    max_val = max(s1, s2, s3)

    if shape == "I":
        if s1 <= s2:
            return "I-A", "S1 thinnest -> stay at 180°"
        return "I-B", "S2 thinnest -> feedback to 0°"

    if shape == "Y":
        if s1 == min_val:
            return "Y-C", "S1 thinnest -> pitch 0°, yaw 90°"
        if (s2 == min_val or s3 == min_val) and s1 == max_val:
            if s2 == min_val:
                return "Y-D-S2", "S2 thinnest & S1 thickest -> pitch 135°, yaw 45°, roll right"
            return "Y-D-S3", "S3 thinnest & S1 thickest -> pitch 135°, yaw -45°, roll left"
        if (s2 == min_val or s3 == min_val) and (s2 == max_val or s3 == max_val):
            if s2 == min_val:
                return "Y-E-S2", "S2 thin & S3 thick -> pitch 45°, yaw 135°"
            return "Y-E-S3", "S3 thin & S2 thick -> pitch 45°, yaw -135°"
        return "", "no matching Y rule -> keep tumbling"

    if shape == "T":
        if s1 == min_val:
            if s2 == max_val:
                return "T-A-S2", "S1 thin (S2 thick) -> pitch 45°, yaw 135°, roll right"
            return "T-A-S3", "S1 thin (S3 thick) -> pitch 45°, yaw -135°, roll left"
        if s2 == min_val:
            return "T-B-S2", "S2 thinnest -> pitch 135°, yaw 45°, roll right"
        return "T-B-S3", "S3 thinnest -> pitch 135°, yaw -45°, roll left"

    if shape == "3D":
        if s1 == min_val:
            return "3D-A", "S1 thinnest -> pitch 0°, yaw 0°"
        if s2 == min_val:
            return "3D-B", "S2 thinnest -> pitch 90°, yaw 90°, roll right"
        return "3D-C", "S3 thinnest -> pitch 90°, yaw -90°, roll left"

    return "", f"unknown shape {shape!r}"
