"""
Stage 3: NORMALIZE
Pure functions that take a raw extracted value and return a normalized one,
or None if normalization fails. Never raise on bad input -- bad data should
degrade to null, not crash the pipeline (see design doc: "Robust" constraint).
"""
import json
import re
from pathlib import Path

import phonenumbers

_ALIASES_PATH = Path(__file__).parent / "configs" / "skill_aliases.json"
_SKILL_ALIASES = json.loads(_ALIASES_PATH.read_text())

# Country -> default region used when a phone number has no country code.
# Kept simple and explicit per design doc's "deliberately left out" scope note.
DEFAULT_PHONE_REGION = "IN"


def normalize_phone(raw, default_region=DEFAULT_PHONE_REGION):
    """Return E.164 formatted phone, or None if unparseable."""
    if not raw or not str(raw).strip():
        return None
    raw = str(raw).strip()
    try:
        parsed = phonenumbers.parse(raw, default_region)
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return None


def normalize_date(raw):
    """
    Accepts things like '2023-01', 'Jan 2023', '2023', '2023-01-15', 'Present'.
    Returns YYYY-MM string, 'Present', or None.
    """
    if not raw:
        return None
    raw = str(raw).strip()
    if raw.lower() == "present":
        return "Present"

    m = re.match(r"^(\d{4})-(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    m = re.match(r"^(\d{4})$", raw)
    if m:
        return f"{m.group(1)}-01"  # month unknown -> default to 01, low confidence upstream

    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    m = re.match(r"^([A-Za-z]{3,9})\.?\s+(\d{4})$", raw)
    if m:
        mon = months.get(m.group(1)[:3].lower())
        if mon:
            return f"{m.group(2)}-{mon}"

    return None


def normalize_country(raw):
    """Map a few common country name spellings to ISO 3166-1 alpha-2. Extend as needed."""
    if not raw:
        return None
    table = {
        "india": "IN", "in": "IN",
        "united states": "US", "usa": "US", "us": "US",
        "united kingdom": "GB", "uk": "GB",
    }
    return table.get(str(raw).strip().lower())


def normalize_skill(raw):
    """Map a raw skill token to its canonical name via alias table; pass through if unknown."""
    if not raw:
        return None
    key = str(raw).strip().lower()
    return _SKILL_ALIASES.get(key, str(raw).strip())


def normalize_email(raw):
    """Lowercase + basic shape check. Returns None for clearly malformed emails."""
    if not raw:
        return None
    raw = str(raw).strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", raw):
        return None
    return raw
