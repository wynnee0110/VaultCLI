Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Installing VaultCLI for Windows..."

$repo = "wynnee0110/VaultCLI"
$binaryName = "vault-windowsV1.exe"
$checksumName = "vault-windowsV1.exe.sha256"
$binaryUrl = "https://github.com/$repo/releases/latest/download/$binaryName"
$checksumUrl = "https://github.com/$repo/releases/latest/download/$checksumName"

$tmpDir = Join-Path $env:TEMP ("vaultcli-install-" + [System.Guid]::NewGuid().ToString("N"))
$tmpExe = Join-Path $tmpDir "vault.exe"
$tmpChecksum = Join-Path $tmpDir "vault.sha256"

try {
    New-Item -ItemType Directory -Path $tmpDir | Out-Null

    Write-Host "Downloading binary..."
    Invoke-WebRequest -UseBasicParsing -Uri $binaryUrl -OutFile $tmpExe
    Invoke-WebRequest -UseBasicParsing -Uri $checksumUrl -OutFile $tmpChecksum

    Write-Host "Verifying checksum..."
    $expected = (Get-Content -Path $tmpChecksum -Raw).Trim()
    $actual = (Get-FileHash -Algorithm SHA256 -Path $tmpExe).Hash.ToLowerInvariant()
    if ($expected.ToLowerInvariant() -ne $actual) {
        throw "Checksum verification failed."
    }

    $installDir = Join-Path $env:LOCALAPPDATA "VaultCLI\bin"
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null

    $targetExe = Join-Path $installDir "vault.exe"
    Move-Item -Path $tmpExe -Destination $targetExe -Force

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $pathEntries = @()
    if ($userPath) {
        $pathEntries = $userPath.Split(';') | Where-Object { $_ -ne "" }
    }

    if ($pathEntries -notcontains $installDir) {
        $newUserPath = if ($userPath) { "$userPath;$installDir" } else { $installDir }
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
        Write-Host "Added $installDir to user PATH. Restart your terminal."
    }

    Write-Host "Installed! Run: vault"
}
finally {
    if (Test-Path $tmpDir) {
        Remove-Item -Path $tmpDir -Recurse -Force
    }
}
