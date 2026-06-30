# Multi-Source Candidate Data Transformer — Technical Design

## Overview

This project transforms messy candidate information from multiple sources into a single trusted canonical candidate profile. The pipeline supports structured input (recruiter CSV) and unstructured input (resume PDFs), performs normalization, merges duplicate candidates, tracks provenance, assigns confidence scores, and generates configurable outputs.

## Pipeline Design

The pipeline follows six stages:

### 1. Ingest & Extract

The system detects input sources and routes them to source-specific extractors. CSV and resume PDF inputs are converted into partial candidate records. Invalid or missing sources are handled gracefully without stopping the pipeline.

### 2. Normalize

Extracted data is standardized before merging:

- Phone numbers → E.164 format
- Dates → YYYY-MM format
- Country → ISO 3166-1 alpha-2 format
- Skills → canonical skill names using alias mapping (example: JS → JavaScript)

### 3. Merge & Conflict Resolution

Candidate records are matched using:

1. Normalized email match
2. Fallback using normalized name + phone

Conflict handling follows source reliability:

- Structured sources are preferred for contact information such as email and phone.
- Resume data is preferred for skills and experience details.

False merges are avoided when confidence is low.

### 4. Confidence & Provenance

Every extracted value maintains:

- Source information
- Extraction method
- Confidence score

Confidence is calculated using source reliability, extraction certainty, and agreement between multiple sources.

## Canonical Profile Schema

The internal canonical profile contains:

- candidate_id
- full_name
- emails
- phones
- location
- links
- headline
- years_experience
- skills
- experience
- education
- provenance
- overall_confidence

The canonical profile acts as the single source of truth for all outputs.

## Runtime Configurable Output

The system separates the internal canonical record from the output projection layer.

Runtime configuration supports:

- Selecting required fields
- Renaming fields
- Applying field-level normalization
- Handling missing values using null, omit, or error strategies

This allows different output formats without modifying pipeline logic.

## Validation

Generated outputs are validated before returning results to ensure:

- Required fields exist
- Data types are correct
- Output follows the requested schema

## Edge Cases Handled

The pipeline handles:

- Missing or corrupted input files → safely skipped
- Duplicate candidate records → merged using matching rules
- Conflicting information → resolved using source priority
- Unreadable/scanned resumes → extraction failure without pipeline crash
- Invalid phone/email values → stored as null instead of guessing
- Unknown skills → retained with reduced confidence

## Design Decisions & Scope

The design prioritizes deterministic and explainable transformations. The pipeline keeps unknown values empty instead of inventing data because incorrect confident information is worse than missing information.

Under time constraints, the following were descoped:

- ML-based fuzzy candidate matching
- LinkedIn/GitHub API integration
- Full UI development

A CLI interface is used as the input/output layer since interface polish was lower priority than pipeline correctness.