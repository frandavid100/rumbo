from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("opencv-python-headless and numpy are required for visual table detection") from exc

VISUAL_DETECTOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class VisualTableRegion:
    name: str
    box: tuple[int, int, int, int]
    score: float
    horizontal_lines: int
    vertical_lines: int
    line_density: float
    path: Path


def _line_count(mask: np.ndarray, *, horizontal: bool) -> int:
    if horizontal:
        projection = (mask > 0).sum(axis=1)
        threshold = max(20, int(mask.shape[1] * 0.22))
    else:
        projection = (mask > 0).sum(axis=0)
        threshold = max(20, int(mask.shape[0] * 0.22))
    active = projection >= threshold
    count = 0
    inside = False
    for value in active:
        if value and not inside:
            count += 1
            inside = True
        elif not value:
            inside = False
    return count


def _iou(a, b) -> float:
    al, at, ar, ab = a
    bl, bt, br, bb = b
    inter = max(0, min(ar, br) - max(al, bl)) * max(0, min(ab, bb) - max(at, bt))
    if inter <= 0:
        return 0.0
    aa = max(1, (ar-al)*(ab-at)); ba = max(1, (br-bl)*(bb-bt))
    return inter / float(aa + ba - inter)


def _prepare(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    norm = clahe.apply(gray)
    binary = cv2.adaptiveThreshold(norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 35, 13)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(18, gray.shape[1] // 45), 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(18, gray.shape[0] // 45)))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
    return binary, horizontal, vertical


def _candidate_boxes(binary: np.ndarray, horizontal: np.ndarray, vertical: np.ndarray):
    h, w = binary.shape[:2]
    line_mask = cv2.bitwise_or(horizontal, vertical)
    # Join nearby table lines into candidate blocks without relying on OCR words.
    join_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 120), max(15, h // 120)))
    joined = cv2.morphologyEx(line_mask, cv2.MORPH_CLOSE, join_kernel, iterations=2)
    joined = cv2.dilate(joined, join_kernel, iterations=1)
    contours, _ = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    image_area = float(w * h)
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cw * ch
        frac = area / image_area
        if frac < 0.012 or frac > 0.72:
            continue
        if cw < w * 0.12 or ch < h * 0.08:
            continue
        pad_x = max(18, int(cw * 0.16)); pad_y = max(18, int(ch * 0.18))
        l=max(0,x-pad_x); t=max(0,y-pad_y); r=min(w,x+cw+pad_x); b=min(h,y+ch+pad_y)
        hroi = horizontal[t:b, l:r]; vroi = vertical[t:b, l:r]; broi = binary[t:b, l:r]
        hlines = _line_count(hroi, horizontal=True)
        vlines = _line_count(vroi, horizontal=False)
        line_pixels = int(cv2.countNonZero(cv2.bitwise_or(hroi, vroi)))
        line_density = line_pixels / max(1.0, float((r-l)*(b-t)))
        ink_density = cv2.countNonZero(broi) / max(1.0, float((r-l)*(b-t)))
        # Nutrition tables often have many horizontal separators; vertical lines
        # are helpful but not mandatory because some labels are visually open.
        structural = min(1.0, hlines / 5.0) * 0.48 + min(1.0, vlines / 3.0) * 0.22
        density = min(1.0, line_density / 0.045) * 0.18 + min(1.0, ink_density / 0.18) * 0.12
        score = structural + density
        if hlines < 3 or score < 0.44:
            continue
        candidates.append((score, (l,t,r,b), hlines, vlines, line_density))

    candidates.sort(reverse=True, key=lambda x: x[0])
    deduped=[]
    for cand in candidates:
        if any(_iou(cand[1], existing[1]) > .58 for existing in deduped):
            continue
        deduped.append(cand)
        if len(deduped) >= 3:
            break
    return deduped


def _deskew_and_save(image: np.ndarray, box, output: Path) -> None:
    l,t,r,b = box
    crop = image[t:b, l:r]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Estimate text/table skew from long line segments. Small-angle correction is
    # intentionally conservative: large perspective distortions remain review.
    edges = cv2.Canny(gray, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=70,
                            minLineLength=max(40, crop.shape[1]//4), maxLineGap=16)
    angles=[]
    if lines is not None:
        for line in lines[:,0]:
            x1,y1,x2,y2 = map(int,line)
            if x2 == x1:
                continue
            angle = np.degrees(np.arctan2(y2-y1, x2-x1))
            if -20 <= angle <= 20:
                angles.append(float(angle))
    if angles:
        angle=float(np.median(angles))
        if abs(angle) >= .7:
            center=(crop.shape[1]/2, crop.shape[0]/2)
            matrix=cv2.getRotationMatrix2D(center, angle, 1.0)
            crop=cv2.warpAffine(crop, matrix, (crop.shape[1], crop.shape[0]),
                                flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    gray=cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray=cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8,8)).apply(gray)
    scale=2.0 if max(gray.shape[:2]) < 2200 else 1.45
    gray=cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(str(output), gray)


def detect_visual_table_regions(image_path: str | Path, output_dir: str | Path) -> list[VisualTableRegion]:
    source=Path(image_path); out=Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    image=cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        return []
    gray=cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary,horizontal,vertical=_prepare(gray)
    regions=[]
    for index,(score,box,hlines,vlines,density) in enumerate(_candidate_boxes(binary,horizontal,vertical)):
        path=out/f"visual-table-{index}.png"
        _deskew_and_save(image, box, path)
        regions.append(VisualTableRegion(
            name=f"visual_table_{index}", box=box, score=float(score),
            horizontal_lines=int(hlines), vertical_lines=int(vlines),
            line_density=float(density), path=path,
        ))
    return regions
