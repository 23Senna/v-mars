"""Process history table with search, sorting and paging."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from vmars.storage.database import HISTORY_COLUMNS
from vmars.ui import style
from vmars.ui.widgets import NumericTableWidgetItem


class DatabaseScreen(QWidget):
    load_more_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    back_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 60)

        group = QGroupBox("RIWAYAT DATABASE")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self.count_label = QLabel("Total Data: -")
        self.count_label.setStyleSheet(style.big_value(style.INK, 14))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Cari data (waktu, bentuk, dll)...")
        self.search_input.setMinimumWidth(250)
        self.search_input.textChanged.connect(self._apply_filter)
        load_more = QPushButton("LOAD MORE")
        load_more.clicked.connect(self.load_more_requested.emit)
        refresh = QPushButton("REFRESH")
        refresh.clicked.connect(self.refresh_requested.emit)

        toolbar.addWidget(self.count_label)
        toolbar.addStretch()
        toolbar.addWidget(self.search_input)
        toolbar.addWidget(load_more)
        toolbar.addWidget(refresh)
        group_layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(len(HISTORY_COLUMNS))
        self.table.setHorizontalHeaderLabels(HISTORY_COLUMNS)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)  # allows horizontal scrolling
        header.setDefaultSectionSize(130)
        header.setMinimumSectionSize(100)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        group_layout.addWidget(self.table)
        layout.addWidget(group)

        back = QPushButton("MAIN MENU")
        back.clicked.connect(self.back_requested.emit)
        layout.addWidget(back)

    def show_rows(self, rows: list) -> None:
        self.table.setSortingEnabled(False)  # sorting while filling scrambles rows
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                if isinstance(value, float):
                    text = f"{value:.2f}"
                else:
                    text = "-" if value is None else str(value)
                item = NumericTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)
        self.count_label.setText(f"Total Data: {len(rows)}")
        self._apply_filter(self.search_input.text())

    def _apply_filter(self, text: str) -> None:
        needle = text.lower()
        for r in range(self.table.rowCount()):
            match = any(
                (item := self.table.item(r, c)) is not None and needle in item.text().lower()
                for c in range(self.table.columnCount())
            )
            self.table.setRowHidden(r, not match)
