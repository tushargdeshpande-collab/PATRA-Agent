"""Company and role research with a transparent offline fallback.

PATRA never requires an API key or paid service to run. When network
access happens to be available, ``research_company`` makes one best-effort,
short-timeout attempt to enrich the result with a public, keyless summary
(Wikipedia's REST API). If that fails for *any* reason — no internet, DNS
failure, timeout, no matching article — it falls back to the bundled local
knowledge base, and if that also has nothing, it returns an honest
``"unavailable"`` status. At no point is a fact invented to fill the gap.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from patra.config import DATA_DIR, RESEARCH_ONLINE_ENABLED, RESEARCH_TIMEOUT_SECONDS

def _load_company_knowledge() -> dict:
    try:
        return json.loads((DATA_DIR / "company_knowledge.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _load_ontology() -> dict:
    try:
        return json.loads((DATA_DIR / "skills_ontology.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _try_online_summary(company: str) -> dict | None:
    """Best-effort, keyless lookup. Returns None on any failure."""
    if not RESEARCH_ONLINE_ENABLED:
        return None
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(company.strip())
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PATRA-offline-agent/2.0"})
        with urllib.request.urlopen(req, timeout=RESEARCH_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        extract = payload.get("extract")
        if not extract or payload.get("type") == "disambiguation":
            return None
        return {
            "status": "online_summary",
            "company": company,
            "source": "Wikipedia (public summary API, no key required)",
            "facts": [extract],
            "note": "Retrieved live at run time; verify independently before use.",
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        return None

def research_company(company: str) -> dict:
    """Research a company, preferring a live lookup and falling back offline."""
    if not company or not company.strip():
        return {"status": "unavailable", "company": company, "note": "No company name was supplied."}

    online = _try_online_summary(company)
    if online:
        return online

    knowledge = _load_company_knowledge()
    record = knowledge.get(company.strip().lower())
    if record:
        return {"status": "local_knowledge", **record}

    return {
        "status": "unavailable",
        "company": company,
        "note": (
            "No verified company research source was available (offline, or no "
            "matching record). No company-specific claim will be made in the resume."
        ),
    }

def research_role(role: str) -> dict:
    """Return the bundled baseline skill expectations for a role, offline.

    This is a transparent, locally-sourced heuristic (not a live lookup) —
    it exists to give the agent a reasonable starting point for common
    roles even when the job description itself is thin.
    """
    ontology = _load_ontology()
    baseline = ontology.get("role_baseline_skills", {}).get(role.strip().lower())
    if baseline:
        return {"status": "role_baseline_available", "role": role, "baseline_skills": baseline}
    return {"status": "role_baseline_unavailable", "role": role, "baseline_skills": []}
