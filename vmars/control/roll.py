"""Dead-reckoning of the roll axis.

The ESP32 drives roll in *speed* mode and reports no position, so the HMI
integrates the commanded speed to estimate where the stick is. When the
sequence asks roll to stop, the tracker keeps it turning until the estimate
reaches a whole revolution — the stick then always faces the lasers the same
way at the start of every measurement.
"""

from __future__ import annotations


class RollPositionTracker:
    def __init__(self, steps_per_rev: float, finish_speed: float):
        self.steps_per_rev = steps_per_rev
        self.finish_speed = finish_speed
        self.position_steps = 0.0
        self.finishing = False
        self._last_sent_speed = 0.0

    def update(self, requested_speed: float, dt_s: float) -> float:
        """Advance the estimate by one tick and return the speed to send."""
        self.position_steps += self._last_sent_speed * dt_s

        speed = requested_speed
        if speed == 0.0:
            # Tolerance of two ticks gives the motor time to react to the stop.
            tolerance = self.finish_speed * dt_s * 2.0
            remainder = self.position_steps % self.steps_per_rev
            if tolerance < remainder < self.steps_per_rev - tolerance:
                speed = self.finish_speed
                self.finishing = True
            else:
                # Aligned: snap the estimate to avoid float drift.
                revolutions = round(self.position_steps / self.steps_per_rev)
                self.position_steps = revolutions * self.steps_per_rev
                self.finishing = False
        else:
            self.finishing = False

        self._last_sent_speed = speed
        return speed
