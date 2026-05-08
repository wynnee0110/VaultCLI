import os
import stat
import sys
import tempfile
import requests
from vaultcli import __version__

VERSION = __version__
GITHUB_REPO = "wynnee0110/VaultCli"
LATEST_RELEASE_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
REQUEST_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": f"VaultCLI/{VERSION}",
}


def _normalize_version(version: str) -> str:
    return version[1:] if version.startswith("v") else version


def _platform_asset_candidates(current_name: str | None = None) -> list[str]:
    candidates: list[str] = []
    if current_name:
        candidates.append(current_name)

    if sys.platform.startswith("linux"):
        candidates.extend(["vault-linuxV1", "vault-linux"])
    elif sys.platform == "darwin":
        candidates.extend(["vault-macosV1", "vault-macos"])
    elif sys.platform == "win32":
        candidates.extend(["vault-windowsV1.exe", "vault-windows.exe"])
    else:
        raise RuntimeError(f"Unsupported OS: {sys.platform}")

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            unique_candidates.append(candidate)
            seen.add(candidate)
    return unique_candidates


def _current_install_path() -> str | None:
    if getattr(sys, "frozen", False):
        return os.path.realpath(sys.executable)

    current_path = os.path.realpath(sys.argv[0])
    basename = os.path.basename(current_path)

    if basename.endswith(".py") or basename in {"pyinstaller_entry.py", "__main__.py"}:
        return None

    return current_path if os.path.isfile(current_path) else None


def _download_release(asset_url: str) -> bytes:
    response = requests.get(asset_url, headers=REQUEST_HEADERS, timeout=60)
    response.raise_for_status()
    return response.content


def _replace_installed_binary(target_path: str, payload: bytes):
    target_dir = os.path.dirname(target_path) or "."
    fd, temp_path = tempfile.mkstemp(prefix=".vault-update-", dir=target_dir)

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)

        current_mode = 0o755
        if os.path.exists(target_path):
            current_mode = stat.S_IMODE(os.stat(target_path).st_mode)
        os.chmod(temp_path, current_mode | 0o755)
        os.replace(temp_path, target_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _print_windows_update_fallback():
    print("Windows keeps running .exe files locked, so in-place self-update may fail.")
    print("Use the installer script instead:")
    print(
        "powershell -ExecutionPolicy Bypass -NoProfile "
        "-Command \"iwr https://raw.githubusercontent.com/"
        f"{GITHUB_REPO}/main/install.ps1 -OutFile install.ps1; ./install.ps1\""
    )


def command_update():
    print("Checking for updates...")

    try:
        response = requests.get(LATEST_RELEASE_API_URL, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        release = response.json()
    except requests.RequestException as exc:
        print(f"❌ Could not check for updates: {exc}")
        return 1

    latest_version = release.get("tag_name")
    if not latest_version:
        print("❌ Latest release information is unavailable.")
        return 1

    if _normalize_version(latest_version) == _normalize_version(VERSION):
        print("✅ Already up to date")
        return 0

    print(f"⬆️ Updating from {VERSION} → {latest_version}")

    current_path = _current_install_path()
    if not current_path:
        print("❌ Self-update only works from an installed VaultCLI executable.")
        print(f"Download the latest binary from: {RELEASES_URL}")
        return 1

    current_name = os.path.basename(current_path)

    try:
        asset_candidates = _platform_asset_candidates(current_name)
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1

    assets = {
        asset.get("name"): asset.get("browser_download_url")
        for asset in release.get("assets", [])
        if asset.get("name") and asset.get("browser_download_url")
    }

    asset_name = next((name for name in asset_candidates if name in assets), None)
    download_url = assets.get(asset_name) if asset_name else None

    if not download_url:
        print("❌ Could not find binary")
        print(f"Expected one of: {', '.join(asset_candidates)}")
        return 1

    print(f"Downloading update ({asset_name})...")

    try:
        binary = _download_release(download_url)
    except requests.RequestException as exc:
        print(f"❌ Could not download update: {exc}")
        return 1

    try:
        _replace_installed_binary(current_path, binary)
    except OSError as exc:
        print(f"❌ Could not replace executable at {current_path}: {exc}")
        if sys.platform == "win32":
            _print_windows_update_fallback()
        return 1

    print("✅ Update complete! Restart CLI.")
    return 0
