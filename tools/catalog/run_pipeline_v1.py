#!/usr/bin/env python3
"""Build and classify a canonical Rumbo catalogue.

This is the publication entry point for phase 1. A catalogue is never considered
ready after acquisition/normalisation alone: the formal classifier must run and
leave no open review item before the command succeeds.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build_catalog_v1.py"
CLASSIFY = HERE / "classify_catalog.py"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mercadona-fixture", required=True)
    p.add_argument("--off-fixture", required=True)
    p.add_argument("--secondary-fixture")
    p.add_argument("--generic-fixture")
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--evidence-dir", required=True)
    p.add_argument("--context", default="Valencia")
    args = p.parse_args()

    build = [
        sys.executable, str(BUILD),
        "--mercadona-fixture", args.mercadona_fixture,
        "--off-fixture", args.off_fixture,
        "--output", args.output,
        "--report", args.report,
        "--evidence-dir", args.evidence_dir,
        "--context", args.context,
    ]
    if args.secondary_fixture:
        build += ["--secondary-fixture", args.secondary_fixture]
    if args.generic_fixture:
        build += ["--generic-fixture", args.generic_fixture]
    run(build)
    run([sys.executable, str(CLASSIFY), args.output])

    con = sqlite3.connect(args.output)
    try:
        products = con.execute("SELECT count(*) FROM products").fetchone()[0]
        classified = con.execute(
            "SELECT count(*) FROM eligibility WHERE classified=1"
        ).fetchone()[0]
        eligible = con.execute(
            "SELECT count(*) FROM eligibility WHERE menu_eligible=1"
        ).fetchone()[0]
        review = con.execute(
            "SELECT count(*) FROM review_queue WHERE status='OPEN'"
        ).fetchone()[0]
        report = {
            "products": products,
            "classified": classified,
            "menu_eligible": eligible,
            "open_review_items": review,
            "nutritional_role_assignments": con.execute(
                "SELECT count(*) FROM nutritional_role_assignments"
            ).fetchone()[0],
            "culinary_role_assignments": con.execute(
                "SELECT count(*) FROM culinary_role_assignments"
            ).fetchone()[0],
        }
        Path(args.report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if review or classified != products:
            raise SystemExit(
                f"Catalogue blocked: {classified}/{products} classified; "
                f"{review} open review items"
            )
    finally:
        con.close()


if __name__ == "__main__":
    main()
