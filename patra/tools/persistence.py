"""Durable, file-backed storage for agent runs.

Streamlit's ``st.session_state`` only survives one browser session. PATRA
also writes every run, its candidates, its full observe→adapt trace and
any human approval decision to a local SQLite database (a single file on
disk, no server required), so run history survives app restarts and can
be reviewed or audited later.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from patra.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    company TEXT,
    role TEXT,
    final_status TEXT,
    final_candidate_name TEXT,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
    run_id TEXT NOT NULL,
    candidate_name TEXT,
    strategy TEXT,
    ats_score INTEGER,
    passed INTEGER,
    candidate_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS trace (
    run_id TEXT NOT NULL,
    step INTEGER,
    phase TEXT,
    tool TEXT,
    outcome TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS approvals (
    run_id TEXT NOT NULL,
    decision TEXT,
    note TEXT,
    created_at REAL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
"""

@contextmanager
def _connect(db_path: Path | None = None):
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()

def save_run(result: dict, db_path: Path | None = None) -> str:
    run_id = result.get("run_id") or str(uuid.uuid4())
    result["run_id"] = run_id
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, created_at, company, role, final_status, final_candidate_name, result_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, time.time(), result["goal"]["company"], result["goal"]["role"],
                result["summary"]["final_status"], result["final"]["name"], json.dumps(result),
            ),
        )
        conn.execute("DELETE FROM candidates WHERE run_id = ?", (run_id,))
        for candidate in result["candidates"]:
            conn.execute(
                "INSERT INTO candidates (run_id, candidate_name, strategy, ats_score, passed, candidate_json) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id, candidate["name"], candidate.get("strategy", ""),
                    candidate["evaluation"]["ats_score"], int(candidate["evaluation"]["passed"]),
                    json.dumps(candidate),
                ),
            )
        conn.execute("DELETE FROM trace WHERE run_id = ?", (run_id,))
        for entry in result["trace"]:
            conn.execute(
                "INSERT INTO trace (run_id, step, phase, tool, outcome) VALUES (?, ?, ?, ?, ?)",
                (run_id, entry["step"], entry["phase"], entry["tool"], entry["outcome"]),
            )
    return run_id

def save_approval(run_id: str, decision: str, note: str, db_path: Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO approvals (run_id, decision, note, created_at) VALUES (?, ?, ?, ?)",
            (run_id, decision, note, time.time()),
        )

def list_runs(limit: int = 25, db_path: Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT run_id, created_at, company, role, final_status, final_candidate_name "
            "FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "run_id": r[0], "created_at": r[1], "company": r[2], "role": r[3],
            "final_status": r[4], "final_candidate_name": r[5],
        }
        for r in rows
    ]

def get_run(run_id: str, db_path: Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT result_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None

def get_approvals(run_id: str, db_path: Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT decision, note, created_at FROM approvals WHERE run_id = ? ORDER BY created_at DESC", (run_id,)
        ).fetchall()
    return [{"decision": r[0], "note": r[1], "created_at": r[2]} for r in rows]
