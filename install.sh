#!/bin/bash
set -euo pipefail

echo "🔐 Installing VaultCLI..."

OS="$(uname -s)"

if [ "$OS" = "Linux" ]; then
  URL="https://github.com/wynnee0110/VaultCli/releases/latest/download/vault-linuxV1"
  CHECKSUM_URL="${URL}.sha256"
elif [ "$OS" = "Darwin" ]; then
  echo "❌ Mac not supported yet"
  exit 1
else
  echo "❌ Windows not supported"
  exit 1
fi

TMP_DIR=$(mktemp -d)
TMP_FILE="$TMP_DIR/vault-linuxV1"
CHECKSUM_FILE="$TMP_DIR/vault-linuxV1.sha256"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "⬇️ Downloading VaultCLI..."
curl -LfsSL "$URL" -o "$TMP_FILE"
curl -LfsSL "$CHECKSUM_URL" -o "$CHECKSUM_FILE"

echo "🔎 Verifying checksum..."
(cd "$TMP_DIR" && sha256sum -c "$(basename "$CHECKSUM_FILE")")

chmod +x "$TMP_FILE"
sudo mv "$TMP_FILE" /usr/local/bin/vault

echo "✅ Installed! Run: vault"
