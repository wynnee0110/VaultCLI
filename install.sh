#!/bin/bash
set -e

echo "🔐 Installing VaultCLI..."

OS="$(uname -s)"

if [ "$OS" = "Linux" ]; then
  URL="https://github.com/wynnee0110/VaultCLI/releases/download/v0.1.0/vault-linux"
elif [ "$OS" = "Darwin" ]; then
  echo "❌ Mac not supported yet"
  exit 1
else
  echo "❌ Windows not supported here"
  exit 1
fi

TMP_FILE=$(mktemp)

echo "⬇️ Downloading VaultCLI..."
curl -L "$URL" -o "$TMP_FILE"   # <-- IMPORTANT: -L handles redirect

chmod +x "$TMP_FILE"
sudo mv "$TMP_FILE" /usr/local/bin/vault

echo "✅ Installed! Run: vault"