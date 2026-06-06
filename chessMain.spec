# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Risorse dell'app + dati delle librerie GUI che spediscono temi/font come
# package data (pygame_menu, pygame_gui): senza questi il build parte ma va in
# crash a runtime quando cerca i font/temi.
datas = [('images/*.png', 'images'), ('pic-chess.png', '.')]
datas += collect_data_files('pygame_menu')
datas += collect_data_files('pygame_gui')

# Import dinamici che l'analisi statica di PyInstaller non rileva.
hiddenimports = [
    'pyttsx3.drivers',
]
if sys.platform == 'win32':
    hiddenimports += [
        'pyttsx3.drivers.sapi5',   # motore Text-To-Speech su Windows (SAPI5)
        'comtypes',                # dipendenza runtime di pyttsx3/SAPI5
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
