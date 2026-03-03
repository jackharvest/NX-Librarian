# NX-Librarian

> A modern Nintendo Switch archive manager and file organizer — built for collectors who care about their library.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white)
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

- **Live database sync** — pulls title, version, and region data from [blawar/titledb](https://github.com/blawar/titledb)
- **Region detection** — consensus voting across 6 regional databases (US, GB, JP, KR, HK, CN); global releases shown as `● GLB`
- **Wrong region flagging** — detects mismatched updates and DLC against their base game's region
- **File quality filters** — surface files with missing title IDs or improper naming in one click
- **Rename / Edit mode** — auto-proposes corrected filenames (`Game Name [TitleID][vVERSION].ext`) with an inline editable rename dialog
- **Live search** — instant filter across all columns as you type
- **Column sorting** — click any header to sort
- **Right-click copy** — copy a cell, row, or the entire table to clipboard
- **Dark mode title bar** — respects your OS dark/light mode setting automatically (Windows DWM)
- **Animated splash screen** — with PNG transparency and OS desktop bleed-through

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
| `norm_t` | Title metadata (name, release date, region votes) |
| `norm_v` | Known version list per title ID |
| `norm_c` | Content metadata from `cnmts.json` (type: base/update/DLC, parent relationships) |

Region is determined by counting how many regional databases contain a given title ID. A tie across multiple regions = `GLB` (global release). A single-region winner = that region. Wrong-region detection compares whether the base game's region appears at all in the DLC/update's regional vote set — not whether the dominant regions match — preventing false positives on global releases.

---

## Project structure

```
nxlib/
├── main.py                  # Entry point — splash screen → app
├── app.py                   # Main window, routing, banner, hamburger menu
├── splash.py                # Animated splash screen
├── db.py                    # Database fetch, cache, and normalization
├── constants.py             # TID classification, region flags, URLs
├── debug_region.py          # Region voting logic
└── ui/
    ├── base_screen.py       # Abstract scaffold all screens inherit
    ├── base_games_screen.py # Base game library view
    ├── updates_screen.py    # Update version tracker
    ├── dlc_screen.py        # DLC browser with completeness status
    ├── edit_dialog.py       # Rename dialog
    └── mode_select.py       # Animated mode selection landing screen
```

---

## Title ID structure (Switch)

```
XXXXXXXXXXXXXXX0XX  →  Base game   (last 3 hex: 000)
XXXXXXXXXXXXXXX8XX  →  Update      (last 3 hex: 800)
XXXXXXXXXXXXXXXxXX →  DLC         (anything else)
```

Unlike WiiU (which had separate regional Title IDs), Switch games use a single global Title ID across all regions. ~98% of releases share one ID worldwide.

---

*Built for personal use. Not affiliated with Nintendo.*
