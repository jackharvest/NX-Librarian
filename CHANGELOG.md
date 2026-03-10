## What's new in this release

### ✨ New
- **Neon mode-selection screen** — pure black background with neon-outline icons drawn as canvas primitives (gamepad, triangle, gift box), neon glow text, and a spotlight hover effect that sweeps down from the top of each panel in that panel's color
- **Release changelogs** — GitHub releases now show human-written notes instead of raw commit messages

### 🔧 Fixed (auto-update system — all Windows)
- Seamless silent in-place upgrades now work without UAC prompts, wizard windows, or elevated rights
- Switched PyInstaller to `--onedir` mode to eliminate Windows Defender interference with temp-dir extraction on every launch
- Fixed installer-detection bug where the downloaded Setup file was saved with a random temp filename, causing it to be treated as a raw exe — which overwrote the app with the installer itself
- Added `taskkill` before install in both the updater batch script and the NSIS section to release file locks cleanly

### 📦 Installation
Download `NX-Librarian-*-Windows-Setup.exe` and run it. No admin rights required — installs to `%LocalAppData%\NX-Librarian`.

> Existing installs upgrade automatically via **Menu → Check for Updates**.
