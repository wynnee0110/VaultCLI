VaultCLI is a Supabase-backed password vault CLI packaged as the `vaultcli` Python package.

## Install

### Linux

```bash
curl -fsSL https://raw.githubusercontent.com/wynnee0110/VaultCLI/main/install.sh | bash
```

### macOS

```bash
curl -fsSL https://raw.githubusercontent.com/wynnee0110/VaultCLI/main/install.sh | bash
```

### Windows (PowerShell)

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/wynnee0110/VaultCLI/main/install.ps1 -OutFile install.ps1
.\install.ps1
```

## Obfuscated Build

To make the Python sources harder to read in the shipped binary, this repo includes a PyArmor-based build helper on top of PyInstaller.

Install the build tools in the project virtualenv:

```bash
./venv/bin/pip install pyarmor pyinstaller
./build_obfuscated.sh

## Release Linux + Windows binaries

This repo includes a GitHub Actions workflow at `.github/workflows/release-binaries.yml`.

- Publish a GitHub release to automatically build and attach:
  - `vault-linuxV1` and `vault-linuxV1.sha256`
  - `vault-windowsV1.exe` and `vault-windowsV1.exe.sha256`
- Or run it manually from the Actions tab (`workflow_dispatch`) to test builds without creating a release.