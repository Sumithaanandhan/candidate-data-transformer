# Multi-Source Candidate Data Transformer

Eightfold Engineering Intern Assignment — Step 2 Implementation.

Builds one clean, canonical candidate profile from messy, multi-source input
(a recruiter CSV and resume PDFs), with normalization, deduplication,
provenance, and confidence scoring — and a runtime config layer that reshapes
the output without touching the pipeline code.

See `DESIGN.md` for the architecture overview, pipeline stages, merge policy, confidence strategy, and edge-case handling.

## Setup

```bash
pip install -r requirements.txt
```

## Run — default schema

```bash
python pipeline.py \
  --csv sources/recruiter_export.csv \
  --resumes sources/resume_aarav_sharma.pdf sources/resume_rohit_verma.pdf \
  --out output/default_output.json
```

## Run — custom output config

```bash
python pipeline.py \
  --csv sources/recruiter_export.csv \
  --resumes sources/resume_aarav_sharma.pdf sources/resume_rohit_verma.pdf \
  --config configs/custom_config.json \
  --out output/custom_output.json
```

`configs/custom_config.json` demonstrates field selection, renaming
(`primary_email` from `emails[0]`), per-field normalization (E.164 for phone,
canonical skill names), and `on_missing: "null"` behavior. Swap in your own
config to reshape the output differently — no code changes needed.

## Run tests

```bash
python -m pytest tests/ -v
```

## Project layout

```
extractors.py    Stage 1-2: ingest + extract (CSV, resume PDF)
normalize.py      Stage 3: per-field normalizers (phone, date, country, skill, email)
merge.py          Stage 4: candidate matching, conflict resolution, confidence
project.py        Stage 5-6: runtime config projection + validation
pipeline.py        CLI entry point wiring all stages together
sources/          Sample input files (recruiter CSV + 2 resume PDFs)
configs/          Runtime output config(s) + skill alias table
output/           Generated output JSON (committed as proof of a run)
tests/            pytest suite
```

## Sample inputs — intentional edge cases

The sample CSV and resumes were built to exercise the pipeline's robustness:

- **Exact duplicate row** (Aarav Sharma appears twice in the CSV) — verifies
  dedup/merge logic collapses it to one candidate.
- **Conflicting title** between CSV and resume for Aarav — verifies the
  conflict-resolution policy (resume wins for narrative fields).
- **Missing phone** (Rohit, in both CSV and resume) — verifies the field
  stays `null` rather than being guessed.
- **Malformed email/phone** (Sneha: `sneha.iyer@`, `98xx wrong`) — verifies
  garbage input is dropped, not silently accepted, and the run doesn't crash.
- **Skill alias** ("JS" in both resumes) — verifies canonicalization maps it
  to "JavaScript".

## Demo Video

A short walkthrough showing:
- pipeline execution
- default output generation
- custom config output
- robustness handling
- test execution

Video link:
https://drive.google.com/file/d/15KcQi1x7Z1IC_5DrGzglOC5-VD8-PB8n/view?usp=sharing

## Assumptions & what's descoped

- Default phone region is assumed to be India (`IN`) when a number has no
  country code, since the sample data is India-based. This is a configurable
  constant in `normalize.py`.
- Resume parsing uses heuristic section-header detection (`SUMMARY`,
  `SKILLS`, `EXPERIENCE`, `EDUCATION` in caps) rather than ML-based layout
  parsing — sufficient for the sample inputs but not robust to wildly
  different resume formats. Noted as a deliberate scope cut in the design doc.
- LinkedIn/GitHub API sources, fuzzy/ML name matching, and a UI were
  descoped per the assignment's stated lower priority on interface polish —
  CLI is the input/output surface.
- `location` fields are left null in the canonical schema since none of the
  chosen sample sources (CSV, resume) explicitly provide structured
  city/region/country — would be populated if a LinkedIn source were added.
