from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "veto-history-site" / "maps"
TARGET_MAPS = {
    "Bind",
    "Breeze",
    "Corrode",
    "Fracture",
    "Haven",
    "Lotus",
    "Pearl",
    "Split",
}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "image/*,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = fetch_json("https://valorant-api.com/v1/maps")["data"]
    by_name = {entry.get("displayName"): entry for entry in data}

    missing = sorted(TARGET_MAPS - by_name.keys())
    if missing:
        raise RuntimeError(f"Missing maps in API payload: {', '.join(missing)}")

    for map_name in sorted(TARGET_MAPS):
        entry = by_name[map_name]
        icon_url = entry.get("displayIcon")
        if not icon_url:
            raise RuntimeError(f"No displayIcon for {map_name}")
        target = OUT_DIR / f"{map_name}.png"
        target.write_bytes(fetch_bytes(icon_url))
        print(f"saved {target}")


if __name__ == "__main__":
    main()
