from __future__ import annotations

import json
import time
from pathlib import Path

from pypdf import PdfReader

from patra.agent.strategies import describe, initial_strategy, select_next_strategy
from patra.tools.drafter import draft_resume
from patra.tools.evaluators import check_no_fabricated_metrics, evaluate_resume
from patra.tools.evidence import build_evidence_index, validate_profile
from patra.tools.jd_parser import parse_job_description
from patra.tools.pdf_renderer import render_resume_pdf
from patra.tools.persistence import save_run
from patra.tools.research import research_company, research_role


class ApplicationAgent:
    """The observe -> decide -> act -> validate -> adapt agent loop.

    Nothing here fabricates candidate facts: every claim that reaches a
    rendered resume has already passed through ``verify_claim`` (structured
    or semantic evidence matching). Failing candidates are kept, not
    discarded, so the full reasoning trail is auditable end to end.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trace: list[dict] = []
        self.tool_calls = 0

    def _log(self, phase: str, tool: str, outcome: str):
        self.trace.append({"step": len(self.trace) + 1, "phase": phase, "tool": tool, "outcome": outcome})

    def _tool(self, name: str, fn, *args):
        self.tool_calls += 1
        result = fn(*args)
        self._log("Tool", name, "completed")
        return result

    def run(
        self,
        profile: dict,
        jd_text: str,
        company: str,
        role: str,
        max_iterations: int = 3,
        uploaded_evidence: list[dict] | None = None,
        persist: bool = True,
    ) -> dict:
        started = time.perf_counter()
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")

        self._log("Observe", "input", "goal and evidence received")
        profile = self._tool("validate_profile", validate_profile, profile)
        jd = self._tool("parse_job_description", parse_job_description, jd_text, role)
        company_research = self._tool("research_company", research_company, company)
        role_research = self._tool("research_role", research_role, role)
        evidence = self._tool(
            "build_evidence_index", build_evidence_index, profile, uploaded_evidence or []
        )
        self._log(
            "Decide", "planner",
            f'{len(jd["requirements"])} requirement(s) identified; '
            f'company research={company_research["status"]}; role research={role_research["status"]}',
        )

        candidates = []
        strategy = initial_strategy()
        for iteration in range(1, max_iterations + 1):
            self._log("Action", "draft_resume", f"iteration {iteration}; strategy={strategy['name']}")
            drafted = self._tool("draft_resume", draft_resume, profile, jd, evidence, strategy)
            pdf_path = self._tool(
                "render_resume_pdf", render_resume_pdf, drafted["markdown"],
                self.output_dir / f"candidate_{iteration}.pdf",
            )
            pages = len(PdfReader(str(pdf_path)).pages)
            evaluation = self._tool("evaluate_resume", evaluate_resume, drafted, jd, profile)
            fabricated_metrics = self._tool("factual_metric_check", check_no_fabricated_metrics, drafted)
            if fabricated_metrics and evaluation["passed"]:
                evaluation["passed"] = False
                evaluation["reasons"].append("Unverified numerical claim detected in rendered resume")
                evaluation["reason_codes"].append("UNSUPPORTED_CLAIMS")

            candidate = {
                "name": f"Candidate {iteration}",
                "strategy": strategy["name"],
                "strategy_description": describe(strategy),
                "resume_markdown": drafted["markdown"],
                "claim_ledger": drafted["claim_ledger"],
                "pdf_path": str(pdf_path),
                "pdf_pages": pages,
                "evaluation": evaluation,
            }
            candidates.append(candidate)
            self._log(
                "Validate", "evaluation_gates",
                "passed" if evaluation["passed"] else "; ".join(evaluation["reasons"]),
            )
            if evaluation["passed"]:
                break
            if iteration == max_iterations:
                break
            strategy = select_next_strategy(strategy, evaluation["reason_codes"])
            self._log("Adapt", "strategy_adapter", describe(strategy))

        valid = [c for c in candidates if c["evaluation"]["passed"]]
        final = max(
            valid or candidates,
            key=lambda c: (c["evaluation"]["passed"], c["evaluation"]["ats_score"], -c["evaluation"]["unsupported_claims"]),
        )
        self._log("Evaluate", "candidate_selector", f'{final["name"]} selected')
        self._log("Approval", "human_review", "pending human decision")

        changes = {
            "project": "PATRA", "target_role": role, "target_company": company,
            "company_research_status": company_research["status"],
            "role_research_status": role_research["status"],
            "selected_candidate": final["name"],
            "changes": (
                [f"Applied fix: {f}" for f in final["strategy"].split("+")] if len(candidates) > 1 else ["No revision required"]
            ),
            "claim_ledger": final["claim_ledger"],
        }
        report_path = self.output_dir / "evidence_change_report.json"
        report_path.write_text(json.dumps(changes, indent=2))

        result = {
            "project": "PATRA", "goal": {"company": company, "role": role},
            "data_notice": "Candidate evidence and local/online research only; no claims are inferred as facts.",
            "trace": self.trace, "candidates": candidates, "final": final,
            "change_report_path": str(report_path),
            "company_research": company_research, "role_research": role_research,
            "summary": {
                "iterations": len(candidates), "tool_calls": self.tool_calls,
                "failed_candidates": sum(not c["evaluation"]["passed"] for c in candidates),
                "final_status": "VALIDATED" if final["evaluation"]["passed"] else "HUMAN_REVIEW_REQUIRED",
                "execution_seconds": round(time.perf_counter() - started, 3),
            },
        }
        (self.output_dir / "run_record.json").write_text(json.dumps(result, indent=2))
        if persist:
            result["run_id"] = save_run(result)
        return result
