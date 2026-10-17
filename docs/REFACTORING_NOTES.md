# Refactoring notes (v8 monolith → v1.0.0 package)

The HMI used to be a single 1,500-line script (`manual v8`). This document
records what moved where, which bugs were fixed on the way, which quirks were
**kept on purpose**, and how the result was verified.

## 1. Where things went

| Old (single file)                                   | New                                        |
|-----------------------------------------------------|--------------------------------------------|
| `DB_CONFIG`, magic numbers scattered in methods     | `vmars/config.py` (+ `.env`)               |
| `ESP32Manager`                                      | `vmars/hardware/esp32.py` → `Esp32MotorLink` |
| `DirectIMUManager`                                  | `vmars/hardware/imu.py` → `Mpu6050Imu`     |
| `DirectTempManager`                                 | `vmars/hardware/temperature.py` → `Sht31TemperatureSensor` |
| `SensorWorker`, `SensorManager`                     | `vmars/hardware/laser.py` → `LaserSensorWorker`, `LaserSensorArray` |
| byte arrays / bit maths inline                      | `vmars/hardware/protocol.py` (pure, tested) |
| `_run_auto_mode` (~300 lines of `if/elif`)          | `vmars/control/auto_controller.py` + data table in `control/sequences.py` |
| `_run_manual_mode`                                  | `vmars/control/manual_controller.py`       |
| roll "snap to 360°" block                           | `vmars/control/roll.py` → `RollPositionTracker` |
| `_calculate_feedback_advanced`                      | `vmars/control/feedback.py` (pure functions) |
| drying FSM inside `update_ui_tick`                  | `vmars/control/drying.py` → `DryingMonitor` |
| `init_db`, `_db_worker_run`, `save_to_db`           | `vmars/storage/database.py` → `HistoryRepository` |
| `setup_*_screen` methods                            | `vmars/ui/screens/*.py`                    |
| `NumpadDialog`, `ClickableLineEdit`, `StickCanvas`  | `vmars/ui/widgets.py`                      |
| `CorrectionDialog`, `CalibrationDialog`             | `vmars/ui/dialogs.py`                      |
| `HMIApp`                                            | `vmars/ui/main_window.py` → `MainWindow` (wiring only) |

The key design change: **motion logic no longer touches Qt or hardware.**
`AutoController.update(now_ms)` returns a `TickResult` (motor command, status
text, IMU on/off, "open correction dialog", feedback result). The window only
forwards those to the devices. This is what makes the sequence testable.

The eleven copy-pasted correction branches (`I-A` … `3D-C`) became one
`CorrectionProfile` table plus a single generic function.

## 2. Bugs fixed (behaviour changes)

| # | Problem in v8 | Effect | Fix |
|---|---------------|--------|-----|
| 1 | `max_val` used but never defined in the **T** and **Y** feedback rules | `NameError` at the first feedback of every T/Y AUTO run. PyQt5 ≥ 5.5 aborts the application on an unhandled exception in a slot | `max_val = max(s1, s2, s3)` (`feedback.decide_condition`) |
| 2 | On the tick that evaluates the measurement, `target_angle_deg`/`target_yaw_deg` were never assigned and stayed at `0.0` | Once per cycle the ESP32 was told to go to **absolute pitch 0 / yaw 0** (≈ 900°+ back) for 100 ms before the next target arrived → visible jerk, lost settling time | Hold the measuring pose on that tick |
| 3 | Critical-temperature popup was modal and shown **before** `stop_process()` | Motors kept running until the operator pressed OK | Stop first, then show the popup |
| 4 | Closed `CorrectionDialog`s were only hidden; their 500 ms timer kept calling `accept()` | A stale dialog could clear `is_correcting` while a newer correction was active | Timer stopped in `done()`, dialog deleted on close |
| 5 | `CalibrationDialog` stopped the lasers only in `closeEvent` | Closing with **Esc** left the lasers on | Cleanup in `done()` (all exit paths) |
| 6 | Target thickness parsed with `int()` | Typing `2.5` made START silently do nothing | Parsed as float; a warning is shown for invalid input |
| 7 | Warning popup reference kept after the operator dismissed it | Next warning could be suppressed | Reference cleared on `finished` |
| 8 | ESP32: duplicate-command filter survived between runs; TX/RX threads were never joined; the final stop command relied on `sleep(0.1)` | First command of a run could be dropped; a fast restart could leave two TX threads on one port | Filter reset on start, threads joined, pending commands flushed on stop |
| 9 | Footer always showed `DB: CONNECTED` | Misleading | Shows the real result of the start-up connection |
| 10 | Images loaded relative to the current directory | Missing pictures when started from another folder (e.g. autostart) | Loaded from `vmars/assets/` |
| 11 | `last_response_time_ms` never reset | A MANUAL run's DB row could contain the previous AUTO run's response time | Reset at start |
| 12 | Database password hard-coded in the source | Credential leak once the code is shared | Read from environment / `.env` (git-ignored) |
| 13 | `LIMIT {limit}` built with an f-string | Bad habit (SQL injection pattern) | Parameterised query |

## 3. Quirks kept on purpose

These look odd but were **not** changed, because changing them alters how the
machine behaves in the lab. They are now explicit and configurable.

* **IMU zero offset.** v8 called `set_zero_offset()` *before* opening the I2C
  bus, so it never did anything; the fixed `-173°` mounting offset is what has
  always been used. It is now `IMU_PITCH_OFFSET_DEG`, and
  `IMU_AUTO_ZERO_ON_START = True` enables a real zeroing if wanted.
* **S2 dual mode vs. shot interval.** S2 must deliver two valid shots (S2 and
  S3) but fires only every `JRT_SHOT_INTERVAL_S = 10 s`, while the UKUR window
  is 5 s. With S2 connected, the window therefore normally times out and the
  correction dialog opens, closing itself when the second shot arrives. If
  that is not what you see on the machine, check this first.
* **No temperature sensor ⇒ abort.** If the SHT31-D is not detected the
  reading stays `0 °C`, which the drying monitor treats as critical and aborts
  after one second. This is a safe default.
* **Target thickness is informational.** It is shown and logged, but the run
  ends on time, not on thickness.
* **Roll position is dead-reckoned.** Roll nudges during a correction are not
  integrated into the estimate (the ESP32 reports no roll position).

## 4. Dead code removed

`skip_count`, `last_cycle_count`, `machine_state`, `has_measured_s1/2/3`,
`measure_done_time_ms`, `reset_system()`, `get_best_latencies()`,
`get_latest_distances()`, the unused `random` import and a few attributes that
were written but never read.

## 5. How the refactor was verified

1. **Tick-by-tick equivalence.** The v8 `HMIApp` and the new controllers were
   driven by the same simulated clock (100 ms ticks, with and without ±15 ms
   jitter), the same scripted laser readings (fast, slow → correction dialog,
   invalid 0 mm reading, disconnected S2, tied thicknesses), pauses and operator
   nudges, for all four shapes in AUTO and MANUAL mode (28 scenarios,
   ~94,000 ticks). Every motor command, status text, IMU flag, sensor
   reset/window call and selected condition was compared.
   * Against v8 **with only fixes 1 and 2 applied: identical** in every scenario.
   * Against untouched v8: T and Y crash (fix 1); for I and 3D the motor
     commands differ on exactly one tick per cycle — the feedback tick (fix 2).
2. **Screens.** All four screens and the MANUAL panel were rendered off-screen
   at 800×480 for both versions and compared pixel by pixel: identical except
   the database footer text (fix 9).
3. **Unit tests** in `tests/` cover the protocol helpers, feedback rules,
   drying FSM, roll tracker, both controllers and an off-screen GUI smoke test.
