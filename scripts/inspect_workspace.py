from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def summarize_text(path: Path, max_lines: int = 12) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    return {
        "kind": "text",
        "line_count": len(lines),
        "preview": lines[:max_lines],
    }


def summarize_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    summary: dict[str, object] = {"kind": "json"}

    if isinstance(data, dict):
        summary["top_level"] = "object"
        summary["key_count"] = len(data)
        summary["keys"] = list(data.keys())[:20]
    elif isinstance(data, list):
        summary["top_level"] = "array"
        summary["item_count"] = len(data)
        if data:
            first = data[0]
            summary["first_item_type"] = type(first).__name__
            if isinstance(first, dict):
                summary["first_item_keys"] = list(first.keys())[:20]
    else:
        summary["top_level"] = type(data).__name__

    return summary


def summarize_jsonl(path: Path, max_preview: int = 2) -> dict:
    line_count = 0
    keys = Counter()
    sample_types = []

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            line_count += 1
            obj = json.loads(line)
            if isinstance(obj, dict):
                keys.update(obj.keys())
            if len(sample_types) < max_preview:
                if isinstance(obj, dict):
                    sample_types.append(
                        {
                            "type": "object",
                            "keys": list(obj.keys())[:20],
                        }
                    )
                else:
                    sample_types.append({"type": type(obj).__name__})

    return {
        "kind": "jsonl",
        "line_count": line_count,
        "top_keys": [name for name, _ in keys.most_common(20)],
        "sample_types": sample_types,
    }


def summarize_csv(path: Path, max_rows: int = 5) -> dict:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    header = rows[0] if rows else []
    return {
        "kind": "csv",
        "row_count": max(len(rows) - 1, 0),
        "column_count": len(header),
        "header": header,
        "preview": rows[1 : 1 + max_rows],
    }


def summarize_xlsx(path: Path) -> dict:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

    with ZipFile(path) as zf:
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        workbook_rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))

        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in workbook_rels
            if rel.tag.endswith("Relationship")
        }

        shared_strings = []
        if "xl/sharedStrings.xml" in zf.namelist():
            shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in shared_root.findall("main:si", namespace):
                parts = [node.text or "" for node in si.findall(".//main:t", namespace)]
                shared_strings.append("".join(parts))

        sheets = []
        for sheet in workbook.findall("main:sheets/main:sheet", namespace):
            rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = rel_map.get(rel_id, "")
            sheet_path = f"xl/{target}".replace("xl/worksheets/../", "xl/")
            root = ET.fromstring(zf.read(sheet_path))

            rows = []
            for row in root.findall("main:sheetData/main:row", namespace)[:6]:
                cells = []
                for cell in row.findall("main:c", namespace):
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("main:v", namespace)
                    value = value_node.text if value_node is not None else ""
                    if cell_type == "s" and value.isdigit():
                        idx = int(value)
                        value = shared_strings[idx] if idx < len(shared_strings) else value
                    cells.append(value)
                rows.append(cells)

            sheets.append(
                {
                    "name": sheet.attrib.get("name", ""),
                    "preview_rows": rows,
                }
            )

    return {
        "kind": "xlsx",
        "sheet_count": len(sheets),
        "sheets": sheets,
    }


def summarize_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    rel = path.relative_to(ROOT).as_posix()

    if suffix in {".md", ".py", ".ps1", ".js"}:
        summary = summarize_text(path)
    elif suffix == ".json":
        summary = summarize_json(path)
    elif suffix == ".jsonl":
        summary = summarize_jsonl(path)
    elif suffix == ".csv":
        summary = summarize_csv(path)
    elif suffix == ".xlsx":
        summary = summarize_xlsx(path)
    else:
        summary = {"kind": "unknown"}

    summary["path"] = rel
    summary["size"] = path.stat().st_size
    return summary


def main() -> None:
    files = sorted(path for path in ROOT.rglob("*") if path.is_file())
    summaries = [summarize_file(path) for path in files]
    print(json.dumps(summaries, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
