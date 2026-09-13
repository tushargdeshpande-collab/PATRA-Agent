from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from patra.agent.controller import ApplicationAgent
from patra.config import (
    ALLOWED_EVIDENCE_EXTENSIONS,
    ALLOWED_JD_EXTENSIONS,
    ALLOWED_RESUME_EXTENSIONS,
    DATA_DIR,
)
from patra.tools.evidence import build_uploaded_evidence
from patra.tools.file_extract import UnsupportedFileError, extract_text
from patra.tools.persistence import get_run, list_runs, save_approval
from patra.tools.resume_parser import parse_resume_text

st.set_page_config(page_title="PATRA | Application Agent", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
/* PATRA visual system */
:root { --ink:#10233f; --muted:#64748b; --line:#e6edf5; --accent:#2563eb; --accent2:#06b6d4; --soft:#f6f9fc; }
.block-container{max-width:1400px;padding:1.5rem 2.2rem 3rem}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0b1f3a 0%,#102f55 100%)}
[data-testid="stSidebar"] *{color:#f8fbff!important}
[data-testid="stSidebar"] .stCaption{color:#cbd8e8!important}
.hero{position:relative;overflow:hidden;padding:2rem 2.2rem;border-radius:24px;background:linear-gradient(120deg,#081b35 0%,#123d68 58%,#0e7490 100%);color:white;margin-bottom:1.25rem;box-shadow:0 18px 45px rgba(15,45,80,.16)}
.hero:after{content:"";position:absolute;width:220px;height:220px;border-radius:50%;right:-50px;top:-90px;background:rgba(255,255,255,.09)}
.hero h1{margin:0;font-size:2.35rem;letter-spacing:-.04em;font-weight:800}.hero p{margin:.45rem 0 0;color:#dbeafe;font-size:1rem;max-width:800px}.hero-badge{display:inline-block;margin-bottom:.7rem;padding:.3rem .65rem;border:1px solid rgba(255,255,255,.2);border-radius:999px;background:rgba(255,255,255,.1);font-size:.78rem;font-weight:700;letter-spacing:.04em}
.section-title{font-size:1.35rem;font-weight:750;color:var(--ink);margin:.5rem 0 .2rem}.section-sub{color:var(--muted);margin-bottom:1rem}
.stepbar{display:flex;gap:.55rem;margin:.3rem 0 1.3rem}.step{padding:.55rem .8rem;border-radius:12px;background:#f1f5f9;color:#64748b;font-size:.82rem;font-weight:700}.step.active{background:#e8f1ff;color:#1d4ed8;border:1px solid #bfdbfe}
div[data-testid="stMetric"]{background:white;border:1px solid var(--line);border-radius:16px;padding:1rem 1.05rem;box-shadow:0 5px 18px rgba(15,35,60,.05)}
div[data-testid="stMetricLabel"]{color:#64748b} div[data-testid="stMetricValue"]{color:#10233f;font-weight:800}
.stButton>button{border-radius:12px!important;font-weight:750!important;min-height:2.65rem}
div.stButton>button[kind="primary"]{background:linear-gradient(90deg,#2563eb,#0891b2)!important;border:0!important;box-shadow:0 8px 20px rgba(37,99,235,.22)}
div[data-testid="stExpander"]{border:1px solid var(--line);border-radius:15px;background:white}
[data-testid="stFileUploader"]{border:1px dashed #bfd0e4;border-radius:16px;padding:.35rem;background:#f8fbff}
.info-card{padding:1rem 1.15rem;border:1px solid var(--line);border-radius:16px;background:linear-gradient(180deg,#fff,#f8fbff);margin:.5rem 0}
[data-testid="stSidebar"] .info-card,[data-testid="stSidebar"] .info-card *{color:#10233f!important}
[data-testid="stSidebar"] input,[data-testid="stSidebar"] textarea{color:#10233f!important}
.status-ok{display:inline-block;padding:.3rem .65rem;border-radius:999px;background:#dcfce7;color:#166534;font-weight:750;font-size:.8rem}.status-warn{display:inline-block;padding:.3rem .65rem;border-radius:999px;background:#fef3c7;color:#92400e;font-weight:750;font-size:.8rem}
.footer-note{color:#94a3b8;text-align:center;font-size:.78rem;margin-top:2rem}
</style>
<div class="hero"><div class="hero-badge">✦ AUTONOMOUS APPLICATION AGENT</div><h1>PATRA</h1><p>Profile Alignment & Truthful Resume Agent — tailor an application to the role using evidence you actually provided.</p></div>
""", unsafe_allow_html=True)


default_jd = (DATA_DIR / "sample_job_description.txt").read_text()
default_profile = json.loads((DATA_DIR / "sample_candidate.json").read_text())

with st.sidebar:
    st.markdown("### ⚙️ PATRA setup")
    st.caption("Configure the target role and agent behavior")
    company = st.text_input("Target company", "Northstar Digital")
    role = st.text_input("Target role", "QA Automation Engineer")
    max_iterations = st.slider("How many times PATRA may try to fix and re-check the resume", 1, 4, 3)
    st.markdown('<div class="info-card"><b>🔒 Evidence-first</b><br><span class="small-note">No API key required · no unsupported claims · human approval required.</span></div>', unsafe_allow_html=True)

tab_setup, tab_run, tab_compare, tab_approve, tab_history = st.tabs(
    ["①  Candidate", "②  Run Agent", "③  Compare", "④  Approve", "⑤  History"]
)

# ---------------------------------------------------------------------
# TAB 1 — Setup: resume, job description, supporting evidence
# ---------------------------------------------------------------------
with tab_setup:
    st.markdown('<div class="section-title">① Build your candidate profile</div><div class="section-sub">Upload your resume and review what PATRA extracted before it makes any decisions.</div>', unsafe_allow_html=True)
    resume_mode = st.radio(
        "How would you like to provide your resume?",
        ["Use the built-in example", "Upload my resume (PDF, DOCX or TXT)", "Paste a structured profile (advanced/JSON)"],
        horizontal=False,
    )

    profile_text = json.dumps(default_profile, indent=2)
    parse_warnings: list[str] = []

    if resume_mode == "Use the built-in example":
        st.info("Using the bundled example candidate so you can try PATRA immediately.")
        profile_text = json.dumps(default_profile, indent=2)

    elif resume_mode == "Upload my resume (PDF, DOCX or TXT)":
        resume_file = st.file_uploader(
            "Upload your resume", type=[e.lstrip(".") for e in sorted(ALLOWED_RESUME_EXTENSIONS)],
        )
        if resume_file is not None:
            try:
                raw_text = extract_text(resume_file.getvalue(), resume_file.name, ALLOWED_RESUME_EXTENSIONS)
                parsed_profile = parse_resume_text(raw_text)
                parse_warnings = parsed_profile.pop("_parse_warnings", [])
                file_key = f"{resume_file.name}:{len(resume_file.getvalue())}"
                if st.session_state.get("parsed_resume_key") != file_key:
                    st.session_state["parsed_resume_profile"] = parsed_profile
                    st.session_state["parsed_resume_key"] = file_key
                profile = st.session_state.get("parsed_resume_profile", parsed_profile)
                st.success(f"Read '{resume_file.name}'. Review the extracted information below before running PATRA.")
                if parse_warnings:
                    st.warning("Please review: " + " • ".join(parse_warnings))

                st.markdown("### Extracted candidate information")
                st.caption("PATRA only displays information extracted from your resume. Missing information is never invented.")

                with st.container(border=True):
                    st.markdown("**Personal information**")
                    c1, c2 = st.columns(2)
                    profile["name"] = c1.text_input("Name", profile.get("name", ""), key="profile_name")
                    profile["contact"] = c2.text_input("Contact / links", profile.get("contact", ""), key="profile_contact")
                    profile["summary"] = st.text_area("Summary / profile", profile.get("summary", ""), height=100, key="profile_summary")

                with st.container(border=True):
                    st.markdown("**Skills**")
                    skills_text = st.text_area("Skills (comma-separated)", ", ".join(profile.get("skills", [])), height=70, key="profile_skills")
                    profile["skills"] = [x.strip() for x in skills_text.split(",") if x.strip()]

                with st.container(border=True):
                    st.markdown("**Experience / internships**")
                    for i, job in enumerate(profile.get("experience", [])):
                        with st.expander(f"{job.get('role', 'Role')} — {job.get('company', 'Company')}", expanded=(i == 0)):
                            a, b = st.columns(2)
                            job["role"] = a.text_input("Role", job.get("role", ""), key=f"exp_role_{i}")
                            job["company"] = b.text_input("Company", job.get("company", ""), key=f"exp_company_{i}")
                            job["period"] = st.text_input("Period", job.get("period", ""), key=f"exp_period_{i}")
                            bullets = "\n".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in job.get("bullets", []))
                            bullets = st.text_area("Responsibilities / achievements (one per line)", bullets, height=110, key=f"exp_bullets_{i}")
                            job["bullets"] = [{"text": x.strip(), "evidence_id": None} for x in bullets.splitlines() if x.strip()]

                if profile.get("education"):
                    with st.container(border=True):
                        st.markdown("**Education**")
                        for i, edu in enumerate(profile["education"]):
                            a, b, c = st.columns([2, 2, 1])
                            edu["degree"] = a.text_input("Degree", edu.get("degree", ""), key=f"edu_degree_{i}")
                            edu["institution"] = b.text_input("Institution", edu.get("institution", ""), key=f"edu_inst_{i}")
                            edu["year"] = c.text_input("Year", edu.get("year", ""), key=f"edu_year_{i}")

                for field, label in [("projects", "Projects"), ("certifications", "Certifications"), ("achievements", "Achievements"), ("leadership", "Leadership / positions"), ("links", "Links")]:
                    with st.container(border=True):
                        st.markdown(f"**{label}**")
                        value = "\n".join((x.get("text", "") if isinstance(x, dict) else str(x)) for x in profile.get(field, []))
                        value = st.text_area(f"{label} (one per line)", value, height=80, key=f"profile_{field}")
                        profile[field] = ([{"text": x.strip()} for x in value.splitlines() if x.strip()] if field != "links" else [x.strip() for x in value.splitlines() if x.strip()])

                st.session_state["parsed_resume_profile"] = profile
                profile_text = json.dumps(profile, indent=2)
                with st.expander("Advanced: edit extracted JSON"):
                    profile_text = st.text_area("Candidate profile (JSON)", profile_text, height=280, key="advanced_profile_json")
                    try:
                        st.session_state["parsed_resume_profile"] = json.loads(profile_text)
                    except json.JSONDecodeError:
                        st.error("The advanced JSON is invalid. Fix it before running PATRA.")
            except UnsupportedFileError as exc:
                st.error(str(exc))
        else:
            st.caption("No file uploaded yet — the example candidate will be used until you upload one.")

    else:  # advanced JSON
        st.info("Paste a full candidate profile as JSON — useful for precise evidence-ID linking.")
        profile_text = st.text_area("Candidate profile (JSON)", json.dumps(default_profile, indent=2), height=320)

    st.markdown('<div class="section-title">② Target job</div><div class="section-sub">Give PATRA the job description it needs to align your application.</div>', unsafe_allow_html=True)
    jd_mode = st.radio("How would you like to provide the job description?", ["Paste text", "Upload a file (PDF, DOCX or TXT)"], horizontal=True)
    jd_text = default_jd
    if jd_mode == "Paste text":
        jd_text = st.text_area("Job description", default_jd, height=200)
    else:
        jd_file = st.file_uploader("Upload the job description", type=[e.lstrip(".") for e in sorted(ALLOWED_JD_EXTENSIONS)], key="jd_upload")
        if jd_file is not None:
            try:
                jd_text = extract_text(jd_file.getvalue(), jd_file.name, ALLOWED_JD_EXTENSIONS)
                st.success(f"Read '{jd_file.name}'.")
                with st.expander("Preview extracted job description text"):
                    st.text(jd_text[:2000])
            except UnsupportedFileError as exc:
                st.error(str(exc))
                jd_text = ""
        else:
            st.caption("No file uploaded yet.")
            jd_text = ""

    st.markdown('<div class="section-title">③ Supporting evidence</div><div class="section-sub">Projects, certificates and other documents strengthen the evidence graph.</div>', unsafe_allow_html=True)
    st.caption(
        "Upload project write-ups, certificates or reference letters. PATRA only lets a resume claim "
        "count as \"Verified\" if it is actually backed by text in one of these documents (or by the "
        "evidence you linked in an advanced JSON profile)."
    )
    evidence_files = st.file_uploader(
        "Upload supporting documents", type=[e.lstrip(".") for e in sorted(ALLOWED_EVIDENCE_EXTENSIONS)],
        accept_multiple_files=True, key="evidence_upload",
    )
    st.session_state["profile_text"] = profile_text
    st.session_state["jd_text"] = jd_text
    st.session_state["evidence_files"] = evidence_files or []

# ---------------------------------------------------------------------
# TAB 2 — Run the agent
# ---------------------------------------------------------------------
with tab_run:
    st.markdown('<div class="section-title">✦ Let PATRA do the work</div><div class="section-sub">PATRA plans, researches, drafts, evaluates and replans until the application passes its checks.</div>', unsafe_allow_html=True)
    st.write(
        "PATRA drafts a resume, checks it against the job description and your evidence, and — if it finds "
        "a problem — automatically revises and re-checks it, up to the limit you set in the sidebar. "
        "Nothing is added to the resume that isn't backed by something you provided."
    )
    run_clicked = st.button("Run PATRA", type="primary", use_container_width=True)
    if run_clicked:
        profile_text = st.session_state.get("profile_text", json.dumps(default_profile, indent=2))
        jd_text = st.session_state.get("jd_text", default_jd)
        evidence_files = st.session_state.get("evidence_files", [])
        if not jd_text or len(jd_text.strip()) < 40:
            st.error("Please provide a job description of at least 40 characters in Step 2 before running PATRA.")
        else:
            try:
                profile = json.loads(profile_text)
                uploaded_evidence, evidence_errors = build_uploaded_evidence(
                    [(f.name, f.getvalue()) for f in evidence_files]
                )
                for err in evidence_errors:
                    st.warning(f"Skipped an evidence file: {err}")
                workdir = Path(tempfile.mkdtemp(prefix="patra_"))
                with st.spinner("PATRA is researching, drafting and checking your resume..."):
                    st.session_state.result = ApplicationAgent(workdir).run(
                        profile=profile, jd_text=jd_text, company=company, role=role,
                        max_iterations=max_iterations, uploaded_evidence=uploaded_evidence,
                    )
                st.session_state.pop("decision", None)
            except json.JSONDecodeError as exc:
                st.error(f"The candidate profile isn't valid JSON: {exc}")
            except (ValueError, KeyError) as exc:
                st.error(f"Input error: {exc}")

    result = st.session_state.get("result")
    if result:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Resume drafts tried", result["summary"]["iterations"])
        c2.metric("Drafts that needed fixing", result["summary"]["failed_candidates"])
        c3.metric("Final match to job", f'{result["final"]["evaluation"]["ats_score"]}%')
        c4.metric("Status", "Ready" if result["summary"]["final_status"] == "VALIDATED" else "Needs review")

        st.markdown("#### What PATRA found")
        for candidate in result["candidates"]:
            ev = candidate["evaluation"]
            if ev["passed"]:
                st.success(f'{candidate["name"]}: passed all checks — {ev["ats_score"]}% match, 0 unverified claims.')
            else:
                st.warning(f'{candidate["name"]} was rejected: ' + "; ".join(ev["reasons"]))
        if len(result["candidates"]) > 1:
            st.caption(f'PATRA then adapted its approach ({result["candidates"][-1]["strategy_description"]}) and tried again.')

        st.markdown("#### Research used")
        cr, rr = result["company_research"], result["role_research"]
        if cr["status"] == "unavailable":
            st.caption(f'Company research: no verified source found for "{company}" — no company-specific claim was made.')
        else:
            st.caption(f'Company research source: {cr.get("source", cr["status"])}')
        if rr["status"] == "role_baseline_available":
            st.caption(f'Role research: used the bundled skill baseline for "{role}" to help interpret the job description.')

        with st.expander("Technical details (agent trace, for the curious)"):
            trace_df = pd.DataFrame(result["trace"])
            st.dataframe(trace_df[["step", "phase", "tool", "outcome"]], use_container_width=True, hide_index=True)
    else:
        st.caption("Fill in Step 1-3 and click 'Run PATRA' to begin.")

# ---------------------------------------------------------------------
# TAB 3 — Compare candidates
# ---------------------------------------------------------------------
with tab_compare:
    st.markdown('<div class="section-title">③ See how PATRA improved the draft</div><div class="section-sub">Compare iterations and understand what changed.</div>', unsafe_allow_html=True)
    result = st.session_state.get("result")
    if not result:
        st.info("Run PATRA first (tab 2).")
    else:
        rows = []
        for candidate in result["candidates"]:
            ev = candidate["evaluation"]
            rows.append({
                "Draft": candidate["name"], "Match to job": f'{ev["ats_score"]}%',
                "Verified claims": ev["verified_claims"], "Unverified claims": ev["unsupported_claims"],
                "Formatting score": ev["format_score"], "Result": "Ready" if ev["passed"] else "Needs work",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        for candidate in result["candidates"]:
            with st.expander(f'{candidate["name"]} — {"Ready" if candidate["evaluation"]["passed"] else "Needs work"}'):
                st.markdown(candidate["resume_markdown"])
                if candidate["evaluation"]["reasons"]:
                    st.warning("\n".join(f'• {x}' for x in candidate["evaluation"]["reasons"]))

# ---------------------------------------------------------------------
# TAB 4 — Approve & export
# ---------------------------------------------------------------------
with tab_approve:
    st.markdown('<div class="section-title">④ Final verification & approval</div><div class="section-sub">Review the evidence ledger, then approve or reject the final application.</div>', unsafe_allow_html=True)
    result = st.session_state.get("result")
    if not result:
        st.info("Run PATRA first (tab 2).")
    else:
        final = result["final"]
        if final["evaluation"]["passed"]:
            st.success("This resume passed the job-match, formatting and fact-check gates.")
        else:
            st.error("No draft passed every check. Please review carefully before using it.")

        st.markdown("#### Claim–Evidence Ledger")
        st.caption("Every factual claim in the final resume, and what it's backed by. Claims without evidence were removed automatically.")
        ledger_df = pd.DataFrame(final["claim_ledger"])
        if not ledger_df.empty:
            ledger_df = ledger_df.rename(columns={
                "claim": "Claim", "status": "Status", "source": "Backed by",
                "match_score": "Match confidence", "included_in_resume": "In final resume",
            })
        st.dataframe(ledger_df, use_container_width=True, hide_index=True)

        decision = st.radio("Your decision", ["Pending", "Approve", "Reject", "Approve with a note"], horizontal=True)
        note = st.text_input("Note (optional)")
        if st.button("Record my decision"):
            st.session_state.decision = {"decision": decision, "note": note}
            run_id = result.get("run_id")
            if run_id:
                save_approval(run_id, decision, note)
            st.toast("Decision recorded")

        col1, col2, col3 = st.columns(3)
        col1.download_button("Download final resume (PDF)", Path(final["pdf_path"]).read_bytes(), "patra_resume.pdf", "application/pdf", use_container_width=True)
        col2.download_button("Download change report", Path(result["change_report_path"]).read_bytes(), "patra_change_report.json", "application/json", use_container_width=True)
        col3.download_button("Download full run record", json.dumps(result, indent=2).encode(), "patra_run_record.json", "application/json", use_container_width=True)
        st.caption("PATRA is decision support, not a submission tool. You remain responsible for reviewing and submitting your application.")

# ---------------------------------------------------------------------
# TAB 5 — History (persisted across sessions)
# ---------------------------------------------------------------------
with tab_history:
    st.markdown('<div class="section-title">⑤ Run history</div><div class="section-sub">Revisit previous application runs and their audit records.</div>', unsafe_allow_html=True)
    st.caption("Every run is saved locally so you can revisit it later, even after closing the app.")
    try:
        runs = list_runs(limit=25)
    except Exception as exc:  # noqa: BLE001
        runs = []
        st.error(f"Could not load run history: {exc}")
    if not runs:
        st.info("No runs saved yet.")
    else:
        history_df = pd.DataFrame(runs)
        history_df["created_at"] = pd.to_datetime(history_df["created_at"], unit="s")
        st.dataframe(
            history_df.rename(columns={
                "run_id": "Run ID", "created_at": "When", "company": "Company",
                "role": "Role", "final_status": "Status", "final_candidate_name": "Selected draft",
            }),
            use_container_width=True, hide_index=True,
        )
        selected = st.selectbox("View a past run", ["(select)"] + [r["run_id"] for r in runs])
        if selected != "(select)":
            past = get_run(selected)
            if past:
                st.json(past, expanded=False)
                st.download_button(
                    "Download this run's record", json.dumps(past, indent=2).encode(),
                    f"patra_run_{selected[:8]}.json", "application/json",
                )


st.markdown('<div class="footer-note">PATRA · Evidence-first application preparation · You remain in control of the final submission.</div>', unsafe_allow_html=True)
