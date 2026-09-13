from __future__ import annotations

import json
import re

from patra.config import DATA_DIR, MIN_JD_CHARS

def _load_ontology() -> dict:
    try:
        return json.loads((DATA_DIR / "skills_ontology.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"skills": [], "synonyms": {}, "role_baseline_skills": {}}

def parse_job_description(text: str, role: str) -> dict:
    if not text or len(text.strip()) < MIN_JD_CHARS:
        raise ValueError(f"Job description must contain at least {MIN_JD_CHARS} characters")
    ontology = _load_ontology()
    known_skills = set(ontology.get("skills", []))
    normalized = re.sub(r"\s+", " ", text.lower())

    skills = sorted(skill for skill in known_skills if skill in normalized)

    role_key = role.strip().lower()
    baseline = ontology.get("role_baseline_skills", {}).get(role_key, [])
    used_role_baseline_fallback = False
    if not skills:
        words = re.findall(r"[a-zA-Z][a-zA-Z+#./-]{2,}", normalized)
        stop = {"and", "the", "with", "for", "that", "this", "from", "will", "our", "you"}
        skills = sorted(set(w for w in words if w not in stop))[:8]
        if baseline:
            skills = sorted(set(skills) | set(baseline))
            used_role_baseline_fallback = True

    return {
        "role": role.strip(),
        "requirements": skills,
        "word_count": len(normalized.split()),
        "used_role_baseline_fallback": used_role_baseline_fallback,
    }
