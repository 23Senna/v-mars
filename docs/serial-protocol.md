# Serial protocols

## ESP32 motor controller

* Port `/dev/ttyS2` (Orange Pi UART), 115200 baud, 8N1
* Direction: Orange Pi → ESP32, one ASCII line per command

```
<pitch_steps>,<roll_speed>,<yaw_steps>\n
```

| Field         | Type  | Meaning |
|---------------|-------|---------|
| `pitch_steps` | int   | **Absolute** pitch target (AccelStepper `moveTo`) |
| `roll_speed`  | float, 1 decimal | Roll **speed** in steps/s (continuous rotation); sign = direction, `0.0` = stop |
| `yaw_steps`   | int   | **Absolute** yaw target |

Example: `7080,0.0,5664\n` → pitch to 900°, roll stopped, yaw to 720°.

* All axes use 2832 steps per revolution (7.867 steps/°).
* The HMI sends at most one line per 100 ms tick and **skips a line identical
  to the previous one** — re-sending the same target makes AccelStepper
  re-plan its ramp, which shows up as stutter.
* Anything the ESP32 sends back is read and discarded.

Implementation: `vmars/hardware/esp32.py`, formatting in
`vmars/hardware/protocol.py::format_motor_command`.

## JRT laser distance sensors

* S1 `/dev/ttyUSB0`, S2 `/dev/ttyUSB1`, 19200 baud, binary
* Initialisation (per sensor): laser off → DTR/RTS reset pulse → auto-baud
  `0x55` → read voltage → laser on (staggered 0.5 s × sensor index to limit
  inrush current)

| Command                | Bytes |
|------------------------|-------|
| Auto-baud              | `55` |
| Read input voltage     | `AA 80 00 06 86` |
| Laser ON               | `AA 00 01 BE 00 01 00 01 C1` |
| Laser OFF              | `AA 00 01 BE 00 01 00 00 C0` |
| Single shot (auto)     | `AA 00 00 20 00 01 00 00 21` |

### Measurement reply

The HMI waits up to 2 s for the header byte `0xAA`, then reads 12 more bytes:

| Body index | Content |
|-----------:|---------|
| 0–4        | header fields (not used by the HMI) |
| 5–8        | distance, mm, big-endian uint32 |
| 9–10       | signal quality, big-endian uint16 (higher = better) |
| 11         | not used by the HMI |

Readings above 100 m are discarded as glitches; only `0 < d < 1000 mm`
counts as valid. One shot is fired per sensor every 10 s.

* **S1** keeps the highest-quality valid reading since the last reset.
* **S2** runs in *dual mode*: its first valid reading is S2, its second is S3.

Implementation: `vmars/hardware/laser.py`, parsing in
`vmars/hardware/protocol.py::parse_jrt_frame`.
