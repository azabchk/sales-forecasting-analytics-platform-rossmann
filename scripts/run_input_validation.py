#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from validation import build_console_summary, load_input_contract, validate_csv_file, write_json_report
from validation import (
    build_unification_console_summary,
    unify_validated_dataframe,
    write_unification_manifest,
    write_unified_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pre-ETL input contract validation on a CSV file")
    parser.add_argument("--file", required=True, help="Path to input CSV file")
    parser.add_argument("--profile", required=True, help="Contract profile name (e.g., rossmann_train)")
    parser.add_argument(
        "--contract",
        default="config/input_contract/contract_v1.yaml",
        help="Path to versioned input contract YAML",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output JSON report path (default: validation_reports/<file>_<timestamp>.json)",
    )
    parser.add_argument(
        "--emit-unified",
        action="store_true",
        help="Emit unified canonical CSV + unification manifest when validation is PASS/WARN",
    )
    parser.add_argument(
        "--unified-output",
        default=None,
        help="Output path for unified CSV (default: validation_reports/<file>_unified_<timestamp>.csv)",
    )
    parser.add_argument(
        "--manifest-output",
        default=None,
        help="Output path for unification manifest JSON (default: validation_reports/<file>_manifest_<timestamp>.json)",
    )
    args = parser.parse_args()

    contract = load_input_contract(PROJECT_ROOT / args.contract)
    result = validate_csv_file(
        file_path=PROJECT_ROOT / args.file,
        contract=contract,
        profile_name=args.profile,
    )

    print(build_console_summary(result.report))

    if args.output:
        report_path = write_json_report(result.report, PROJECT_ROOT / args.output)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        default_path = PROJECT_ROOT / "validation_reports" / f"{Path(args.file).stem}_{timestamp}.json"
        report_path = write_json_report(result.report, default_path)

    print(f"\nJSON report saved to: {report_path}")

    if args.emit_unified:
        if result.report["status"] == "FAIL":
            print("\nUnification skipped: validation status is FAIL.")
            return 1

        unification_result = unify_validated_dataframe(
            validation_result=result,
            contract=contract,
            profile_name=args.profile,
            source_file_name=Path(args.file).name,
        )

        if args.unified_output:
            unified_path = write_unified_csv(unification_result.unified_dataframe, PROJECT_ROOT / args.unified_output)
        else:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            unified_default = PROJECT_ROOT / "validation_reports" / f"{Path(args.file).stem}_unified_{timestamp}.csv"
            unified_path = write_unified_csv(unification_result.unified_dataframe, unified_default)

        if args.manifest_output:
            manifest_path = write_unification_manifest(unification_result.manifest, PROJECT_ROOT / args.manifest_output)
        else:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            manifest_default = PROJECT_ROOT / "validation_reports" / f"{Path(args.file).stem}_manifest_{timestamp}.json"
            manifest_path = write_unification_manifest(unification_result.manifest, manifest_default)

        print()
        print(build_unification_console_summary(unification_result.manifest))
        print(f"\nUnified CSV saved to: {unified_path}")
        print(f"Unification manifest saved to: {manifest_path}")

    return 0 if result.report["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
