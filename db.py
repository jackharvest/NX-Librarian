"""
db.py — database fetch, cache, and lookup logic for NX-Librarian.

Provides a single public function:
    load_db(force_refresh, progress_cb) -> (norm_v, norm_t, norm_c)

Where:
    norm_v  : dict  title_id_lower -> list/dict of version ints
    norm_t  : dict  title_id_lower -> entry dict (with '_region_votes' data)
    norm_c  : dict  title_id_lower -> content type string ('Application','Patch','AddOnContent')
"""

import os
import json
import time
import configparser
import requests

from constants import (
    CACHE_FILE, CACHE_DURATION, CONFIG_FILE,
    DB_MIRRORS, DEFAULT_MIRROR, get_db_urls,
)


def _load_mirror_urls() -> tuple[dict, str]:
    """Read the configured mirror from config and return (urls_dict, label)."""
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    key    = cfg.get("Settings", "db_mirror", fallback=DEFAULT_MIRROR)
    custom = cfg.get("Settings", "db_mirror_custom", fallback="").strip()

    if key == "Custom" and custom:
        return get_db_urls(custom), f"Custom ({custom})"
    if key in DB_MIRRORS and DB_MIRRORS[key]:
        return get_db_urls(DB_MIRRORS[key]), key
    # Fallback to default
    return get_db_urls(DB_MIRRORS[DEFAULT_MIRROR]), DEFAULT_MIRROR


def _mirror_fallback_order(primary_key: str) -> list[tuple[dict, str]]:
    """Return list of (urls, label) to try, primary first then others."""
    order = []
    # Primary first
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    custom = cfg.get("Settings", "db_mirror_custom", fallback="").strip()
    if primary_key == "Custom" and custom:
        order.append((get_db_urls(custom), f"Custom ({custom})"))
    elif primary_key in DB_MIRRORS and DB_MIRRORS[primary_key]:
        order.append((get_db_urls(DB_MIRRORS[primary_key]), primary_key))
    # Then the rest (named mirrors only, skip Custom since we have no URL)
    for name, base in DB_MIRRORS.items():
        if name == primary_key or name == "Custom" or not base:
            continue
        order.append((get_db_urls(base), name))
    return order


def _get(url, timeout=20, retries=2):
    """GET a URL, retrying on transient failures."""
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception:
            if attempt == retries:
                raise
            time.sleep(2)


def _fetch_versions(urls, progress_cb, base, span):
    progress_cb(base)
    r = _get(urls["versions"])
    progress_cb(base + span)
    return r.json()


def _fetch_titles(urls, progress_cb, base, span):
    """Fetch all regional title DBs and merge with region voting."""
    t = {}
    region_votes = {}
    title_urls = urls["titles"]
    step = span / max(len(title_urls), 1)

    for i, (region_tag, url) in enumerate(title_urls.items()):
        try:
            r = _get(url)
            for entry in r.json().values():
                if isinstance(entry, dict) and entry.get("id"):
                    tid_key = entry["id"].lower()
                    if tid_key not in t:
                        entry["_region"] = region_tag
                        t[tid_key] = entry
                    if tid_key not in region_votes:
                        region_votes[tid_key] = {}
                    region_votes[tid_key][region_tag] = (
                        region_votes[tid_key].get(region_tag, 0) + 1
                    )
        except Exception:
            pass
        progress_cb(base + step * (i + 1))

    for tid_key, entry in t.items():
        if tid_key in region_votes:
            votes = region_votes[tid_key]
            entry["_regions"] = sorted(votes.keys())
            entry["_region_votes"] = votes

    return t


def _fetch_cnmts(urls, progress_cb, base, span):
    """Fetch cnmts.json — maps title IDs to type and parent game TID."""
    progress_cb(base)
    try:
        r = _get(urls["cnmts"])
        raw = r.json()
    except Exception:
        progress_cb(base + span)
        return {}

    TYPE_MAP = {128: "Application", 129: "Patch", 130: "AddOnContent"}
    c = {}
    for tid_key, versions in raw.items():
        if not isinstance(versions, dict):
            continue
        for ver_data in versions.values():
            if not isinstance(ver_data, dict):
                continue
            title_type = ver_data.get("titleType")
            type_str = TYPE_MAP.get(title_type)
            if not type_str:
                break
            parent = str(ver_data.get("otherApplicationId") or "").lower()
            c[tid_key.lower()] = {"type": type_str, "parent": parent}
            break

    progress_cb(base + span)
    return c


def _try_fetch(urls: dict, progress_cb) -> dict | None:
    """Attempt a full fetch from a single mirror. Returns data dict or None.

    Returns None if any critical component is missing or fails validation,
    so the caller can fall through to the next mirror.
    """
    try:
        v = _fetch_versions(urls, progress_cb, 0, 15)
        t = _fetch_titles(urls, progress_cb, 15, 60)
        c = _fetch_cnmts(urls, progress_cb, 75, 20)
    except Exception:
        return None

    data = {"versions": v, "titles": t, "cnmts": c}
    if not _cache_is_valid(data):
        return None   # empty or malformed — try next mirror
    return data


def _cache_is_valid(data):
    """Return True if cached data is complete and up-to-date.

    Checks:
    - titles have _region_votes (added with voting system)
    - cnmts is populated and uses the new dict-per-entry format
    """
    sample = list(data.get("titles", {}).values())[:10]
    if not any("_region_votes" in e for e in sample):
        return False
    cnmts = data.get("cnmts", {})
    if not cnmts:
        return False
    # New format stores dicts per entry; old format stored plain strings
    first_entry = next(iter(cnmts.values()), None)
    if not isinstance(first_entry, dict):
        return False
    return True


def load_db(force_refresh: bool = False, progress_cb=None):
    """Load and return normalised databases, fetching from network if needed.

    Args:
        force_refresh: Bypass cache age check and re-download everything.
        progress_cb:   Callable(float 0-100) called during download for splash.

    Returns:
        (norm_v, norm_t, norm_c) tuple, or (None, None, None) on hard failure.
        Sets module-level `last_mirror_used` to the label of the mirror that
        succeeded, or "cache" if served from disk.
    """
    global last_mirror_used
    if progress_cb is None:
        progress_cb = lambda p: None

    cache_exists  = os.path.exists(CACHE_FILE)
    cache_expired = cache_exists and (
        time.time() - os.path.getmtime(CACHE_FILE)
    ) > CACHE_DURATION

    needs_fetch = force_refresh or not cache_exists or cache_expired

    cached_data = None
    if cache_exists and not needs_fetch:
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            if not _cache_is_valid(cached_data):
                needs_fetch = True
                cached_data = None
        except Exception:
            needs_fetch = True
            cached_data = None

    if needs_fetch:
        # Read configured mirror; build ordered list with fallbacks
        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_FILE)
        primary_key = cfg.get("Settings", "db_mirror", fallback=DEFAULT_MIRROR)
        mirrors = _mirror_fallback_order(primary_key)

        fresh = None
        for urls, label in mirrors:
            fresh = _try_fetch(urls, progress_cb)
            if fresh is not None:
                last_mirror_used = label
                break

        if fresh is not None:
            progress_cb(95)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(fresh, f)
            progress_cb(100)
            cached_data = fresh
        # else: network failure on all mirrors — fall through to disk cache

    if cached_data is None:
        if not os.path.exists(CACHE_FILE):
            return None, None, None
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
        except Exception:
            return None, None, None

    if not needs_fetch:
        last_mirror_used = "cache"
        progress_cb(100)

    norm_v = {k.lower(): v for k, v in cached_data.get("versions", {}).items()}
    norm_t = cached_data.get("titles", {})
    norm_c = cached_data.get("cnmts", {})

    return norm_v, norm_t, norm_c


last_mirror_used: str = "cache"


def cache_age_string():
    """Return a human-readable string describing how fresh the cache is."""
    if not os.path.exists(CACHE_FILE):
        return "No cache"
    rem = max(0, CACHE_DURATION - (time.time() - os.path.getmtime(CACHE_FILE)))
    h = int(rem // 3600)
    m = int((rem % 3600) // 60)
    return f"Cache refreshes in {h:02d}h {m:02d}m"
