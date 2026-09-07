from pathlib import Path


path = Path(__file__).with_name("nutrition_label_reader.py")
text = path.read_text()

old_version = 'READER_VERSION = "1.4.8"'
new_version = 'READER_VERSION = "1.4.9"'
if text.count(old_version) != 1:
    raise SystemExit("expected exactly one reader version 1.4.8 marker")

function_start = text.index("def _fat_value(")
function_end = text.index("\ndef _interleaved_carbohydrate", function_start)
block = text[function_start:function_end]
anchor = "            tail = folded[label_match.end():label_match.end() + 90]\n"
if block.count(anchor) != 1:
    raise SystemExit(f"expected one _fat_value tail anchor, got {block.count(anchor)}")

repair = '''            # EasyOCR can linearise a printed total-fat `0 g` cell as the
            # standalone token `09` immediately *before* `Grasas`, while the
            # saturated-fat subrow remains immediately after the label. Accept
            # that reversed value only under this exact three-row structure.
            # This deliberately does not rewrite arbitrary `09` tokens.
            if re.match(
                r"\\s*de\\s*las\\s+cuales\\s*:?\\s*\\n"
                r"\\s*(?:[<>]?\\s*\\d{1,3}(?:\\.\\d{1,2})?\\s*(?:g|q|yg|y)|0\\s*9)\\s*\\n"
                r"\\s*[-–—]?\\s*(?:saturad|baturad)",
                tail,
                flags=re.I,
            ):
                return before
'''

block = block.replace(anchor, anchor + repair, 1)
text = text[:function_start] + block + text[function_end:]
text = text.replace(old_version, new_version, 1)
path.write_text(text)
