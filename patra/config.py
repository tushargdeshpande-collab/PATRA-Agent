"""Central configuration and thresholds for PATRA.

Every tunable number the agent uses to decide pass/fail lives here so the
behaviour of the whole system can be audited and adjusted from one place.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RUNS_DIR = ROOT / "runs"
DB_PATH = ROOT / "data" / "patra_history.sqlite3"

PROJECT_NAME = "PATRA"
PROJECT_FULL_NAME = "PATRA — Profile Alignment and Truthful Resume Agent"

DEFAULT_ATS_THRESHOLD = 70
DEFAULT_FORMAT_THRESHOLD = 80
MAX_RESUME_WORDS = 900
MAX_BULLET_WORDS = 28
MIN_JD_CHARS = 40

SEMANTIC_MATCH_THRESHOLD = 0.32

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_JD_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_EVIDENCE_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

RESEARCH_TIMEOUT_SECONDS = 3.0
RESEARCH_ONLINE_ENABLED = True

RUNS_DIR.mkdir(parents=True, exist_ok=True)
