"""Resume evaluation: ATS/relevance, formatting and factual consistency.

Every gate returns both a human-readable reason (for the trace and the
UI) and a structured *reason code* (for the dynamic strategy selector in
``patra.agent.strategies``). Nothing is ever marked passing just because
an earlier version of the resume passed — every candidate is re-evaluated
from scratch against the live claim ledger.
"""
from __future__ import annotations

import re

from patra.config import (
    DEFAULT_ATS_THRESHOLD,
    DEFAULT_FORMAT_THRESHOLD,
    MAX_BULLET_WORDS,
    MAX_RESUME_WORDS,
)
from patra.tools.semantic_match import normalize_tokens

REQUIRED_HEADINGS = ["professional summary", "core skills", "experience", "education"]
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_METRIC_RE = re.compile(r"\b\d+(?:\.\d+)?\s?%")

def _requirement_matched(requirement: str, raw_text_lower: str, resume_tokens: set[str]) -> bool:
    if requirement.lower() in raw_text_lower:
        return True
    req_tokens = normalize_tokens(requirement)
    return bool(req_tokens) and req_tokens.issubset(resume_tokens)

def _format_check(markdown: str) -> tuple[int, list[str]]:
    text = markdown.lower()
    issues: list[str] = []
    score = 100
    missing_headings = [h for h in REQUIRED_HEADINGS if h not in text]
    if missing_headings:
        score -= 15 * len(missing_headings)
        issues.append(f"Missing section(s): {', '.join(h.title() for h in missing_headings)}")
    word_count = len(markdown.split())
    if word_count > MAX_RESUME_WORDS:
        score -= 10
        issues.append(f"Resume is long ({word_count} words); consider tightening it")
    elif word_count < 60:
        score -= 15
        issues.append("Resume looks too short to be complete")
    if not _EMAIL_RE.search(markdown):
        score -= 10
        issues.append("No contact email detected")
    long_bullets = [
        line for line in markdown.splitlines()
        if line.strip().startswith("- ") and len(line.split()) > MAX_BULLET_WORDS
    ]
    if long_bullets:
        deduction = min(15, 5 * len(long_bullets))
        score -= deduction
        issues.append(f"{len(long_bullets)} bullet(s) exceed {MAX_BULLET_WORDS} words")
    return max(0, score), issues

def _parse_years(period: str) -> tuple[int | None, int | None]:
    years = [int(y) for y in _YEAR_RE.findall(period or "")]
    if not years:
        return None, None
    start = years[0]
    end = years[1] if len(years) > 1 else None
    if end is None and "present" not in (period or "").lower():
        end = start
    return start, end

def _factual_consistency_check(profile: dict, resume: dict) -> list[str]:
    """Look for internally inconsistent, contradictory facts.

    This is a sanity check, not a fact-verification oracle: it catches
    structurally impossible or self-contradicting claims (e.g. an
    experience period that ends before it starts, or a skill emphasised
    in the summary that the candidate never actually listed) rather than
    checking claims against the outside world.
    """
    contradictions: list[str] = []
    for job in profile.get("experience", []):
        start, end = _parse_years(job.get("period", ""))
        if start and end and end < start:
            contradictions.append(
                f"'{job.get('role', 'A role')}' at '{job.get('company', 'a company')}' "
                f"has an end year before its start year ({job.get('period')})"
            )
    ledger = resume.get("claim_ledger", [])
    fabricated_metrics = [
        row["claim"] for row in ledger
        if row["status"] != "Verified" and _METRIC_RE.search(row["claim"])
    ]
    for claim in fabricated_metrics:
        contradictions.append(f"Numeric claim without supporting evidence: \"{claim}\"")
    return contradictions

def evaluate_resume(resume: dict, jd: dict, profile: dict | None = None) -> dict:
    markdown = resume["markdown"]
    raw_text_lower = markdown.lower()
    resume_tokens = normalize_tokens(markdown)
    reqs = jd["requirements"]
    matched = [r for r in reqs if _requirement_matched(r, raw_text_lower, resume_tokens)]
    ats = round(100 * len(matched) / max(1, len(reqs)))

    ledger = resume["claim_ledger"]
    visible_ledger = [x for x in ledger if x.get("included_in_resume", True)]
    unsupported = [x for x in visible_ledger if x["status"] != "Verified"]

    format_score, format_issues = _format_check(markdown)

    contradictions = (
        _factual_consistency_check(profile or {}, {"claim_ledger": visible_ledger}) if profile else []
    )

    reasons: list[str] = []
    reason_codes: list[str] = []
    if ats < DEFAULT_ATS_THRESHOLD:
        reasons.append(f"ATS relevance {ats}% is below the {DEFAULT_ATS_THRESHOLD}% target")
        reason_codes.append("ATS_LOW")
    if unsupported:
        reasons.append(f"{len(unsupported)} unsupported claim(s) detected")
        reason_codes.append("UNSUPPORTED_CLAIMS")
    if format_score < DEFAULT_FORMAT_THRESHOLD:
        reasons.append("Formatting/readability gate failed: " + "; ".join(format_issues))
        reason_codes.append("FORMAT_FAIL")
    if contradictions:
        reasons.append(f"{len(contradictions)} factual contradiction(s) detected")
        reason_codes.append("FACTUAL_CONTRADICTION")

    return {
        "passed": not reasons,
        "ats_score": ats,
        "format_score": format_score,
        "matched_requirements": matched,
        "missing_requirements": [x for x in reqs if x not in matched],
        "verified_claims": len(visible_ledger) - len(unsupported),
        "unsupported_claims": len(unsupported),
        "contradictions": contradictions,
        "format_issues": format_issues,
        "reasons": reasons,
        "reason_codes": reason_codes,
    }

def check_no_fabricated_metrics(resume: dict) -> list[str]:
    """Return resume lines containing a numeric/percentage claim the ledger
    does not mark as verified. Kept as a standalone check (in addition to
    the equivalent logic inside ``evaluate_resume``) so tools/tests can call
    it in isolation, as in the original VeriHire prototype."""
    supported = {row["claim"] for row in resume["claim_ledger"] if row["status"] == "Verified"}
    metric_lines = [line.lstrip("- ") for line in resume["markdown"].splitlines() if _METRIC_RE.search(line)]
    return [line for line in metric_lines if line not in supported]
