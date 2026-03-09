"""
build_scripts/gen_nsis_filelist.py
Generate installer/filelist.nsh from the PyInstaller onedir output.

NSIS's File /r does not preserve directory structure, so we enumerate
the dist/NX-Librarian/ tree and emit explicit SetOutPath + File lines
for every file found.

Usage:
    python build_scripts/gen_nsis_filelist.py
"""

import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE    = os.path.join(REPO_ROOT, "dist", "NX-Librarian")
OUTPUT    = os.path.join(REPO_ROOT, "installer", "filelist.nsh")


def main():
    if not os.path.isdir(SOURCE):
        raise SystemExit(f"ERROR: onedir output not found at {SOURCE}\n"
                         "Run 'pyinstaller main.spec' first.")

    lines = []
    last_outdir = None

    for root, _dirs, files in os.walk(SOURCE):
        if not files:
            continue
        reldir = os.path.relpath(root, SOURCE)
        if reldir == ".":
            outdir = "$INSTDIR"
        else:
            outdir = f"$INSTDIR\\{reldir}"

        if outdir != last_outdir:
            lines.append(f'SetOutPath "{outdir}"')
            last_outdir = outdir

        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            lines.append(f'File "{fpath}"')

    with open(OUTPUT, "w", encoding="ascii") as fh:
        fh.write("\r\n".join(lines) + "\r\n")

    print(f"Generated {OUTPUT}  ({len(lines)} lines, "
          f"{sum(1 for l in lines if l.startswith('File'))} files)")


if __name__ == "__main__":
    main()
