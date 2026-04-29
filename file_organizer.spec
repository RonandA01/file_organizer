# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for File Organizer
# Build: pyinstaller file_organizer.spec

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['file_organizer_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the core module alongside the app
        ('file_organizer.py', '.'),
        # Bundle the icon so Qt can load it at runtime for the title bar
        ('app_icon.ico', '.'),
    ],
    hiddenimports=[
        # PyQt6 modules that may not be auto-detected
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim unused heavy packages
        'matplotlib', 'numpy', 'pandas', 'scipy',
        'tkinter', 'PIL',
        'IPython', 'jupyter',
        'PyQt5', 'PySide2', 'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,       # onedir mode — fast startup
    name='File Organizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                    # compress binaries if UPX is available
    upx_exclude=[],
    console=False,               # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='File Organizer',
)
