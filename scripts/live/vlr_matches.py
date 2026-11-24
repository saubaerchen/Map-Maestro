"""Step 1: scrape a team's official matches from VLR.

Usage:
  python scripts/live/vlr_matches.py --prefix sge --team-id 14478 --slug eintracht-frankfurt [--since 2026-09-01]
  python scripts/live/vlr_matches.py --search "joblife"      (lists VLR team ids)

Writes data/registry/vlr/{prefix}.json
"""
import argparse
import datetime
import json
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import VLR_DIR, vlr_get  # noqa: E402

STAT_COLS = ["rating2", "acs", "kast", "adr", "hsp", "fb", "fd"]


def search(q):
    s = BeautifulSoup(vlr_get("/search/?q=" + q.replace(" ", "+") + "&type=teams"), "html.parser")
    for a in s.select("a.search-item"):
        m = re.search(r"/team/(\d+)/", a.get("href", ""))
        print(m.group(1) if m else "?", "|", a.get_text(" ", strip=True))


def both(cell):
    if cell is None:
        return None
    sp = cell.select_one("span.side.mod-both") or cell.select_one(".mod-both")
    return sp.get_text(strip=True) if sp else cell.get_text(strip=True)


def to_num(v):
    if v is None:
        return None
    v = v.replace("%", "").replace("+", "").strip()
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return None


def parse_match(url):
    s = BeautifulSoup(vlr_get(url), "html.parser")
    ts = None
    tz = s.select_one(".match-header-date .moment-tz-convert")
    if tz and tz.get("data-utc-ts"):
        ts = tz["data-utc-ts"]
    names = [n.get_text(strip=True) for n in s.select(".match-header-link-name .wf-title-med")]
    veto = [n.get_text(" ", strip=True) for n in s.select(".match-header-note")]
    event = s.select_one(".match-header-event")
    event = re.sub(r"\s+", " ", event.get_text(" ", strip=True)) if event else ""
    maps = []
    for g in s.select(".vm-stats-game"):
        gid = g.get("data-game-id")
        if gid in (None, "all"):
            continue
        hdr = g.select_one(".vm-stats-game-header")
        if not hdr:
            continue
        map_el = hdr.select_one(".map")
        map_name = map_el.select_one("span").get_text(" ", strip=True) if map_el and map_el.select_one("span") else (map_el.get_text(" ", strip=True) if map_el else "")
        map_name = re.sub(r"\s*(PICK|DECIDER)?\s*\d+:\d+(:\d+)?\s*$", "", map_name).replace("PICK", "").strip()
        map_name = map_name.split()[0] if map_name else map_name
        scores = [to_num(x.get_text(strip=True)) for x in hdr.select(".score")]
        sides = [t.get_text(strip=True) for t in hdr.select(".team-name")]
        players = []
        for row in g.select(".ovw-row"):
            pn = row.select_one(".ovw-player-name")
            if not pn:
                continue
            tag = row.select_one(".ovw-player-tag")
            agents = [i.get("title") for i in row.select(".mod-agents img")]
            rec = {
                "name": pn.get_text(strip=True),
                "teamTag": tag.get_text(strip=True) if tag else "",
                "agent": agents[0] if agents else None,
                "k": to_num(both(row.select_one('[data-col="kills"]'))),
                "d": to_num(both(row.select_one('[data-col="deaths"]'))),
                "a": to_num(both(row.select_one('[data-col="assists"]'))),
            }
            for c in STAT_COLS:
                rec[c] = to_num(both(row.select_one(f'[data-col="{c}"]')))
            players.append(rec)
        if not players or None in scores or len(scores) < 2:
            continue
        maps.append({"gameId": gid, "map": map_name, "teams": sides, "score": scores[:2], "players": players})
    return {"url": url, "utc": ts, "event": event, "teams": names, "veto": veto, "maps": maps}


def team_matches(team_id, slug, since):
    out = []
    page = 1
    while True:
        url = f"/team/matches/{team_id}/{slug}/?page={page}"
        s = BeautifulSoup(vlr_get(url), "html.parser")
        items = s.select("a.m-item")
        if not items:
            break
        stop = False
        for a in items:
            d = a.select_one(".m-item-date div")
            date = d.get_text(strip=True).replace("/", "-") if d else ""
            if date and date < since:
                stop = True
                continue
            teams = [t.get_text(strip=True) for t in a.select(".m-item-team-name")]
            tags = [t.get_text(strip=True) for t in a.select(".m-item-team-tag")]
            core = [t.get_text(strip=True) for t in a.select(".m-item-team-core")]
            res = [x.get_text(strip=True) for x in a.select(".m-item-result span")]
            ev = a.select_one(".m-item-event")
            out.append({
                "href": a.get("href"), "date": date, "teams": teams, "tags": tags, "core": core,
                "result": res, "event": re.sub(r"\s+", " ", ev.get_text(" ", strip=True)) if ev else "",
            })
        if stop or page >= 10:
            break
        page += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search")
    ap.add_argument("--prefix")
    ap.add_argument("--team-id")
    ap.add_argument("--slug")
    ap.add_argument("--since", default="2026-09-01")
    a = ap.parse_args()
    if a.search:
        search(a.search)
        return
    listing = team_matches(a.team_id, a.slug, a.since)
    matches = []
    for m in listing:
        if not m["result"] or m["result"] == ["", ""]:
            continue
        try:
            det = parse_match(m["href"])
        except Exception as e:
            print("FAILED", m["href"], e)
            continue
        det.update({"listDate": m["date"], "listTeams": m["teams"], "listTags": m["tags"], "core": m["core"], "result": m["result"]})
        matches.append(det)
        print(f'{m["date"]} {m["event"][:45]:45} {" vs ".join(m["teams"])} {"-".join(m["result"])} maps={len(det["maps"])}')
    out = {"prefix": a.prefix, "teamId": a.team_id, "slug": a.slug, "since": a.since,
           "scraped": datetime.datetime.now(datetime.UTC).isoformat(), "matches": matches}
    path = os.path.join(VLR_DIR, f"{a.prefix}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(matches)} matches, {sum(len(m['maps']) for m in matches)} maps -> {path}")


if __name__ == "__main__":
    main()
