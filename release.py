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
REQUIRED_IMPORTS = [
    "chess",
    "pygame",
    "pygame_menu",
    "pygame_gui",
    "pyperclip",
    "pyttsx3",
    "requests",
]


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


def package_windows() -> Path:
    bundle_root = DIST / "chessMain"
    if not bundle_root.exists():
        raise FileNotFoundError(f"Missing build output: {bundle_root}")
    WINDOWS_ZIP.unlink(missing_ok=True)
    shutil.make_archive(str(WINDOWS_ZIP.with_suffix("")), "zip", root_dir=bundle_root, base_dir=".")
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
