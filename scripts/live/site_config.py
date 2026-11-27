"""New-season site configuration (single source of truth for the site build).

Used by prepare_site_data.py, analyze_early_positioning.py and build_site.py.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE_RAW_DIR = os.path.join(ROOT, "data", "site")
PUBLISH_DIR = os.path.join(ROOT, "veto-history-site-publish")

KICKOFF_POOL = ["Abyss", "Bind", "Corrode", "Haven", "Lotus", "Summit", "Sunset"]

MAP_SITES = {
    "Abyss": ["A", "B"], "Bind": ["A", "B"], "Corrode": ["A", "B"], "Haven": ["A", "B", "C"],
    "Lotus": ["A", "B", "C"], "Summit": ["A", "B"], "Sunset": ["A", "B"],
    "Ascent": ["A", "B"], "Split": ["A", "B"], "Breeze": ["A", "B"], "Fracture": ["A", "B"], "Pearl": ["A", "B"],
}

# valorant-api.com /v1/maps values (verified 2026-11-22 against the displayIcon images:
# Sunset/Summit 0.0%, Abyss 0.7%, Corrode 1.1% of positions off-map). Ascent keeps its rotated-PNG transform.
MAP_TRANSFORMS = {
    "Abyss":    {"xMultiplier": 8.1e-05, "yMultiplier": -8.1e-05, "xScalarToAdd": 0.5,      "yScalarToAdd": 0.5},
    "Ascent":   {"xMultiplier": 7.0e-05, "yMultiplier": 7.0e-05,  "xScalarToAdd": 0.426758, "yScalarToAdd": 0.813895, "swap_xy": True},
    "Bind":     {"xMultiplier": 5.9e-05, "yMultiplier": -5.9e-05, "xScalarToAdd": 0.576941, "yScalarToAdd": 0.967566},
    "Breeze":   {"xMultiplier": 7.0e-05, "yMultiplier": -7.0e-05, "xScalarToAdd": 0.465123, "yScalarToAdd": 0.833078},
    "Corrode":  {"xMultiplier": 7.0e-05, "yMultiplier": -7.0e-05, "xScalarToAdd": 0.526158, "yScalarToAdd": 0.5},
    "Fracture": {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.556952, "yScalarToAdd": 1.155886},
    "Haven":    {"xMultiplier": 7.5e-05, "yMultiplier": -7.5e-05, "xScalarToAdd": 1.09345,  "yScalarToAdd": 0.642728},
    "Lotus":    {"xMultiplier": 7.2e-05, "yMultiplier": -7.2e-05, "xScalarToAdd": 0.454789, "yScalarToAdd": 0.917752},
    "Pearl":    {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.480469, "yScalarToAdd": 0.916016},
    "Split":    {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.842188, "yScalarToAdd": 0.697578},
    "Summit":   {"xMultiplier": 7.5e-05, "yMultiplier": -7.5e-05, "xScalarToAdd": 0.047401, "yScalarToAdd": 0.978891},
    "Sunset":   {"xMultiplier": 7.8e-05, "yMultiplier": -7.8e-05, "xScalarToAdd": 0.5,      "yScalarToAdd": 0.515625},
}


def transforms_short():
    """Same transforms in the xMul/yMul/xAdd/yAdd shape used by build_map_control_bundle.py."""
    out = {}
    for k, t in MAP_TRANSFORMS.items():
        out[k] = {"xMul": t["xMultiplier"], "yMul": t["yMultiplier"], "xAdd": t["xScalarToAdd"], "yAdd": t["yScalarToAdd"]}
        if t.get("swap_xy"):
            out[k]["swap_xy"] = True
    return out


PALETTE = ["#1565C0", "#F9A825", "#C62828", "#2E7D32", "#E91E63"]
STANDIN_COLOR = "#9E9E9E"

# Display-name aliases: VLR scoreboard name -> Liquipedia Kickoff roster name.
NAME_ALIASES = {"Indra": "xserten", "sizo": "sizovskyy", "Darxcioo": "Darxcio"}

# key = site team key (TEAMS_CONFIG), prefix = file prefix (= registry key), tag = VLR team tag
# roster = players coloured with the palette (current Kickoff roster first); others get STANDIN_COLOR.
TEAMS = {
    "eintracht": {"prefix": "sge", "tag": "SGE", "name": "Eintracht Frankfurt",
                  "roster": ["azury", "musashi", "Fizzy", "foe", "H1ber"]},
    "mir":       {"prefix": "mir", "tag": "MIR", "name": "MIR",
                  "roster": ["Bishepss", "reblyik", "innersavage", "kospa1n", "xserten"]},
    "joblife":   {"prefix": "jl", "tag": "JL", "name": "Joblife",
                  "roster": ["WanZeru", "Sevire", "hoody", "runneR", "soulcas"]},
    "nvjunior":  {"prefix": "nvj", "tag": "NVJ", "name": "NAVI Junior",
                  "roster": ["avey", "Darxcio", "Javelin", "Kolosha", "sizovskyy"]},
    # --- Open Qualifier teams (core = their Kickoff Open Qualifier five) ---
    "barca":       {"prefix": "bar", "tag": "BAR", "name": "Barça eSports",
                    "roster": ["purp0", "Fit1nho", "Pa1ze", "MONSTEERR", "Proxh"]},
    "f9eicar":     {"prefix": "f9", "tag": "F9", "name": "F9 EICAR",
                    "roster": ["TITOUNE", "Kajuks", "Yohpa", "poeth", "H1ber"]},
    "wip":         {"prefix": "wip", "tag": "WIP", "name": "WIP Esports",
                    "roster": ["Vorwenn", "mepeezy", "TakaS", "Jesse", "wtex"]},
    "aurora":      {"prefix": "aur", "tag": "AURA", "name": "Aurora Gaming",
                    "roster": ["Boo", "B1SK", "chiwa", "trexx", "Derke"]},
    "pixellumina": {"prefix": "pxl", "tag": "PXL", "name": "Pixel Lumina",
                    "roster": ["MOLSI", "Chadi", "nataNk", "Kamisseq", "Saiz"]},
    # hidden: built as usual (its vetoes are still mirrored to opponents) but not in the team dropdown
    "mpmt":        {"prefix": "mpmt", "tag": "MPMT", "name": "xXxMasterProMegaTeamxXx", "hidden": True,
                    "roster": ["adore", "Michel", "moner", "ORI4K", "shawN"]},
    "lamasia":     {"prefix": "lam", "tag": "MSA", "name": "La Masia",
                    "roster": ["soren", "izana", "nayte", "lux9", "askoo"]},
    # --- Invited teams without usable official data (shown with a 'no data yet' note) ---
    "giantx":      {"prefix": "gx", "tag": "GX", "name": "GIANTX",
                    "roster": ["globeX", "sickrey", "Vitie", "WACKIE", "ZachKappa"]},
    "ucam":        {"prefix": "ucam", "tag": "UCAM", "name": "UCAM Esports Club",
                    "roster": ["BULD", "Filu", "Flickless", "kamyk", "waddle"]},
    "mandatory":   {"prefix": "mdr", "tag": "MDR", "name": "Mandatory",
                    "roster": ["Veqaj", "starxo", "runneR", "Kicks", "MiniBoo"]},
    "enterprise":  {"prefix": "ep", "tag": "EP", "name": "Enterprise Esports",
                    "roster": ["sh1n", "rexxtoned", "iluri", "koshmaras", "stonezy"],
                    # Veto view: every 2026 veto from Liquipedia (+ tournament map pool), requested 2026-11-26.
                    # Refresh: python scripts/fetch_liquipedia_team_vetoes.py --page Enterprise_Esports --year 2026
                    #          --tag EP --out data/staging/ep_vetoes_2026
                    "liquipedia_vetoes": os.path.join(ROOT, "data", "staging", "ep_vetoes_2026.json"),
                    "veto_subtitle": "All 2026 official vetoes (Liquipedia), map pool per tournament"},
    # --- Special data sets (bypass the baseline-core + 2026-09-01 rules on purpose) ---
    # UCAM (OLD): UCAM's tournament-account games 2026-05-01..2026-07-09 (old roster), any roster,
    # from scripts/live/fetch_ucam_esports.py. Kickoff map pool only (Bind/Haven/Lotus). Requested by Vincent 2026-11-24.
    "ucamold":     {"prefix": "ucamold", "tag": "UCAM", "name": "UCAM (OLD)", "hidden": True,
                    "roster": ["B1SK", "BULD", "Famsii", "Jesse", "OLIZERA"],
                    "esports_source": os.path.join(ROOT, "data", "raw", "ucam_esports_since_2026-05_raw_responses.jsonl"),
                    "ignore_core": True, "min_date": "2026-05-01",   # maps: Kickoff pool only
                    # + the 3 Abyss maps of March 2026 (vs JL 03-22, EP 03-27, MDR 03-28); requested by Vincent 2026-11-25
                    "extra_windows": [{"from": "2026-03-01", "to": "2026-03-31", "maps": ["Abyss"]}],
                    # Veto view: every 2026 veto from Liquipedia (+ tournament map pool), requested 2026-11-25.
                    # Refresh: python scripts/fetch_liquipedia_team_vetoes.py --page UCAM_Esports_Club --year 2026
                    #          --out data/staging/ucam_vetoes_2026
                    "liquipedia_vetoes": os.path.join(ROOT, "data", "staging", "ucam_vetoes_2026.json"),
                    "veto_subtitle": "Old roster — all 2026 official vetoes (Liquipedia), map pool per tournament"},
    # Enterprise (iluri): EP's official 2026 games before the Kickoff (2026-01-29..2026-08-23), all with
    # iluri (IGL), on the 5 Kickoff maps they played. Requested by Vincent 2026-11-27. All games are used
    # (no last-3 sample). Source = Liquipedia map ids -> Valolytics esports details (+ local old-season data).
    "epiluri":     {"prefix": "epiluri", "tag": "EP", "name": "Enterprise Esports (iluri)",
                    "roster": ["iluri", "Lime", "MAGNUM", "Proxh", "kozzy"],
                    "esports_source": os.path.join(ROOT, "data", "staging", "ep_iluri_2026_preNov_raw_responses.jsonl"),
                    "ignore_core": True, "min_date": "2026-01-01",
                    "maps": ["Abyss", "Bind", "Corrode", "Lotus", "Summit"],
                    "sample_maps": None,
                    "liquipedia_vetoes": os.path.join(ROOT, "data", "staging", "ep_vetoes_2026.json"),
                    "veto_before": "2026-11-01",
                    "veto_subtitle": "Enterprise 2026 before the Kickoff — official vetoes (Liquipedia)"},
}


def team_pool(cfg):
    """Maps a team is built for: the Kickoff pool unless the team sets its own 'maps'."""
    return cfg.get("maps", KICKOFF_POOL)


def team_min_date(cfg):
    """Earliest game date a team's site data may contain (main window or any extra window)."""
    return min([cfg.get("min_date", "2026-09-01")] + [w["from"] for w in cfg.get("extra_windows", [])])


def in_team_window(cfg, day, map_name):
    """True if a game on `day` (YYYY-MM-DD) on `map_name` belongs to the team's data set."""
    if day >= cfg.get("min_date", "2026-09-01"):
        return True
    return any(w["from"] <= day <= w["to"] and map_name in w.get("maps", [map_name])
               for w in cfg.get("extra_windows", []))


def site_jsonl(prefix):
    return os.path.join(SITE_RAW_DIR, f"{prefix}_2026_raw_responses.jsonl")
