# Architecture

## Agent loop

1. **Observe** — the goal (company, role), the candidate's resume (uploaded
   file or structured JSON), the job description (pasted or uploaded), and any
   supporting evidence files, all arrive together.
2. **Validate input** — `evidence.validate_profile` checks the profile has the
   required shape; `jd_parser.parse_job_description` rejects a job description
   that is too short to be meaningful.
3. **Research** — `research.research_company` tries a live, keyless public
   summary lookup with a short timeout, and falls back to a bundled offline
   knowledge base (then to an honest "unavailable" status) if that fails for
   any reason. `research.research_role` looks up a bundled per-role skill
   baseline, entirely offline, to help interpret thin job descriptions.
4. **Build the evidence index** — `evidence.build_evidence_index` merges any
   structured JSON evidence records (explicit `evidence_id` citations) with
   text extracted from uploaded evidence documents.
5. **Decide** — the planner logs how many requirements were found and what
   research succeeded, then starts from a neutral "broad first pass" strategy
   (`agent.strategies.initial_strategy`).
6. **Act (draft)** — `drafter.draft_resume` writes a candidate resume. For
   every experience bullet, `evidence.verify_claim` decides whether it's
   "Verified" (either an explicit evidence citation flagged verified, or a
   semantic match against evidence text above a threshold) or "Unsupported".
7. **Render** — `pdf_renderer.render_resume_pdf` turns the markdown into a PDF.
8. **Validate (evaluate)** — `evaluators.evaluate_resume` runs three
   independent gates and returns both human-readable reasons and structured
   reason codes:
   - **ATS/relevance** — how many JD requirements the resume covers (direct
     substring match, or all-tokens-present match for multi-word skills).
   - **Formatting** — required sections present, word count sane, an email is
     detected, no oversized bullets.
   - **Factual consistency** — internally-impossible date ranges, and numeric
     claims the claim ledger could not verify.
9. **Adapt** — if any gate failed, `agent.strategies.select_next_strategy`
   reads the reason codes and turns on exactly the corresponding fixes
   (`evidence_first`, `keyword_boost`, `trim_long_bullets`,
   `fix_contradictions`), compounding them across iterations rather than
   resetting between attempts.
10. **Repeat** steps 6-9 up to the configured iteration limit.
11. **Select** the best candidate (prefer any that passed; otherwise the one
    with the highest ATS score and fewest unsupported claims).
12. **Present for human approval** — the Claim–Evidence Ledger, PDF and change
    report are handed to a human, who must record Approve / Reject /
    Approve-with-a-note before the run is considered final.
13. **Persist** — the full run (goal, every candidate, the full trace, the
    final selection) is written to a local SQLite database
    (`patra/tools/persistence.py`) so it survives an app restart.

The controller (`agent/controller.py`) only makes *workflow* decisions; every
actual judgement (is this claim verified? does this resume pass ATS?) is made
by a small, independently testable, deterministic tool. Nothing in this
pipeline calls an LLM or requires a network connection to function — research
online-lookup is a bonus path with a fully-offline fallback.

## Data flow for a single run

```
resume (upload or JSON) ---> resume_parser / (JSON as-is) ---> profile
job description (paste/upload) ---> file_extract (if uploaded) ---> jd_parser ---> jd
evidence files (upload) ---> file_extract ---> build_uploaded_evidence ---> evidence records
                                                        |
profile + jd + evidence ---> evidence.build_evidence_index ---> evidence_index
                                                        |
strategy (starts neutral) ---> drafter.draft_resume(profile, jd, evidence_index, strategy)
                                                        |
                                            markdown + claim ledger
                                                        |
                             pdf_renderer.render_resume_pdf -> PDF
                                                        |
                          evaluators.evaluate_resume -> passed? reasons + reason codes
                                                        |
                    if not passed: strategies.select_next_strategy -> new strategy -> loop
                                                        |
                                        final candidate selected
                                                        |
                              human approval (Streamlit UI) + persistence.save_run
```

## Why this is "semantic" and not just string matching

`patra/tools/semantic_match.py` normalises text into token sets (lower-cased,
stopwords removed, a small synonym table applied), then scores a claim
against an evidence document using an **overlap coefficient** — the fraction
of the claim's own tokens that are also present in the evidence — rather than
a full-document Jaccard index, so a short resume bullet can be correctly
matched against a much longer evidence document without being unfairly
diluted. A character-level `difflib` ratio is blended in as a minor
tie-breaker. This is a documented, honest approximation of semantic
similarity — see `docs/METHODOLOGY_AND_LIMITATIONS.md` — not a claim of true
natural-language understanding, and it requires no model weights, API key or
network access.
