from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
from typing import Callable

try:
    from PIL import Image, ImageEnhance, ImageOps
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Pillow is required for nutrition table region detection") from exc

DETECTOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class OCRWord:
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass(frozen=True)
class RegionCandidate:
    name: str
    box: tuple[int, int, int, int]
    marker_kinds: tuple[str, ...]
    marker_count: int
    confidence: float
    path: Path


class RegionDetectionError(RuntimeError):
    pass


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFD", value.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


MARKERS = {
    "energy": ("kcal", "energetico", "energia"),
    "fat": ("grasas", "grasa"),
    "carb": ("hidratos", "carbohidratos"),
    "protein": ("proteinas", "proteina"),
    "basis": ("100",),
    "salt": ("sal",),
}


def _marker_kind(text: str) -> str | None:
    folded = _fold(text)
    folded = re.sub(r"[^a-z0-9]+", "", folded)
    for kind, values in MARKERS.items():
        if any(value in folded for value in values):
            return kind
    return None


def _default_runner(args: list[str], input_path: str) -> str:
    return subprocess.run(
        args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    ).stdout


def extract_words(
    image_path: str | Path,
    *, language: str = "spa", psm: int = 11,
    runner: Callable[[list[str], str], str] = _default_runner,
) -> list[OCRWord]:
    path = Path(image_path)
    binary = shutil.which("tesseract") or "tesseract"
    args = [binary, str(path), "stdout", "-l", language, "--psm", str(psm), "tsv"]
    try:
        tsv = runner(args, str(path))
    except Exception as exc:
        raise RegionDetectionError(f"Tesseract region scan failed: {exc}") from exc
    words: list[OCRWord] = []
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
            conf = float(cols[10]) / 100.0
            left, top, width, height = map(int, cols[6:10])
        except ValueError:
            continue
        if conf < .35 or width <= 0 or height <= 0:
            continue
        words.append(OCRWord(text, conf, left, top, width, height))
    return words


def _expand(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    l, t, r, b = box
    pad_x = max(40, int((r - l) * .35))
    pad_y = max(50, int((b - t) * .45))
    return max(0, l-pad_x), max(0, t-pad_y), min(width, r+pad_x), min(height, b+pad_y)


def _candidate_windows(words: list[OCRWord], image_width: int, image_height: int):
    markers = [(w, _marker_kind(w.text)) for w in words]
    markers = [(w, kind) for w, kind in markers if kind]
    if len(markers) < 2:
        return []

    windows = []
    # Tables usually place marker labels in a compact vertical band. Build a
    # window around every marker and collect nearby markers/text without assuming
    # a fixed place on the package.
    radius_y = int(image_height * .23)
    radius_x = int(image_width * .38)
    for anchor, _ in markers:
        nearby_markers = [
            (w, kind) for w, kind in markers
            if abs((w.top + w.height/2) - (anchor.top + anchor.height/2)) <= radius_y
            and abs((w.left + w.width/2) - (anchor.left + anchor.width/2)) <= radius_x
        ]
        kinds = {kind for _, kind in nearby_markers}
        if len(kinds) < 2:
            continue
        ml = min(w.left for w, _ in nearby_markers)
        mt = min(w.top for w, _ in nearby_markers)
        mr = max(w.right for w, _ in nearby_markers)
        mb = max(w.bottom for w, _ in nearby_markers)
        box = _expand((ml, mt, mr, mb), image_width, image_height)
        # Pull in nearby non-marker words so the crop includes numeric columns.
        l, t, r, b = box
        inside = [w for w in words if w.right >= l and w.left <= r and w.bottom >= t and w.top <= b]
        if inside:
            l = min(w.left for w in inside); t = min(w.top for w in inside)
            r = max(w.right for w in inside); b = max(w.bottom for w in inside)
            box = _expand((l, t, r, b), image_width, image_height)
        confidence = sum(w.confidence for w, _ in nearby_markers) / len(nearby_markers)
        score = (len(kinds), len(nearby_markers), confidence)
        windows.append((score, box, tuple(sorted(kinds))))

    deduped = []
    for score, box, kinds in sorted(windows, reverse=True):
        l, t, r, b = box
        duplicate = False
        for _, existing, _ in deduped:
            el, et, er, eb = existing
            inter = max(0, min(r, er)-max(l, el)) * max(0, min(b, eb)-max(t, et))
            area = max(1, (r-l)*(b-t))
            if inter / area > .70:
                duplicate = True
                break
        if not duplicate:
            deduped.append((score, box, kinds))
        if len(deduped) >= 3:
            break
    return deduped


def detect_nutrition_regions(
    image_path: str | Path,
    output_dir: str | Path,
    *,
    word_extractor: Callable[[str | Path], list[OCRWord]] = extract_words,
) -> list[RegionCandidate]:
    source = Path(image_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    words = word_extractor(source)
    if not words:
        return []
    regions: list[RegionCandidate] = []
    with Image.open(source) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
        for index, (score, box, kinds) in enumerate(_candidate_windows(words, image.width, image.height)):
            crop = image.crop(box)
            # Text on packaging is often small. Upscaling a focused region is
            # materially different from generic whole-image cropping.
            scale = 2.0 if max(crop.size) < 2200 else 1.5
            crop = crop.resize((int(crop.width*scale), int(crop.height*scale)), Image.Resampling.LANCZOS)
            gray = ImageOps.grayscale(crop)
            gray = ImageOps.autocontrast(gray, cutoff=1)
            gray = ImageEnhance.Contrast(gray).enhance(1.25)
            path = out / f"nutrition-region-{index}.png"
            gray.save(path)
            marker_count = score[1]
            regions.append(RegionCandidate(
                name=f"detected_region_{index}", box=box,
                marker_kinds=kinds, marker_count=marker_count,
                confidence=float(score[2]), path=path,
            ))
    return regions
