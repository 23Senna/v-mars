"""Landing screen with the three navigation buttons."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from vmars import config
from vmars.ui.widgets import asset_pixmap


class MainMenuScreen(QWidget):
    open_input = pyqtSignal()
    open_monitoring = pyqtSignal()
    open_database = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 35)  # keep clear of the panel's bottom edge
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("mainCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(10)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        pixmap = asset_pixmap(config.LOGO_IMAGE)
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        card_layout.addWidget(logo)

        title = QLabel("V-MARS")
        title.setObjectName("menuTitle")
        subtitle = QLabel("Vascular – Multi Axis Rotation System")
        subtitle.setObjectName("menuSub")
        for label in (title, subtitle):
            label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(label)
        card_layout.addSpacing(15)

        for text, signal in (
            ("MENU INPUT PARAMETER", self.open_input),
            ("MENU DATA MONITORING", self.open_monitoring),
            ("MENU DATABASE", self.open_database),
        ):
            button = QPushButton(text)
            button.setObjectName("btnMenu")
            button.clicked.connect(signal.emit)
            card_layout.addWidget(button)
        card_layout.addStretch()

        self.footer = QLabel()
        self.footer.setObjectName("footerText")
        self.footer.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.footer)
        self.set_database_status(True)

        layout.addWidget(card)

    def set_database_status(self, connected: bool) -> None:
        db = "CONNECTED" if connected else "OFFLINE"
        self.footer.setText(f"STATUS: READY | DB: {db}")
