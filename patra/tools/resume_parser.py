from __future__ import annotations

"""Conservative section-aware resume parser.

Extracts only information present in the uploaded resume. It supports common
headings, month/year dates, inline role/company formats, and extra sections
such as projects and certifications without inventing candidate facts.
"""
import json
import re
from patra.config import DATA_DIR

_SECTION_HEADERS = {
    "summary": ["summary", "professional summary", "profile", "professional profile", "objective", "career objective", "about me", "about"],
    "skills": ["skills", "core skills", "technical skills", "key skills", "technical expertise", "technologies", "competencies", "skills & technologies", "technical proficiencies"],
    "experience": ["experience", "work experience", "professional experience", "employment history", "work history", "internship", "internships", "experience & internships"],
    "education": ["education", "academic background", "academic qualifications", "qualifications", "educational qualifications"],
    "projects": ["projects", "academic projects", "personal projects", "key projects", "project experience"],
    "certifications": ["certifications", "certificates", "licenses & certifications", "licenses and certifications"],
    "achievements": ["achievements", "awards", "honors", "honours", "accomplishments"],
    "leadership": ["leadership", "positions of responsibility", "responsibilities", "extracurricular activities", "activities"],
    "links": ["links", "profiles", "online profiles", "social links"],
}
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|(?:linkedin\.com|github\.com)/\S+", re.I)
_BULLET_RE = re.compile(r"^[\-\u2022\*\u25cf\u25aa\u25e6\u2013\u2014]\s*")
_DATE_RE = re.compile(r"(?:\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+)?(?:19|20)\d{2}\s*(?:[-–—]|to)\s*(?:present|current|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(?:19|20)\d{2}|(?:19|20)\d{2})", re.I)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def _load_known_skills() -> set[str]:
    try:
        return set(json.loads((DATA_DIR / "skills_ontology.json").read_text()).get("skills", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _clean(line: str) -> str:
    line = line.replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"[ \t]+", " ", line).strip()


def _normalise_header(line: str) -> str:
    x = line.lower().strip()
    x = re.sub(r"^[\s\d.)-]+", "", x)
    x = re.sub(r"[|:•·\-–—_]+", " ", x)
    x = re.sub(r"[^a-z0-9& ]", "", x)
    return re.sub(r"\s+", " ", x).strip()


def _classify_header(line: str) -> str | None:
    n = _normalise_header(line)
    for section, aliases in _SECTION_HEADERS.items():
        if n in {re.sub(r"[^a-z0-9& ]", "", a.lower()).strip() for a in aliases}:
            return section
    return None


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections = {"header": []}
    current = "header"
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        header = _classify_header(line)
        if header:
            current = header
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return sections


def _guess_name(header: list[str]) -> str:
    for line in header:
        if _EMAIL_RE.search(line) or _PHONE_RE.search(line) or _URL_RE.search(line):
            continue
        words = line.split()
        if 2 <= len(words) <= 5 and len(line) <= 60 and not any(c.isdigit() for c in line):
            return line
    return ""


def _guess_contact(header: list[str]) -> str:
    text = " | ".join(header)
    parts = []
    for regex in (_EMAIL_RE, _PHONE_RE):
        m = regex.search(text)
        if m:
            parts.append(m.group(0).strip())
    parts.extend(_URL_RE.findall(text)[:4])
    return " | ".join(dict.fromkeys(parts)) or text[:300]


def _parse_list(lines: list[str]) -> list[str]:
    out = []
    for raw in lines:
        line = _BULLET_RE.sub("", _clean(raw))
        if not line:
            continue
        out.extend(x.strip() for x in re.split(r"\s*[,;|]\s*", line) if 1 < len(x.strip()) <= 100)
    return list(dict.fromkeys(out))


def _parse_skills(lines: list[str], known: set[str], full_text: str) -> list[str]:
    listed = _parse_list(lines)
    return listed or sorted({s for s in known if s.lower() in full_text.lower()})


def _strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


def _date_match(line: str):
    return _DATE_RE.search(line)


def _split_role_company(text: str) -> tuple[str, str]:
    text = text.strip(" -|—–:@")
    for sep in ("—", "–", " at ", " @ ", " | ", " / ", " - "):
        if sep.lower() in text.lower():
            parts = re.split(re.escape(sep), text, maxsplit=1, flags=re.I)
            return parts[0].strip(), parts[1].strip()
    return text, "Company not specified"


def _looks_like_header(line: str) -> bool:
    if _BULLET_RE.match(line) or len(line) > 100:
        return False
    return bool(_date_match(line)) or any(s in line.lower() for s in (" — ", " – ", " - ", " at ", " | ", " @ ", " / "))


def _parse_experience(lines: list[str]) -> list[dict]:
    jobs = []
    current = None
    pending = None
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        bullet = _strip_bullet(line)
        if bullet != line:
            if current is None:
                role, company = _split_role_company(pending or "Role not specified")
                current = {"role": role, "company": company, "period": "Dates not specified", "bullets": []}
                jobs.append(current)
                pending = None
            current["bullets"].append({"text": bullet, "evidence_id": None})
            continue

        dm = _date_match(line)
        if dm:
            title = (line[:dm.start()] + line[dm.end():]).strip(" -|—–:@")
            if title:
                role, company = _split_role_company(title)
                current = {"role": role or "Role not specified", "company": company or "Company not specified", "period": dm.group(0), "bullets": []}
                jobs.append(current)
            elif pending:
                role, company = _split_role_company(pending)
                current = {"role": role, "company": company, "period": dm.group(0), "bullets": []}
                jobs.append(current)
                pending = None
            continue

        if _looks_like_header(line):
            role, company = _split_role_company(line)
            current = {"role": role or "Role not specified", "company": company or "Company not specified", "period": "Dates not specified", "bullets": []}
            jobs.append(current)
            continue

        # A short unbulleted line before any bullets is often the role/company line.
        if current is None and len(line) <= 90:
            pending = line
            continue
        if pending and current is None:
            role, company = _split_role_company(pending)
            current = {"role": role, "company": company, "period": "Dates not specified", "bullets": []}
            jobs.append(current)
            pending = None
        if current is not None:
            current["bullets"].append({"text": line, "evidence_id": None})
    if pending and current is None:
        role, company = _split_role_company(pending)
        jobs.append({"role": role, "company": company, "period": "Dates not specified", "bullets": []})
    return jobs


def _parse_education(lines: list[str]) -> list[dict]:
    out = []
    for raw in lines:
        line = _strip_bullet(raw)
        if not line:
            continue
        ym = _YEAR_RE.search(line)
        year = ym.group(0) if ym else "Year not specified"
        rest = (line[:ym.start()] + line[ym.end():]) if ym else line
        rest = rest.strip(" ,-|—–:@")
        parts = re.split(r"\s*[,|—–]\s*", rest, maxsplit=1)
        out.append({"degree": parts[0].strip() or "Degree not specified", "institution": parts[1].strip() if len(parts) > 1 else "Institution not specified", "year": year})
    return out


def _simple_records(lines: list[str]) -> list[dict]:
    return [{"text": _strip_bullet(x)} for x in lines if _strip_bullet(x)]


def parse_resume_text(raw_text: str) -> dict:
    if not raw_text or not raw_text.strip():
        raise ValueError("The uploaded resume appears to be empty.")
    raw_text = re.sub(r"(?<=\w)-\n(?=\w)", "", raw_text)
    lines = [_clean(x) for x in raw_text.splitlines()]
    sections = _split_sections(lines)
    known = _load_known_skills()
    profile = {
        "name": _guess_name(sections.get("header", [])) or "Name not detected — please edit",
        "contact": _guess_contact(sections.get("header", [])) or "Contact details not detected — please edit",
        "summary": " ".join(sections.get("summary", [])).strip() or "Summary not detected — please edit",
        "skills": _parse_skills(sections.get("skills", []), known, raw_text),
        "experience": _parse_experience(sections.get("experience", [])),
        "education": _parse_education(sections.get("education", [])),
        "projects": _simple_records(sections.get("projects", [])),
        "certifications": _simple_records(sections.get("certifications", [])),
        "achievements": _simple_records(sections.get("achievements", [])),
        "leadership": _simple_records(sections.get("leadership", [])),
        "links": _parse_list(sections.get("links", [])),
        "evidence": [],
    }
    warnings = []
    if "not detected" in profile["name"].lower(): warnings.append("Could not confidently detect a name — please review.")
    if "not detected" in profile["contact"].lower(): warnings.append("Could not confidently detect contact details — please review.")
    if "not detected" in profile["summary"].lower(): warnings.append("No summary/profile section was detected — please review or add one.")
    if not profile["skills"]: warnings.append("No skills were detected — please review the Skills section.")
    if not profile["experience"]: warnings.append("No experience/internship entries were confidently detected — please review.")
    if not profile["education"]: warnings.append("No education entries were confidently detected — please review.")
    profile["_parse_warnings"] = warnings
    return profile
