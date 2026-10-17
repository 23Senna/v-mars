"""I2C bus access with a graceful fallback when no bus library is installed."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

try:  # Debian/Armbian package: sudo apt install python3-smbus
    from smbus import SMBus  # type: ignore[import-not-found]
except ImportError:
    try:  # pure-python alternative: pip install smbus2
        from smbus2 import SMBus  # type: ignore[import-not-found,no-redef]
    except ImportError:
        SMBus = None  # type: ignore[assignment,misc]

SMBUS_AVAILABLE = SMBus is not None


def open_bus(bus_num: int):
    """Return an ``SMBus`` handle, or raise ``RuntimeError`` if unavailable."""
    if SMBus is None:
        raise RuntimeError(
            "No I2C library found. Install it with "
            "'sudo apt install python3-smbus' or 'pip install smbus2'."
        )
    return SMBus(bus_num)
