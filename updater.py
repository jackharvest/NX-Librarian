"""
updater.py — Auto-update logic for NX-Librarian.

No UI dependencies. Works only when running as a PyInstaller bundle
(sys.frozen is set). Source-run invocations silently no-op in apply_and_relaunch.
"""

import os
import sys
import re
import configparser
import tempfile

import requests

from constants import APP_VERSION, GITHUB_REPO, CONFIG_FILE

# ------------------------------------------------------------------
# Semver helpers
# ------------------------------------------------------------------

_PRE_ORDER = {"alpha": 0, "beta": 1, "rc": 2}


def _parse_semver(v: str):
    """
    Parse a version string like "3.0.0", "3.1.0-beta.1", "v2.2.0".
    Returns (major, minor, patch, pre_label, pre_num) where pre_label
    is None for stable releases and pre_num is the numeric suffix.
    Stable releases sort *after* any pre-release with the same base triple.
    """
    v = v.lstrip("v")
    m = re.match(
        r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.?(\d+))?$",
        v, re.IGNORECASE
    )
    if not m:
        return (0, 0, 0, None, 0)
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    pre_label = m.group(4).lower() if m.group(4) else None
    pre_num   = int(m.group(5)) if m.group(5) else 0
    return (major, minor, patch, pre_label, pre_num)


def _version_key(v: str):
    """Comparable tuple for sorting versions; stable > any pre-release."""
    major, minor, patch, pre_label, pre_num = _parse_semver(v)
    # Pre-releases sort below stable: (0, order, num) vs (1, 0, 0)
    if pre_label is None:
        pre_tuple = (1, 0, 0)
    else:
        pre_tuple = (0, _PRE_ORDER.get(pre_label, -1), pre_num)
    return (major, minor, patch, *pre_tuple)


def _is_newer(remote_ver: str, local_ver: str) -> bool:
    """Return True if remote_ver is strictly newer than local_ver."""
    return _version_key(remote_ver) > _version_key(local_ver)


# ------------------------------------------------------------------
# Config persistence
# ------------------------------------------------------------------

def load_update_prefs():
    """
    Return (auto_update: bool, beta_channel: bool, skip_version: str|None)
    from ~/.nxlibrarian_config.ini.
    """
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    sect = "updates"
    auto_update   = cfg.getboolean(sect, "auto_update",   fallback=True)
    beta_channel  = cfg.getboolean(sect, "beta_channel",  fallback=False)
    skip_version  = cfg.get(sect, "skip_version", fallback=None) or None
    return auto_update, beta_channel, skip_version


_SKIP_SENTINEL = object()


def save_update_prefs(auto_update=None, beta_channel=None, skip_version=_SKIP_SENTINEL):
    """
    Persist update preferences. Pass only the keys you want to change;
    unspecified keys retain their current values.
    """
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    if not cfg.has_section("updates"):
        cfg.add_section("updates")

    if auto_update is not None:
        cfg.set("updates", "auto_update", "true" if auto_update else "false")
    if beta_channel is not None:
        cfg.set("updates", "beta_channel", "true" if beta_channel else "false")
    if skip_version is not _SKIP_SENTINEL:
        if skip_version is None:
            cfg.remove_option("updates", "skip_version")
        else:
            cfg.set("updates", "skip_version", str(skip_version))

    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        cfg.write(fh)


# ------------------------------------------------------------------
# Asset selection
# ------------------------------------------------------------------

def _pick_asset(assets: list) -> dict | None:
    """
    Pick the best release asset for the current platform.
    Windows  → *-Setup.exe  (preferred) else *.exe
    macOS    → *.dmg
    Linux    → *.AppImage   (preferred) else *.deb
    """
    if sys.platform == "win32":
        for a in assets:
            if a["name"].endswith(".exe") and "Setup" in a["name"]:
                return a
        for a in assets:
            if a["name"].endswith(".exe"):
                return a
    elif sys.platform == "darwin":
        for a in assets:
            if a["name"].endswith(".dmg"):
                return a
    else:  # Linux
        for a in assets:
            if a["name"].endswith(".AppImage"):
                return a
        for a in assets:
            if a["name"].endswith(".deb"):
                return a
    return None


# ------------------------------------------------------------------
# Update check
# ------------------------------------------------------------------

def check_for_update(current_version=None, include_prerelease=False):
    """
    Query GitHub Releases API and return update info if a newer version exists.

    Returns (tag, asset_url, release_notes, html_url) or None.
    Raises requests.RequestException on network failure (caller should catch).
    """
    if current_version is None:
        current_version = APP_VERSION

    _, beta_channel, skip_version = load_update_prefs()
    if include_prerelease is False:
        include_prerelease = beta_channel

    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
    resp = requests.get(url, timeout=10,
                        headers={"Accept": "application/vnd.github+json",
                                 "X-GitHub-Api-Version": "2022-11-28"})
    if resp.status_code == 404:
        return None  # Repo exists but has no releases yet
    resp.raise_for_status()
    releases = resp.json()

    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease") and not include_prerelease:
            continue

        tag = release.get("tag_name", "").lstrip("v")
        if not _is_newer(tag, current_version):
            continue
        if tag == skip_version:
            continue

        asset = _pick_asset(release.get("assets", []))
        if asset is None:
            continue

        notes   = release.get("body") or ""
        html_url = release.get("html_url", "")
        return tag, asset["browser_download_url"], notes, html_url

    return None


# ------------------------------------------------------------------
# Download
# ------------------------------------------------------------------

def download_release(url: str, progress_cb=None):
    """
    Stream the release asset to a temp file.

    progress_cb(int 0-100) is called periodically.
    Returns the local path string, or None on failure.
    """
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        suffix = os.path.splitext(url.split("/")[-1])[1] or ".bin"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)

        downloaded = 0
        with os.fdopen(fd, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if total and progress_cb:
                        progress_cb(int(downloaded * 100 / total))

        if progress_cb:
            progress_cb(100)
        return tmp_path
    except Exception:
        return None


# ------------------------------------------------------------------
# Apply & relaunch
# ------------------------------------------------------------------

def apply_and_relaunch(new_path: str, quit_fn):
    """
    Write a helper script that waits for this process to exit, installs/
    replaces the binary, then relaunches. Calls quit_fn() to trigger exit.

    Only operates when sys.frozen is True (PyInstaller bundle).
    In source-run mode this is a no-op.
    """
    if not getattr(sys, "frozen", False):
        return

    current_exe = sys.executable
    pid = os.getpid()

    if sys.platform == "win32":
        _apply_windows(new_path, current_exe, pid, quit_fn)
    elif sys.platform == "darwin":
        _apply_macos(new_path, current_exe, pid, quit_fn)
    else:
        _apply_linux(new_path, current_exe, pid, quit_fn)


def _apply_windows(new_path, current_exe, pid, quit_fn):
    is_installer = new_path.lower().endswith(".exe") and "setup" in os.path.basename(new_path).lower()

    if is_installer:
        script = (
            f'@echo off\r\n'
            f':wait\r\n'
            f'tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL\r\n'
            f'IF NOT ERRORLEVEL 1 (\r\n'
            f'    timeout /t 1 /nobreak >NUL\r\n'
            f'    GOTO wait\r\n'
            f')\r\n'
            f'start "" /wait "{new_path}" /S\r\n'
            f'start "" "{current_exe}"\r\n'
        )
    else:
        script = (
            f'@echo off\r\n'
            f':wait\r\n'
            f'tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL\r\n'
            f'IF NOT ERRORLEVEL 1 (\r\n'
            f'    timeout /t 1 /nobreak >NUL\r\n'
            f'    GOTO wait\r\n'
            f')\r\n'
            f'move /y "{new_path}" "{current_exe}"\r\n'
            f'start "" "{current_exe}"\r\n'
        )

    fd, bat_path = tempfile.mkstemp(suffix=".bat")
    with os.fdopen(fd, "w") as fh:
        fh.write(script)

    import subprocess
    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )
    quit_fn()


def _apply_macos(new_path, current_exe, pid, quit_fn):
    script = (
        f'#!/bin/sh\n'
        f'while kill -0 {pid} 2>/dev/null; do sleep 1; done\n'
        f'MP=$(hdiutil attach -nobrowse -readonly "{new_path}" | tail -1 | cut -f3)\n'
        f'APP=$(ls "$MP"/*.app 2>/dev/null | head -1)\n'
        f'if [ -n "$APP" ]; then\n'
        f'    cp -R "$APP" /Applications/\n'
        f'    hdiutil detach "$MP" -quiet\n'
        f'    open "/Applications/$(basename "$APP")"\n'
        f'fi\n'
        f'rm -- "$0"\n'
    )
    fd, sh_path = tempfile.mkstemp(suffix=".sh")
    with os.fdopen(fd, "w") as fh:
        fh.write(script)
    os.chmod(sh_path, 0o755)

    import subprocess
    subprocess.Popen([sh_path], close_fds=True)
    quit_fn()


def _apply_linux(new_path, current_exe, pid, quit_fn):
    script = (
        f'#!/bin/sh\n'
        f'while kill -0 {pid} 2>/dev/null; do sleep 1; done\n'
        f'mv -f "{new_path}" "{current_exe}"\n'
        f'chmod +x "{current_exe}"\n'
        f'exec "{current_exe}"\n'
        f'rm -- "$0"\n'
    )
    fd, sh_path = tempfile.mkstemp(suffix=".sh")
    with os.fdopen(fd, "w") as fh:
        fh.write(script)
    os.chmod(sh_path, 0o755)

    import subprocess
    subprocess.Popen([sh_path], close_fds=True)
    quit_fn()
