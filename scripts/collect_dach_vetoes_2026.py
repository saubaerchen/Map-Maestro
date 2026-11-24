from __future__ import annotations

import html as html_lib
import re
import urllib.request


USER_AGENT = "Codex/1.0"

TEAM_CONFIG = [
    {
        "name": "ALTERNATE aTTaX",
        "matches_url": "https://liquipedia.net/valorant/ALTERNATE_aTTaX/Matches",
    },
    {
        "name": "Dortmund eSports",
        "matches_url": "https://liquipedia.net/valorant/Dortmund_eSports/Matches",
    },
]


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_team_page(url: str) -> list[dict[str, str]]:
    html = fetch_text(url)
    rows = re.findall(r'<tr class="table2&#95;&#95;row--body.*?</tr>', html, flags=re.S)
    parsed: list[dict[str, str]] = []
    for row in rows:
        visible_date = re.search(r">([A-Za-z]+ \d{1,2}, 2026)", row)
        if not visible_date:
            continue

        month_name, day, year_str = re.match(r"([A-Za-z]+) (\d{1,2}), (\d{4})", visible_date.group(1)).groups()
        month_index = {
            "January": 1,
            "February": 2,
            "March": 3,
            "April": 4,
            "May": 5,
            "June": 6,
            "July": 7,
            "August": 8,
            "September": 9,
            "October": 10,
            "November": 11,
            "December": 12,
        }[month_name]
        date = f"{year_str}-{month_index:02d}-{int(day):02d}"
        if not date.startswith("2026-"):
            continue

        score_match = re.search(
            r'<td data-align="center" data-nowrap=""><span(?: style="font-weight:bold")?>(\d+)</span>&#160;&#58;&#160;<span(?: style="font-weight:bold")?>(\d+)</span></td>',
            row,
        )
        if not score_match:
            continue
        score = f"{score_match.group(1)} - {score_match.group(2)}"

        sorts = re.findall(r'data-sort-value="([^"]+)"', row)
        opponent = html_lib.unescape(sorts[-1].strip()) if sorts else ""

        opponent_abbr_matches = re.findall(
            r'<span class="name"[^>]*><a [^>]*>([^<]+)</a></span>',
            row,
        )
        opponent_abbr = html_lib.unescape(opponent_abbr_matches[-1].strip()) if opponent_abbr_matches else opponent

        link_match = re.search(r'href="(/valorant/Match:ID_[^"]+)"', row)
        if not link_match:
            continue

        parsed.append(
            {
                "date": date,
                "opponent": opponent,
                "opponent_abbr": opponent_abbr,
                "score": score,
                "link": "https://liquipedia.net" + link_match.group(1),
            }
        )
    return parsed


def parse_raw_veto(raw: str) -> dict[str, str]:
    opponent1 = re.search(r"\|opponent1=\{\{TeamOpponent\|([^}]+)\}\}", raw)
    opponent2 = re.search(r"\|opponent2=\{\{TeamOpponent\|([^}]+)\}\}", raw)
    if not opponent1 or not opponent2:
        raise ValueError("Missing opponent data")

    team1 = opponent1.group(1)
    team2 = opponent2.group(1)

    veto_match = re.search(r"(?s)\|mapveto=\{\{MapVeto(.*?)\}\}", raw)
    if not veto_match:
        raise ValueError("Missing veto block")
    block = veto_match.group(1)

    firstpick_match = re.search(r"\|firstpick=(\d+)", block)
    firstpick = int(firstpick_match.group(1)) if firstpick_match else 1

    team_field_order = [("t1", team1), ("t2", team2)] if firstpick == 1 else [("t2", team2), ("t1", team1)]
    slot_pairs = [
        ("ban1", "ban2", "map1"),
        ("pick1", "pick2", "map2"),
        ("ban3", "ban4", "map3"),
    ]

    slots: dict[str, dict[str, str]] = {}
    for first_slot, second_slot, suffix in slot_pairs:
        first_prefix, first_owner = team_field_order[0]
        second_prefix, second_owner = team_field_order[1]
        ordered_fields = [
            (first_slot, first_prefix, first_owner),
            (second_slot, second_prefix, second_owner),
        ]
        for slot_key, prefix, owner_label in ordered_fields:
            field_match = re.search(rf"\|{prefix}{suffix}=([^\r\n|}}]+)", block)
            slots[slot_key] = {
                "map": field_match.group(1).strip() if field_match else "-",
                "owner": owner_label,
            }

    decider_match = re.search(r"\|decider=([^\r\n|}]+)", block)
    decider = decider_match.group(1).strip() if decider_match else "-"

    return {
        "ban1": f"{slots['ban1']['owner']} ban {slots['ban1']['map']}",
        "ban2": f"{slots['ban2']['owner']} ban {slots['ban2']['map']}",
        "pick1": f"{slots['pick1']['owner']} pick {slots['pick1']['map']}",
        "pick2": f"{slots['pick2']['owner']} pick {slots['pick2']['map']}",
        "ban3": f"{slots['ban3']['owner']} ban {slots['ban3']['map']}",
        "ban4": f"{slots['ban4']['owner']} ban {slots['ban4']['map']}",
        "decider": decider,
    }


def main() -> None:
    for team in TEAM_CONFIG:
        print(team["name"])
        print("=" * len(team["name"]))
        rows = parse_team_page(team["matches_url"])
        for row in rows:
            raw = fetch_text(row["link"] + "?action=raw")
            try:
                veto = parse_raw_veto(raw)
                print(
                    f"{row['date']} vs {row['opponent_abbr']} ({row['score']}): "
                    f"{veto['ban1']} | {veto['ban2']} | {veto['pick1']} | {veto['pick2']} | "
                    f"{veto['ban3']} | {veto['ban4']} | Decider {veto['decider']}"
                )
            except ValueError as exc:
                print(
                    f"{row['date']} vs {row['opponent_abbr']} ({row['score']}): "
                    f"[unable to parse veto: {exc}] {row['link']}"
                )
        print()


if __name__ == "__main__":
    main()
