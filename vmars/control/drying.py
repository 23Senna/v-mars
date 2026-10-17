"""Drying-environment supervision (temperature state machine).

    NORMAL ──T < 24 °C──▶ WARNING ──T < 20 °C──▶ INTERVENTION (abort)
       ▲                     │
       └─────T ≥ 24 °C───────┘
    NORMAL ──T < 20 °C──▶ INTERVENTION (abort)
"""

from __future__ import annotations

from enum import Enum

from vmars import config


class DryingState(str, Enum):
    WAIT_START = "WAIT_START"
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    PAUSED = "PAUSED"
    INTERVENTION = "INTERVENTION"
    FINISHED = "FINISHED"


class DryingAction(str, Enum):
    NONE = "NONE"
    SHOW_WARNING = "SHOW_WARNING"
    CLEAR_WARNING = "CLEAR_WARNING"
    ABORT = "ABORT"


class DryingMonitor:
    def __init__(
        self,
        warning_c: float = config.TEMP_WARNING_C,
        critical_c: float = config.TEMP_CRITICAL_C,
    ):
        self.warning_c = warning_c
        self.critical_c = critical_c
        self.state = DryingState.WAIT_START

    def start(self) -> None:
        self.state = DryingState.NORMAL

    def pause(self) -> None:
        self.state = DryingState.PAUSED

    def resume(self) -> None:
        self.state = DryingState.NORMAL

    def finish(self) -> None:
        self.state = DryingState.FINISHED

    def reset(self) -> None:
        self.state = DryingState.WAIT_START

    def update(self, temperature_c: float) -> DryingAction:
        """Feed one temperature sample, get back what the UI should do."""
        if self.state == DryingState.NORMAL:
            if temperature_c < self.critical_c:
                self.state = DryingState.INTERVENTION
                return DryingAction.ABORT
            if temperature_c < self.warning_c:
                self.state = DryingState.WARNING
                return DryingAction.SHOW_WARNING

        elif self.state == DryingState.WARNING:
            if temperature_c >= self.warning_c:
                self.state = DryingState.NORMAL
                return DryingAction.CLEAR_WARNING
            if temperature_c < self.critical_c:
                self.state = DryingState.INTERVENTION
                return DryingAction.ABORT

        return DryingAction.NONE
