"""Lightweight, fully-offline semantic matching between resume claims and
supplied evidence text.

This is deliberately *not* a neural embedding model — PATRA runs without
any API key or downloaded model weights. Instead it combines normalized
token-set overlap (Jaccard) with a character-level similarity ratio
(``difflib.SequenceMatcher``) and a small synonym table, which is enough
to recognise that "Built Selenium regression suites" and "Selenium
regression suite and test planning records" are talking about the same
thing, without ever inventing a match that isn't textually grounded.

This is an honest, documented approximation of semantic similarity, not
a claim of true natural-language understanding — see
docs/METHODOLOGY_AND_LIMITATIONS.md.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from functools import lru_cache

from patra.config import DATA_DIR, SEMANTIC_MATCH_THRESHOLD

_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "of", "to", "in", "on", "with",
    "at", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "this", "that", "these", "those", "it", "its", "their", "our", "we",
    "using", "used", "use", "across", "while", "into", "over", "also",
    "including", "i", "my",
}

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#./-]*")

@lru_cache(maxsize=1)
def _synonyms() -> dict[str, list[str]]:
    try:
        raw = json.loads((DATA_DIR / "skills_ontology.json").read_text())
        return raw.get("synonyms", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def normalize_tokens(text: str) -> set[str]:
    """Lowercase, tokenize and strip stopwords/short tokens from ``text``."""
    words = (w.lower().strip(".") for w in _WORD_RE.findall(text or ""))
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}

def _expand_with_synonyms(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    synonyms = _synonyms()
    joined = " ".join(tokens)
    for canonical, alt_list in synonyms.items():
        if canonical in joined:
            expanded.update(canonical.split())
        for alt in alt_list:
            if alt in joined:
                expanded.add(canonical.split()[0])
                expanded.update(canonical.split())
    return expanded

def similarity(claim: str, evidence_text: str) -> float:
    """Return a 0-1 similarity score between a claim and one evidence text.

    Evidence documents are often longer than the specific claim being
    checked (a whole project write-up vs. one resume bullet), so this
    uses an *overlap coefficient* (intersection over the smaller token
    set — normally the claim's) rather than a symmetric Jaccard index,
    which would otherwise unfairly penalise a claim for matching only a
    fraction of a long evidence document even when everything the claim
    asserts is, in fact, present in that document.
    """
    if not claim or not evidence_text:
        return 0.0
    claim_tokens = _expand_with_synonyms(normalize_tokens(claim))
    evidence_tokens = _expand_with_synonyms(normalize_tokens(evidence_text))
    if not claim_tokens or not evidence_tokens:
        return 0.0
    intersection = claim_tokens & evidence_tokens
    smaller = min(len(claim_tokens), len(evidence_tokens))
    overlap = len(intersection) / smaller if smaller else 0.0
    ratio = SequenceMatcher(None, claim.lower(), evidence_text.lower()).ratio()

    return round(min(1.0, 0.85 * overlap + 0.15 * ratio), 4)

def best_match(claim: str, evidence_index: dict[str, dict]) -> dict:
    """Find the evidence entry that best supports ``claim``.

    Returns a dict with ``evidence_id``, ``score`` and ``verified`` (score
    at or above ``SEMANTIC_MATCH_THRESHOLD``). If ``evidence_index`` is
    empty, ``evidence_id`` is ``None`` and ``verified`` is ``False`` —
    PATRA never treats an unsupported claim as verified by default.
    """
    best_id, best_score = None, 0.0
    for evidence_id, item in evidence_index.items():
        text = " ".join(str(v) for v in item.values() if isinstance(v, (str, int, float)))
        score = similarity(claim, text)
        if score > best_score:
            best_id, best_score = evidence_id, score
    return {
        "evidence_id": best_id,
        "score": best_score,
        "verified": best_id is not None and best_score >= SEMANTIC_MATCH_THRESHOLD,
    }
