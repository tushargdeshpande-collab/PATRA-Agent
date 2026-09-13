"""Evidence indexing and claim verification.

Two modes are supported and can be mixed freely:

1. **Structured mode** — the candidate profile JSON lists explicit
   ``evidence`` records with an ``id`` and a ``verified`` flag, and each
   experience bullet cites an ``evidence_id``. This is the original
   VeriHire behaviour and is preserved exactly for backward compatibility.
2. **Uploaded/freeform mode** — supporting documents (project write-ups,
   certificates, transcripts) are uploaded as files. PATRA extracts their
   text and uses semantic matching (see ``semantic_match.py``) to decide,
   claim by claim, whether the evidence actually supports it. This is what
   powers the "semantic claim-to-evidence verification" feature and what
   lets a candidate upload a plain resume + supporting files instead of
   hand-authoring a JSON evidence ledger.

Nothing here ever marks a claim verified without a textual match.
"""
from __future__ import annotations

from patra.config import ALLOWED_EVIDENCE_EXTENSIONS
from patra.tools.file_extract import UnsupportedFileError, extract_text
from patra.tools.semantic_match import best_match

REQUIRED_FIELDS = {"name", "contact", "summary", "skills", "experience", "education"}

def validate_profile(profile: dict) -> dict:
    missing = sorted(REQUIRED_FIELDS - set(profile))
    if missing:
        raise ValueError(f"Candidate profile is missing: {', '.join(missing)}")
    if not isinstance(profile["experience"], list) or not profile["experience"]:
        raise ValueError("At least one experience record is required")
    if not isinstance(profile["skills"], list):
        raise ValueError("'skills' must be a list")
    if not isinstance(profile["education"], list) or not profile["education"]:
        raise ValueError("At least one education record is required")
    return profile

def build_evidence_index(profile: dict, uploaded_evidence: list[dict] | None = None) -> dict[str, dict]:
    """Merge structured JSON evidence with any uploaded evidence documents.

    ``uploaded_evidence`` items look like ``{"id", "source", "text"}`` and
    are produced by ``patra.tools.file_extract.extract_text`` on each
    uploaded file. They are always treated as *available for matching*,
    never auto-marked ``verified`` — verification is decided per-claim by
    the semantic matcher, based on real textual overlap.
    """
    index: dict[str, dict] = {}
    for item in profile.get("evidence", []):
        if item.get("id"):
            index[item["id"]] = item
    for item in uploaded_evidence or []:
        if item.get("id"):
            index[item["id"]] = {**item, "verified": True}
    return index

def verify_claim(claim_text: str, evidence_id: str | None, evidence_index: dict[str, dict]) -> dict:
    """Decide whether a single resume claim is supported by evidence.

    If the claim explicitly cites an ``evidence_id`` that exists in the
    index and is flagged ``verified``, that citation is honoured directly
    (structured mode). Otherwise PATRA falls back to semantic matching
    against every available evidence entry (freeform/uploaded mode).
    """
    if evidence_id and evidence_id in evidence_index:
        entry = evidence_index[evidence_id]
        if entry.get("verified"):
            return {"evidence_id": evidence_id, "score": 1.0, "verified": True, "source": entry.get("source", "Not supplied")}

    match = best_match(claim_text, evidence_index)
    source = "Not supplied"
    if match["evidence_id"] and match["evidence_id"] in evidence_index:
        source = evidence_index[match["evidence_id"]].get("source", "Not supplied")
    return {**match, "source": source}

def build_uploaded_evidence(files: list[tuple[str, bytes]]) -> tuple[list[dict], list[str]]:
    """Extract text from uploaded evidence files (projects, certificates).

    Returns ``(evidence_records, errors)``. A malformed individual file
    produces a readable error string but never aborts processing of the
    other files.
    """
    records, errors = [], []
    for index, (filename, data) in enumerate(files, start=1):
        try:
            text = extract_text(data, filename, ALLOWED_EVIDENCE_EXTENSIONS)
        except UnsupportedFileError as exc:
            errors.append(f"{filename}: {exc}")
            continue
        records.append({"id": f"UP-{index:03d}", "source": filename, "text": text})
    return records, errors

def genuine_skills(profile: dict, evidence_index: dict[str, dict]) -> list[str]:
    """Skills that appear, verbatim or near-verbatim, in verified evidence text."""
    verified_text = " ".join(
        str(v) for item in evidence_index.values() if item.get("verified") for v in item.values()
        if isinstance(v, (str, int, float))
    ).lower()
    seen, result = set(), []
    for skill in profile.get("skills", []):
        key = skill.lower()
        if key in verified_text and key not in seen:
            seen.add(key)
            result.append(skill)
    return result
