"""
Stage 5: PROJECT-TO-OUTPUT
Stage 6: VALIDATE

The canonical record (from merge.py) is the single internal source of truth.
A "config" is a declarative spec describing the desired OUTPUT shape -- it
never touches the canonical record itself. This keeps the engine reusable:
same canonical data, many possible output shapes, zero code changes.

Config format (matches the assignment's example):
{
  "fields": [
    {"path": "full_name", "type": "string", "required": true},
    {"path": "primary_email", "from": "emails[0]", "type": "string", "required": true},
    {"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164"},
    {"path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical"}
  ],
  "include_confidence": true,
  "include_provenance": false,
  "on_missing": "null"   # null | omit | error
}
"""
import re

from normalize import normalize_phone, normalize_skill


def _resolve_path(record, path):
    """
    Resolve a dotted/indexed path like 'emails[0]' or 'skills[].name' against
    the canonical record. Returns a single value, a list (for '[].' paths),
    or None if not found.
    """
    list_match = re.match(r"^(\w+)\[\]\.(\w+)$", path)
    if list_match:
        field, subfield = list_match.groups()
        items = record.get(field) or []
        return [item.get(subfield) for item in items if isinstance(item, dict)]

    index_match = re.match(r"^(\w+)\[(\d+)\]$", path)
    if index_match:
        field, idx = index_match.groups()
        items = record.get(field) or []
        idx = int(idx)
        return items[idx] if idx < len(items) else None

    return record.get(path)


_NORMALIZERS = {
    "E164": normalize_phone,
    "canonical": normalize_skill,
}


def project_record(record, config):
    """Apply a config to one canonical record. Returns (output_dict, errors_list)."""
    out = {}
    errors = []
    on_missing = config.get("on_missing", "null")

    for field_spec in config["fields"]:
        path = field_spec["path"]
        source_path = field_spec.get("from", path)
        value = _resolve_path(record, source_path)

        normalizer_name = field_spec.get("normalize")
        if normalizer_name and value is not None:
            fn = _NORMALIZERS.get(normalizer_name)
            if fn:
                value = [fn(v) for v in value] if isinstance(value, list) else fn(value)

        is_missing = value is None or value == [] or value == ""
        if is_missing:
            if field_spec.get("required") or on_missing == "error":
                errors.append(f"required field '{path}' is missing")
                if on_missing == "error":
                    continue
            if on_missing == "omit":
                continue
            out[path] = None
        else:
            out[path] = value

    if config.get("include_confidence"):
        out["overall_confidence"] = record.get("overall_confidence")
    if config.get("include_provenance"):
        out["provenance"] = record.get("provenance")

    return out, errors


DEFAULT_SCHEMA_FIELDS = [
    "candidate_id", "full_name", "emails", "phones", "location", "links",
    "headline", "years_experience", "skills", "experience", "education",
    "provenance", "overall_confidence",
]


def project_default(record):
    """The default (non-custom-config) projection: the canonical record as-is."""
    return {k: record.get(k) for k in DEFAULT_SCHEMA_FIELDS}, []


def validate_against_config(output, config):
    """
    Stage 6: VALIDATE.
    Builds a tiny JSON-schema-like check dynamically from the config's field
    list (type + required) and verifies the projected output conforms.
    Returns a list of error strings (empty list = valid).
    """
    errors = []
    type_checks = {
        "string": lambda v: isinstance(v, str),
        "string[]": lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v),
        "number": lambda v: isinstance(v, (int, float)),
    }
    for field_spec in config["fields"]:
        path = field_spec["path"]
        expected_type = field_spec.get("type")
        if path not in output:
            continue  # omitted on purpose via on_missing='omit'
        value = output[path]
        if value is None:
            continue  # null is always a valid 'missing' representation
        check = type_checks.get(expected_type)
        if check and not check(value):
            errors.append(f"field '{path}' expected type {expected_type}, got {type(value).__name__}")
    return errors


def validate_default(output):
    """Validate the default schema output: every top-level field must be present (value may be null)."""
    errors = []
    for field in DEFAULT_SCHEMA_FIELDS:
        if field not in output:
            errors.append(f"default schema missing required field '{field}'")
    return errors
