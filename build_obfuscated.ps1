Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvScripts = Join-Path $rootDir "venv\Scripts"
$pyarmor = Join-Path $venvScripts "pyarmor.exe"

if (-not (Test-Path $pyarmor)) {
    throw "PyArmor is not installed in $venvScripts. Run: .\venv\Scripts\pip install pyarmor pyinstaller"
}

Remove-Item -Path (Join-Path $rootDir "build") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path (Join-Path $rootDir "dist") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path (Join-Path $rootDir ".pyarmor") -Recurse -Force -ErrorAction SilentlyContinue

& $pyarmor gen --pack (Join-Path $rootDir "vault.spec") -r `
    (Join-Path $rootDir "pyinstaller_entry.py") `
    (Join-Path $rootDir "vaultcli")

$distDir = Join-Path $rootDir "dist"
$assetExe = Join-Path $distDir "vault-windowsV1.exe"
if (-not (Test-Path $assetExe)) {
    throw "Expected build output not found: $assetExe"
}

$hash = (Get-FileHash -Algorithm SHA256 -Path $assetExe).Hash.ToLowerInvariant()
Set-Content -Path (Join-Path $distDir "vault-windowsV1.exe.sha256") -Value $hash -NoNewline

Write-Host ""
Write-Host "Obfuscated Windows build created at: $assetExe"
