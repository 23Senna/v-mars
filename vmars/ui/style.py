"""Colour palette and Qt style sheets."""

RED = "#CE1116"
RED_DARK = "#8a0b0e"
ORANGE = "#F15A24"
GREEN = "#67C23A"
GREY = "#909399"
INK = "#1A1A1A"
PAPER = "#f5f5f5"
WHITE = "#ffffff"
BLUSH = "#fceceb"
BORDER = "#dcdfe6"
CANVAS_BG = "#f8f9fa"

APP_STYLE = f"""
QMainWindow {{ background-color: {PAPER}; color: {INK}; }}
QLabel {{ color: {INK}; font-size: 14px; }}
QGroupBox {{ background-color: white; border: 2px solid {RED}; border-radius: 6px;
            margin-top: 15px; font-weight: bold; color: {RED}; font-size: 14px; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top center;
                   padding: 0 10px; background-color: {PAPER}; color: {RED}; }}
QLineEdit {{ border: 2px solid {ORANGE}; border-radius: 4px; padding: 5px;
            color: {INK}; background-color: white; font-size: 14px; }}
QPushButton {{ background-color: {WHITE}; border: 2px solid {RED}; border-radius: 6px;
              padding: 8px; font-weight: bold; color: {RED}; font-size: 14px; }}
QPushButton:hover {{ background-color: {BLUSH}; }}
#infoBox {{ background-color: {WHITE}; border: 2px solid {ORANGE}; border-radius: 6px; padding: 5px 10px; }}
#mainCard {{ background-color: {WHITE}; border-radius: 10px; border: 3px solid {RED}; }}
#menuTitle {{ color: {RED}; font-size: 26px; font-weight: 900; letter-spacing: 1px; }}
#menuSub {{ color: {ORANGE}; font-size: 16px; font-weight: bold; margin-bottom: 10px; }}
#footerText {{ color: {GREY}; font-size: 12px; font-weight: bold; margin-top: 10px; }}
#btnMenu {{ background-color: {RED}; color: white; border: none; font-size: 20px;
           min-height: 45px; border-radius: 8px; }}
#btnMenu:hover {{ background-color: {ORANGE}; }}
#btnStart {{ background-color: {GREEN}; color: white; border: none; min-height: 45px; font-size: 18px; }}
#btnStop  {{ background-color: {RED}; color: white; border: none; min-height: 40px; font-size: 16px; }}
#btnReset {{ background-color: {GREY}; color: white; border: none; min-height: 40px; font-size: 16px; }}
#btnShape:checked {{ background-color: {RED}; color: white; border: 2px solid {RED_DARK}; }}
#btnMode:checked {{ background-color: {RED}; color: white; border: 2px solid {RED_DARK}; }}
QTableWidget {{ border: 2px solid {ORANGE}; font-size: 12px; color: {INK}; background-color: white; }}
QHeaderView::section {{ background-color: {BLUSH}; padding: 4px; border: 1px solid {ORANGE};
                        font-weight: bold; color: {RED}; font-size: 12px; }}
QMessageBox {{ background-color: white; font-size: 14px; }}
QMessageBox QPushButton {{ min-width: 80px; padding: 5px; }}
"""

NUMPAD_STYLE = f"""
QDialog {{ background-color: {PAPER}; }}
QPushButton {{ background-color: white; border: 2px solid {RED}; border-radius: 6px; padding: 15px;
              font-weight: bold; color: {RED}; font-size: 18px; }}
QPushButton:hover {{ background-color: {BLUSH}; }}
QLineEdit {{ border: 2px solid {ORANGE}; border-radius: 4px; padding: 10px; font-size: 20px;
            font-weight: bold; color: {INK}; background-color: white; }}
"""

CORRECTION_DIALOG_STYLE = f"""
QDialog {{ background-color: {PAPER}; }}
QPushButton {{ background-color: white; border: 2px solid {RED}; border-radius: 6px; padding: 10px;
              font-weight: bold; color: {RED}; font-size: 14px; }}
QPushButton:hover {{ background-color: {BLUSH}; }}
QLabel {{ font-weight: bold; font-size: 14px; color: {RED}; }}
"""

CALIBRATION_DIALOG_STYLE = f"""
QDialog {{ background-color: {PAPER}; }}
QPushButton {{ background-color: white; border: 2px solid {RED}; border-radius: 6px; padding: 10px;
              font-weight: bold; color: {RED}; font-size: 14px; }}
QPushButton:hover {{ background-color: {BLUSH}; }}
QLabel {{ font-weight: bold; font-size: 16px; color: {INK}; }}
"""

OK_BUTTON_STYLE = f"background-color: {GREEN}; color: white; border: none;"

MANUAL_GROUP_STYLE = f"""
QGroupBox {{ background-color: {BLUSH}; border: 2px solid {ORANGE}; border-radius: 6px; margin-top: 18px;
            padding-top: 15px; font-weight: bold; color: {RED}; font-size: 14px; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top center; padding: 0 10px;
                   background-color: transparent; }}
"""

NUDGE_BUTTON_STYLE = (
    f"background-color: white; border: 2px solid {RED}; border-radius: 4px; padding: 5px; "
    f"min-width: 155px; font-weight: bold; color: {RED}; font-size: 12px;"
)

# Preset button size per shape (tuned for the 5" Waveshare panel).
PRESET_BUTTON_SIZE = {
    "I": ("120px", "55px"),
    "T": ("20px", "10px"),
    "Y": ("20px", "10px"),
    "3D": ("100px", "50px"),
}


def preset_button_style(width: str, height: str) -> str:
    return (
        f"min-width: {width}; min-height: {height}; font-size: 13px; font-weight: bold; "
        f"background-color: {WHITE}; color: {RED}; border: 2px solid {RED}; border-radius: 4px;"
    )


def big_value(color: str, size: int = 16) -> str:
    return f"font-size: {size}px; font-weight: bold; color: {color};"
