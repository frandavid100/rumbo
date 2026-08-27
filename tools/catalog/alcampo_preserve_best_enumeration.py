from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def score(report: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
    """Rank one *single-run* enumeration audit without hiding partial failures.

    Completeness wins outright. Before completeness is achieved, prefer the run
    that successfully traversed the most scheduled root shards; then use total
    roots observed, unique first-party products, fewer failed roots, and deeper
    recursive coverage as deterministic tie breakers.

    The cumulative union used by the fast-detail workflow is intentionally a
    separate concept: it is the widest observed SKU inventory, not proof that a
    single category-tree traversal completed.
    """
    seen = as_int(report.get("root_shards_seen"))
    failed = as_int(report.get("root_shards_failed"))
    successful = max(0, seen - failed)
    unique = as_int(report.get("unique_products_after_dedup"))
    nodes = as_int(report.get("recursive_category_nodes_visited"))
    complete = 1 if report.get("complete_enumeration") is True else 0
    return (complete, successful, seen, unique, -failed, nodes)


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--candidate-report", type=Path, required=True)
    p.add_argument("--candidate-summary", type=Path, required=True)
    p.add_argument("--best-report", type=Path, required=True)
    p.add_argument("--best-summary", type=Path, required=True)
    p.add_argument("--observed-report", type=Path)
    p.add_argument("--observed-summary", type=Path)
    args = p.parse_args()

    candidate = read_json(args.candidate_report)
    if not candidate:
        raise SystemExit("Candidate enumeration report is missing or invalid")
    candidate_score = score(candidate)
    previous = read_json(args.best_report)
    previous_score = score(previous) if previous else (-1, -1, -1, -1, -10**9, -1)

    # Preserve the literal most recent observation separately, so a transient
    # partial run remains auditable without being allowed to lower the high-water
    # report that humans and downstream checks normally inspect.
    if args.observed_report:
        args.observed_report.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.candidate_report, args.observed_report)
    if args.observed_summary:
        args.observed_summary.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.candidate_summary, args.observed_summary)

    selected = "previous"
    if not previous or candidate_score > previous_score:
        args.best_report.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.candidate_report, args.best_report)
        shutil.copyfile(args.candidate_summary, args.best_summary)
        selected = "candidate"

    result = {
        "selected": selected,
        "candidate_score": candidate_score,
        "previous_score": previous_score,
        "candidate_unique_products": as_int(candidate.get("unique_products_after_dedup")),
        "candidate_root_shards_seen": as_int(candidate.get("root_shards_seen")),
        "candidate_root_shards_failed": as_int(candidate.get("root_shards_failed")),
        "candidate_complete": candidate.get("complete_enumeration") is True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
