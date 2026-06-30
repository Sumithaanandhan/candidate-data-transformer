"""
Stage 4: MERGE & CONFIDENCE
Combine partial records (from possibly several sources) into one canonical
record per real candidate.

Matching policy (see one-pager):
  1. Primary key: normalized email (case-insensitive exact match).
  2. Fallback key: normalized full_name + phone, when no email overlap exists.
  If neither matches, treat as a separate, unmerged candidate -- a missed
  merge is recoverable later; a false merge silently corrupts two people's
  data into one, which is worse.

Conflict-resolution policy for a field that differs across sources:
  - Contact fields (emails/phones): structured sources win (CSV/ATS), since
    structured data entry is less error-prone than resume parsing.
  - Narrative fields (skills/experience/education): unstructured sources
    (resumes) win, since structured exports rarely capture this well.
  - Ties broken by source priority order, configurable below.

Confidence per field = source_reliability_weight * agreement_bonus, clamped
to [0, 1]. Fields with no value get confidence 0 and method 'missing'.
"""
import uuid
from collections import defaultdict

from normalize import normalize_email, normalize_phone, normalize_skill, normalize_country, normalize_date

# Higher = more trusted for CONTACT fields. Reversed priority is used for
# NARRATIVE fields (skills/experience/education) -- see _field_priority().
SOURCE_RELIABILITY = {
    "recruiter_csv": 0.9,
    "ats_json": 0.85,
    "resume": 0.75,
    "recruiter_notes": 0.6,
}

CONTACT_FIELDS = {"emails", "phones", "full_name", "headline"}
NARRATIVE_FIELDS = {"skills", "experience", "education"}


def _source_kind(source_tag):
    if source_tag.startswith("resume"):
        return "resume"
    if source_tag.startswith("notes"):
        return "recruiter_notes"
    return source_tag  # 'recruiter_csv', 'ats_json' etc already match


def _field_priority(field, source_tag):
    kind = _source_kind(source_tag)
    base = SOURCE_RELIABILITY.get(kind, 0.5)
    if field in NARRATIVE_FIELDS and kind == "resume":
        base += 0.1  # resumes are the authority on narrative content
    return base


def _match_key(record):
    email = normalize_email(record["emails"][0]) if record.get("emails") else None
    if email:
        return ("email", email)
    name = (record.get("full_name") or "").strip().lower()
    phone = normalize_phone(record["phones"][0]) if record.get("phones") else None
    if name and phone:
        return ("name_phone", name, phone)
    return ("unmatched", id(record))  # never collides -> stays its own candidate


def merge_records(partial_records):
    """Group partial records by match key, then merge each group into one canonical record."""
    groups = defaultdict(list)
    for r in partial_records:
        groups[_match_key(r)].append(r)

    canonical_records = []
    for group in groups.values():
        canonical_records.append(_merge_group(group))
    return canonical_records


def _merge_group(group):
    candidate_id = str(uuid.uuid4())
    provenance = []

    full_name = _pick_scalar(group, "full_name", provenance)
    emails = _pick_list(group, "emails", normalize_email, provenance)
    phones = _pick_list(group, "phones", normalize_phone, provenance)

    skills = _merge_skills(group, provenance)
    experience = _merge_list_field(group, "experience", provenance)
    education = _merge_list_field(group, "education", provenance)
    headline = _pick_scalar(group, "headline", provenance)

    field_confidences = [p["confidence"] for p in provenance if p["confidence"] > 0]
    overall_confidence = round(sum(field_confidences) / len(field_confidences), 2) if field_confidences else 0.0

    return {
        "candidate_id": candidate_id,
        "full_name": full_name,
        "emails": emails,
        "phones": phones,
        "location": {"city": None, "region": None, "country": None},  # not in our sample sources
        "links": {},
        "headline": headline,
        "years_experience": _estimate_years_experience(experience),
        "skills": skills,
        "experience": experience,
        "education": education,
        "provenance": provenance,
        "overall_confidence": overall_confidence,
    }


def _pick_scalar(group, field, provenance):
    """Pick the highest-priority non-null value for a scalar field across the group."""
    candidates = [(r.get(field), r["_source"], r["_method"]) for r in group if r.get(field)]
    if not candidates:
        provenance.append({"field": field, "source": None, "method": "missing", "confidence": 0})
        return None
    candidates.sort(key=lambda c: _field_priority(field, c[1]), reverse=True)
    value, source, method = candidates[0]
    agreement = sum(1 for c in candidates if c[0] == value)
    confidence = min(1.0, _field_priority(field, source) + 0.05 * (agreement - 1))
    provenance.append({"field": field, "source": source, "method": method, "confidence": round(confidence, 2)})
    return value


def _pick_list(group, field, normalizer, provenance):
    """Union of normalized values across sources, deduped, highest-priority source first."""
    seen = {}
    for r in sorted(group, key=lambda r: _field_priority(field, r["_source"]), reverse=True):
        for raw in r.get(field, []):
            norm = normalizer(raw)
            if norm and norm not in seen:
                seen[norm] = (r["_source"], r["_method"])
    values = list(seen.keys())
    if values:
        best_source, best_method = next(iter(seen.values()))
        confidence = _field_priority(field, best_source)
        provenance.append({"field": field, "source": best_source, "method": best_method,
                            "confidence": round(confidence, 2)})
    else:
        provenance.append({"field": field, "source": None, "method": "missing", "confidence": 0})
    return values


def _merge_skills(group, provenance):
    seen = {}
    for r in sorted(group, key=lambda r: _field_priority("skills", r["_source"]), reverse=True):
        for raw in r.get("skills", []):
            name = normalize_skill(raw)
            if not name:
                continue
            if name not in seen:
                conf = _field_priority("skills", r["_source"])
                seen[name] = {"name": name, "confidence": round(conf, 2), "sources": [r["_source"]]}
            else:
                seen[name]["sources"].append(r["_source"])
                seen[name]["confidence"] = round(min(1.0, seen[name]["confidence"] + 0.05), 2)
    skills = list(seen.values())
    provenance.append({
        "field": "skills",
        "source": skills[0]["sources"][0] if skills else None,
        "method": "union_across_sources",
        "confidence": round(sum(s["confidence"] for s in skills) / len(skills), 2) if skills else 0,
    })
    return skills


def _merge_list_field(group, field, provenance):
    """For experience/education: take the richest source's list (most entries), normalize dates."""
    candidates = [(r.get(field, []), r["_source"], r["_method"]) for r in group if r.get(field)]
    if not candidates:
        provenance.append({"field": field, "source": None, "method": "missing", "confidence": 0})
        return []
    candidates.sort(key=lambda c: (len(c[0]), _field_priority(field, c[1])), reverse=True)
    values, source, method = candidates[0]

    if field == "experience":
        for entry in values:
            entry["start"] = normalize_date(entry.get("start"))
            entry["end"] = normalize_date(entry.get("end"))

    confidence = _field_priority(field, source)
    provenance.append({"field": field, "source": source, "method": method, "confidence": round(confidence, 2)})
    return values


def _estimate_years_experience(experience):
    """Rough estimate: count distinct start years present, take span. Returns None if unknown."""
    years = []
    for e in experience:
        if e.get("start") and e["start"] != "Present":
            try:
                years.append(int(e["start"][:4]))
            except ValueError:
                pass
    if not years:
        return None
    return max(0, 2026 - min(years))
