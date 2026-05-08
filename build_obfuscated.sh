#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_BIN="$ROOT_DIR/venv/bin"
OS="$(uname -s)"

if [ "$OS" = "Linux" ]; then
  ASSET_NAME="vault-linuxV1"
elif [ "$OS" = "Darwin" ]; then
  ASSET_NAME="vault-macosV1"
else
  echo "Unsupported OS for this script: $OS"
  echo "Use install.ps1 and a Windows-native build pipeline for Windows binaries."
  exit 1
fi

if [ ! -x "$VENV_BIN/pyarmor" ]; then
  echo "PyArmor is not installed in $VENV_BIN"
  echo "Run: ./venv/bin/pip install pyarmor pyinstaller"
  exit 1
fi

rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist" "$ROOT_DIR/.pyarmor"

"$VENV_BIN/pyarmor" gen --pack "$ROOT_DIR/vault.spec" -r \
  "$ROOT_DIR/pyinstaller_entry.py" \
  "$ROOT_DIR/vaultcli"

(
  cd "$ROOT_DIR/dist"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$ASSET_NAME" | awk '{print $1}' > "$ASSET_NAME.sha256"
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$ASSET_NAME" | awk '{print $1}' > "$ASSET_NAME.sha256"
  else
    echo "No SHA-256 tool found (need sha256sum or shasum)."
    exit 1
  fi
)

echo
echo "Obfuscated build created at: $ROOT_DIR/dist/$ASSET_NAME"
