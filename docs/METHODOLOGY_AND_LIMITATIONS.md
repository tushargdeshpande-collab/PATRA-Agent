# Methodology and limitations

This document is deliberately blunt about what PATRA does and doesn't do.
Treat it as the honest counterpart to the feature list in `README.md`.

## ATS / relevance scoring

The ATS score is a **transparent keyword-coverage proxy**: the fraction of job
description requirements found in the resume, either as a direct phrase match
or as a token-subset match (all the words of a multi-word skill present
somewhere in the resume, in any order). It is not a prediction of how any
specific commercial ATS product (Workday, Greenhouse, Taleo, etc.) would
score the document, and it is not trained on real ATS behaviour.

## Semantic claim-to-evidence matching

The matcher in `patra/tools/semantic_match.py` is a **fully offline, explainable
lexical heuristic** — token-set overlap plus a small synonym table plus a
character-level tie-breaker. It is *not* a neural embedding model, does not
use any pretrained language model, and cannot recognise a paraphrase that
shares no vocabulary with the evidence at all (e.g. it will not connect
"led the checkout revamp" to "owned the payments redesign" unless enough
shared or synonymous words are present). Its threshold (0.32 by default,
`patra/config.py`) was tuned against the bundled sample data and a handful of
hand-written test cases, not a labelled dataset — treat it as a reasonable
default, not a calibrated statistic. A determined but honest candidate should
find that claims genuinely backed by their evidence pass, and claims with no
textual relationship to any evidence do not.

## Resume parsing (uploaded PDF/DOCX/TXT)

`patra/tools/resume_parser.py` uses heading detection and simple heuristics
(bullet markers, year ranges, common separators) to split a resume into
sections. It works well on straightforward, single-column resumes with
conventional section headings ("Experience", "Education", "Skills", etc.). It
will likely struggle with:
- Multi-column or heavily designed resume templates (text may extract out of
  reading order).
- Non-English resumes or unconventional section names.
- Resumes with no clear section headings at all.

When the parser can't confidently identify a field, it fills it with an
explicit placeholder ("Name not detected — please edit") and lists a warning,
rather than guessing — the candidate is expected to review and correct the
detected profile before running the agent. This is a deliberate design choice:
**an honest gap is safer than a plausible-looking guess.**

## Scanned / image-only PDFs

PDF text extraction (`pypdf`) only reads embedded selectable text. A scanned
resume with no text layer will be rejected with a clear error rather than
silently producing an empty or garbled profile. OCR is out of scope for this
offline prototype.

## Company and role research

- **Company research** first attempts a live, keyless lookup (Wikipedia's
  public summary API) with a 3-second timeout, and falls back to a small
  bundled local knowledge base, and then to an explicit "unavailable" status,
  in that order. The bundled knowledge base covers only a couple of
  illustrative demo entries — real-world use would need a broader, properly
  licensed research source. No company-specific claim is ever fabricated when
  research is unavailable.
- **Role research** is a small, hand-curated baseline skill list for about
  ten common roles (`data/skills_ontology.json`). It is not derived from
  labour-market data and should be treated as a reasonable, transparent
  starting point, not an authoritative source.

## Factual-consistency checking

The contradiction checker looks for **structurally impossible or internally
inconsistent** claims (an employment period that ends before it starts, a
numeric/percentage claim the evidence doesn't support) — it is a sanity check,
not a fact-verification oracle. It cannot verify that a company genuinely
exists, that a candidate genuinely worked there, or that a certificate is
genuine; it only checks that the resume doesn't contradict itself or the
evidence supplied to it.

## Formatting checks

Formatting checks look for required section headings, a sane word count, an
email address, and no excessively long bullets. They approximate general
resume-hygiene best practice; they do not replicate the parsing behaviour of
any specific ATS product's document parser.

## Scope boundaries

- PATRA **prepares** application material. It never submits an application,
  contacts an employer, or claims to have verified a candidate's identity,
  credentials or employment history against an authoritative source.
- A human must review and explicitly approve, reject, or approve-with-a-note
  before a resume produced by PATRA is treated as final. Every run and every
  claim is recorded so this decision is auditable.
- PATRA is a decision-support and drafting tool, not legal, career, or hiring
  advice.
