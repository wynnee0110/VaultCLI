# -*- mode: python ; coding: utf-8 -*-
import os
import platform
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs
hiddenimports = (
    collect_submodules("supabase")
    + collect_submodules("argon2")
    + collect_submodules("cryptography")
    + collect_submodules("questionary")
)

binaries = collect_dynamic_libs("argon2")



# ---------------------------------------------------
# Detect operating system
# Used for naming final executable artifacts
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
# Automatically collect ALL Supabase internal modules
#
# This prevents:
# ModuleNotFoundError: No module named 'supabase'
#
# PyInstaller sometimes misses dynamically loaded
# submodules, especially in SDK-based libraries.
# ---------------------------------------------------


# ---------------------------------------------------
# PyInstaller Analysis Phase
# ---------------------------------------------------

a = Analysis(
    ['pyinstaller_entry.py'],

    # Project search paths
    pathex=['.'],

    # Additional binaries to include
    binaries=[],

    # Additional files/folders to include
    datas=[],

    # Hidden imports collected automatically
    hiddenimports=supabase_hiddenimports,

    # Optional hook paths
    hookspath=[],

    # Hook configs
    hooksconfig={},

    # Runtime hooks
    runtime_hooks=[],

    # Excluded modules
    excludes=[],

    # Store bytecode in archive
    noarchive=False,

    # Python optimization level
    optimize=0,
)


# ---------------------------------------------------
# Python module archive
# ---------------------------------------------------

pyz = PYZ(a.pure)


# ---------------------------------------------------
# Final executable build
# ---------------------------------------------------

exe = EXE(
    pyz,

    # Scripts
    a.scripts,

    # Binary dependencies
    a.binaries,

    # Data files
    a.datas,

    # ZIP files
    [],

    # Output executable name
    name=artifact_name,

    # Debug mode
    debug=False,

    # Signal handling
    bootloader_ignore_signals=False,

    # Strip debug symbols
    strip=False,

    # UPX compression
    upx=True,

    # Files excluded from UPX
    upx_exclude=[],

    # Temporary runtime dir
    runtime_tmpdir=None,

    # Console application
    console=True,

    # Disable GUI traceback window
    disable_windowed_traceback=False,

    # macOS argv emulation
    argv_emulation=False,

    # Target architecture
    target_arch=None,

    # macOS signing
    codesign_identity=None,

    # macOS entitlements
    entitlements_file=None,
)