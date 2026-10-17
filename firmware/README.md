# ESP32 firmware (espmotor)

The ESP32 sketch that drives the pitch, roll and yaw steppers lives here.

> The firmware source is not yet included in this repository. Add the
> `espmotor` sketch to this folder (e.g. `firmware/espmotor/espmotor.ino`).

The only contract between the HMI and the firmware is the serial line
documented in [`docs/serial-protocol.md`](../docs/serial-protocol.md):

```
<pitch_steps>,<roll_speed>,<yaw_steps>\n      115200 baud
```

* `pitch_steps`, `yaw_steps` — absolute targets (2832 steps/rev)
* `roll_speed` — continuous roll speed in steps/s, `0.0` = stop
