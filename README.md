# VaultCLI

VaultCLI is a Supabase-backed password vault CLI packaged as the `vaultcli` Python package.

## Obfuscated Build

To make the Python sources harder to read in the shipped binary, this repo includes a PyArmor-based build helper on top of PyInstaller.

Install the build tools in the project virtualenv:

```bash
./venv/bin/pip install pyarmor pyinstaller
```

Build an obfuscated executable:

```bash
./build_obfuscated.sh
```

The resulting binary is written to:

```bash
dist/vault-linuxv1
```

This uses PyArmor to obfuscate `pyinstaller_entry.py` and the `vaultcli/` package, then repacks the app through `vault.spec`.
