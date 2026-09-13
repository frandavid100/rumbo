from __future__ import annotations

from pathlib import Path


path = Path(__file__).with_name("summarize_mercadona_ocr_run_union.py")
text = path.read_text(encoding="utf-8")

old = "import math\nfrom collections import Counter, defaultdict\n"
new = "import math\nfrom collections import Counter, defaultdict\nfrom datetime import datetime, timezone\n"
if old not in text:
    raise SystemExit("import anchor not found")
text = text.replace(old, new, 1)

anchor = "\n\ndef complete_nutrition(value: Any) -> dict[str, float] | None:\n"
helper = '''

def _parse_evidence_created_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _format_evidence_created_at(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_artifact_created_at(tsv: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not tsv.exists():
        return out
    for line in tsv.read_text(encoding="utf-8").splitlines():
        parts = line.split("\\t")
        if len(parts) < 5:
            continue
        run_id, _run_name, artifact_id, _artifact_name, created_at = parts[:5]
        parsed = _parse_evidence_created_at(created_at)
        if not run_id.isdigit() or not artifact_id.isdigit() or parsed is None:
            raise ValueError(f"invalid artifact chronology row: {line!r}")
        key = f"{run_id}-{artifact_id}"
        normalized = _format_evidence_created_at(parsed)
        prior = out.get(key)
        if prior is not None and prior != normalized:
            raise ValueError(f"conflicting artifact chronology for {key}: {prior} vs {normalized}")
        out[key] = normalized or created_at
    return out
'''
if anchor not in text:
    raise SystemExit("complete_nutrition anchor not found")
text = text.replace(anchor, helper + anchor, 1)

start = text.index("Observation = (\n")
end = text.index("\n\ndef _identity_meta(", start)
observation_block = '''Observation = (
    tuple[int, str, str, Any]
    | tuple[int, str, str, Any, bool]
    | tuple[int, str, str, Any, bool, Any]
    | tuple[int, str, str, Any, bool, Any, Any]
)
'''
text = text[:start] + observation_block + text[end:]

start = text.index("def reconcile_latest_observations(\n")
end = text.index("\n\ndef main() -> int:", start)
reconcile = r'''def reconcile_latest_observations(
    observations: Iterable[Observation],
) -> dict[str, dict[str, Any]]:
    """Return one conservative latest persisted live OCR state per product.

    Legacy four/five/six-item observations use numeric run-id ordering so existing
    callers remain deterministic. Production passes seven items, adding the GitHub
    artifact ``created_at`` timestamp. That persisted evidence timestamp is the
    canonical chronology because a rerun keeps its original workflow run id while
    producing a genuinely newer artifact. Product identity is anchored to the EAN
    in the earliest persisted evidence batch under the same chronology.
    """
    grouped: dict[
        str,
        list[tuple[int, str, Any, bool, str | None, bool, datetime | None, bool]],
    ] = defaultdict(list)

    for observation in observations:
        if len(observation) == 4:
            run_id, product_id, status, nutrition = observation
            strict_provenance = True
            ean = None
            identity_enforced = False
            evidence_created_at = None
            chronology_enforced = False
        elif len(observation) == 5:
            run_id, product_id, status, nutrition, strict_provenance = observation
            ean = None
            identity_enforced = False
            evidence_created_at = None
            chronology_enforced = False
        elif len(observation) == 6:
            run_id, product_id, status, nutrition, strict_provenance, raw_ean = observation
            ean = normalize_ean(raw_ean)
            identity_enforced = True
            evidence_created_at = None
            chronology_enforced = False
        elif len(observation) == 7:
            run_id, product_id, status, nutrition, strict_provenance, raw_ean, raw_created_at = observation
            ean = normalize_ean(raw_ean)
            identity_enforced = True
            evidence_created_at = _parse_evidence_created_at(raw_created_at)
            if evidence_created_at is None:
                raise ValueError(
                    f"invalid persisted evidence created_at for product {product_id}: {raw_created_at!r}"
                )
            chronology_enforced = True
        else:
            raise ValueError("observations must contain 4, 5, 6 or 7 values")
        if status not in VALID:
            continue
        grouped[str(product_id)].append(
            (
                int(run_id), status, nutrition, bool(strict_provenance), ean,
                identity_enforced, evidence_created_at, chronology_enforced,
            )
        )

    result: dict[str, dict[str, Any]] = {}
    for product_id, records in grouped.items():
        chronology_modes = {record[7] for record in records}
        if len(chronology_modes) != 1:
            result[product_id] = {
                "latest_run_id": max(record[0] for record in records),
                "latest_evidence_created_at": None,
                "status": "IDENTITY_UNRESOLVED",
                "latest_run_statuses": sorted({record[1] for record in records}),
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": "MIXED_EVIDENCE_CHRONOLOGY",
                **_identity_meta(enforced=any(record[5] for record in records), ean=None),
            }
            continue

        chronology_enforced = next(iter(chronology_modes))
        by_batch: dict[
            Any,
            list[tuple[int, str, Any, bool, str | None, bool, datetime | None, bool]],
        ] = defaultdict(list)
        for record in records:
            batch = record[6] if chronology_enforced else record[0]
            by_batch[batch].append(record)

        def batch_meta(
            batch: Any,
            values: list[tuple[int, str, Any, bool, str | None, bool, datetime | None, bool]],
        ) -> tuple[int, str | None]:
            return (
                max(value[0] for value in values),
                _format_evidence_created_at(batch) if chronology_enforced else None,
            )

        identity_enforced = any(record[5] for record in records)
        filtered_by_batch = by_batch
        identity = _identity_meta(enforced=False, ean=None)

        if identity_enforced:
            earliest_batch = min(by_batch)
            earliest_values = [value for value in by_batch[earliest_batch] if value[5]]
            earliest_eans = {value[4] for value in earliest_values if value[4] is not None}
            earliest_has_unverified = any(value[4] is None for value in earliest_values)
            if earliest_has_unverified or len(earliest_eans) != 1:
                earliest_run_id, earliest_created_at = batch_meta(
                    earliest_batch, earliest_values or by_batch[earliest_batch]
                )
                result[product_id] = {
                    "latest_run_id": earliest_run_id,
                    "latest_evidence_created_at": earliest_created_at,
                    "status": "IDENTITY_UNRESOLVED",
                    "latest_run_statuses": sorted({value[1] for value in earliest_values}),
                    "usable_complete": False,
                    "nutrition": None,
                    "nutrition_issue": "AMBIGUOUS_EARLIEST_EAN_ANCHOR",
                    **_identity_meta(enforced=True, ean=None),
                }
                continue

            anchor_ean = next(iter(earliest_eans))
            conflict_runs: set[int] = set()
            conflict_eans: set[str] = set()
            unverified_runs: set[int] = set()
            filtered: dict[
                Any,
                list[tuple[int, str, Any, bool, str | None, bool, datetime | None, bool]],
            ] = defaultdict(list)
            for batch, values in by_batch.items():
                for value in values:
                    run_id, _status, _nutrition, _strict, ean, enforced, _created_at, _chrono = value
                    if not enforced or ean is None:
                        unverified_runs.add(run_id)
                        continue
                    if ean != anchor_ean:
                        conflict_runs.add(run_id)
                        conflict_eans.add(ean)
                        continue
                    filtered[batch].append(value)
            filtered_by_batch = dict(filtered)
            identity = _identity_meta(
                enforced=True,
                ean=anchor_ean,
                conflict_runs=conflict_runs,
                conflict_eans=conflict_eans,
                unverified_runs=unverified_runs,
            )

        if not filtered_by_batch:
            earliest_batch = min(by_batch)
            earliest_run_id, earliest_created_at = batch_meta(earliest_batch, by_batch[earliest_batch])
            result[product_id] = {
                "latest_run_id": earliest_run_id,
                "latest_evidence_created_at": earliest_created_at,
                "status": "IDENTITY_UNRESOLVED",
                "latest_run_statuses": [],
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": "NO_IDENTITY_VERIFIED_OBSERVATION",
                **identity,
            }
            continue

        latest_batch = max(filtered_by_batch)
        values = filtered_by_batch[latest_batch]
        latest_run_id, latest_created_at = batch_meta(latest_batch, values)
        statuses = {value[1] for value in values}
        if len(statuses) != 1:
            result[product_id] = {
                "latest_run_id": latest_run_id,
                "latest_evidence_created_at": latest_created_at,
                "status": "MULTIPLE_STATUSES_LATEST_RUN",
                "latest_run_statuses": sorted(statuses),
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": "MULTIPLE_STATUSES_LATEST_RUN",
                **identity,
            }
            continue

        status = next(iter(statuses))
        if status != "DECLARED":
            result[product_id] = {
                "latest_run_id": latest_run_id,
                "latest_evidence_created_at": latest_created_at,
                "status": status,
                "latest_run_statuses": [status],
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": None,
                **identity,
            }
            continue

        if any(not value[3] for value in values):
            result[product_id] = {
                "latest_run_id": latest_run_id,
                "latest_evidence_created_at": latest_created_at,
                "status": "DECLARED",
                "latest_run_statuses": ["DECLARED"],
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": "INCOMPLETE_STRICT_PROVENANCE_LATEST_RUN",
                **identity,
            }
            continue

        normalized = [complete_nutrition(value[2]) for value in values]
        if any(item is None for item in normalized):
            result[product_id] = {
                "latest_run_id": latest_run_id,
                "latest_evidence_created_at": latest_created_at,
                "status": "DECLARED",
                "latest_run_statuses": ["DECLARED"],
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": "INCOMPLETE_DECLARED_NUTRITION_LATEST_RUN",
                **identity,
            }
            continue
        complete_values = [item for item in normalized if item is not None]
        if len({nutrition_key(item) for item in complete_values}) != 1:
            result[product_id] = {
                "latest_run_id": latest_run_id,
                "latest_evidence_created_at": latest_created_at,
                "status": "DECLARED",
                "latest_run_statuses": ["DECLARED"],
                "usable_complete": False,
                "nutrition": None,
                "nutrition_issue": "CONFLICTING_COMPLETE_NUTRITION_LATEST_RUN",
                **identity,
            }
            continue
        result[product_id] = {
            "latest_run_id": latest_run_id,
            "latest_evidence_created_at": latest_created_at,
            "status": "DECLARED",
            "latest_run_statuses": ["DECLARED"],
            "usable_complete": True,
            "nutrition": complete_values[0],
            "nutrition_issue": None,
            **identity,
        }
    return result
'''
text = text[:start] + reconcile + text[end:]

old = "    observations: list[tuple[int, str, str, Any, bool, Any]] = []\n"
new = "    observations: list[tuple[int, str, str, Any, bool, Any, Any]] = []\n"
if old not in text:
    raise SystemExit("observations type anchor not found")
text = text.replace(old, new, 1)

old = (
    "    strict_provenance_failures: Counter[str] = Counter()\n\n"
    "    for path in sorted(Path(args.root).rglob(\"*.jsonl\")):\n"
)
new = (
    "    strict_provenance_failures: Counter[str] = Counter()\n"
    "    artifact_created_at = load_artifact_created_at(Path(args.artifacts_tsv))\n\n"
    "    for path in sorted(Path(args.root).rglob(\"*.jsonl\")):\n"
)
if old not in text:
    raise SystemExit("artifact chronology map anchor not found")
text = text.replace(old, new, 1)

old = "        run_id = first.split(\"-\", 1)[0]\n        if not run_id.isdigit():\n"
new = (
    "        run_id = first.split(\"-\", 1)[0]\n"
    "        evidence_created_at = artifact_created_at.get(first)\n"
    "        if not run_id.isdigit():\n"
)
if old not in text:
    raise SystemExit("run id anchor not found")
text = text.replace(old, new, 1)

old = (
    "                observations.append((int(run_id), product_id, status, row.get(\"nutrition\"), strict, ean))\n"
)
new = (
    "                if evidence_created_at is None:\n"
    "                    raise SystemExit(f\"Missing artifact created_at chronology for {first}\")\n"
    "                observations.append((\n"
    "                    int(run_id), product_id, status, row.get(\"nutrition\"), strict, ean, evidence_created_at\n"
    "                ))\n"
)
if old not in text:
    raise SystemExit("observations append anchor not found")
text = text.replace(old, new, 1)

old = (
    "            \"latest_run_id\": item[\"latest_run_id\"],\n"
    "            \"nutrition\": item[\"nutrition\"],\n"
)
new = (
    "            \"latest_run_id\": item[\"latest_run_id\"],\n"
    "            \"latest_evidence_created_at\": item.get(\"latest_evidence_created_at\"),\n"
    "            \"nutrition\": item[\"nutrition\"],\n"
)
if old not in text:
    raise SystemExit("usable products anchor not found")
text = text.replace(old, new, 1)

old = (
    '            "Raw-live product identity is anchored to the unique EAN in the earliest persisted raw-live "\n'
    '            "OCR run for each product_id. Later rows with a missing or different EAN remain auditable "'
)
new = (
    '            "Raw-live product identity is anchored to the unique EAN in the earliest persisted raw-live "\n'
    '            "OCR artifact by GitHub artifact creation time for each product_id; numeric workflow run id is "\n'
    '            "not used as freshness because reruns retain the original run id. Later rows with a missing or "\n'
    '            "different EAN remain auditable "'
)
if old not in text:
    raise SystemExit("policy anchor not found")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print(f"patched {path}")
