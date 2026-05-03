VaultCLI is a Supabase-backed password vault CLI packaged as the `vaultcli` Python package.

## Obfuscated Build

To make the Python sources harder to read in the shipped binary, this repo includes a PyArmor-based build helper on top of PyInstaller.

Install the build tools in the project virtualenv:

```bash
./venv/bin/pip install pyarmor pyinstaller