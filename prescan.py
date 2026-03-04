"""
prescan.py — Headless pre-scan functions for splash-time background loading.

Each function mirrors the corresponding screen's scan() method but has zero
UI dependencies — no tkinter, no messagebox, no label updates.  Returns
(all_data, missing_tid_count, improper_name_count, unknown_tid_count).
"""

import os
import re
from collections import defaultdict

from constants import REGION_FLAGS, is_clean_filename, classify_title_id
from debug_region import get_region_from_votes

_id_pat  = re.compile(r'(?<![0-9A-Fa-f])([01][0-9A-Fa-f]{15})(?![0-9A-Fa-f])')
_ver_pat = re.compile(r'\[v(\d+)\]|\[(\d{5,15})\]|[vV](\d+)(?!\.\d)')


# ---------------------------------------------------------------------------
# Base Games
# ---------------------------------------------------------------------------

def scan_base(folder: str, norm_v: dict, norm_t: dict):
    """Return (all_data, missing_tid, improper_name, unknown_tid) for base games."""
    all_data      = []
    missing_tid   = 0
    improper_name = 0
    unknown_tid   = 0

    try:
        entries = os.listdir(folder)
    except OSError:
        return all_data, missing_tid, improper_name, unknown_tid

    for fname in entries:
        fpath = os.path.join(folder, fname)
        if not os.path.isfile(fpath):
            continue
        if not fname.lower().endswith(('.nsp', '.xci')):
            continue

        match = _id_pat.search(fname)
        if not match:
            missing_tid += 1
            all_data.append({
                "filename": fname, "filepath": fpath,
                "filetype": os.path.splitext(fname)[1].lstrip(".").upper(),
                "tid": "—", "version": "—",
                "release_date": "—", "has_update": "—", "has_dlc": "—",
                "rgn": "—", "_quality": "missing_tid",
            })
            continue

        is_bad_name = not is_clean_filename(fname)
        if is_bad_name:
            improper_name += 1

        tid      = match.group(1).lower()
        base_tid = tid[:13] + "000"

        version = 0
        try:
            v_m = re.search(r'\[v(\d+)\]', fname, re.IGNORECASE)
            if v_m:
                version = int(v_m.group(1))
        except Exception:
            pass

        db_entry = norm_t.get(tid) or norm_t.get(base_tid) or {}
        region   = get_region_from_votes(db_entry) if db_entry else ""
        if not region:
            region = "—"

        release_date = str(db_entry.get("releaseDate", "") or "—")
        if len(release_date) == 8 and release_date.isdigit():
            release_date = f"{release_date[:4]}-{release_date[4:6]}-{release_date[6:]}"

        update_tid      = base_tid[:-3] + "800"
        v_list          = norm_v.get(update_tid) or norm_v.get(base_tid)
        has_update_flag = False
        if v_list:
            ints = [int(v) for v in (v_list.keys() if isinstance(v_list, dict) else v_list)
                    if str(v).isdigit()]
            has_update_flag = bool(ints)

        has_dlc_flag = any(k.startswith(base_tid[:13]) for k in norm_t)
        quality = "bad_name" if is_bad_name else ("unknown_tid" if not db_entry else "ok")

        if not is_bad_name and not db_entry:
            unknown_tid += 1

        all_data.append({
            "filename":     fname,
            "filepath":     fpath,
            "filetype":     os.path.splitext(fname)[1].lstrip(".").upper(),
            "tid":          tid.upper(),
            "version":      version,
            "release_date": release_date,
            "has_update":   "✓ Released" if has_update_flag else "—",
            "has_dlc":      "✓ Released" if has_dlc_flag else "—",
            "rgn":          REGION_FLAGS.get(region, region),
            "_quality":     quality,
        })

    all_data.sort(key=lambda x: x["filename"].lower())
    return all_data, missing_tid, improper_name, unknown_tid


# ---------------------------------------------------------------------------
# Updates
# ---------------------------------------------------------------------------

def scan_updates(folder: str, norm_v: dict, norm_t: dict):
    """Return (all_data, missing_tid, improper_name, unknown_tid) for updates."""
    all_data      = []
    missing_tid   = 0
    improper_name = 0
    unknown_tid   = 0

    for root_dir, _, files in os.walk(folder):
        for fname in files:
            if not fname.lower().endswith((".nsp", ".xci")):
                continue

            tid_m = _id_pat.search(fname)
            if not tid_m:
                missing_tid += 1
                all_data.append({
                    "filename": fname, "filepath": os.path.join(root_dir, fname),
                    "tid": "—", "cur_ver": "—", "lat_ver": "—",
                    "cur_int": 0, "lat_int": 0, "status": "✗ NO TITLE ID",
                    "tag": "missing_tid", "mid": "", "rgn": "—",
                    "_quality": "missing_tid",
                })
                continue

            is_bad_name = not is_clean_filename(fname)
            if is_bad_name:
                improper_name += 1

            tid   = tid_m.group(1).lower()
            ver_m = _ver_pat.search(fname)
            cur_i = int(ver_m.group(1) or ver_m.group(2) or ver_m.group(3)) if ver_m else 0

            # Region
            base_tid      = tid[:13] + "000"
            db_entry_base = norm_t.get(base_tid, {})
            db_entry_tid  = norm_t.get(tid, {})
            db_entry      = db_entry_base or db_entry_tid
            region        = get_region_from_votes(db_entry) if db_entry else ""

            base_region  = get_region_from_votes(db_entry_base) if db_entry_base else ""
            update_votes = db_entry_tid.get("_region_votes", {}) if db_entry_tid else {}
            update_is_glb = len(update_votes) >= 3
            wrong_region  = bool(
                base_region and base_region != "GLB"
                and update_votes and not update_is_glb
                and base_region not in update_votes
            )

            # Version list
            v_list = None
            mid    = None
            for sid in [tid, tid[:-3] + "000", tid[:-3] + "800"]:
                if sid in norm_v:
                    v_list = norm_v[sid]
                    mid    = sid
                    break

            if cur_i == 0:
                all_data.append({
                    "filename": fname, "filepath": os.path.join(root_dir, fname),
                    "tid": tid.upper(), "base_tid": base_tid,
                    "cur_ver": "v0", "lat_ver": "—",
                    "cur_int": 0, "lat_int": 0,
                    "status": "🎮 BASE GAME", "tag": "base",
                    "mid": mid or tid,
                    "rgn": REGION_FLAGS.get(region, region),
                    "_quality": "bad_name" if is_bad_name else (
                                "unknown_tid" if not db_entry else "ok"),
                })
                if not is_bad_name and not db_entry:
                    unknown_tid += 1
                continue

            lat_i = 0
            cur_d = "N/A"
            lat_d = "N/A"
            stat  = "Unknown"
            tag   = "unknown"

            if v_list:
                ints = [int(v) for v in (v_list.keys() if isinstance(v_list, dict) else v_list)
                        if str(v).isdigit()]
                if ints:
                    lat_i = max(ints)
                    cur_d = f"v{cur_i // 65536}.0"
                    lat_d = f"v{lat_i // 65536}.0"
                    if cur_i < lat_i:
                        stat = "⚠ OLD UPDATE"
                        tag  = "outdated"
                    else:
                        stat = "✓ LATEST"
                        tag  = "latest"

            if wrong_region:
                stat = "✗ WRONG REGION"
                tag  = "wrong_region"

            if not is_bad_name and not db_entry:
                unknown_tid += 1

            all_data.append({
                "filename": fname, "filepath": os.path.join(root_dir, fname),
                "tid": tid.upper(), "base_tid": base_tid,
                "cur_ver": cur_d, "lat_ver": lat_d,
                "cur_int": cur_i, "lat_int": lat_i,
                "status": stat, "tag": tag,
                "mid": mid or tid,
                "rgn": REGION_FLAGS.get(region, region),
                "_quality": "bad_name" if is_bad_name else (
                            "unknown_tid" if not db_entry else "ok"),
            })

    all_data.sort(key=lambda x: x["filename"].lower())
    return all_data, missing_tid, improper_name, unknown_tid


# ---------------------------------------------------------------------------
# DLC
# ---------------------------------------------------------------------------

def scan_dlc(folder: str, norm_t: dict, norm_c: dict):
    """Return (all_data, missing_tid, improper_name, unknown_tid) for DLC."""
    all_data      = []
    missing_tid   = 0
    improper_name = 0
    unknown_tid   = 0

    for root_dir, _, files in os.walk(folder):
        for fname in files:
            if not fname.lower().endswith((".nsp", ".xci")):
                continue

            tid_m = _id_pat.search(fname)
            if not tid_m:
                missing_tid += 1
                all_data.append({
                    "parent_name": "—", "parent_tid": "", "parent_region": "",
                    "dlc_region_votes": {}, "filename": fname,
                    "filepath": os.path.join(root_dir, fname),
                    "tid": "—", "dlc_name": "—", "status": "✗ NO TITLE ID",
                    "rgn": "—", "_quality": "missing_tid",
                })
                continue

            is_bad_name = not is_clean_filename(fname)
            if is_bad_name:
                improper_name += 1

            tid  = tid_m.group(1).lower()
            kind = classify_title_id(tid)

            cnmt_entry = norm_c.get(tid, {})
            if kind != "dlc":
                if cnmt_entry.get("type") != "AddOnContent":
                    continue

            parent_tid   = cnmt_entry.get("parent") or tid[:13] + "000"
            parent_entry = norm_t.get(parent_tid, {})
            parent_name  = parent_entry.get("name", "") or f"[{parent_tid.upper()}]"

            dlc_entry = norm_t.get(tid, {})
            dlc_name  = dlc_entry.get("name", "") or "—"

            parent_region    = get_region_from_votes(parent_entry)
            dlc_region_votes = dlc_entry.get("_region_votes", {})
            region           = parent_region or get_region_from_votes(dlc_entry)

            if not is_bad_name and not (parent_entry or dlc_entry):
                unknown_tid += 1

            all_data.append({
                "parent_name":      parent_name,
                "parent_tid":       parent_tid,
                "parent_region":    parent_region,
                "dlc_region_votes": dlc_region_votes,
                "filename":         fname,
                "filepath":         os.path.join(root_dir, fname),
                "tid":              tid.upper(),
                "dlc_name":         dlc_name,
                "status":           "",
                "rgn":              REGION_FLAGS.get(region, region),
                "_quality":         "bad_name" if is_bad_name else (
                                    "unknown_tid" if not (parent_entry or dlc_entry) else "ok"),
            })

    all_data.sort(key=lambda x: x["filename"].lower())

    # Post-scan completeness
    db_dlc_counts    = defaultdict(int)
    local_dlc_counts = defaultdict(int)
    for tid_key, cnmt_info in (norm_c or {}).items():
        if isinstance(cnmt_info, dict) and cnmt_info.get("type") == "AddOnContent":
            parent = cnmt_info.get("parent", "")
            if parent:
                db_dlc_counts[parent] += 1
    for item in all_data:
        local_dlc_counts[item["parent_tid"]] += 1

    for item in all_data:
        if item.get("_quality") == "missing_tid":
            continue
        p_region  = item["parent_region"]
        dlc_votes = item["dlc_region_votes"]
        dlc_is_glb = len(dlc_votes) >= 3
        if p_region and p_region != "GLB" and dlc_votes and not dlc_is_glb and p_region not in dlc_votes:
            item["status"] = "✗ WRONG REGION"
        else:
            p_tid    = item["parent_tid"]
            local    = local_dlc_counts[p_tid]
            db_total = db_dlc_counts.get(p_tid, 0)
            if db_total > 0 and local >= db_total:
                item["status"] = "✓ COMPLETE"
            elif db_total > 0 and local < db_total:
                item["status"] = f"⚠ PARTIAL {local}/{db_total}"
            else:
                item["status"] = "✓ OK"

    return all_data, missing_tid, improper_name, unknown_tid
