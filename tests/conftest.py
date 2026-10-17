import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class FakeSensors:
    """In-memory stand-in for :class:`vmars.hardware.laser.LaserSensorArray`.

    Readings become valid ``valid_after_ms`` after the last reset.
    """

    def __init__(self, clock, distances=(98.0, 117.0, 136.0), valid_after_ms=2000.0,
                 connected=(True, True, True)):
        self.clock = clock
        self.distances = distances
        self.valid_after_ms = valid_after_ms
        self._connected = connected
        self.last_reset = clock.now
        self.resets = 0
        self.window_events = []

    def set_measurement_window(self, active):
        self.window_events.append((self.clock.now, active))

    def reset(self):
        self.resets += 1
        self.last_reset = self.clock.now

    def all_valid(self):
        return self.clock.now - self.last_reset >= self.valid_after_ms

    def best_distances(self):
        return self.distances

    def connected(self):
        return self._connected

    def last_valid_finish_time(self):
        return 0.0


class Clock:
    def __init__(self, start=0.0):
        self.now = start

    def advance(self, ms=100.0):
        self.now += ms
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def fake_sensors_cls():
    return FakeSensors
