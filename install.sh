#!/bin/bash
set -euo pipefail

echo "🔐 Installing VaultCLI..."

OS="$(uname -s)"

if [ "$OS" = "Linux" ]; then
URL="https://github.com/wynnee0110/VaultCLI/releases/download/v1.0.0/vault-linuxV1"

else
  echo "❌ Only Linux is supported right now"
  exit 1
fi

TMP_DIR=$(mktemp -d)
TMP_FILE="$TMP_DIR/vault"


cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "⬇️ Downloading VaultCLI..."
curl -LfsSL "$URL" -o "$TMP_FILE"


chmod +x "$TMP_FILE"
sudo mv "$TMP_FILE" /usr/local/bin/vault

echo "✅ Installed! Run: vault"