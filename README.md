# NX-Librarian

> A modern Nintendo Switch archive manager and file organizer — built for collectors who care about their library.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%2F%20Linux-0078D6?style=flat-square&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-Private-red?style=flat-square)

---

## What it does

NX-Librarian scans a folder of `.nsp` and `.xci` files and gives you a clean, organized view of your collection across three modes:

| Mode | What you get |
|---|---|
| 🎮 **Base Games** | Full library list with release dates, update availability, and DLC presence |
| 🔼 **Updates** | Version comparison against the latest known release — instantly spot outdated files |
| 🎁 **DLC & Add-ons** | Parent game grouping with completeness tracking (`COMPLETE`, `PARTIAL 3/7`, etc.) |

---

## Features

### Library management
- **Live database sync** — pulls title, version, and region data from [blawar/titledb](https://github.com/blawar/titledb)
- **Region detection** — consensus voting across 6 regional databases (US, GB, JP, KR, HK, CN); global releases shown as `● GLB`
- **Wrong region flagging** — detects mismatched updates and DLC against their base game's region; never fires false positives on global releases
- **File quality filters** — surface files with missing title IDs, unknown title IDs, or improper naming in one click
- **Live search** — instant filter across all columns as you type
- **Column sorting** — click any header to sort
- **Right-click copy** — copy a cell, row, or the entire table to clipboard
- **Cross-screen navigation** — click the UPDATE? or DLC? cell on a base game to jump straight to that game's update or DLC; double-click any update/DLC row to jump back to its base game

### Smart file fixing
- **✎ Fix Name** — amber overlay button on improperly named files; auto-proposes corrected filenames (`Game Name [TitleID][vVERSION].ext`) with an inline editable rename dialog
- **✎ Fix TID** — red/purple overlay button on files with missing or unrecognized title IDs; opens an intelligent search dialog:
  - OR-based word matching — searches the title DB for any word in the filename, not just exact phrases
  - Scene tag filtering — strips noise like `Switch`, `NSP`, `USA`, `UPD`, domain names, and other scene tokens before searching
  - File size scoring — compares your file's actual size against the DB's expected v0 size to rank candidates; shows a `✓` / `~` / `✗` proximity indicator next to each result
  - Smart TID proposal — automatically proposes the right TID type: `000` for base games, `800` for updates, actual DLC TIDs from the content metadata DB for DLC screens

### Version & placement warnings
- **⚠ Version warning (Base Games)** — any base game file with a version above v0 gets a yellow `⚠ v{n}` overlay on its version cell; clicking opens a two-panel resolution dialog:
  - **Override to v0** — renames `[vXXXX]` to `[v0]` in place
  - **Migrate to Updates** — moves the file to your configured updates folder
  - Both panels show a **SUGGESTED** badge with a **Why:** explanation based on the file's actual size vs. the DB's expected base game size
- **⚠ Base game warning (Updates)** — any file in your updates folder tagged as v0 or `[Base]` gets a yellow `⚠ v0` overlay; clicking opens the inverse dialog:
  - **Strip Base Tag** — removes `[Base]` from the filename in place
  - **Migrate to Base Games** — moves the file to your configured base games folder
  - Same size-ratio suggestion logic: a file close to the expected base game size is confidently recommended for migration; significantly smaller or larger files are recommended for tag stripping

### Startup & performance
- **Pre-Scan** — toggle on the home screen footer (default: ON when folder paths are already saved); on every launch after the first, NX-Librarian scans all three of your configured folders *during* the splash screen, so the library list is instant when you click a mode — no separate scan step needed
- **Splash progress is real** — the loading circle reflects actual work: DB cache load (0–60%) + base game scan + updates scan + DLC scan (60–97%) all shown as live progress
- **Cache timer** — the home screen footer shows exactly how long until the database auto-refreshes, updated every minute; a **Sync Database** button forces an immediate re-download from any screen

### Cosmetics
- **Dark mode title bar** — respects your OS dark/light mode setting automatically (Windows DWM)
- **Animated splash screen** — growing circle animation with PNG transparency and desktop bleed-through on Windows and macOS
- **Nintendo Switch color palette** — red / blue / green three-panel home screen; consistent accent colors throughout

---

## Naming convention

NX-Librarian uses (and can auto-rename toward) the standard convention:

```
Game Name [TitleID][vVERSION].nsp
Game Name [TitleID][vVERSION].xci
```

**Example:**
```
The Legend of Zelda Tears of the Kingdom [0100F2C0115B6000][v0].nsp
The Legend of Zelda Tears of the Kingdom [0100F2C0115B6800][v65536].nsp
```

Title IDs are the source of truth — region tags in filenames are ignored entirely.

Version integers follow the Nintendo format: `65536` = v1.0, `131072` = v2.0, etc. NX-Librarian also recognises bare bracketed version numbers like `[262144]` (no `v` prefix) that some scene releases use.

---

## Requirements

- Python 3.10+
- [Pillow](https://pillow.readthedocs.io/) — `pip install Pillow`
- Internet connection for the first database sync (cached locally after)

---

## Running it

```bash
git clone https://github.com/jackharvest/NX-Librarian.git
cd NX-Librarian
pip install Pillow
python main.py
```

---

## How it works

On first launch (or when you click **Sync Database**), NX-Librarian downloads the [blawar/titledb](https://github.com/blawar/titledb) JSON files — one per region — and merges them into three in-memory lookup tables:

| Table | Contents |
|---|---|
| `norm_t` | Title metadata (name, release date, region votes, expected file size) |
| `norm_v` | Known version list per title ID |
| `norm_c` | Content metadata from `cnmts.json` (type: base/update/DLC, parent relationships) |

Region is determined by counting how many regional databases contain a given title ID. A tie across multiple regions = `GLB` (global release). A single-region winner = that region. Wrong-region detection compares whether the base game's region appears at all in the DLC/update's regional vote set — not whether the dominant regions match — preventing false positives on global releases.

The `size` field in `norm_t` stores the expected v0 byte size for each title. NX-Librarian uses this to suggest resolutions when a file appears to be in the wrong folder: a file within ±15% of the expected size is recommended as a correctly-sized base game; a file significantly smaller is flagged as a likely patch.

---

## Project structure

```
NX-Librarian/
├── main.py                  # Entry point — splash screen → pre-scan → app
├── app.py                   # Main window, routing, banner, hamburger menu
├── splash.py                # Animated splash screen with progress circle
├── db.py                    # Database fetch, cache, and normalization
├── prescan.py               # Headless scan functions for splash-time pre-loading
├── constants.py             # TID classification, region flags, URLs
├── debug_region.py          # Region voting logic
└── ui/
    ├── base_screen.py           # Abstract scaffold all screens inherit
    ├── base_games_screen.py     # Base game library view
    ├── updates_screen.py        # Update version tracker
    ├── dlc_screen.py            # DLC browser with completeness status
    ├── mode_select.py           # Home screen — three-panel selector + footer bar
    ├── fix_tid_dialog.py        # Smart TID search & rename dialog
    ├── version_warn_dialog.py   # Version/placement warning dialogs
    └── edit_dialog.py           # General filename rename dialog
```

---

## Title ID structure (Switch)

```
XXXXXXXXXXXXXXX000  →  Base game
XXXXXXXXXXXXXXX800  →  Update
XXXXXXXXXXXXXXXxXX →  DLC (anything else in the last three hex digits)
```

Unlike WiiU (which had separate regional Title IDs), Switch games use a single global Title ID across all regions. ~98% of releases share one ID worldwide.

---

*Built for personal use. Not affiliated with Nintendo.*
