#!/bin/bash
set -euo pipefail

# ANSI color codes
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Confirmation prompt
read -rp "Do you want to install VaultCLI? (y/n): " response
if [[ ! "$response" =~ ^[yY](es)?$ ]]; then
  echo -e "${YELLOW}Installation cancelled.${NC}"
  exit 0
fi

echo -e "\n${CYAN}Installing VaultCLI...${NC}"

OS="$(uname -s)"

if [ "$OS" = "Linux" ]; then
  URL="https://github.com/wynnee0110/VaultCLI/releases/latest/download/vault-linuxV1"
  CHECKSUM_URL="https://github.com/wynnee0110/VaultCLI/releases/latest/download/vault-linuxV1.sha256"
elif [ "$OS" = "Darwin" ]; then
  URL="https://github.com/wynnee0110/VaultCLI/releases/latest/download/vault-macosV1"
  CHECKSUM_URL="https://github.com/wynnee0110/VaultCLI/releases/latest/download/vault-macosV1.sha256"
else
  echo -e "${RED}❌ Unsupported platform: $OS${NC}"
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

echo -e "${GRAY}-> Downloading release files...${NC}"
curl -LfsSL "$URL" -o "$TMP_FILE"
curl -LfsSL "$CHECKSUM_URL" -o "$CHECKSUM_FILE"

echo -e "${GRAY}-> Verifying checksum...${NC}"

cd "$TMP_DIR"

EXPECTED_HASH="$(tr -d '\r\n' < "$CHECKSUM_FILE")"
if command -v sha256sum >/dev/null 2>&1; then
  ACTUAL_HASH="$(sha256sum "$TMP_FILE" | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  ACTUAL_HASH="$(shasum -a 256 "$TMP_FILE" | awk '{print $1}')"
else
  echo -e "${RED}❌ No SHA-256 tool found (need sha256sum or shasum).${NC}"
  exit 1
fi

if [ "$EXPECTED_HASH" != "$ACTUAL_HASH" ]; then
  echo -e "${RED}❌ Checksum verification failed!${NC}"
  exit 1
fi

chmod +x "$TMP_FILE"
sudo mv "$TMP_FILE" /usr/local/bin/vault

echo -e "\n${GREEN}VaultCLI successfully installed! Run 'vault' to get started.${NC}"