# Changelog

## [1.0.0] — 2026-10-17

First structured release; refactor of the single-file `manual v8` HMI.
Details and verification: [`docs/REFACTORING_NOTES.md`](docs/REFACTORING_NOTES.md).

### Changed
- Split into the `vmars` package: `config`, `control` (pure logic), `hardware`,
  `storage`, `ui`.
- Correction branches turned into a data table (`control/sequences.py`).
- Credentials and serial ports read from environment / `.env`.
- `print` replaced by `logging`; `python -m vmars --windowed --debug`.

### Fixed
- T- and Y-shape AUTO runs crashed at the first feedback (`max_val` undefined).
- Feedback tick commanded absolute pitch 0 / yaw 0 for 100 ms every cycle.
- Critical-temperature abort now stops the motors before showing the popup.
- Correction dialog timer leak; lasers left on when calibration was cancelled with Esc.
- Decimal target thickness (e.g. `2.5`) silently blocked START.
- ESP32 link: threads joined, duplicate filter reset per run, stop command flushed.
- Real database status in the menu footer; images load regardless of working directory.

### Added
- Unit tests, off-screen GUI smoke test, GitHub Actions CI.
- Documentation: architecture, process sequence, serial protocol, hardware, database.
- `deploy/` udev rules and autostart entry.
