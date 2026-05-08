#!/bin/bash
set -euo pipefail

echo "🔐 Installing VaultCLI..."

OS="$(uname -s)"

if [ "$OS" = "Linux" ]; then
  URL="https://github.com/wynnee0110/VaultCLI/releases/latest/download/vault-linuxV1"
  CHECKSUM_URL="https://github.com/wynnee0110/VaultCLI/releases/latest/download/vault-linuxV1.sha256"
elif [ "$OS" = "Darwin" ]; then
  URL="https://github.com/wynnee0110/VaultCLI/releases/latest/download/vault-macosV1"
  CHECKSUM_URL="https://github.com/wynnee0110/VaultCLI/releases/latest/download/vault-macosV1.sha256"
else
  echo "❌ Unsupported platform: $OS"
  echo "For Windows, use install.ps1."
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

EXPECTED_HASH="$(tr -d '\r\n' < "$CHECKSUM_FILE")"
if command -v sha256sum >/dev/null 2>&1; then
  ACTUAL_HASH="$(sha256sum "$TMP_FILE" | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  ACTUAL_HASH="$(shasum -a 256 "$TMP_FILE" | awk '{print $1}')"
else
  echo "❌ No SHA-256 tool found (need sha256sum or shasum)."
  exit 1
fi

if [ "$EXPECTED_HASH" != "$ACTUAL_HASH" ]; then
  echo "❌ Checksum verification failed!"
  exit 1
fi

chmod +x "$TMP_FILE"
sudo mv "$TMP_FILE" /usr/local/bin/vault

echo "✅ Installed! Run: vault"