"""Shared helpers for the main-account fetch workflow.

See docs/superpowers/specs/2026-11-22-main-account-fetch-workflow-design.md
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRY_DIR = os.path.join(ROOT, "data", "registry")
VLR_DIR = os.path.join(REGISTRY_DIR, "vlr")
CACHE_DIR = os.path.join(ROOT, "data", "cache", "matches")
RAW_DIR = os.path.join(ROOT, "data", "raw")
REGISTRY_PATH = os.path.join(REGISTRY_DIR, "teams.json")

API_BASE = "https://api.valolytics.gg"
API_DELAY = 3.0
VLR_DELAY = 1.5

for _d in (REGISTRY_DIR, VLR_DIR, CACHE_DIR, RAW_DIR):
    os.makedirs(_d, exist_ok=True)


def _api_key():
    text = open(os.path.join(ROOT, "API_REFERENCE.md"), encoding="utf-8").read()
    return re.search(r"x-api-key:\s*(\S+)", text).group(1)


_HEADERS = None


def api_get(path):
    """GET a Valolytics path. Returns parsed JSON, or None on 404/400. Retries on 429."""
    global _HEADERS
    if _HEADERS is None:
        _HEADERS = {"x-api-key": _api_key(), "Accept": "application/json", "User-Agent": "curl/8.0.0"}
    for attempt in range(4):
        try:
            req = urllib.request.Request(API_BASE + path, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            time.sleep(API_DELAY)
            return data
        except urllib.error.HTTPError as e:
            time.sleep(API_DELAY)
            if e.code == 429:
                time.sleep(60)
                continue
            if e.code in (400, 404):
                return None
            raise
        except urllib.error.URLError:
            time.sleep(10)
    return None


def resolve_account(riot_id):
    """'Name#TAG' -> account dict (puuid, gameName, tagLine) via the live /europe/ route."""
    name, tag = riot_id.rsplit("#", 1)
    return api_get(
        "/api/riot/account/v1/accounts/by-riot-id/europe/"
        + urllib.parse.quote(name) + "/" + urllib.parse.quote(tag)
    )


def match_history(puuid):
    data = api_get("/api/riot/match/v1/matchlists/by-puuid/eu/" + puuid)
    return (data or {}).get("history", [])


def match_detail(match_id):
    """Full match detail, cached on disk under data/cache/matches/."""
    path = os.path.join(CACHE_DIR, match_id + ".json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    data = api_get("/api/matches/eu/" + match_id)
    if data:
        json.dump(data, open(path, "w", encoding="utf-8"))
    return data


def import_jsonl_to_cache(jsonl_path):
    """Seed the match cache from an existing JSONL (e.g. data/staging/*.jsonl)."""
    n = 0
    for line in open(jsonl_path, encoding="utf-8"):
        d = json.loads(line)
        mid = d.get("matchInfo", {}).get("matchId")
        if not mid:
            continue
        path = os.path.join(CACHE_DIR, mid + ".json")
        if not os.path.exists(path):
            json.dump(d, open(path, "w", encoding="utf-8"))
            n += 1
    return n


def vlr_get(url):
    if url.startswith("/"):
        url = "https://www.vlr.gg" + url
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")
    time.sleep(VLR_DELAY)
    return html


def load_registry():
    if os.path.exists(REGISTRY_PATH):
        return json.load(open(REGISTRY_PATH, encoding="utf-8"))
    return {"teams": {}, "accounts": {}}


def save_registry(reg):
    tmp = REGISTRY_PATH + ".tmp"
    json.dump(reg, open(tmp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    os.replace(tmp, REGISTRY_PATH)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())
