"""
ui/credits.py — Credits & Acknowledgements window.

Open source attribution for every library, database, and inspiration
that contributed to NX-Librarian.
"""

import tkinter as tk
from tkinter import ttk
from constants import UI_FONT, FONT_BOOST, APP_VERSION, APP_COPYRIGHT

_F  = FONT_BOOST
_BG = "#0a0a14"

# ── Palette ───────────────────────────────────────────────────────────────────
_C = {
    "header_bg":   "#0d1220",
    "accent":      "#60a5fa",
    "accent2":     "#06d6d0",
    "accent3":     "#f59e0b",
    "white":       "#ffffff",
    "body":        "#c0c2d8",
    "dim":         "#6b7280",
    "url":         "#60a5fa",
    "section_bar": "#1e2d4a",
    "divider":     "#1a2235",
    "card_bg":     "#0f1626",
}

# ── Credits data ──────────────────────────────────────────────────────────────
_SECTIONS = [
    {
        "title": "TITLE DATABASE",
        "color": "#06d6d0",
        "entries": [
            {
                "name":  "blawar / titledb",
                "role":  "The backbone of NX-Librarian's entire lookup engine.",
                "desc":  (
                    "Provides game names, title IDs, version histories, DLC parent "
                    "relationships, and content-type classification (Application / "
                    "Patch / AddOnContent). NX-Librarian pulls eight JSON feeds from "
                    "this repository at startup: versions.json, cnmts.json, and six "
                    "regional catalogues (US · GB · JP · KR · HK · CN). Without this "
                    "project none of the rename or verify features would be possible."
                ),
                "url":   "github.com/blawar/titledb",
            },
        ],
    },
    {
        "title": "PYTHON LIBRARIES",
        "color": "#60a5fa",
        "entries": [
            {
                "name":  "Python 3",
                "role":  "The Python Software Foundation",
                "desc":  "The core language the entire application is written in.",
                "url":   "python.org",
            },
            {
                "name":  "Pillow  (PIL Fork)",
                "role":  "Alex Clark and Contributors",
                "desc":  (
                    "Image loading and compositing, logo rendering, splash-screen "
                    "circle animation, and all tooltip card drawing. Every pixel "
                    "of custom art in this app goes through Pillow."
                ),
                "url":   "python-pillow.org  ·  github.com/python-pillow/Pillow",
            },
            {
                "name":  "Requests",
                "role":  "Kenneth Reitz and Contributors",
                "desc":  (
                    "HTTP library used to fetch all title-database JSON files "
                    "from GitHub. Handles retries, timeouts, and streaming "
                    "responses during the splash-screen load phase."
                ),
                "url":   "requests.readthedocs.io",
            },
        ],
    },
    {
        "title": "GUI FRAMEWORK",
        "color": "#a78bfa",
        "entries": [
            {
                "name":  "Tkinter  /  Tcl-Tk",
                "role":  "Python Software Foundation  ·  The Tcl Developer Xchange",
                "desc":  (
                    "The cross-platform GUI toolkit the entire app is built on. "
                    "Every window, panel, canvas, label, and animation frame runs "
                    "through Tkinter's Tcl/Tk bridge."
                ),
                "url":   "tcl.tk  ·  docs.python.org/library/tkinter",
            },
        ],
    },
    {
        "title": "LINUX SYSTEM APIS",
        "color": "#f97316",
        "entries": [
            {
                "name":  "X11 Shape Extension  (libXext)",
                "role":  "X.Org Foundation",
                "desc":  (
                    "XShapeCombineMask is used to clip the splash-screen window "
                    "to a circle shape at the OS level, giving true transparent "
                    "corners on Linux without a compositing manager."
                ),
                "url":   "x.org  ·  x.org/releases/X11R7.6/doc/libXext",
            },
            {
                "name":  "Xlib  (libX11)",
                "role":  "X.Org Foundation",
                "desc":  (
                    "Low-level X11 display connection and pixmap creation used "
                    "alongside libXext to build the 1-bit bitmap mask for the "
                    "splash circle clip."
                ),
                "url":   "x.org",
            },
        ],
    },
    {
        "title": "TYPOGRAPHY",
        "color": "#34d399",
        "entries": [
            {
                "name":  "DejaVu Sans",
                "role":  "The DejaVu Fonts Team",
                "desc":  (
                    "Primary font used for tooltip card text rendering on Linux. "
                    "Loaded at runtime via Pillow's ImageFont."
                ),
                "url":   "dejavu-fonts.github.io",
            },
            {
                "name":  "Liberation Sans",
                "role":  "Red Hat, Inc.  ·  Steve Matteson",
                "desc":  "First fallback font for tooltip rendering when DejaVu is unavailable.",
                "url":   "github.com/liberationfonts/liberation-fonts",
            },
            {
                "name":  "FreeSans",
                "role":  "GNU FreeFont Project",
                "desc":  "Second fallback font for tooltip rendering.",
                "url":   "gnu.org/software/freefont",
            },
        ],
    },
    {
        "title": "DESIGN INSPIRATION",
        "color": "#f59e0b",
        "entries": [
            {
                "name":  "Nintendo Switch™  Home Menu",
                "role":  "Nintendo Co., Ltd.",
                "desc":  (
                    "The three-panel mode selector, color palette (red / blue / green), "
                    "and overall visual language are affectionately inspired by the "
                    "Switch home screen UI. NX-Librarian is an independent fan project "
                    "and is not affiliated with or endorsed by Nintendo."
                ),
                "url":   "nintendo.com",
            },
            {
                "name":  "Nintendo Switch™  eShop",
                "role":  "Nintendo Co., Ltd.",
                "desc":  (
                    "Card layout, accent-color usage, and hover interaction patterns "
                    "draw visual cues from the eShop's game-detail pages."
                ),
                "url":   "nintendo.com",
            },
        ],
    },
    {
        "title": "COMMUNITY & SPECIAL THANKS",
        "color": "#ec4899",
        "entries": [
            {
                "name":  "r/SwitchPirates  &  r/128bitbay",
                "role":  "Reddit Communities",
                "desc":  (
                    "Real-world file naming conventions, edge-case dump formats, "
                    "and metadata quirks surfaced in these communities shaped the "
                    "rename engine's regex patterns and verification logic."
                ),
                "url":   "reddit.com",
            },
            {
                "name":  "Open Source Contributors",
                "role":  "GitHub",
                "desc":  (
                    "Countless Stack Overflow answers, GitHub issues, and gist "
                    "snippets from the wider Python and Tkinter communities informed "
                    "solutions throughout this codebase. Thank you all."
                ),
                "url":   "github.com",
            },
            {
                "name":  "You",
                "role":  "The User",
                "desc":  (
                    "For using an open-source tool and caring enough to read this far. "
                    "NX-Librarian exists to make managing your library easier — "
                    "we hope it delivers."
                ),
                "url":   "",
            },
        ],
    },
]


def show_credits(parent: tk.Misc):
    """Open the Credits & Acknowledgements window."""
    win = tk.Toplevel(parent)
    win.title("Credits & Acknowledgements — NX-Librarian")
    win.configure(bg=_BG)
    win.resizable(False, False)

    W, H = 680, 720
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sw - W)//2}+{(sh - H)//2}")
    win.grab_set()

    # ── Header ────────────────────────────────────────────────────────────────
    header = tk.Frame(win, bg=_C["header_bg"])
    header.pack(fill="x")

    tk.Label(header, text="NX-LIBRARIAN",
             bg=_C["header_bg"], fg=_C["white"],
             font=(UI_FONT, 18 + _F, "bold")).pack(pady=(22, 0))
    tk.Label(header, text="CREDITS  &  ACKNOWLEDGEMENTS",
             bg=_C["header_bg"], fg=_C["accent"],
             font=(UI_FONT, 9 + _F, "bold")).pack()
    tk.Label(header, text=f"v{APP_VERSION}  ·  {APP_COPYRIGHT}",
             bg=_C["header_bg"], fg=_C["dim"],
             font=(UI_FONT, 8 + _F)).pack(pady=(2, 14))

    tk.Label(header, text="Open source and proud.",
             bg=_C["header_bg"], fg=_C["accent2"],
             font=(UI_FONT, 9 + _F, "italic")).pack(pady=(0, 16))

    # Accent divider
    tk.Frame(header, bg=_C["accent"], height=2).pack(fill="x")

    # ── Scrollable body ───────────────────────────────────────────────────────
    body = tk.Frame(win, bg=_BG)
    body.pack(fill="both", expand=True)

    canvas = tk.Canvas(body, bg=_BG, highlightthickness=0)
    vsb    = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)

    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg=_BG)
    cw_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_canvas_resize(e):
        canvas.itemconfig(cw_id, width=e.width)
    canvas.bind("<Configure>", _on_canvas_resize)
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    # Mouse-wheel scrolling
    def _on_wheel(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
    def _on_wheel_linux(e):
        canvas.yview_scroll(-1 if e.num == 4 else 1, "units")
    canvas.bind_all("<MouseWheel>",     _on_wheel)
    canvas.bind_all("<Button-4>",       _on_wheel_linux)
    canvas.bind_all("<Button-5>",       _on_wheel_linux)
    win.bind("<Destroy>", lambda e: (
        canvas.unbind_all("<MouseWheel>"),
        canvas.unbind_all("<Button-4>"),
        canvas.unbind_all("<Button-5>"),
    ) if e.widget is win else None)

    # ── Populate sections ─────────────────────────────────────────────────────
    for section in _SECTIONS:
        _add_section(inner, section, W)

    # Bottom breathing room
    tk.Frame(inner, bg=_BG, height=24).pack(fill="x")

    # ── Footer close button ───────────────────────────────────────────────────
    foot = tk.Frame(win, bg=_C["header_bg"])
    foot.pack(fill="x", side="bottom")
    tk.Frame(foot, bg=_C["accent"], height=2).pack(fill="x")

    close_btn = tk.Label(foot, text="CLOSE",
                         bg=_C["header_bg"], fg=_C["accent"],
                         font=(UI_FONT, 9 + _F, "bold"),
                         padx=28, pady=10, cursor="hand2")
    close_btn.pack(pady=6)
    close_btn.bind("<Button-1>", lambda e: win.destroy())
    close_btn.bind("<Enter>", lambda e: close_btn.config(bg=_C["section_bar"]))
    close_btn.bind("<Leave>", lambda e: close_btn.config(bg=_C["header_bg"]))


def _add_section(parent, section: dict, win_w: int):
    """Render one credit section with its entries."""
    color = section["color"]

    # Section header bar
    bar = tk.Frame(parent, bg=_C["section_bar"])
    bar.pack(fill="x", padx=0, pady=(16, 0))
    tk.Frame(bar, bg=color, width=4).pack(side="left", fill="y")
    tk.Label(bar, text=section["title"],
             bg=_C["section_bar"], fg=color,
             font=(UI_FONT, 9 + _F, "bold"),
             padx=14, pady=7).pack(side="left")

    for entry in section["entries"]:
        _add_entry(parent, entry, color)


def _add_entry(parent, entry: dict, accent: str):
    """Render a single credit card."""
    card = tk.Frame(parent, bg=_C["card_bg"])
    card.pack(fill="x", padx=20, pady=(6, 0))

    # Left accent stripe
    tk.Frame(card, bg=accent, width=2).pack(side="left", fill="y")

    content = tk.Frame(card, bg=_C["card_bg"])
    content.pack(side="left", fill="both", expand=True, padx=14, pady=10)

    # Name
    tk.Label(content, text=entry["name"],
             bg=_C["card_bg"], fg=_C["white"],
             font=(UI_FONT, 10 + _F, "bold"),
             anchor="w", justify="left").pack(fill="x")

    # Role / author
    if entry.get("role"):
        tk.Label(content, text=entry["role"],
                 bg=_C["card_bg"], fg=accent,
                 font=(UI_FONT, 8 + _F),
                 anchor="w", justify="left").pack(fill="x")

    # Description — wraplength set after layout
    desc_lbl = tk.Label(content, text=entry["desc"],
                        bg=_C["card_bg"], fg=_C["body"],
                        font=(UI_FONT, 9 + _F),
                        anchor="w", justify="left",
                        wraplength=560)
    desc_lbl.pack(fill="x", pady=(4, 0))

    # URL
    if entry.get("url"):
        tk.Label(content, text=entry["url"],
                 bg=_C["card_bg"], fg=_C["dim"],
                 font=(UI_FONT, 8 + _F),
                 anchor="w", justify="left").pack(fill="x", pady=(3, 0))
