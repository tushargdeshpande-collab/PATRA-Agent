from __future__ import annotations

from patra.config import MAX_BULLET_WORDS
from patra.tools.evidence import genuine_skills, verify_claim

def _truncate_bullet(text: str, max_words: int = MAX_BULLET_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",.;") + "…"

def _experience_lines(profile: dict, evidence_index: dict, strategy: dict) -> tuple[list[str], list[dict]]:
    evidence_first = strategy.get("evidence_first", False)
    trim_long_bullets = strategy.get("trim_long_bullets", False)
    fix_contradictions = strategy.get("fix_contradictions", False)

    lines, ledger = [], []
    for job in profile["experience"]:
        lines.append(f'### {job["role"]} — {job["company"]} | {job["period"]}')
        job_had_bullet = False
        for bullet in job.get("bullets", []):
            text = bullet["text"]
            evidence_id = bullet.get("evidence_id")
            verification = verify_claim(text, evidence_id, evidence_index)
            status = "Verified" if verification["verified"] else "Unsupported"

            drop_for_contradiction = fix_contradictions and status != "Verified"
            drop_for_evidence = evidence_first and status != "Verified"
            if drop_for_contradiction or drop_for_evidence:
                ledger.append({
                    "claim": text, "evidence_id": evidence_id or "none",
                    "source": verification.get("source", "Not supplied"),
                    "status": status, "match_score": verification["score"],
                    "included_in_resume": False,
                })
                continue

            display_text = _truncate_bullet(text) if trim_long_bullets else text
            lines.append(f'- {display_text}')
            job_had_bullet = True
            ledger.append({
                "claim": text, "evidence_id": evidence_id or "none",
                "source": verification.get("source", "Not supplied"),
                "status": status, "match_score": verification["score"],
                "included_in_resume": True,
            })
        if not job_had_bullet:
            lines.append("- (No verifiable achievements available for this role yet.)")
    return lines, ledger

def _supplementary_lines(
    profile: dict, evidence_index: dict, strategy: dict
) -> tuple[list[str], list[dict]]:
    """Render additional factual sections through the same evidence gate.

    Projects, certifications, achievements and leadership entries are claims,
    exactly like experience bullets.  They must therefore appear in the
    Claim-Evidence Ledger and must be removed in evidence-first mode when no
    supporting evidence exists.
    """
    evidence_first = strategy.get("evidence_first", False)
    fix_contradictions = strategy.get("fix_contradictions", False)
    trim_long_bullets = strategy.get("trim_long_bullets", False)
    lines: list[str] = []
    ledger: list[dict] = []

    for field, heading in (
        ("projects", "Projects"),
        ("certifications", "Certifications"),
        ("achievements", "Achievements"),
        ("leadership", "Leadership & Positions"),
    ):
        section_lines: list[str] = []
        for item in profile.get(field, []):
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            text = text.strip()
            if not text:
                continue
            evidence_id = item.get("evidence_id") if isinstance(item, dict) else None
            verification = verify_claim(text, evidence_id, evidence_index)
            status = "Verified" if verification["verified"] else "Unsupported"
            include = not ((evidence_first or fix_contradictions) and status != "Verified")
            ledger.append({
                "claim": text,
                "section": heading,
                "evidence_id": evidence_id or verification.get("evidence_id") or "none",
                "source": verification.get("source", "Not supplied"),
                "status": status,
                "match_score": verification["score"],
                "included_in_resume": include,
            })
            if include:
                section_lines.append(
                    f'- {_truncate_bullet(text) if trim_long_bullets else text}'
                )
        if section_lines:
            lines.extend(["", f"## {heading}", *section_lines])

    links = [str(link).strip() for link in profile.get("links", []) if str(link).strip()]
    if links:
        lines.extend(["", "## Links", *[f"- {link}" for link in links]])
    return lines, ledger

def draft_resume(profile: dict, jd: dict, evidence_index: dict, strategy: dict) -> dict:
    evidence_first = strategy.get("evidence_first", False)
    keyword_boost = strategy.get("keyword_boost", False)

    verified_skills = genuine_skills(profile, evidence_index)

    skills = verified_skills if evidence_first else profile.get("skills", [])
    skill_lookup = {x.lower(): x for x in skills}

    requirements = jd["requirements"]
    relevant = [skill_lookup[s.lower()] for s in requirements if s.lower() in skill_lookup]
    relevant_keys = {x.lower() for x in relevant}
    if keyword_boost or evidence_first:
        ordered_skills = relevant + [s for s in skills if s.lower() not in relevant_keys]
    else:
        ordered_skills = skills

    exp_lines, ledger = _experience_lines(profile, evidence_index, strategy)
    supplementary_lines, supplementary_ledger = _supplementary_lines(
        profile, evidence_index, strategy
    )
    ledger.extend(supplementary_ledger)

    summary = profile["summary"]
    if (evidence_first or keyword_boost) and relevant:
        summary = f'{jd["role"]} candidate with verified experience in {", ".join(relevant[:4])}. {summary}'

    lines = [
        f'# {profile["name"]}', profile["contact"], "",
        "## Professional Summary", summary, "",
        "## Core Skills", ", ".join(ordered_skills) if ordered_skills else "(none listed)", "",
        "## Experience", *exp_lines, "",
        "## Education",
    ]
    for edu in profile["education"]:
        lines.append(f'- {edu["degree"]}, {edu["institution"]} ({edu["year"]})')

    lines.extend(supplementary_lines)
    return {
        "markdown": "\n".join(lines),
        "claim_ledger": ledger,
        "strategy": strategy.get("name", "broad-first-pass"),
    }
