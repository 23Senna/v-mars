"""PostgreSQL process log.

All queries run on one background thread fed by a queue, so a slow or
unreachable database never freezes the touchscreen. Results come back to the
GUI thread through a Qt signal.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import astuple, dataclass

import psycopg2
from PyQt5.QtCore import QObject, pyqtSignal

from vmars import config

log = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS history_log (
    id               SERIAL PRIMARY KEY,
    waktu            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    bentuk_stick     VARCHAR(10),
    ketebalan_1      FLOAT,
    ketebalan_2      FLOAT,
    ketebalan_3      FLOAT,
    suhu_akhir       FLOAT,
    pitch_sistem     FLOAT,
    response_time    FLOAT,
    mode_operasi     VARCHAR(20) DEFAULT 'AUTO',
    target_ketebalan FLOAT DEFAULT 0,
    target_waktu     FLOAT DEFAULT 0
)
"""

# Upgrades databases created by older HMI versions.
_MIGRATIONS = (
    "ALTER TABLE history_log ADD COLUMN IF NOT EXISTS pitch_sistem FLOAT DEFAULT 0",
    "ALTER TABLE history_log ADD COLUMN IF NOT EXISTS response_time FLOAT DEFAULT 0",
    "ALTER TABLE history_log ADD COLUMN IF NOT EXISTS mode_operasi VARCHAR(20) DEFAULT 'AUTO'",
    "ALTER TABLE history_log ADD COLUMN IF NOT EXISTS target_ketebalan FLOAT DEFAULT 0",
    "ALTER TABLE history_log ADD COLUMN IF NOT EXISTS target_waktu FLOAT DEFAULT 0",
)

_INSERT = (
    "INSERT INTO history_log (bentuk_stick, mode_operasi, target_ketebalan, target_waktu, "
    "ketebalan_1, ketebalan_2, ketebalan_3, suhu_akhir, pitch_sistem, response_time) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

_SELECT_RECENT = (
    "SELECT TO_CHAR(waktu, 'HH24:MI:SS'), bentuk_stick, mode_operasi, target_ketebalan, "
    "target_waktu, ketebalan_1, ketebalan_2, ketebalan_3, pitch_sistem, suhu_akhir, response_time "
    "FROM history_log ORDER BY id DESC LIMIT %s"
)

HISTORY_COLUMNS = (
    "Waktu", "Bentuk", "Mode", "Tgt Tebal (mm)", "Tgt Waktu (s)",
    "Tebal S1", "Tebal S2", "Tebal S3", "Pitch Sistem", "Suhu (°C)", "Response Time (ms)",
)


@dataclass(frozen=True)
class ProcessRecord:
    shape: str
    mode: str
    target_thickness_mm: float
    target_time_s: float
    thickness_1: float
    thickness_2: float
    thickness_3: float
    final_temperature_c: float
    pitch_deg: float
    response_time_ms: float


class HistoryRepository(QObject):
    history_loaded = pyqtSignal(list)

    _STOP = object()

    def __init__(self, db_config: dict | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._db_config = db_config or config.DB_CONFIG
        self._tasks: queue.Queue = queue.Queue(maxsize=50)
        self._thread: threading.Thread | None = None

    # ── lifecycle ────────────────────────────────────────────────────────────
    def initialise(self) -> bool:
        """Create/upgrade the table. Returns True if the database is reachable."""
        try:
            with psycopg2.connect(**self._db_config) as conn, conn.cursor() as cur:
                cur.execute(_CREATE_TABLE)
                for statement in _MIGRATIONS:
                    cur.execute(statement)
            conn.close()
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("Database unavailable: %s", exc)
            return False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._worker, name="db-worker", daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        try:
            self._tasks.put_nowait(self._STOP)
        except queue.Full:
            pass

    # ── public API (non-blocking) ────────────────────────────────────────────
    def save(self, record: ProcessRecord) -> None:
        self._enqueue(("save", astuple(record)))

    def request_history(self, limit: int) -> None:
        self._enqueue(("load", int(limit)))

    def _enqueue(self, task) -> None:
        try:
            self._tasks.put_nowait(task)
        except queue.Full:
            log.warning("Database queue full, dropping %s", task[0])

    # ── worker thread ────────────────────────────────────────────────────────
    def _worker(self) -> None:
        conn = None
        while True:
            try:
                task = self._tasks.get(timeout=2.0)
            except queue.Empty:
                conn = self._check_alive(conn)
                continue
            if task is self._STOP:
                break

            if conn is None:
                try:
                    conn = psycopg2.connect(**self._db_config)
                except Exception as exc:  # noqa: BLE001
                    log.error("Database connect failed: %s", exc)
                    continue

            action, payload = task
            try:
                with conn.cursor() as cur:
                    if action == "save":
                        cur.execute(_INSERT, payload)
                        conn.commit()
                    elif action == "load":
                        cur.execute(_SELECT_RECENT, (payload,))
                        rows = cur.fetchall()
                        conn.commit()
                        self.history_loaded.emit(rows)
            except Exception as exc:  # noqa: BLE001
                log.error("Database %s failed: %s", action, exc)
                conn = self._close(conn)

        self._close(conn)

    @staticmethod
    def _check_alive(conn):
        if conn is None:
            return None
        try:
            conn.poll()
            return conn
        except Exception:  # noqa: BLE001
            return HistoryRepository._close(conn)

    @staticmethod
    def _close(conn):
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        return None
