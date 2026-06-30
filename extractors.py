"""
Stage 1+2: INGEST/DETECT + EXTRACT
Each extractor reads one raw source and returns a list of "partial records":
loosely-typed dicts with whatever fields that source could provide, plus
metadata about where each field came from (used later for provenance).

Design principle (see one-pager): a broken/garbage source must never raise
out of these functions. Catch, log a warning, return whatever partial data
was salvageable (possibly an empty list).
"""
import csv
import re
import sys

import pdfplumber


def extract_csv(path):
    """Recruiter CSV -> list of partial records. Structured source."""
    records = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append({
                    "full_name": row.get("name", "").strip() or None,
                    "emails": [row["email"].strip()] if row.get("email") else [],
                    "phones": [row["phone"].strip()] if row.get("phone") else [],
                    "experience": [{
                        "company": row.get("current_company", "").strip() or None,
                        "title": row.get("title", "").strip() or None,
                        "start": None, "end": None, "summary": None,
                    }] if row.get("current_company") else [],
                    "skills": [],
                    "education": [],
                    "headline": row.get("title", "").strip() or None,
                    "_source": "recruiter_csv",
                    "_method": "structured_field",
                })
    except (FileNotFoundError, csv.Error) as e:
        print(f"[WARN] could not read CSV source {path}: {e}", file=sys.stderr)
        return []
    return records


def _extract_resume_text(path):
    """Pull raw text out of a PDF resume. Returns '' on failure (e.g. scanned image)."""
    try:
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        return text
    except Exception as e:
        print(f"[WARN] could not extract text from resume {path}: {e}", file=sys.stderr)
        return ""


def extract_resume(path):
    """Resume PDF -> single partial record (heuristic section parsing). Unstructured source."""
    text = _extract_resume_text(path)
    if not text.strip():
        # Scanned/unreadable resume: salvage nothing, but don't crash the run.
        return [{
            "full_name": None, "emails": [], "phones": [], "skills": [],
            "experience": [], "education": [], "headline": None,
            "_source": f"resume:{path}", "_method": "extraction_failed",
        }]

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    full_name = lines[0] if lines else None

    email_match = re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", text)
    email = email_match.group(0) if email_match else None

    phone_match = re.search(r"(\+?\d[\d\-\s]{7,}\d)", text)
    phone = phone_match.group(0) if phone_match else None

    # Heuristic section split on common resume headers.
    sections = {}
    current = "header"
    sections[current] = []
    for line in lines:
        upper = line.upper()
        if upper in ("SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION"):
            current = upper.lower()
            sections[current] = []
        else:
            sections.setdefault(current, []).append(line)

    skills = []
    for line in sections.get("skills", []):
        skills.extend([s.strip() for s in line.split(",") if s.strip()])

    # Experience: pair "Company - Title (start to end)" lines with the summary
    # line that follows, per the resume format our extractor expects.
    experience = []
    exp_lines = sections.get("experience", [])
    i = 0
    while i < len(exp_lines):
        m = re.match(r"^(.+?)\s*-\s*(.+?)\s*\((.+?)\s+to\s+(.+?)\)$", exp_lines[i])
        if m:
            summary = exp_lines[i + 1] if i + 1 < len(exp_lines) and not re.match(
                r"^.+-.+\(.+to.+\)$", exp_lines[i + 1]) else None
            experience.append({
                "company": m.group(1).strip(),
                "title": m.group(2).strip(),
                "start": m.group(3).strip(),
                "end": m.group(4).strip(),
                "summary": summary,
            })
            i += 2 if summary else 1
        else:
            i += 1

    education = []
    for line in sections.get("education", []):
        m = re.match(r"^(.+?),\s*(.+?),\s*(\d{4})$", line)
        if m:
            education.append({
                "institution": m.group(2).strip(),
                "degree": m.group(1).strip(),
                "field": None,
                "end_year": int(m.group(3)),
            })

    return [{
        "full_name": full_name,
        "emails": [email] if email else [],
        "phones": [phone] if phone else [],
        "skills": skills,
        "experience": experience,
        "education": education,
        "headline": sections.get("summary", [None])[0] if sections.get("summary") else None,
        "_source": f"resume:{path}",
        "_method": "heuristic_section_parse",
    }]
