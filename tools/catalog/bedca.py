from __future__ import annotations

import hashlib
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path


ENDPOINT = "https://www.bedca.net/bdpub/procquery.php"
USER_AGENT = "Rumbo-catalog-development/0.1 (contact: repository frandavid100/rumbo)"


@dataclass(frozen=True)
class BedcaGroup:
    id: str
    name_es: str
    name_en: str | None


@dataclass(frozen=True)
class BedcaIndexFood:
    id: str
    group_id: str
    name_es: str
    name_en: str | None
    origin: str | None
    langual: str | None


def _selection(*names: str) -> str:
    return "".join(f'<atribute name="{name}"/>' for name in names)


def groups_request() -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?><foodquery><type level="3"/>'
        f'<selection>{_selection("fg_id", "fg_ori_name", "fg_eng_name")}</selection>'
        '<order ordtype="ASC"><atribute3 name="fg_id"/></order></foodquery>'
    ).encode()


def group_request(group_id: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?><foodquery><type level="1"/>'
        f'<selection>{_selection("f_id", "f_ori_name", "f_eng_name", "langual", "f_origen")}</selection>'
        '<condition><cond1><atribute1 name="foodgroup_id"/></cond1><relation type="EQUAL"/>'
        f'<cond3>{group_id}</cond3></condition>'
        '<order ordtype="ASC"><atribute3 name="f_ori_name"/></order></foodquery>'
    ).encode()


DETAIL_FIELDS = (
    "f_id", "f_ori_name", "f_eng_name", "sci_name", "langual", "foodexcode",
    "mainlevelcode", "codlevel1", "namelevel1", "codsublevel", "codlevel2",
    "namelevel2", "f_des_esp", "f_des_ing", "photo", "edible_portion", "f_origen",
    "c_id", "c_ori_name", "c_eng_name", "eur_name", "componentgroup_id", "glos_esp",
    "best_location", "v_unit", "moex", "stdv", "min", "max", "v_n", "value_type",
    "mu_id", "mu_descripcion", "ref_id", "citation", "at_descripcion", "pt_descripcion",
    "method_id", "mt_descripcion", "m_descripcion", "m_nom_esp", "mhd_descripcion",
)


def detail_request(food_id: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?><foodquery><type level="2"/>'
        f'<selection>{_selection(*DETAIL_FIELDS)}</selection>'
        '<condition><cond1><atribute1 name="f_id"/></cond1><relation type="EQUAL"/>'
        f'<cond3>{food_id}</cond3></condition>'
        '<condition><cond1><atribute1 name="publico"/></cond1><relation type="EQUAL"/>'
        '<cond3>1</cond3></condition><order ordtype="ASC">'
        '<atribute3 name="componentgroup_id"/></order></foodquery>'
    ).encode()


class BedcaClient:
    def __init__(self, cache_dir: Path, delay_seconds: float = 0.15, retries: int = 4):
        self.cache_dir = cache_dir
        self.delay_seconds = delay_seconds
        self.retries = retries
        cache_dir.mkdir(parents=True, exist_ok=True)

    def request(self, key: str, body: bytes) -> bytes:
        target = self.cache_dir / f"{key}.xml"
        if target.exists() and target.stat().st_size > 30:
            return target.read_bytes()
        error: Exception | None = None
        for attempt in range(self.retries):
            try:
                request = urllib.request.Request(
                    ENDPOINT, data=body,
                    headers={"Content-Type": "text/xml", "User-Agent": USER_AGENT},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = response.read()
                ET.fromstring(payload)
                target.write_bytes(payload)
                time.sleep(self.delay_seconds)
                return payload
            except Exception as caught:  # network and malformed upstream responses are retriable
                error = caught
                time.sleep(2 ** attempt)
        raise RuntimeError(f"BEDCA request failed for {key}") from error

    def groups(self) -> list[BedcaGroup]:
        root = ET.fromstring(self.request("groups", groups_request()))
        return [
            BedcaGroup(_text(node, "fg_id") or "", _text(node, "fg_ori_name") or "", _text(node, "fg_eng_name"))
            for node in root.findall("food")
        ]

    def index(self, groups: list[BedcaGroup]) -> list[BedcaIndexFood]:
        by_id: dict[str, BedcaIndexFood] = {}
        for group in groups:
            root = ET.fromstring(self.request(f"group-{group.id}", group_request(group.id)))
            for node in root.findall("food"):
                food_id = _text(node, "f_id")
                if not food_id:
                    continue
                item = BedcaIndexFood(
                    food_id, group.id, _text(node, "f_ori_name") or "",
                    _text(node, "f_eng_name"), _text(node, "f_origen"), _text(node, "langual"),
                )
                previous = by_id.get(food_id)
                if previous and previous.group_id != item.group_id:
                    raise ValueError(f"BEDCA food {food_id} appears in groups {previous.group_id} and {item.group_id}")
                by_id[food_id] = item
        return sorted(by_id.values(), key=lambda item: int(item.id))

    def detail(self, food_id: str) -> dict:
        payload = self.request(f"food-{food_id}", detail_request(food_id))
        root = ET.fromstring(payload)
        node = root.find("food")
        if node is None:
            raise ValueError(f"BEDCA returned no detail for food {food_id}")
        result = {child.tag: _clean(child.text) for child in node if child.tag != "foodvalue"}
        result["components"] = [
            {child.tag: _clean(child.text) for child in value}
            for value in node.findall("foodvalue")
        ]
        result["raw_sha256"] = hashlib.sha256(payload).hexdigest()
        return result


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


def _text(node: ET.Element, name: str) -> str | None:
    return _clean(node.findtext(name))


def write_manifest(path: Path, groups: list[BedcaGroup], foods: list[BedcaIndexFood]) -> None:
    path.write_text(json.dumps({
        "groups": [asdict(group) for group in groups],
        "foods": [asdict(food) for food in foods],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
