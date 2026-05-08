# -*- mode: python ; coding: utf-8 -*-

import os
import platform
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs

# ---------------------------------------------------
# OS-based artifact naming
# ---------------------------------------------------

system = platform.system()

if system == "Linux":
    artifact_name = "vault-linuxV1"
elif system == "Windows":
    artifact_name = "vault-windowsV1.exe"
elif system == "Darwin":
    artifact_name = "vault-macosV1"
else:
    artifact_name = "vault"

# ---------------------------------------------------
# Dependencies (IMPORTANT FIX)
# ---------------------------------------------------

hiddenimports = (
    collect_submodules("supabase")
    + collect_submodules("argon2")
    + collect_submodules("cryptography")
    + collect_submodules("questionary")
)

binaries = collect_dynamic_libs("argon2")

# ---------------------------------------------------
# PyInstaller Analysis
# ---------------------------------------------------

a = Analysis(
    ['pyinstaller_entry.py'],

    pathex=['.'],

    binaries=binaries,   # ✅ FIXED (was empty before)

    datas=[],

    hiddenimports=hiddenimports,  # ✅ FIXED (was wrong variable)

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# ---------------------------------------------------
# PYZ archive
# ---------------------------------------------------

pyz = PYZ(a.pure)

# ---------------------------------------------------
# EXE build
# ---------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=artifact_name,

    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)