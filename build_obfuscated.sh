#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_BIN="$ROOT_DIR/venv/bin"

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
  sha256sum vault-linuxV1 > vault-linuxV1.sha256
)

echo
echo "Obfuscated build created at: $ROOT_DIR/dist/vault-linuxV1"
