# -*- mode: python ; coding: utf-8 -*-
import platform

system = platform.system()
if system == "Linux":
    artifact_name = "vault-linuxV1"
elif system == "Windows":
    artifact_name = "vault-windowsV1"
elif system == "Darwin":
    artifact_name = "vault-macosV1"
else:
    artifact_name = "vault"


a = Analysis(
    ['pyinstaller_entry.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
hiddenimports=[
    "supabase",
    "postgrest",
    "gotrue",
    "storage3",
    "realtime",
],
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
