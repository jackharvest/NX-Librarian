## What's new in this release

### ✨ New
- **Neon mode-selection screen** — pure black background, each panel glows in its own color (red · blue · green) with an animated spotlight that sweeps down from the top on hover
- **Emoji panel icons** — 🎮 🔄 🎁 rendered in each panel's neon color with a multi-layer glow effect matching the title text
- **Multi-layer neon glow** — titles, subtitles, and icons all use a layered outer-to-inner glow with a near-white hot core, just like a real neon tube
- **Smarter spotlight hover** — hovering one panel immediately clears any stuck spotlight on the others, so the effect stays crisp as you move across panels

### 🔧 Fixed (auto-update system — all Windows)
- Seamless silent in-place upgrades now work without UAC prompts, wizard windows, or elevated rights
- Switched PyInstaller to `--onedir` mode to eliminate Windows Defender interference with temp-dir extraction on every launch
- Fixed installer-detection bug where the downloaded Setup file was saved with a random temp filename, causing it to be treated as a raw exe — which overwrote the app with the installer itself
- Added `taskkill` before install in both the updater batch script and the NSIS section to release file locks cleanly

### 📦 Installation
Download `NX-Librarian-*-Windows-Setup.exe` and run it. No admin rights required — installs to `%LocalAppData%\NX-Librarian`.

> Existing installs upgrade automatically via **Menu → Check for Updates**.
