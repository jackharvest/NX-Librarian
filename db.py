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
import requests

from constants import (
    CACHE_FILE, CACHE_DURATION,
    VERSIONS_DB, CNMTS_DB, TITLES_DBS,
)


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


def _fetch_versions(progress_cb, base, span):
    progress_cb(base)
    r = _get(VERSIONS_DB)
    progress_cb(base + span)
    return r.json()


def _fetch_titles(progress_cb, base, span):
    """Fetch all regional title DBs and merge with region voting.

    Each entry in the returned dict has:
      "_region"       : first region that contained this title (fallback only)
      "_regions"      : sorted list of all regions that have this title
      "_region_votes" : dict mapping region -> vote count
    """
    t = {}
    region_votes = {}
    step = span / max(len(TITLES_DBS), 1)

    for i, (region_tag, url) in enumerate(TITLES_DBS.items()):
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
            pass  # Skip unavailable regional DB; other regions still vote
        progress_cb(base + step * (i + 1))

    # Attach vote data to each entry
    for tid_key, entry in t.items():
        if tid_key in region_votes:
            votes = region_votes[tid_key]
            entry["_regions"] = sorted(votes.keys())
            entry["_region_votes"] = votes

    return t


def _fetch_cnmts(progress_cb, base, span):
    """Fetch cnmts.json — maps title IDs to type and parent game TID.

    cnmts.json structure (current):
        { "<titleId>": { "<version>": { "titleType": <int>, "otherApplicationId": "<baseTid>", ... } } }

    titleType integers:
        128 = Application (base game)
        129 = Patch (update)
        130 = AddOnContent (DLC)

    Returns dict: { tid_lower: {"type": type_str, "parent": parent_tid_lower} }
    """
    progress_cb(base)
    try:
        r = _get(CNMTS_DB)
        raw = r.json()
    except Exception:
        progress_cb(base + span)
        return {}

    TYPE_MAP = {128: "Application", 129: "Patch", 130: "AddOnContent"}

    c = {}
    for tid_key, versions in raw.items():
        if not isinstance(versions, dict):
            continue
        # All versions of a title share the same type; use the first entry found
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
    """
    if progress_cb is None:
        progress_cb = lambda p: None

    cache_exists  = os.path.exists(CACHE_FILE)
    cache_expired = cache_exists and (
        time.time() - os.path.getmtime(CACHE_FILE)
    ) > CACHE_DURATION

    needs_fetch = force_refresh or not cache_exists or cache_expired

    # Load existing cache early so we can check its integrity
    cached_data = None
    if cache_exists and not needs_fetch:
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            if not _cache_is_valid(cached_data):
                # Stale cache from before voting was implemented — rebuild
                needs_fetch = True
                cached_data = None
        except Exception:
            needs_fetch = True
            cached_data = None

    if needs_fetch:
        try:
            # Progress allocation:
            #   0–15  : versions.json
            #   15–75 : regional title DBs (6 × 10 %)
            #   75–95 : cnmts.json
            #   95–100: write cache
            v = _fetch_versions(progress_cb, 0, 15)
            t = _fetch_titles(progress_cb, 15, 60)
            c = _fetch_cnmts(progress_cb, 75, 20)

            progress_cb(95)
            fresh = {"versions": v, "titles": t, "cnmts": c}
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(fresh, f)
            progress_cb(100)
            cached_data = fresh

        except Exception:
            # Network failure — fall through to whatever is on disk
            pass

    # If we still don't have data, load from disk (may be the old stale cache)
    if cached_data is None:
        if not os.path.exists(CACHE_FILE):
            return None, None, None
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
        except Exception:
            return None, None, None

    if not needs_fetch:
        progress_cb(100)

    norm_v = {k.lower(): v for k, v in cached_data.get("versions", {}).items()}
    norm_t = cached_data.get("titles", {})
    norm_c = cached_data.get("cnmts", {})

    return norm_v, norm_t, norm_c


def cache_age_string():
    """Return a human-readable string describing how fresh the cache is."""
    if not os.path.exists(CACHE_FILE):
        return "No cache"
    rem = max(0, CACHE_DURATION - (time.time() - os.path.getmtime(CACHE_FILE)))
    h = int(rem // 3600)
    m = int((rem % 3600) // 60)
    return f"Cache refreshes in {h:02d}h {m:02d}m"
