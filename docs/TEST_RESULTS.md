# Test results

- Date: 12 September 2026
- Environment: Linux, Python 3.12, dependencies installed from `requirements.txt`
  into a clean virtual environment (streamlit, pandas, pydantic, reportlab,
  pypdf, python-docx)
- Command: `python -m unittest discover -s tests -v`
- Tests collected: **76**
- Tests passed: **76**
- Tests failed: **0**
- Errors: **0**

## What was additionally verified in this environment

- `python scripts/validate_setup.py` → `RESULT: Ready to run`
- `python scripts/run_demo.py` → completed the full agent loop, produced a
  valid PDF, and printed a `VALIDATED` summary
- `python -m py_compile` on every `.py` file in the project → compiled cleanly
- The Streamlit app (`streamlit run app.py --server.headless true`) was
  launched directly and confirmed to serve `HTTP 200` with no errors or
  tracebacks in its log output
- A full, freeform, offline upload pipeline was manually exercised end to end:
  a resume generated as a real PDF (via reportlab, simulating a candidate's
  own upload) was extracted, heuristically parsed into a structured profile,
  combined with an uploaded plain-text evidence document, and run through the
  full agent — the semantic matcher correctly verified claims that were
  genuinely backed by the evidence document and left claims with no
  supporting evidence unverified, producing a `VALIDATED` final resume

## Final package re-verification

The uploaded final working package was extracted into a clean directory on
12 September 2026. A fresh virtual environment was created, dependencies were
installed from `requirements.txt`, the setup validator returned
`RESULT: Ready to run`, and the complete suite returned:

```text
Ran 76 tests in 50.006s
OK
```

## Test suite breakdown

| File | Focus |
|---|---|
| `tests/test_tools.py` | JD parsing (incl. role-baseline fallback for thin JDs), profile validation, evidence indexing, genuine-skill filtering, draft/evaluate/adapt cycle, company & role research |
| `tests/test_agent.py` | Full controller run: replanning after failure, genuinely different candidates, agentic trace phases, PDF validity, change report, iteration limits, the "no fabricated claim reaches the final resume" safety invariant, and end-to-end uploaded-evidence acceptance |
| `tests/test_uploads.py` | PDF/DOCX/TXT extraction (valid and malformed), oversized/empty/wrong-extension files, scanned/no-text PDFs, resume-parser field detection and honest gap-flagging, uploaded-evidence record building |
| `tests/test_research.py` | Online-lookup failure modes (timeout, DNS failure, malformed response, disabled) all falling back to the offline knowledge base or an honest "unavailable" status |
| `tests/test_contradictions.py` | Unsupported numeric claims, invalid date ranges, valid "Present"-ended roles not being falsely flagged, and dropped claims not being double-counted after a fix is applied |
| `tests/test_replanning.py` | The dynamic strategy selector: single-reason fixes, multi-reason combination, fix accumulation across iterations, idempotence, and safe handling of an unrecognised reason code |
| `tests/test_persistence.py` | SQLite-backed run/candidate/approval storage, retrieval, ordering, and survival across separate connections (simulating an app restart) |
| `tests/test_enhanced_parser.py` | Extra-section recognition and month/year employment date preservation |
| `tests/test_supplementary_claims.py` | Evidence-ledger enforcement for projects, certifications, achievements and leadership; verified inclusion; unsupported removal; link rendering |

## Known gaps in this test run

- No browser-automation (e.g. Selenium/Playwright) test clicked through the
  actual Streamlit UI widgets — the app was verified to boot and serve
  correctly, and every underlying function it calls is covered by the
  automated suite above, but a full UI click-through was not scripted for
  this submission.
- The live "online" branch of company research (a real Wikipedia summary
  fetch succeeding) could not be exercised in this sandboxed build
  environment, which has no general internet access — only the failure/
  fallback branch was exercised here. The code path itself is a short,
  well-isolated `try`/`except` around a single `urllib` call
  (`patra/tools/research.py:_try_online_summary`); reviewers with normal
  internet access can confirm the success path by running
  `python -c "from patra.tools.research import research_company; print(research_company('Python (programming language)'))"`.
