#!/bin/bash
set -euo pipefail

echo "🔐 Installing VaultCLI..."

OS="$(uname -s)"

if [ "$OS" = "Linux" ]; then
  URL="https://github.com/wynnee0110/VaultV1/releases/latest/download/vault-linuxV1"
  CHECKSUM_URL="https://github.com/wynnee0110/VaultCLI/releases/latest/download/vault-linuxV1.sha256"
else
  echo "❌ Only Linux is supported right now"
  exit 1
fi

TMP_DIR=$(mktemp -d)
TMP_FILE="$TMP_DIR/vault"
CHECKSUM_FILE="$TMP_DIR/vault.sha256"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "⬇️ Downloading VaultCLI..."
curl -LfsSL "$URL" -o "$TMP_FILE"
curl -LfsSL "$CHECKSUM_URL" -o "$CHECKSUM_FILE"

echo "🔎 Verifying checksum..."

cd "$TMP_DIR"

# safer manual verification (works with plain hash file)
EXPECTED_HASH=$(cat vault.sha256)
ACTUAL_HASH=$(sha256sum vault | awk '{print $1}')

if [ "$EXPECTED_HASH" != "$ACTUAL_HASH" ]; then
  echo "❌ Checksum verification failed!"
  exit 1
fi

chmod +x "$TMP_FILE"
sudo mv "$TMP_FILE" /usr/local/bin/vault

echo "✅ Installed! Run: vault"