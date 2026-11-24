from __future__ import annotations

import re
import urllib.request

URL = "https://liquipedia.net/valorant/Match:ID_GI5qn6P4FC_0002"

request = urllib.request.Request(URL, headers={"User-Agent": "Codex/1.0"})
with urllib.request.urlopen(request, timeout=30) as response:
    html = response.read().decode("utf-8", errors="replace")

patterns = [
    r".{0,120}match-bm-map-veto-card.{0,2500}",
    r".{0,120}match-bm-game.{0,2500}",
    r".{0,120}Breeze.{0,2500}",
    r".{0,120}Lotus.{0,2500}",
    r".{0,120}Split.{0,1200}",
    r".{0,120}13&#160;&#58;&#160;5.{0,1200}",
    r".{0,120}13&#160;&#58;&#160;12.{0,1200}",
]

for pattern in patterns:
    print(f"\n--- PATTERN: {pattern} ---")
    for match in re.finditer(pattern, html, flags=re.S | re.I):
        snippet = match.group(0).replace("\n", " ")
        print(snippet[:800])
        print()
        break
