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
# Nome della cartella radice dentro lo zip (l'utente estrae e trova "HiresChess/").
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

# Cartelle utente create nel pacchetto. Per ognuna, se nel repo esiste un
# README (README.md / README.en.md) viene copiato dentro: cosi' l'app
# distribuita e' auto-documentata e i README non si sovrappongono mai (ognuno
# resta nella sua cartella).
PACKAGED_FOLDERS = ["engines", "books", "data", "pgn", "openings", "endgames"]
FOLDER_READMES = ["README.md", "README.en.md"]

ENGINES_NOTE = """\
METTI QUI IL FILE DI STOCKFISH
==============================

1) Scarica Stockfish (gratis) da:  https://stockfishchess.org/download/
   -> scegli la versione "AVX2" per Windows.
2) Estrai e copia il file  stockfish-*.exe  IN QUESTA CARTELLA.
3) Avvia  chessMain.exe  ->  Tools  ->  Setup  ->  Choose engine
   e selezionalo.

Senza Stockfish non funzionano l'analisi e il gioco contro il computer.
(Questo file di testo puoi cancellarlo.)
"""

BOOKS_NOTE = """\
LIBRO D'APERTURA (OPZIONALE)
============================

Metti qui un libro d'apertura Polyglot (file .bin) se vuoi che il computer
giochi "su libro". Poi: chessMain.exe -> Tools -> Setup -> Choose book.

Non e' obbligatorio. (Questo file di testo puoi cancellarlo.)
"""

LEGGIMI_TXT = """\
========================================
  Hires Chess Trainer  v1.0.0
========================================

Grazie per aver scaricato Hires Chess Trainer!

------------------------------------------------
PRIMO AVVIO - 3 passi
------------------------------------------------

1) SCARICA STOCKFISH (il motore scacchistico, gratis):
   https://stockfishchess.org/download/
   Scegli la versione "AVX2" per Windows.
   Estrai il file .exe e copialo nella cartella:
        engines\\
   (la trovi qui dentro, accanto a chessMain.exe)

2) AVVIA il programma:
   doppio clic su  chessMain.exe

3) COLLEGA il motore:
   nel menu vai su  Tools  ->  Setup  ->  Choose engine
   e seleziona il file di Stockfish che hai messo in  engines\\

Fatto! Ora puoi usare l'analisi, il gioco contro il computer e
l'allenamento sui tuoi errori.

------------------------------------------------
LE CARTELLE
------------------------------------------------
- engines\\   : il motore Stockfish (vedi sopra)
- books\\     : libro d'apertura .bin (opzionale)
- pgn\\       : le tue partite scaricate/analizzate
- openings\\  : il tuo repertorio d'apertura
- endgames\\  : studi di finale
- data\\      : le tue learning base (errori da ripassare)
Ogni cartella contiene un README con la spiegazione.

------------------------------------------------
NOTE
------------------------------------------------
- Non serve installare Python: e' tutto incluso nel pacchetto.
- Richiede Windows 64-bit.
- Se Windows SmartScreen avvisa "app non riconosciuta":
  clic su "Ulteriori informazioni" -> "Esegui comunque".
  (Succede con i programmi non firmati; e' normale.)

Guida completa e codice sorgente:
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
    """Crea le cartelle utente accanto all'eseguibile e ci copia dentro il
    README di ciascuna (preso dal repo). Aggiunge LEGGIMI.txt in radice e le
    note per engines/ e books/ (che nel repo non hanno un README)."""
    for name in PACKAGED_FOLDERS:
        dest = bundle_root / name
        dest.mkdir(parents=True, exist_ok=True)
        src_folder = ROOT / name
        for readme in FOLDER_READMES:
            src = src_folder / readme
            if src.exists():
                shutil.copy2(src, dest / readme)

    (bundle_root / "engines" / "METTI_QUI_STOCKFISH.txt").write_text(ENGINES_NOTE, encoding="utf-8")
    (bundle_root / "books" / "LEGGIMI.txt").write_text(BOOKS_NOTE, encoding="utf-8")
    (bundle_root / "LEGGIMI.txt").write_text(LEGGIMI_TXT, encoding="utf-8")


def package_windows() -> Path:
    bundle_root = DIST / "chessMain"
    if not bundle_root.exists():
        raise FileNotFoundError(f"Missing build output: {bundle_root}")

    # Rinomina temporaneamente chessMain -> HiresChess cosi' lo zip ha una
    # cartella radice "HiresChess/" (estraendo non si sparpaglia tutto).
    staged = DIST / PACKAGE_NAME
    if staged.exists():
        shutil.rmtree(staged)
    bundle_root.rename(staged)
    try:
        stage_user_folders(staged)
        WINDOWS_ZIP.unlink(missing_ok=True)
        shutil.make_archive(str(WINDOWS_ZIP.with_suffix("")), "zip", root_dir=DIST, base_dir=PACKAGE_NAME)
    finally:
        # Ripristina il nome originale per coerenza con build successive.
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
    # Cartelle utente + README accanto alla .app dentro il DMG.
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
