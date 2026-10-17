# Assets

Images loaded by the HMI. Put these files in this folder:

| File | Used for |
|------|----------|
| `logov-removebg-preview.png` | logo on the main menu |
| `I-hmi.png` | I-shape stick picture |
| `T-hmi.png` | T-shape stick picture |
| `Y-hmi.png` | Y-shape stick picture |
| `3D-hmi.png` | 3D-shape stick picture |

Names are configured in `vmars/config.py` (`LOGO_IMAGE`, `SHAPE_IMAGES`).
Missing images do not break the HMI — the canvas shows "Gambar tidak ditemukan".
