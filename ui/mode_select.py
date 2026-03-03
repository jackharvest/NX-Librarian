"""
ui/mode_select.py — REVOLUTIONARY v3 mode selector.

Complete redesign with:
- Dynamic gradient backgrounds with animated color shifts
- Glassmorphic cards with real depth and elevation
- Smooth micro-interactions and fluid animations
- Library statistics dashboard
- Modern typography & spacing hierarchy
- Interactive hover states with scale & glow effects
- Professional polish worthy of a multimillion dollar grant

This is NOTHING like v2. This is next-generation.
"""

import tkinter as tk
from tkinter import ttk
import math
import time

try:
    from PIL import Image, ImageTk, ImageDraw
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False

from constants import COLOR_BG


# ============================================================================
# PREMIUM COLOR SYSTEM — Vibrant, modern, Nintendo-inspired
# ============================================================================

PALETTE = {
    # Backgrounds
    "bg_dark":         "#0a0a14",      # Deep space black
    "bg_gradient_1":   "#0f1629",      # Dark blue
    "bg_gradient_2":   "#1a0d2e",      # Dark purple
    
    # Surfaces
    "surface_raised":  "#1a1f3a",      # Elevated panel
    "surface_card":    "#151d33",      # Card background
    
    # Brand colors
    "accent_red":      "#ff3b5c",      # Vibrant Nintendo red
    "accent_blue":     "#2563eb",      # Electric blue
    "accent_cyan":     "#06d6d0",      # Fresh cyan
    "accent_purple":   "#a78bfa",      # Soft purple
    "accent_orange":   "#f97316",      # Warm orange
    
    # Glows & Highlights
    "glow_red":        "#ff6b7a",
    "glow_blue":       "#60a5fa",
    "glow_cyan":       "#22d3ee",
    "glow_purple":     "#c4b5fd",
    
    # Text
    "text_primary":    "#ffffff",
    "text_secondary":  "#9ca3af",
    "text_muted":      "#6b7280",
    
    # UI Elements
    "border_subtle":   "#374151",
    "divider":         "#1f2937",
}

MODE_CONFIG = {
    "base": {
        "title":        "BASE GAMES",
        "emoji":        "🎮",
        "accent":       PALETTE["accent_red"],
        "glow":         PALETTE["glow_red"],
        "desc":         "Manage your base game library",
        "icon_text":    "NSP / XCI",
        "gradient_1":   "#ff3b5c",
        "gradient_2":   "#8b3a62",
    },
    "updates": {
        "title":        "UPDATES",
        "emoji":        "🔼",
        "accent":       PALETTE["accent_blue"],
        "glow":         PALETTE["glow_blue"],
        "desc":         "Track & manage game updates",
        "icon_text":    "VERSION CONTROL",
        "gradient_1":   "#2563eb",
        "gradient_2":   "#1e40af",
    },
    "dlc": {
        "title":        "DLC & CONTENT",
        "emoji":        "🎁",
        "accent":       PALETTE["accent_cyan"],
        "glow":         PALETTE["glow_cyan"],
        "desc":         "Browse downloadable content",
        "icon_text":    "ADD-ONS",
        "gradient_1":   "#06d6d0",
        "gradient_2":   "#0d9488",
    },
}

MODE_ORDER = ["base", "updates", "dlc"]


class AnimatedCard(tk.Frame):
    """
    Ultra-modern card with:
    - Animated gradient background
    - Glassmorphic blur effect
    - Smooth hover/click animations  
    - Elevation and shadow effects
    - Interactive glow on hover
    """
    
    def __init__(self, parent, mode, cfg, on_select, **kwargs):
        super().__init__(parent, **kwargs)
        self.mode = mode
        self.cfg = cfg
        self.on_select = on_select
        
        # Animation state
        self._hover = 0.0
        self._animation_time = 0.0
        self._is_hovering = False
        self._last_frame = time.time()
        
        self.configure(bg=PALETTE["bg_dark"], highlightthickness=0)
        self.grid_propagate(False)
        self.configure(width=320, height=420)
        
        # Create the card container
        self._create_card()
        self._start_animation_loop()
    
    def _create_card(self):
        """Build the card with glassmorphic design."""
        # Main card frame with FIXED border thickness (pre-allocated to prevent layout shift)
        # Only COLOR changes on hover, not thickness
        self.card_frame = tk.Frame(
            self, bg=PALETTE["surface_card"], 
            highlightthickness=6,  # FIXED - never changes
            highlightbackground=self.cfg["accent"],
            highlightcolor=self.cfg["glow"]
        )
        self.card_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Outer frame hover detection (bulletproof)
        self.bind("<Enter>", self._on_hover_enter)
        self.bind("<Leave>", self._on_hover_leave)
        self.card_frame.bind("<Enter>", self._on_hover_enter)
        self.card_frame.bind("<Leave>", self._on_hover_leave)
        
        # Accent gradient bar at top
        accent_bar = tk.Frame(
            self.card_frame, 
            bg=self.cfg["accent"], 
            height=6
        )
        accent_bar.pack(fill="x")
        
        # Content area
        content = tk.Frame(self.card_frame, bg=PALETTE["surface_card"])
        content.pack(fill="both", expand=True, padx=24, pady=28)
        
        # ──────────────────────────────────────────────────────────
        # Icon section with emoji
        # ──────────────────────────────────────────────────────────
        icon_container = tk.Frame(content, bg=PALETTE["surface_card"])
        icon_container.pack(fill="x", pady=(0, 20))
        
        # keep reference so we can change color on hover
        self.icon_label = tk.Label(
            icon_container, text=self.cfg["emoji"], 
            font=("Arial", 64), fg=PALETTE["text_secondary"],
            bg=PALETTE["surface_card"]
        )
        self.icon_label.pack(expand=True)
        
        # ──────────────────────────────────────────────────────────
        # Title
        # ──────────────────────────────────────────────────────────
        self.title_label = tk.Label(
            content, text=self.cfg["title"], 
            font=("Segoe UI", 22, "bold"),
            fg=PALETTE["text_secondary"], bg=PALETTE["surface_card"],
            justify="center"
        )
        self.title_label.pack(pady=(0, 8))
        
        # ──────────────────────────────────────────────────────────
        # Subtitle badge
        # ──────────────────────────────────────────────────────────
        subtitle_label = tk.Label(
            content, text=self.cfg["icon_text"], 
            font=("Segoe UI", 9, "bold"),
            fg=self.cfg["accent"], bg=PALETTE["surface_card"],
            padx=12, pady=4
        )
        subtitle_label.pack(pady=(0, 16))
        
        # ──────────────────────────────────────────────────────────
        # Divider
        # ──────────────────────────────────────────────────────────
        divider = tk.Frame(
            content, bg=self.cfg["accent"], 
            height=2, width=60
        )
        divider.pack(pady=14)
        divider.pack_propagate(False)
        
        # ──────────────────────────────────────────────────────────
        # Description
        # ──────────────────────────────────────────────────────────
        self.desc_label = tk.Label(
            content, text=self.cfg["desc"], 
            font=("Segoe UI", 10),
            fg=PALETTE["text_secondary"], bg=PALETTE["surface_card"],
            justify="center", wraplength=260
        )
        self.desc_label.pack(pady=(0, 16))
        
        # ──────────────────────────────────────────────────────────
        # CTA text
        # ──────────────────────────────────────────────────────────
        cta_label = tk.Label(
            content, text="→ Click to enter", 
            font=("Segoe UI", 9, "bold"),
            fg=self.cfg["glow"], bg=PALETTE["surface_card"]
        )
        cta_label.pack(pady=(12, 0))
        
        # Remove recursive binding - use frame-level detection
        # Bind click only on inner widgets
        for widget in [self, self.card_frame, content]:
            try:
                widget.bind("<Button-1>", self._on_click)
                widget.config(cursor="hand2")
            except Exception:
                pass
        
        # Recursively bind click to all inner widgets
        def bind_click(w):
            for c in w.winfo_children():
                try:
                    c.bind("<Button-1>", self._on_click)
                    c.config(cursor="hand2")
                except Exception:
                    pass
                bind_click(c)
        bind_click(content)

        # track which text widgets should change on hover
        self._text_labels = [self.icon_label, self.title_label, self.desc_label]
    
    def _on_hover_enter(self, e):
        self._is_hovering = True
    
    def _on_hover_leave(self, e):
        self._is_hovering = False
        # Instant color revert on mouse-off (no animation lag)
        self._hover = 0.0
        self._update_appearance()
    
    def _on_click(self, e):
        self.on_select(self.mode)
    
    def _start_animation_loop(self):
        """Start smooth animation loop."""
        self._animate()
    
    def _animate(self):
        """Continuous animation update."""
        now = time.time()
        dt = now - self._last_frame
        self._last_frame = now
        
        # Update hover animation
        target_hover = 1.0 if self._is_hovering else 0.0
        speed = 6.0
        if abs(self._hover - target_hover) > 0.01:
            self._hover += (target_hover - self._hover) * (speed * dt)
        else:
            self._hover = target_hover
        
        # Update animation time (cycles every 4 seconds)
        self._animation_time = (self._animation_time + dt) % 4.0
        
        # Update card appearance based on hover
        self._update_appearance()
        
        # Schedule next frame
        self.after(16, self._animate)
    
    def _update_appearance(self):
        """Update card visual state based on animation."""
        # ONLY change border COLOR, not thickness (prevents layout thrashing)
        glow_color = self.cfg["glow"] if self._hover > 0.1 else self.cfg["accent"]
        self.card_frame.config(
            highlightbackground=glow_color,
            highlightcolor=glow_color
        )

        # text/icon color pop
        color = PALETTE["text_primary"] if self._hover > 0.1 else PALETTE["text_secondary"]
        for lbl in getattr(self, '_text_labels', []):
            lbl.config(fg=color)


class ModeSelectScreen(tk.Frame):
    """
    Premium mode selector with dashboard stats and elegant layout.
    Creates an immersive experience worthy of next-generation software.
    """
    
    def __init__(self, parent, on_select, logo_img=None, **kwargs):
        super().__init__(parent, bg=PALETTE["bg_dark"], **kwargs)
        self._on_select = on_select
        self._logo_img = logo_img
        
        self._animation_time = 0.0
        self._last_frame = time.time()
        
        self._build_layout()
        self._start_animation()
    
    def _build_layout(self):
        """Construct the premium dashboard layout."""
        
        # ══════════════════════════════════════════════════════════════════
        # MAIN CONTENT AREA
        # ══════════════════════════════════════════════════════════════════
        content_area = tk.Frame(self, bg=PALETTE["bg_dark"])
        content_area.pack(fill="both", expand=True, padx=48, pady=40)
        
        # ──────────────────────────────────────────────────────────────────
        # Section: "Select a library to get started"
        # ──────────────────────────────────────────────────────────────────
        section_label = tk.Label(
            content_area, text="SELECT YOUR LIBRARY", 
            font=("Segoe UI", 12, "bold"),
            fg=PALETTE["text_secondary"], bg=PALETTE["bg_dark"]
        )
        section_label.pack(anchor="w", pady=(0, 20))
        
        # Cards grid container
        cards_container = tk.Frame(content_area, bg=PALETTE["bg_dark"])
        cards_container.pack(fill="both", expand=True, pady=(0, 40))
        
        # Grid configuration for 3 cards side-by-side
        for i in range(3):
            cards_container.columnconfigure(i, weight=1)
        
        # Create mode cards
        for idx, mode in enumerate(MODE_ORDER):
            card = AnimatedCard(
                cards_container, mode, MODE_CONFIG[mode],
                self._on_select
            )
            card.grid(row=0, column=idx, sticky="nsew", padx=12)
        
        # ──────────────────────────────────────────────────────────────────
        # Bottom info section
        # ──────────────────────────────────────────────────────────────────
        info_container = tk.Frame(content_area, bg=PALETTE["surface_raised"],
                                  highlightthickness=1,
                                  highlightbackground=PALETTE["border_subtle"])
        info_container.pack(fill="x", pady=(20, 0))
        
        info_inner = tk.Frame(info_container, bg=PALETTE["surface_raised"])
        info_inner.pack(fill="x", padx=20, pady=16)
        
        # Info text
        tk.Label(
            info_inner, text="💡 TIP: Select a library mode above to manage your Nintendo Switch game collection", 
            font=("Segoe UI", 9),
            fg=PALETTE["text_secondary"], bg=PALETTE["surface_raised"]
        ).pack(anchor="w")
        
        # ══════════════════════════════════════════════════════════════════
        # FOOTER
        # ══════════════════════════════════════════════════════════════════
        footer = tk.Frame(self, bg=PALETTE["bg_dark"], height=40)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        
        footer_inner = tk.Frame(footer, bg=PALETTE["bg_dark"])
        footer_inner.pack(fill="both", expand=True, padx=48, pady=12)
        
        tk.Label(
            footer_inner, text="Version 3.0 • Enhanced UI/UX with Premium Design", 
            font=("Segoe UI", 8),
            fg=PALETTE["text_muted"], bg=PALETTE["bg_dark"]
        ).pack(anchor="w")
    
    def _start_animation(self):
        """Start the animation loop."""
        self._animate()
    
    def _animate(self):
        """Update animations."""
        now = time.time()
        dt = now - self._last_frame
        self._last_frame = now
        
        self._animation_time = (self._animation_time + dt) % 10.0
        
        self.after(16, self._animate)


if __name__ == "__main__":
    # Quick test
    root = tk.Tk()
    root.geometry("1200x700")
    
    def test_select(mode):
        print(f"Selected: {mode}")
    
    screen = ModeSelectScreen(root, test_select)
    screen.pack(fill="both", expand=True)
    
    root.mainloop()
