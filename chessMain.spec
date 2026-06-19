# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# App resources + data files of the GUI libraries that ship themes/fonts as
# package data (pygame_menu, pygame_gui): without these the build succeeds but
# crashes at runtime when it looks for the fonts/themes.
datas = [('images/*.png', 'images'), ('images/icons/*.png', 'images/icons'), ('pic-chess.png', '.')]
datas += collect_data_files('pygame_menu')
datas += collect_data_files('pygame_gui')
# NOTE: do NOT bundle books/ -- it holds COMMERCIAL opening books (ChessBase/Fritz)
# that must not be redistributed. The user downloads a free Polyglot book (INSTALL.md).

# Dynamic imports that PyInstaller's static analysis does not detect.
hiddenimports = [
    'pyttsx3.drivers',
]
if sys.platform == 'win32':
    hiddenimports += [
        'pyttsx3.drivers.sapi5',   # Text-To-Speech engine on Windows (SAPI5)
        'comtypes',                # runtime dependency of pyttsx3/SAPI5
    ]
elif sys.platform == 'darwin':
    hiddenimports += ['pyttsx3.drivers.nsss']
hiddenimports += collect_submodules('pygame_menu')
hiddenimports += collect_submodules('pygame_gui')

a = Analysis(
    ['chessMain.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='chessMain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=sys.platform == 'win32',
    disable_windowed_traceback=False,
    argv_emulation=sys.platform == 'darwin',
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='chessMain',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='HiresChess.app',
        icon=None,
        bundle_identifier='org.hireschess.trainer',
        info_plist={
            'CFBundleDisplayName': 'HiresChess',
            'CFBundleName': 'HiresChess',
            'NSHighResolutionCapable': True,
        },
    )
