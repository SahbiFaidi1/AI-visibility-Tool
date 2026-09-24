"""SQLite persistence. One `runs` row per tracking run, one `answers` row per prompt x provider x repeat."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  brand TEXT NOT NULL,
  config_json TEXT NOT NULL,
  notes TEXT
);
CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  provider_id TEXT NOT NULL,
  provider_label TEXT NOT NULL,
  model TEXT,
  prompt_id TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  category TEXT NOT NULL,
  repeat_index INTEGER NOT NULL DEFAULT 0,
  text TEXT,
  citations_json TEXT,
  mentions_json TEXT,
  sentiment_json TEXT,
  latency_ms INTEGER,
  error TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_answers_run ON answers(run_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # -- runs -----------------------------------------------------------------
    def create_run(self, brand: str, config_snapshot: dict[str, Any], notes: str | None = None) -> str:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        with self._conn() as c:
            c.execute("INSERT INTO runs (id, started_at, status, brand, config_json, notes) VALUES (?,?,?,?,?,?)",
                      (run_id, now_iso(), "running", brand, json.dumps(config_snapshot), notes))
        return run_id

    def finish_run(self, run_id: str, status: str = "done") -> None:
        with self._conn() as c:
            c.execute("UPDATE runs SET finished_at=?, status=? WHERE id=?", (now_iso(), status, run_id))

    def list_runs(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT r.*, 
                       (SELECT COUNT(*) FROM answers a WHERE a.run_id=r.id) AS n_answers,
                       (SELECT COUNT(*) FROM answers a WHERE a.run_id=r.id AND a.error IS NULL) AS n_ok
                FROM runs r ORDER BY r.started_at DESC""").fetchall()
        return [self._run_row(r) for r in rows]

    def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return self._run_row(r) if r else None

    def latest_run_id(self) -> Optional[str]:
        with self._conn() as c:
            r = c.execute("SELECT id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        return r["id"] if r else None

    def delete_run(self, run_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM answers WHERE run_id=?", (run_id,))
            c.execute("DELETE FROM runs WHERE id=?", (run_id,))

    @staticmethod
    def _run_row(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        d["config"] = json.loads(d.pop("config_json") or "{}")
        return d

    # -- answers --------------------------------------------------------------
    def save_answer(self, run_id: str, provider_label: str, answer, prompt_id: str, category: str,
                    repeat_index: int, enrichment: dict[str, Any], sentiment: dict[str, str] | None) -> int:
        with self._conn() as c:
            cur = c.execute("""
                INSERT INTO answers (run_id, provider_id, provider_label, model, prompt_id, prompt_text, category,
                                     repeat_index, text, citations_json, mentions_json, sentiment_json, latency_ms, error, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run_id, answer.provider_id, provider_label, answer.model, prompt_id, answer.prompt_text, category,
                 repeat_index, answer.text, json.dumps(enrichment.get("citations", [])),
                 json.dumps(enrichment.get("mentions", [])), json.dumps(sentiment or {}),
                 answer.latency_ms, answer.error, now_iso()))
            return int(cur.lastrowid)

    def answers(self, run_id: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM answers WHERE run_id=? ORDER BY prompt_id, provider_id, repeat_index", (run_id,)).fetchall()
        return [self._answer_row(r) for r in rows]

    def get_answer(self, answer_id: int) -> Optional[dict[str, Any]]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM answers WHERE id=?", (answer_id,)).fetchone()
        return self._answer_row(r) if r else None

    @staticmethod
    def _answer_row(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        d["citations"] = json.loads(d.pop("citations_json") or "[]")
        d["mentions"] = json.loads(d.pop("mentions_json") or "[]")
        d["sentiment"] = json.loads(d.pop("sentiment_json") or "{}")
        return d
