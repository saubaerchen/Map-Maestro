"""Polite, cached Liquipedia fetcher.

Rules followed (Liquipedia API/usage terms): single-threaded, >= 2 s between requests
(we use ~10 s + jitter), gzip accepted, descriptive User-Agent, every response cached
on disk so a page is never fetched twice, and a hard stop on 429/403 instead of retrying.
"""
from __future__ import annotations

import gzip
import hashlib
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "staging" / "liquipedia_cache"
CONTACT_FILE = ROOT / "data" / "staging" / "liquipedia_contact.txt"  # gitignored; Liquipedia requires a contact
_contact = CONTACT_FILE.read_text(encoding="utf-8").strip() if CONTACT_FILE.exists() else ""
USER_AGENT = f"VetoFetcher/1.0 ({_contact}; non-commercial, low-volume, cached)"
# Use the official API (api.php): plain page URLs return 403 for scripts.
# Limits: action=parse <= 1 per 30 s; other API calls <= 1 per 2 s. MIN_DELAY covers both.
MIN_DELAY = 30.0
JITTER = 4.0

_last_request = 0.0


class LiquipediaBlocked(RuntimeError):
    pass


def _cache_path(url: str) -> Path:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    slug = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1][:60]
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in slug)
    return CACHE_DIR / f"{safe}_{h}.txt"


def fetch(url: str) -> str:
    global _last_request
    path = _cache_path(url)
    if path.exists():
        return path.read_text(encoding="utf-8")

    wait = MIN_DELAY + random.uniform(0, JITTER) - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)

    parsed = urllib.parse.urlparse(url)
    safe_path = urllib.parse.quote(parsed.path, safe="/:@!$&'()*+,;=")
    safe_url = urllib.parse.urlunparse(parsed._replace(path=safe_path))
    req = urllib.request.Request(
        safe_url,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            body = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
    except urllib.error.HTTPError as e:
        _last_request = time.time()
        if e.code in (403, 429):
            raise LiquipediaBlocked(f"HTTP {e.code} on {url} - stopping, do not retry soon")
        raise
    _last_request = time.time()
    text = body.decode("utf-8", errors="replace")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  fetched {url}", file=sys.stderr, flush=True)
    return text
