from __future__ import annotations

"""Geometry-only helpers for conservative nutrition-table diagnostics.

The canonical label parser intentionally rejects ambiguous multi-column OCR.  This
module does not weaken that policy: it only exposes Tesseract word boxes and finds
an *explicit* per-100-g/per-100-ml column header.  Consumers must fail closed when
that header is missing or ambiguous and must never choose a column from nutritional
plausibility alone.
"""

from dataclasses import dataclass
import csv
import io
import re
import subprocess
from pathlib import Path

GEOMETRY_VERSION = "1.0.0"


@dataclass(frozen=True)
class TsvToken:
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int
    block_num: int
    par_num: int
    line_num: int
    word_num: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def center_x(self) -> float:
        return self.left + self.width / 2.0

    @property
    def center_y(self) -> float:
        return self.top + self.height / 2.0

    @property
    def line_key(self) -> tuple[int, int, int]:
        return (self.block_num, self.par_num, self.line_num)


@dataclass(frozen=True)
class BasisHeader:
    basis: str
    left: int
    right: int
    top: int
    bottom: int
    line_key: tuple[int, int, int]
    text: str

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2.0


_HEADER_COMPACT_RE = re.compile(r"^100(?:g|gr|ml)$", re.IGNORECASE)


def _compact_token(text: str) -> str:
    return re.sub(r"[^0-9a-záéíóúüñ]+", "", text.casefold())


def parse_tesseract_tsv(raw_tsv: str) -> list[TsvToken]:
    """Parse word-level Tesseract TSV, preserving text and geometry only."""
    reader = csv.DictReader(io.StringIO(raw_tsv), delimiter="\t")
    required = {
        "level", "block_num", "par_num", "line_num", "word_num",
        "left", "top", "width", "height", "conf", "text",
    }
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise ValueError("invalid Tesseract TSV header")

    tokens: list[TsvToken] = []
    for row in reader:
        if str(row.get("level") or "").strip() != "5":
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        try:
            token = TsvToken(
                text=text,
                confidence=float(row["conf"]),
                left=int(row["left"]),
                top=int(row["top"]),
                width=int(row["width"]),
                height=int(row["height"]),
                block_num=int(row["block_num"]),
                par_num=int(row["par_num"]),
                line_num=int(row["line_num"]),
                word_num=int(row["word_num"]),
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"invalid Tesseract TSV word row: {row!r}") from exc
        tokens.append(token)
    return tokens


def _lines(tokens: list[TsvToken]) -> list[list[TsvToken]]:
    grouped: dict[tuple[int, int, int], list[TsvToken]] = {}
    for token in tokens:
        grouped.setdefault(token.line_key, []).append(token)
    lines = []
    for line in grouped.values():
        lines.append(sorted(line, key=lambda token: (token.left, token.word_num)))
    return sorted(lines, key=lambda line: (min(t.top for t in line), min(t.left for t in line)))


def _basis_from_compact(compact: str) -> str | None:
    if compact in {"100g", "100gr"}:
        return "100_g"
    if compact == "100ml":
        return "100_ml"
    return None


def find_explicit_basis_headers(tokens: list[TsvToken]) -> list[BasisHeader]:
    """Find explicit 100 g/100 ml headers without interpreting nearby values.

    Headers may be one token (``100g``) or two adjacent tokens (``100`` ``g``).
    A caller may use geometry only if exactly one candidate remains.  We do not
    rank candidates by macro values, energy coherence or physical plausibility.
    """
    headers: list[BasisHeader] = []
    for line in _lines(tokens):
        for index, token in enumerate(line):
            compact = _compact_token(token.text)
            if _HEADER_COMPACT_RE.fullmatch(compact):
                basis = _basis_from_compact(compact)
                if basis:
                    headers.append(BasisHeader(
                        basis=basis,
                        left=token.left,
                        right=token.right,
                        top=token.top,
                        bottom=token.bottom,
                        line_key=token.line_key,
                        text=token.text,
                    ))
                    continue

            if compact != "100" or index + 1 >= len(line):
                continue
            unit = line[index + 1]
            unit_compact = _compact_token(unit.text)
            basis = _basis_from_compact("100" + unit_compact)
            if basis is None:
                continue
            # Require visual adjacency as well as token adjacency.  This prevents
            # pairing a lone "100" with a far-away serving-column unit.
            horizontal_gap = max(0, unit.left - token.right)
            max_gap = max(12, round(max(token.height, unit.height) * 1.5))
            vertical_overlap = min(token.bottom, unit.bottom) - max(token.top, unit.top)
            if horizontal_gap > max_gap or vertical_overlap <= 0:
                continue
            headers.append(BasisHeader(
                basis=basis,
                left=min(token.left, unit.left),
                right=max(token.right, unit.right),
                top=min(token.top, unit.top),
                bottom=max(token.bottom, unit.bottom),
                line_key=token.line_key,
                text=f"{token.text} {unit.text}",
            ))
    return headers


def unique_basis_header(tokens: list[TsvToken]) -> tuple[str, BasisHeader | None]:
    headers = find_explicit_basis_headers(tokens)
    if not headers:
        return "MISSING_EXPLICIT_100_BASIS_HEADER", None
    if len(headers) != 1:
        return "AMBIGUOUS_EXPLICIT_100_BASIS_HEADER", None
    return "UNIQUE_EXPLICIT_100_BASIS_HEADER", headers[0]


def run_tesseract_tsv(
    image_path: str | Path,
    *,
    language: str = "spa",
    psm: int = 6,
    timeout_seconds: int = 90,
) -> list[TsvToken]:
    if psm not in {4, 6, 11, 12}:
        raise ValueError(f"unsupported Tesseract psm: {psm}")
    command = [
        "tesseract", str(Path(image_path)), "stdout",
        "-l", language, "--psm", str(psm), "tsv",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Tesseract TSV extraction failed: {exc}") from exc
    return parse_tesseract_tsv(completed.stdout)


def geometry_lines(tokens: list[TsvToken]) -> list[dict[str, object]]:
    """Return compact auditable OCR line geometry for diagnostic artifacts."""
    output: list[dict[str, object]] = []
    for line in _lines(tokens):
        output.append({
            "line_key": list(line[0].line_key),
            "text": " ".join(token.text for token in line),
            "tokens": [
                {
                    "text": token.text,
                    "confidence": token.confidence,
                    "left": token.left,
                    "top": token.top,
                    "width": token.width,
                    "height": token.height,
                }
                for token in line
            ],
        })
    return output
