#!/usr/bin/env python3
"""
Multi-Source Candidate Data Transformer -- CLI entry point.

Usage:
    python pipeline.py --csv sources/recruiter_export.csv \\
                        --resumes sources/resume_aarav_sharma.pdf sources/resume_rohit_verma.pdf \\
                        --out output/default_output.json

    python pipeline.py --csv sources/recruiter_export.csv \\
                        --resumes sources/resume_aarav_sharma.pdf sources/resume_rohit_verma.pdf \\
                        --config configs/custom_config.json \\
                        --out output/custom_output.json
"""
import argparse
import json
import sys

from extractors import extract_csv, extract_resume
from merge import merge_records
from project import project_default, project_record, validate_default, validate_against_config


def run_pipeline(csv_paths, resume_paths, config=None):
    """Stages 1-4: ingest, extract, normalize (inside extractors/merge), merge."""
    partial_records = []

    for path in csv_paths:
        partial_records.extend(extract_csv(path))

    for path in resume_paths:
        partial_records.extend(extract_resume(path))

    if not partial_records:
        print("[WARN] no records extracted from any source -- check your input paths", file=sys.stderr)

    canonical_records = merge_records(partial_records)

    # Stages 5-6: project + validate, per record.
    results = []
    for record in canonical_records:
        if config:
            output, errors = project_record(record, config)
            errors += validate_against_config(output, config)
        else:
            output, errors = project_default(record)
            errors += validate_default(output)

        if errors:
            print(f"[WARN] validation issues for candidate {record.get('full_name')}: {errors}", file=sys.stderr)

        results.append(output)

    return results


def main():
    parser = argparse.ArgumentParser(description="Multi-Source Candidate Data Transformer")
    parser.add_argument("--csv", nargs="*", default=[], help="Recruiter CSV file(s)")
    parser.add_argument("--resumes", nargs="*", default=[], help="Resume PDF file(s)")
    parser.add_argument("--config", help="Path to a runtime output config JSON (omit for default schema)")
    parser.add_argument("--out", required=True, help="Path to write output JSON")
    args = parser.parse_args()

    config = None
    if args.config:
        with open(args.config) as f:
            config = json.load(f)

    results = run_pipeline(args.csv, args.resumes, config)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Wrote {len(results)} candidate profile(s) to {args.out}")


if __name__ == "__main__":
    main()
