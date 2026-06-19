"""Build and package a release artifact for the current platform.

Windows -> HiresChess-windows.zip
macOS   -> HiresChess-macos.dmg

This script is intentionally platform-aware: it packages the app you build on
the current machine. To ship both artifacts, run it once on Windows and once
on macOS.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
WINDOWS_ZIP = DIST / "HiresChess-windows.zip"
MACOS_DMG = DIST / "HiresChess-macos.dmg"
MACOS_STAGE = DIST / "_release_macos"
# Name of the root folder inside the zip (the user extracts and finds "HiresChess/").
PACKAGE_NAME = "HiresChess"
REQUIRED_IMPORTS = [
    "chess",
    "pygame",
    "pygame_menu",
    "pygame_gui",
    "pyperclip",
    "pyttsx3",
    "requests",
]

# User folders created in the package. For each one, if the repo contains a
# README (README.md / README.en.md) it is copied inside: this way the
# distributed app is self-documented and the READMEs never overlap (each one
# stays in its own folder).
PACKAGED_FOLDERS = ["engines", "books", "data", "pgn", "openings", "endgames"]
FOLDER_READMES = ["README.md", "README.en.md"]

ENGINES_NOTE = """\
PUT THE STOCKFISH FILE HERE
==============================

1) Download Stockfish (free) from:  https://stockfishchess.org/download/
   -> choose the "AVX2" version for Windows.
2) Extract and copy the file  stockfish-*.exe  INTO THIS FOLDER.
3) Launch  chessMain.exe  ->  Tools  ->  Setup  ->  Choose engine
   and select it.

Without Stockfish, analysis and playing against the computer do not work.
(You can delete this text file.)
"""

BOOKS_NOTE = """\
OPENING BOOK (OPTIONAL)
============================

Put a Polyglot opening book (.bin file) here if you want the computer to
play "from the book". Then: chessMain.exe -> Tools -> Setup -> Choose book.

It is not required. (You can delete this text file.)
"""

LEGGIMI_TXT = """\
========================================
  Hires Chess Trainer  v1.4.0
========================================

Thank you for downloading Hires Chess Trainer!

------------------------------------------------
FIRST RUN - 3 steps
------------------------------------------------

1) DOWNLOAD STOCKFISH (the chess engine, free):
   https://stockfishchess.org/download/
   Choose the "AVX2" version for Windows.
   Extract the .exe file and copy it into the folder:
        engines\\
   (you'll find it in here, next to chessMain.exe)

2) LAUNCH the program:
   double-click on  chessMain.exe

3) CONNECT the engine:
   in the menu go to  Tools  ->  Setup  ->  Choose engine
   and select the Stockfish file you put in  engines\\

Done! Now you can use analysis, playing against the computer, and
training on your own mistakes.

------------------------------------------------
THE FOLDERS
------------------------------------------------
- engines\\   : the Stockfish engine (see above)
- books\\     : .bin opening book (optional)
- pgn\\       : your downloaded/analyzed games
- openings\\  : your opening repertoire
- endgames\\  : endgame studies
- data\\      : your learning bases (mistakes to review)
Each folder contains a README with the explanation.

------------------------------------------------
NOTES
------------------------------------------------
- No need to install Python: everything is included in the package.
- Requires Windows 64-bit.
- If Windows SmartScreen warns "unrecognized app":
  click "More info" -> "Run anyway".
  (This happens with unsigned programs; it's normal.)

Full guide and source code:
https://github.com/gaelazzo/python_chess
"""


def check_runtime_dependencies() -> None:
    failures = []
    for module in REQUIRED_IMPORTS:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                importlib.import_module(module)
        except Exception as exc:
            failures.append(f"{module} ({exc.__class__.__name__}: {exc})")

    if not failures:
        return

    details = "\n".join(f"- {failure}" for failure in failures)
    raise SystemExit(
        "Runtime dependency check failed:\n"
        f"{details}\nInstall/fix them with: {sys.executable} -m pip install -r requirements-dev.txt"
    )


def run_pyinstaller() -> None:
    check_runtime_dependencies()
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "chessMain.spec", "--noconfirm", "--clean"],
        cwd=ROOT,
        check=True,
    )


def stage_user_folders(bundle_root: Path) -> None:
    """Create the user folders next to the executable and copy each one's
    README inside (taken from the repo). Add LEGGIMI.txt at the root and the
    notes for engines/ and books/ (which have no README in the repo)."""
    for name in PACKAGED_FOLDERS:
        dest = bundle_root / name
        dest.mkdir(parents=True, exist_ok=True)
        src_folder = ROOT / name
        for readme in FOLDER_READMES:
            src = src_folder / readme
            if src.exists():
                shutil.copy2(src, dest / readme)

    (bundle_root / "engines" / "PUT_STOCKFISH_HERE.txt").write_text(ENGINES_NOTE, encoding="utf-8")
    (bundle_root / "books" / "README.txt").write_text(BOOKS_NOTE, encoding="utf-8")
    (bundle_root / "README.txt").write_text(LEGGIMI_TXT, encoding="utf-8")


def package_windows() -> Path:
    bundle_root = DIST / "chessMain"
    if not bundle_root.exists():
        raise FileNotFoundError(f"Missing build output: {bundle_root}")

    # Temporarily rename chessMain -> HiresChess so the zip has a
    # root folder "HiresChess/" (extracting doesn't scatter everything around).
    staged = DIST / PACKAGE_NAME
    if staged.exists():
        shutil.rmtree(staged)
    bundle_root.rename(staged)
    try:
        stage_user_folders(staged)
        WINDOWS_ZIP.unlink(missing_ok=True)
        shutil.make_archive(str(WINDOWS_ZIP.with_suffix("")), "zip", root_dir=DIST, base_dir=PACKAGE_NAME)
    finally:
        # Restore the original name for consistency with subsequent builds.
        staged.rename(bundle_root)
    return WINDOWS_ZIP


def _macos_bundle_root() -> Path:
    candidates = [DIST / "HiresChess.app", DIST / "chessMain.app"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Missing macOS app bundle: {candidates[0]} or {candidates[1]}")


def package_macos() -> Path:
    bundle_root = _macos_bundle_root()

    shutil.rmtree(MACOS_STAGE, ignore_errors=True)
    staging_bundle = MACOS_STAGE / "HiresChess.app"
    staging_bundle.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundle_root, staging_bundle)
    # User folders + README next to the .app inside the DMG.
    stage_user_folders(MACOS_STAGE)
    applications_alias = MACOS_STAGE / "Applications"
    if not applications_alias.exists():
        applications_alias.symlink_to("/Applications")

    MACOS_DMG.unlink(missing_ok=True)
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            "Hires Chess",
            "-srcfolder",
            str(MACOS_STAGE),
            "-ov",
            "-format",
            "UDZO",
            str(MACOS_DMG),
        ],
        check=True,
    )
    shutil.rmtree(MACOS_STAGE, ignore_errors=True)
    return MACOS_DMG


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and package the current platform release.")
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Stop after PyInstaller builds the app.",
    )
    args = parser.parse_args()

    run_pyinstaller()
    if args.build_only:
        return

    if sys.platform == "win32":
        artifact = package_windows()
    elif sys.platform == "darwin":
        artifact = package_macos()
    else:
        raise SystemExit(f"Unsupported platform: {sys.platform}")

    print(f"Created {artifact}")


if __name__ == "__main__":
    main()
