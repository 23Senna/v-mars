# Hardware setup

## Bill of materials (control side)

| Part | Role | Interface |
|------|------|-----------|
| Orange Pi 4 Pro | runs the HMI and PostgreSQL | — |
| Waveshare 5" HDMI touch LCD (fixed resolution) | operator panel | HDMI + USB touch |
| ESP32 (firmware "espmotor") | drives pitch, roll, yaw steppers with AccelStepper | UART → `/dev/ttyS2` |
| 3 × stepper motor + drivers | pitch / roll / yaw | ESP32 GPIO |
| MPU-6050 | platform pitch feedback | I2C bus 1, `0x68` |
| SHT31-D | drying-chamber temperature | I2C bus 1, `0x44` |
| 2 × JRT laser distance sensor | hydrogel thickness (S1, S2 + S3) | USB-serial → `/dev/ttyUSB0`, `/dev/ttyUSB1` |

## Orange Pi configuration

1. **Enable I2C bus 1 and the UART used for the ESP32** in the board's overlay
   configuration (e.g. `orangepi-config` / `armbian-config` → *Hardware*), then
   reboot. Check with:
   ```bash
   ls /dev/i2c-1 /dev/ttyS2
   sudo i2cdetect -y 1        # expect 44 and 68
   ```
2. **Give your user access** to serial and I2C devices:
   ```bash
   sudo usermod -aG dialout,i2c $USER   # log out and back in
   ```
3. **Stable serial names (recommended).** `ttyUSB0/1` can swap after a reboot
   or re-plug. Copy `deploy/99-vmars-serial.rules` to `/etc/udev/rules.d/`,
   fill in the serial numbers (`udevadm info -a -n /dev/ttyUSB0 | grep serial`),
   then point `.env` at `/dev/vmars-laser-s1` and `/dev/vmars-laser-s2`.
   The same file disables USB autosuspend for the adapters, which otherwise
   causes random PL2303 disconnects.

## Noise on the I2C line

Stepper switching can couple onto the I2C wires and cause temperature spikes.
Keep I2C wiring short and away from motor cables, add a decoupling capacitor
near the sensor and tune the pull-up resistors if spikes appear.

## Kiosk autostart

Copy `deploy/vmars.desktop` to `~/.config/autostart/` to start the HMI in full
screen after login. Press **F11** to toggle full screen and **Esc** to leave it
(Esc again closes the app).
