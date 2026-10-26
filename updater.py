import os
import sys
import json
import urllib.request
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

CURRENT_VERSION = "2.0.0"
GITHUB_REPO = "crtGhoul/VoidOrganize"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def parse_semver(v_str: str) -> Tuple[int, ...]:
    """Parse version string into tuple of integers."""
    clean = v_str.strip().lstrip("vV")
    parts = []
    for part in clean.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            break
    return tuple(parts)

def check_for_updates() -> Optional[Dict[str, Any]]:
    """
    Check GitHub Releases for a newer version of VoidOrganize.
    Returns release info dict if an update is available, else None.
    """
    try:
        req = urllib.request.Request(
            API_URL,
            headers={
                "User-Agent": "VoidOrganize-AutoUpdater",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "")
        if not latest_tag:
            return None

        current = parse_semver(CURRENT_VERSION)
        latest = parse_semver(latest_tag)

        if latest > current:
            exe_url = None
            for asset in data.get("assets", []):
                if asset.get("name", "").lower().endswith(".exe"):
                    exe_url = asset.get("browser_download_url")
                    break

            return {
                "current_version": CURRENT_VERSION,
                "latest_version": latest_tag,
                "release_name": data.get("name", latest_tag),
                "html_url": data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases"),
                "body": data.get("body", "Bug fixes and improvements."),
                "download_url": exe_url,
            }
    except Exception as e:
        print(f"Update check error: {e}")
    return None

def download_and_apply_update(download_url: str, progress_callback=None) -> bool:
    """
    Download updated executable and spawn a batch script to replace the running executable seamlessly.
    """
    try:
        current_exe = Path(sys.executable).resolve()
        temp_dir = Path(os.environ.get("TEMP", "."))
        new_exe = temp_dir / "VoidOrganize_Update.exe"

        def _reporthook(blocknum, blocksize, totalsize):
            if progress_callback and totalsize > 0:
                percent = min(100, int((blocknum * blocksize / totalsize) * 100))
                progress_callback(percent)

        urllib.request.urlretrieve(download_url, str(new_exe), reporthook=_reporthook)

        if not new_exe.exists() or new_exe.stat().st_size < 1000000:
            return False

        updater_bat = temp_dir / "voidorganize_updater.bat"
        pid = os.getpid()
        bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
:retry
taskkill /F /PID {pid} > nul 2>&1
timeout /t 1 /nobreak > nul
move /Y "{new_exe}" "{current_exe}" > nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak > nul
    goto retry
)
start "" "{current_exe}"
del "%~f0"
"""
        with open(updater_bat, "w") as f:
            f.write(bat_content)

        subprocess.Popen(
            ["cmd.exe", "/c", str(updater_bat)],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        sys.exit(0)
    except Exception as e:
        print(f"Failed to apply update: {e}")
        return False
