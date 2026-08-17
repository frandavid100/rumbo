from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable


EXTRACTOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class TextExtraction:
    text: str
    confidence: float
    engine: str
    engine_version: str | None
    language: str


class ExtractionError(RuntimeError):
    pass


def _default_runner(args: list[str], input_path: str) -> tuple[str, str]:
    completed = subprocess.run(
        args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout, completed.stderr


def _tesseract_version() -> str | None:
    binary = shutil.which("tesseract")
    if not binary:
        return None
    try:
        out = subprocess.run([binary, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout
        return out.splitlines()[0].strip()
    except Exception:
        return None


def extract_with_tesseract(
    image_path: str | Path,
    *,
    language: str = "spa",
    psm: int = 6,
    runner: Callable[[list[str], str], tuple[str, str]] = _default_runner,
) -> TextExtraction:
    """Extract text from a pack-label image using build-time Tesseract.

    This is deliberately outside Android/runtime. The nutritional parser remains
    authoritative: OCR output is only a proposal and never becomes DECLARED
    unless the deterministic label reader validates basis, core macros and
    energy coherence.
    """
    path = Path(image_path)
    if not path.is_file():
        raise ExtractionError(f"Image not found: {path}")
    binary = shutil.which("tesseract") or "tesseract"
    args = [binary, str(path), "stdout", "-l", language, "--psm", str(psm), "tsv"]
    try:
        tsv, _ = runner(args, str(path))
    except Exception as exc:
        raise ExtractionError(f"Tesseract failed: {exc}") from exc

    words: list[str] = []
    confidences: list[float] = []
    lines: dict[tuple[str, str, str, str], list[tuple[int, str]]] = {}
    for index, raw in enumerate(tsv.splitlines()):
        if index == 0 or not raw.strip():
            continue
        cols = raw.split("\t")
        if len(cols) < 12:
            continue
        text = cols[11].strip()
        if not text:
            continue
        try:
            conf = float(cols[10])
        except ValueError:
            conf = -1.0
        if conf >= 0:
            confidences.append(conf)
        key = (cols[2], cols[3], cols[4], cols[5])
        try:
            word_num = int(cols[5])
        except ValueError:
            word_num = len(lines.get(key, []))
        lines.setdefault(key, []).append((word_num, text))
        words.append(text)

    ordered_lines = [
        " ".join(text for _, text in sorted(parts))
        for _, parts in sorted(lines.items())
        if parts
    ]
    text = "\n".join(ordered_lines).strip()
    confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
    return TextExtraction(
        text=text,
        confidence=max(0.0, min(1.0, confidence)),
        engine="tesseract",
        engine_version=_tesseract_version(),
        language=language,
    )
