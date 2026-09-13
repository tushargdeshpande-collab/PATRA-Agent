"""Dynamic, reason-code-driven strategy selection.

The original prototype hard-switched between exactly two strategies. PATRA
instead reads the *structured* reason codes an evaluation gate produced
(``ATS_LOW``, ``UNSUPPORTED_CLAIMS``, ``FORMAT_FAIL``,
``FACTUAL_CONTRADICTION``) and turns on exactly the fixes needed to
address them, compounding fixes across iterations rather than discarding
what already worked. This means a candidate that fails for two unrelated
reasons gets both fixes applied at once instead of ping-ponging between
strategies.
"""
from __future__ import annotations

# Each flag maps 1:1 to a concrete behaviour change in patra.tools.drafter.
_FLAG_FOR_REASON = {
    "UNSUPPORTED_CLAIMS": "evidence_first",
    "ATS_LOW": "keyword_boost",
    "FORMAT_FAIL": "trim_long_bullets",
    "FACTUAL_CONTRADICTION": "fix_contradictions",
}

_DESCRIPTIONS = {
    "evidence_first": "keep only claims with matching evidence",
    "keyword_boost": "prioritize verified skills that match the job description",
    "trim_long_bullets": "shorten oversized bullets and tighten formatting",
    "fix_contradictions": "remove claims flagged as factually contradictory",
}


def initial_strategy() -> dict:
    return {
        "name": "broad-first-pass",
        "evidence_first": False,
        "keyword_boost": False,
        "trim_long_bullets": False,
        "fix_contradictions": False,
        "applied_fixes": [],
    }


def select_next_strategy(previous: dict, reason_codes: list[str]) -> dict:
    """Return the next strategy, layering new fixes on top of ``previous``.

    Unrecognised reason codes are ignored (fail safe: no behaviour change)
    rather than raising, so a new evaluator reason never crashes the agent.
    """
    next_strategy = dict(previous)
    applied = list(previous.get("applied_fixes", []))
    for code in reason_codes:
        flag = _FLAG_FOR_REASON.get(code)
        if flag and not next_strategy.get(flag):
            next_strategy[flag] = True
            applied.append(flag)
    next_strategy["applied_fixes"] = applied
    if applied:
        next_strategy["name"] = "+".join(dict.fromkeys(applied))
    return next_strategy


def describe(strategy: dict) -> str:
    fixes = strategy.get("applied_fixes", [])
    if not fixes:
        return "Broad first pass using all declared skills and claims"
    return "Adapted strategy: " + "; ".join(_DESCRIPTIONS[f] for f in fixes if f in _DESCRIPTIONS)
