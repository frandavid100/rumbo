from pathlib import Path


path = Path(__file__).with_name("nutrition_label_reader.py")
text = path.read_text(encoding="utf-8")

old_version = 'READER_VERSION = "1.4.22"'
new_version = 'READER_VERSION = "1.4.23"'
new_marker = "When a dedicated gram cell sits immediately before `Proteínas`"

if new_version in text and new_marker in text:
    print("narrow protein/salt reversal fix already applied")
    raise SystemExit(0)

if text.count(old_version) != 1:
    raise SystemExit("reader version drift")

start_marker = "def _protein_value(label_patterns: tuple[str, ...], text: str) -> float | None:"
end_marker = "\n\ndef _interleaved_carbohydrate"
if text.count(start_marker) != 1 or text.count(end_marker) != 1:
    raise SystemExit("protein helper boundary drift")

start = text.index(start_marker)
end = text.index(end_marker, start)
old_block = text[start:end]
required_old_fragments = (
    "Do not borrow a salt cell as protein after a two-row OCR reversal.",
    "two consecutive",
    "head = folded[max(0, label_match.start() - 100):label_match.start()]",
)
if not all(fragment in old_block for fragment in required_old_fragments):
    raise SystemExit("protein/salt reversal block drift")

new_block = """def _protein_value(label_patterns: tuple[str, ...], text: str) -> float | None:
    \"\"\"Do not borrow a reversed salt cell as protein.

    When a dedicated gram cell sits immediately before `Proteínas`, another
    dedicated gram cell sits immediately after it, and that forward cell is
    immediately followed by the standalone `Sal` row *without* its own following
    gram cell, the forward cell is structurally the reversed salt value rather
    than safe protein evidence. Returning None lets the existing single-reversed
    macro path expose the pre-label value only as REVIEW evidence, subject to
    whole-tuple energy coherence and later independent OCR-family corroboration.

    A conventional `... / Proteínas / 0.02 g / Sal / 0.05 g` layout is kept
    unchanged because the explicit value after `Sal` proves that 0.02 g belongs
    to protein. No numeric value is rewritten or inferred here.
    \"\"\"
    ordinary = _number_after(label_patterns, text)
    folded = _strip_ocr_unit_parentheses(_fold(text))
    cell = r"[<>]?\\s*\\d{1,3}(?:\\.\\d{1,2})?\\s*(?:g|9|q|yg|y)"
    for label in label_patterns:
        for label_match in re.finditer(label, folded, flags=re.I):
            before = _number_immediately_before((label,), text)
            if before is None:
                continue
            tail = folded[label_match.end():label_match.end() + 120]
            forward_then_salt = re.match(
                rf"\\s*{cell}\\s*\\n\\s*sal\\b",
                tail,
                flags=re.I,
            )
            if not forward_then_salt:
                continue
            after_salt = tail[forward_then_salt.end():]
            if re.match(
                rf"\\s*\\n?\\s*{cell}(?:\\s|$)",
                after_salt,
                flags=re.I,
            ):
                continue
            return None
    return ordinary
"""

text = text.replace(old_version, new_version, 1)
text = text[:start] + new_block + text[end:]
path.write_text(text, encoding="utf-8")
