# PATRA — Profile Alignment and Truthful Resume Agent

Built for **Tech Zephyr 4.0 — Problem Statement 11 (Autonomous Resume & Application Agent)**.

PATRA plans, drafts, checks and revises a role-specific resume from a candidate's
own evidence — and never invents a fact to make it fit a job description better.
It runs **entirely offline** (no API key, no LLM call, no paid service) and keeps a
human in the loop for the final decision.

## What it does

1. **Observe** — takes a target company, role, a job description (pasted or
   uploaded), a candidate resume (uploaded PDF/DOCX/TXT, or a structured JSON
   profile), and any supporting evidence documents (project write-ups,
   certificates, reference letters).
2. **Research** — looks up the company (tries a live, keyless public summary
   first, falls back to a bundled offline knowledge base) and the role (a
   bundled skill baseline), and is always transparent about which source it used.
3. **Draft** — writes a first resume candidate using every claim the candidate
   supplied.
4. **Verify** — checks the draft against three independent gates: ATS/keyword
   relevance to the job description, formatting/readability, and factual
   consistency (including semantic claim-to-evidence matching).
5. **Adapt** — if a gate fails, PATRA reads the *structured reason codes* the
   gate produced and turns on exactly the fixes needed (drop unsupported
   claims, reorder skills toward the job description, trim oversized bullets,
   remove contradictions) — compounding fixes across iterations rather than
   guessing blindly.
6. **Re-draft and re-verify** — up to a configurable number of attempts.
7. **Present for approval** — every claim in the final resume is listed in a
   Claim–Evidence Ledger with its source and match confidence. A human must
   approve, reject, or approve-with-a-note before the PDF is treated as final.
8. **Persist** — every run, its candidates, its full reasoning trace and the
   human decision are saved to a local SQLite database, so history survives
   restarting the app.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/validate_setup.py # confirms dependencies and required files are present
python -m streamlit run app.py
```

No `.env` file or API key is required — `.env.example` is present only for a
possible future integration and is not read by the current code.

Try the command-line demo (no browser needed):

```bash
python scripts/run_demo.py
```

Run the automated test suite:

```bash
python -m unittest discover -s tests -v
```

## Core capabilities

- **Resume upload** — PDF, DOCX or TXT, heuristically parsed into a structured
  profile (never guesses a fact it can't find; flags gaps for you to fill in).
- **Job description upload or paste** — PDF, DOCX, TXT, or plain text box.
- **Supporting evidence upload** — project write-ups, certificates, etc., used
  to verify resume claims automatically.
- **Semantic claim-to-evidence verification** — an offline, explainable
  lexical-overlap matcher (not a hosted embedding model) decides whether a
  claim is actually backed by the evidence text, even when the wording differs.
- **Stronger ATS, formatting and factual-consistency checks**, each producing
  structured reason codes.
- **Dynamic strategy selection** — the agent composes fixes from whichever
  reason codes actually fired, instead of switching between two fixed modes.
- **Better, transparent company/role research**, with an explicit offline
  fallback path that is exercised (and tested) even without internet access.
- **A clean, non-technical Streamlit UI**, with the full agent trace tucked
  into an optional "technical details" panel.
- **Persistent run/candidate/trace/approval history** via SQLite.
- **A verified automated test suite** — 76 tests covering uploads, malformed
  files, research failure/fallback, contradiction detection and dynamic
  replanning, enhanced resume parsing and supplementary-claim safety, in
  addition to the original core-agent tests.

### Evidence safety across every resume section

Experience bullets, projects, certifications, achievements and leadership
entries all pass through the same claim-verification gate. Each appears in the
Claim-Evidence Ledger. During evidence-first recovery, unsupported entries are
removed from the final resume while remaining visible in the audit record.
Links are rendered as candidate-supplied identifiers rather than achievement
claims.

See `docs/ARCHITECTURE.md` for the full pipeline, `docs/METHODOLOGY_AND_LIMITATIONS.md`
for an honest account of what the offline heuristics can and can't do, and
`docs/TEST_RESULTS.md` for the exact test run used for this submission.

## Project layout

```
app.py                     Streamlit UI
patra/
  config.py                 all thresholds/settings in one place
  agent/
    controller.py            observe -> decide -> act -> validate -> adapt loop
    strategies.py             dynamic, reason-code-driven strategy selection
  tools/
    file_extract.py           PDF/DOCX/TXT text extraction
    resume_parser.py          freeform resume -> structured profile
    jd_parser.py               job description -> requirement list
    research.py                company/role research, online-first + offline fallback
    semantic_match.py          offline claim<->evidence similarity scoring
    evidence.py                evidence index + claim verification
    drafter.py                  resume drafting under a given strategy
    evaluators.py               ATS/format/factual-consistency gates
    pdf_renderer.py             resume -> PDF
    persistence.py              SQLite-backed run/candidate/trace/approval history
data/                        bundled sample profile, JD, company knowledge, skills ontology
tests/                       76 automated tests
docs/                        architecture, methodology and test results
scripts/                     CLI demo + environment validator
.github/workflows/ci.yml     GitHub Actions test workflow
```

## Known limitations

See `docs/METHODOLOGY_AND_LIMITATIONS.md` for the full, honest list — in
short: the resume parser and semantic matcher are deterministic heuristics,
not machine-learned NLP; scanned/image-only PDFs aren't supported without
OCR; and offline company research only covers a small bundled knowledge base.
PATRA prepares application material — it never submits anything, and a human
always makes the final call.
