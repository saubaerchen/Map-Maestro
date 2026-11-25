"""Collect a team's map vetoes for a year from Liquipedia via the official API.

Request budget: 1x action=parse (team Matches page) + 1x action=query per 50 match pages.
All responses are cached by liquipedia_polite, so re-runs cost zero requests.

Usage:
  python scripts/fetch_liquipedia_team_vetoes.py --page UCAM_Esports_Club --year 2026 --out data/staging/ucam_vetoes_2026
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html as html_lib
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from liquipedia_polite import fetch  # noqa: E402

API = "https://liquipedia.net/valorant/api.php"


def match_list(page: str, year: int) -> list[dict]:
    url = f"{API}?action=parse&page={page}/Matches&prop=text&format=json&formatversion=2"
    h = json.loads(fetch(url))["parse"]["text"]
    rows = re.findall(r'<tr class="table2&#95;&#95;row--body.*?</tr>', h, flags=re.S)
    out = []
    for r in rows:
        ts = re.search(r'data-timestamp="(\d+)"', r)
        if not ts:
            continue
        when = dt.datetime.fromtimestamp(int(ts.group(1)), dt.timezone.utc)
        if when.year != year:
            continue
        tour = re.findall(r'<td data-nowrap=""><a [^>]*>([^<]+)</a></td>', r)
        sc = re.search(r"<span[^>]*>(\d+)</span>&#160;&#58;&#160;<span[^>]*>(\d+)</span>", r)
        opp = re.findall(r'<span class="name"[^>]*><a [^>]*title="([^"]+)"[^>]*>([^<]+)</a>', r)
        mid = re.search(r"Match:ID_([A-Za-z0-9_\-]+)", r)
        tpage = re.search(r'<td data-nowrap=""><a href="/valorant/([^"#]+)', r)
        out.append({
            "tournamentPage": urllib.parse.unquote(tpage.group(1)) if tpage else "",
            "date": when.strftime("%Y-%m-%d"),
            "tournament": html_lib.unescape(tour[0]) if tour else "",
            "score": f"{sc.group(1)}:{sc.group(2)}" if sc else "",
            "opponent": html_lib.unescape(opp[-1][0]) if opp else "",
            "opponentAbbr": html_lib.unescape(opp[-1][1]) if opp else "",
            "matchPage": f"Match:ID_{mid.group(1)}" if mid else None,
        })
    return out


def fetch_wikitext(titles: list[str], redirects: bool = False) -> dict[str, str]:
    result = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        url = (f"{API}?action=query&prop=revisions&rvprop=content&rvslots=main&format=json"
               f"&formatversion=2" + ("&redirects=1" if redirects else "") + "&titles="
               + urllib.parse.quote("|".join(chunk), safe="|:/"))
        for p in json.loads(fetch(url))["query"]["pages"]:
            if "revisions" in p:
                result[p["title"].replace(" ", "_")] = p["revisions"][0]["slots"]["main"]["content"]
    return result


def parse_veto(raw: str, team_names: list[str]) -> dict | None:
    o1 = re.search(r"\|opponent1=\{\{TeamOpponent\|([^}|]+)", raw)
    o2 = re.search(r"\|opponent2=\{\{TeamOpponent\|([^}|]+)", raw)
    vb = re.search(r"(?s)\|mapveto=\{\{MapVeto(.*?)\n\s*\}\}", raw)
    if not (o1 and o2 and vb):
        return None
    t1, t2 = o1.group(1).strip(), o2.group(1).strip()
    block = vb.group(1)
    names_l = [n.lower() for n in team_names]
    focus = 1 if t1.lower() in names_l else 2 if t2.lower() in names_l else None
    fp = re.search(r"\|firstpick=(\d)", block)
    firstpick = int(fp.group(1)) if fp else 1
    types_m = re.search(r"\|types=([^\n|]+)", block)
    types = [t.strip() for t in types_m.group(1).split(",")] if types_m else ["ban", "pick", "ban", "decider"]

    steps = []
    rnd = 0
    for typ in types:
        if typ == "decider":
            continue
        rnd += 1
        for team in (firstpick, 3 - firstpick):
            m = re.search(rf"\|t{team}map{rnd}=([^\n|]*)", block)
            mp = m.group(1).strip() if m else ""
            if not mp:
                continue
            steps.append({
                "action": typ,
                "map": mp,
                "by": "team" if team == focus else "opp",
            })
    dm = re.search(r"\|decider=([^\n|]*)", block)
    decider = dm.group(1).strip() if dm else ""
    if decider:
        steps.append({"action": "decider", "map": decider, "by": ""})

    played = []
    for mb in re.finditer(r"(?s)\|map\d=\{\{ApiMap(.*?)\}\}", raw):
        b = mb.group(1)
        if re.search(r"\|finished=skip", b):
            continue
        name = re.search(r"\|map=([^\n|}]+)", b)
        played.append(name.group(1).strip() if name else None)

    map_ids = re.findall(r"\|matchid=([0-9a-f\-]{36})", raw)
    return {
        "mapIds": map_ids,
        "team1": t1, "team2": t2, "focusSlot": focus, "firstPickBy": "team" if firstpick == focus else "opp",
        "types": types, "steps": steps, "decider": decider, "mapsPlayedCount": len(played),
    }


def infobox_pool(text: str) -> list[str]:
    box = re.search(r"(?s)\{\{Infobox league(.*?)\n\}\}", text)
    src = box.group(1) if box else ""
    found = sorted(((int(n), m.strip()) for n, m in re.findall(r"\|map(\d+)=([^\n|}]+)", src)), key=lambda x: x[0])
    return [m for _, m in found if m]


def tournament_pools(rows: list[dict]) -> None:
    """Attach each match's map pool from its Liquipedia tournament page (infobox map1..mapN).

    Falls back to the parent page when a subpage has no infobox. When the page contradicts the
    vetoes of that tournament (a vetoed map missing, or more than 7 maps listed), the pool is
    corrected from the vetoes and the reason is stored in mapPoolNote.
    """
    pages = []
    for r in rows:
        tp = r["tournamentPage"]
        while tp:
            if tp not in pages:
                pages.append(tp)
            tp = tp.rsplit("/", 1)[0] if tp.count("/") > 3 else ""
    texts = {k.replace(" ", "_"): v for k, v in fetch_wikitext(pages, redirects=True).items()}

    def page_pool(tp: str) -> tuple[list[str], str]:
        while tp:
            pool = infobox_pool(texts.get(tp, ""))
            if pool:
                return pool, tp
            tp = tp.rsplit("/", 1)[0] if tp.count("/") > 3 else ""
        return [], ""

    vetoed: dict[str, set] = {}
    for r in rows:
        if r["veto"]:
            vetoed.setdefault(r["tournamentPage"], set()).update(s["map"] for s in r["veto"]["steps"])

    for r in rows:
        pool, src = page_pool(r["tournamentPage"])
        used = vetoed.get(r["tournamentPage"], set())
        note = ""
        if pool and (not used <= set(pool) or len(pool) > 7):
            extra = [m for m in pool if m not in used] if len(used) >= 7 else []
            missing = sorted(used - set(pool))
            fixed = sorted((set(pool) - set(extra)) | used)
            parts = []
            if missing:
                parts.append(f"{', '.join(missing)} vetoed but not listed")
            if extra:
                parts.append(f"{', '.join(extra)} listed but never vetoed")
            note = f"Liquipedia page lists {', '.join(pool)} - corrected from the vetoes ({'; '.join(parts)})"
            pool = fixed
        r["mapPool"] = sorted(pool)
        r["mapPoolSource"] = f"https://liquipedia.net/valorant/{src}" if src else ""
        r["mapPoolNote"] = note


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", required=True, help="Liquipedia team page, e.g. UCAM_Esports_Club")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--names", nargs="*", default=None,
                    help="Team names as used in match wikitext (defaults to page name variants)")
    ap.add_argument("--out", required=True, help="Output path without extension")
    args = ap.parse_args()

    matches = match_list(args.page, args.year)
    titles = [m["matchPage"] for m in matches if m["matchPage"]]
    wikitext = fetch_wikitext(titles)

    base = args.page.replace("_", " ")
    names = args.names or [base, re.sub(r"\s+(Esports Club|Club)$", "", base), "UCAM Esports"]

    rows = []
    for m in matches:
        raw = wikitext.get(m["matchPage"] or "")
        veto = parse_veto(raw, names) if raw else None
        rows.append({**m, "veto": veto})
        if veto and veto["focusSlot"] is None:
            print(f"WARN {m['date']} {m['matchPage']}: team name not found ({veto['team1']} vs {veto['team2']})",
                  file=sys.stderr)
        if not veto:
            print(f"WARN {m['date']} vs {m['opponentAbbr']}: no veto on Liquipedia", file=sys.stderr)

    tournament_pools(rows)
    for r in rows:
        if r["mapPoolNote"]:
            print(f"NOTE {r['date']} {r['tournament']}: {r['mapPoolNote']}", file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    with out.with_suffix(".csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Date", "Tournament", "Opponent", "Score", "First action", "Veto sequence", "Decider",
                    "Team bans", "Team picks", "Opp bans", "Opp picks", "Source"])
        for r in rows:
            v = r["veto"]
            if not v:
                w.writerow([r["date"], r["tournament"], r["opponentAbbr"], r["score"], "", "NO VETO", "", "", "", "",
                            "", f"https://liquipedia.net/valorant/{r['matchPage']}"])
                continue
            tag = "UCAM"
            seq = " > ".join(
                f"{tag if s['by'] == 'team' else r['opponentAbbr']} {s['action']} {s['map']}" if s["by"]
                else f"{s['map']} decider" for s in v["steps"])
            pick = lambda by, act: ", ".join(s["map"] for s in v["steps"] if s["by"] == by and s["action"] == act)
            w.writerow([r["date"], r["tournament"], r["opponentAbbr"], r["score"],
                        tag if v["firstPickBy"] == "team" else r["opponentAbbr"], seq, v["decider"],
                        pick("team", "ban"), pick("team", "pick"), pick("opp", "ban"), pick("opp", "pick"),
                        f"https://liquipedia.net/valorant/{r['matchPage']}"])
    print(f"{len(rows)} matches, {sum(1 for r in rows if r['veto'])} with veto -> {out}.json/.csv", file=sys.stderr)


if __name__ == "__main__":
    main()
