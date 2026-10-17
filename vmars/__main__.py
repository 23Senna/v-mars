"""Entry point: ``python -m vmars`` (or the ``vmars`` console script)."""

from __future__ import annotations

import argparse
import logging
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="vmars", description="V-MARS touchscreen HMI")
    parser.add_argument("--windowed", action="store_true", help="start in a window instead of full screen")
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="[%(asctime)s] %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Imported late so --help works without a display.
    from PyQt5.QtWidgets import QApplication

    from vmars.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    if args.windowed:
        window.resize(1024, 600)
        window.show()
    else:
        window.showFullScreen()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
