"""
Minimal test suite. Run with: python -m pytest tests/ -v
Covers: normalization correctness, merge/dedup behavior, and the malformed-data
edge case the assignment specifically asks us to handle gracefully.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from normalize import normalize_phone, normalize_date, normalize_skill, normalize_email
from extractors import extract_csv
from merge import merge_records


def test_normalize_phone_valid():
    assert normalize_phone("9876543210") == "+919876543210"
    assert normalize_phone("+91 98765 11223") == "+919876511223"


def test_normalize_phone_garbage_returns_none():
    assert normalize_phone("98xx wrong") is None
    assert normalize_phone("") is None
    assert normalize_phone(None) is None


def test_normalize_date_formats():
    assert normalize_date("2023-01-15") == "2023-01"
    assert normalize_date("Jan 2023") == "2023-01"
    assert normalize_date("Present") == "Present"
    assert normalize_date(None) is None


def test_normalize_skill_alias():
    assert normalize_skill("JS") == "JavaScript"
    assert normalize_skill("RandomNicheTool") == "RandomNicheTool"  # passthrough


def test_normalize_email_malformed():
    assert normalize_email("sneha.iyer@") is None
    assert normalize_email("Aarav.Sharma@Gmail.com") == "aarav.sharma@gmail.com"


def test_csv_dedup_merges_exact_duplicate_row():
    """The sample CSV has an exact duplicate Aarav row -- should merge into ONE candidate."""
    records = extract_csv("sources/recruiter_export.csv")
    canonical = merge_records(records)
    aarav_matches = [c for c in canonical if c["full_name"] == "Aarav Sharma"]
    assert len(aarav_matches) == 1


def test_garbage_row_does_not_crash_and_yields_low_confidence():
    """Sneha's row has a malformed email and phone -- pipeline must not crash, and the
    bad values must not appear as if they were valid."""
    records = extract_csv("sources/recruiter_export.csv")
    canonical = merge_records(records)
    sneha = next(c for c in canonical if c["full_name"] == "Sneha Iyer")
    assert sneha["emails"] == []  # malformed email was correctly dropped, not invented
    assert sneha["phones"] == []
