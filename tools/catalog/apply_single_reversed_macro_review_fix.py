from pathlib import Path


path = Path(__file__).with_name("nutrition_label_reader.py")
text = path.read_text(encoding="utf-8")

old_version = 'READER_VERSION = "1.4.23"'
new_version = 'READER_VERSION = "1.4.24"'
new_marker = "Even when no dedicated gram cell is visible before `Proteínas`"

if new_version in text and new_marker in text:
    print("conservative protein/salt ambiguity fix already applied")
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
    "When a dedicated gram cell sits immediately before `Proteínas`",
    "before = _number_immediately_before((label,), text)",
    "if before is None:\n                continue",
)
if not all(fragment in old_block for fragment in required_old_fragments):
    raise SystemExit("protein/salt reversal block drift")

new_block = """def _protein_value(label_patterns: tuple[str, ...], text: str) -> float | None:
    \"\"\"Do not borrow an unpaired salt cell as protein.

    OCR can linearise the tail of a nutrition table as `Proteínas / 0.02 g /
    Sal` while omitting or moving the actual protein cell. If `Sal` has no own
    following gram cell, the value immediately after `Proteínas` is structurally
    ambiguous and is withheld rather than assigned to protein.

    Even when no dedicated gram cell is visible before `Proteínas`, this remains
    ambiguous: interleaved package text can separate the real protein value from
    its label. Returning None keeps the observation in REVIEW. When a dedicated
    pre-label protein cell is present, the existing single-reversed-macro path may
    expose that value only after whole-tuple energy coherence checks; this helper
    itself never rewrites or infers a number.

    A conventional `... / Proteínas / 0.02 g / Sal / 0.05 g` layout is kept
    unchanged because the explicit value after `Sal` proves that 0.02 g belongs
    to protein.
    \"\"\"
    ordinary = _number_after(label_patterns, text)
    folded = _strip_ocr_unit_parentheses(_fold(text))
    cell = r"[<>]?\\s*\\d{1,3}(?:\\.\\d{1,2})?\\s*(?:g|9|q|yg|y)"
    for label in label_patterns:
        for label_match in re.finditer(label, folded, flags=re.I):
            tail = folded[label_match.end():label_match.end() + 120]
            forward_then_salt = re.match(
                rf"\\s*{cell}\\s*\\n\\s*sal[ \\t]*(?=\\n|$)",
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
