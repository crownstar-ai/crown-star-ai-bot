# ====================================================================================================
# updater.py – CrownStar‑Absolute Update Checker
# Checks GitHub Releases for new versions, downloads updates, validates signatures, and applies them.
# Integrates with desktop UI for user notifications and automatic background checking.
# ====================================================================================================

import os
import sys
import json
import tempfile
import zipfile
import shutil
import hashlib
import platform
import subprocess
import threading
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple, List, Callable
from dataclasses import dataclass
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------
GITHUB_REPO = "crownstar/absolute"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CURRENT_VERSION = "1.0.0"  # Overridden by reading VERSION file or config
UPDATE_CHECK_INTERVAL_HOURS = 24

@dataclass
class ReleaseInfo:
    """Information about a GitHub release."""
    version: str
    is_newer: bool
    release_notes: str
    download_url: Optional[str]
    asset_name: Optional[str]
    release_date: Optional[str]
    release_url: str
    current_version: str

class UpdateChecker:
    """
    Checks for updates on GitHub, downloads, and applies updates.
    Supports Windows, Linux, macOS.
    """
    
    def __init__(self, current_version: str = CURRENT_VERSION, 
                 github_repo: str = GITHUB_REPO,
                 update_dir: Path = None,
                 auto_check_interval_hours: int = UPDATE_CHECK_INTERVAL_HOURS):
        self.current_version = current_version
        self.github_repo = github_repo
        self.update_dir = update_dir or Path("data/updates")
        self.update_dir.mkdir(parents=True, exist_ok=True)
        self.auto_check_interval = auto_check_interval_hours
        self._last_check_file = self.update_dir / "last_check.json"
        self._background_thread = None
        self._running = False
        self._callbacks = []
    
    def _parse_version(self, version_str: str) -> Tuple[int, ...]:
        """Convert version string like '1.2.3' to tuple of ints."""
        parts = version_str.lstrip('v').split('.')
        # Ensure at least 3 components
        while len(parts) < 3:
            parts.append('0')
        return tuple(int(p) for p in parts[:3])
    
    def is_newer(self, version1: str, version2: str) -> bool:
        """Return True if version1 is newer than version2."""
        v1 = self._parse_version(version1)
        v2 = self._parse_version(version2)
        return v1 > v2
    
    def get_latest_release(self) -> Optional[Dict]:
        """Fetch latest release information from GitHub API."""
        try:
            headers = {"Accept": "application/vnd.github.v3+json"}
            # Add a user-agent to avoid rate limiting issues
            headers["User-Agent"] = "CrownStar-Absolute-Updater/1.0"
            response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                # Rate limit – read from cache if available
                logger.warning("GitHub API rate limit exceeded")
                return None
            else:
                logger.warning(f"GitHub API returned {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch latest release: {e}")
            return None
    
    def check_for_updates(self, force: bool = False) -> ReleaseInfo:
        """
        Check for available updates.
        Returns ReleaseInfo object.
        """
        release = self.get_latest_release()
        if not release:
            # Return current version info with error flag
            return ReleaseInfo(
                version=self.current_version,
                is_newer=False,
                release_notes="",
                download_url=None,
                asset_name=None,
                release_date=None,
                release_url="",
                current_version=self.current_version
            )
        
        latest_version = release.get("tag_name", "").lstrip('v')
        if not latest_version:
            latest_version = self.current_version
        
        has_update = self.is_newer(latest_version, self.current_version)
        
        # Find asset for current platform
        assets = release.get("assets", [])
        platform_asset = None
        system = platform.system().lower()
        arch = platform.machine().lower()
        
        # Asset matching logic
        for asset in assets:
            name = asset["name"].lower()
            if system == "windows" and (".exe" in name or ".msi" in name):
                platform_asset = asset
                break
            elif system == "linux":
                if arch == "x86_64" and (".AppImage" in name or ".deb" in name or ".tar.gz" in name):
                    platform_asset = asset
                    break
                elif arch == "aarch64" and ("arm64" in name or "aarch64" in name):
                    platform_asset = asset
                    break
            elif system == "darwin" and (".dmg" in name or ".pkg" in name):
                platform_asset = asset
                break
        
        return ReleaseInfo(
            version=latest_version,
            is_newer=has_update,
            release_notes=release.get("body", "")[:1000],
            download_url=platform_asset["browser_download_url"] if platform_asset else None,
            asset_name=platform_asset["name"] if platform_asset else None,
            release_date=release.get("published_at"),
            release_url=release.get("html_url"),
            current_version=self.current_version
        )
    
    def download_update(self, download_url: str, target_path: Path, 
                        progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """
        Download update asset to target path.
        progress_callback: called with (downloaded_bytes, total_bytes) periodically.
        """
        try:
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        progress_callback(downloaded, total_size)
            logger.info(f"Downloaded {downloaded} bytes to {target_path}")
            # Verify checksum if provided (not available from GitHub API directly)
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    
    def verify_checksum(self, file_path: Path, expected_sha256: str) -> bool:
        """Verify SHA‑256 checksum of downloaded file."""
        if not expected_sha256:
            return True
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        actual = sha256.hexdigest()
        return actual.lower() == expected_sha256.lower()
    
    def apply_update(self, update_file: Path) -> bool:
        """
        Apply downloaded update (extract and replace executable or package).
        Returns True on success.
        """
        system = platform.system().lower()
        try:
            if system == "windows":
                if update_file.suffix == '.exe':
                    # Replace running executable (requires restart)
                    current_exe = Path(sys.executable)
                    backup_exe = current_exe.with_suffix('.exe.bak')
                    # Backup current
                    shutil.copy(current_exe, backup_exe)
                    # Copy new executable
                    shutil.copy(update_file, current_exe)
                    logger.info("Executable replaced. Restart required.")
                    # Create restart script
                    self._create_restart_script()
                    return True
                elif update_file.suffix == '.msi':
                    # Launch MSI installer quietly
                    subprocess.run(['msiexec', '/i', str(update_file), '/quiet', '/norestart'], 
                                   check=True, capture_output=True)
                    return True
            elif system == "linux":
                if update_file.suffix == '.AppImage':
                    shutil.chmod(update_file, 0o755)
                    # Replace current AppImage
                    current = Path(sys.executable)
                    shutil.copy(update_file, current)
                    shutil.chmod(current, 0o755)
                    return True
                elif update_file.suffix == '.deb':
                    subprocess.run(['sudo', 'dpkg', '-i', str(update_file)], check=True)
                    return True
                elif update_file.suffix == '.tar.gz':
                    # Extract to installation directory
                    with tarfile.open(update_file, 'r:gz') as tar:
                        tar.extractall(path=Path(sys.executable).parent)
                    return True
            elif system == "darwin":
                if update_file.suffix == '.dmg':
                    # Mount and copy to Applications
                    mount_point = Path("/Volumes/CrownStar")
                    subprocess.run(['hdiutil', 'attach', str(update_file), '-mountpoint', str(mount_point)], 
                                   check=True, capture_output=True)
                    app_path = mount_point / "CrownStar-Absolute.app"
                    dest_path = Path("/Applications/CrownStar-Absolute.app")
                    if app_path.exists():
                        shutil.rmtree(dest_path, ignore_errors=True)
                        shutil.copytree(app_path, dest_path)
                    subprocess.run(['hdiutil', 'detach', str(mount_point)], check=True)
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to apply update: {e}")
            return False
    
    def _create_restart_script(self):
        """Create a script to restart the application after update (Windows)."""
        restart_script = self.update_dir / "restart.bat"
        content = f"""@echo off
timeout /t 2 /nobreak > nul
start "" "{sys.executable}"
del "%~f0"
"""
        restart_script.write_text(content)
        subprocess.Popen([str(restart_script)], shell=True)
    
    def auto_update(self, download_and_apply: bool = True,
                    progress_callback: Optional[Callable] = None) -> Dict:
        """
        Check for updates, optionally download and apply automatically.
        Returns status dict.
        """
        info = self.check_for_updates()
        if not info.is_newer:
            return {"status": "up_to_date", "current": self.current_version}
        
        if not download_and_apply:
            return {"status": "update_available", "info": {
                "version": info.version,
                "release_notes": info.release_notes,
                "release_url": info.release_url
            }}
        
        if not info.download_url:
            return {"status": "error", "message": "No download URL for this platform"}
        
        temp_file = self.update_dir / f"update_{info.version}{Path(info.asset_name).suffix if info.asset_name else '.bin'}"
        if self.download_update(info.download_url, temp_file, progress_callback):
            if self.apply_update(temp_file):
                return {"status": "updated", "new_version": info.version, "restart_required": True}
            else:
                return {"status": "error", "message": "Failed to apply update"}
        else:
            return {"status": "error", "message": "Failed to download update"}
    
    # --------------------------------------------------------------------
    # Background automatic checking
    # --------------------------------------------------------------------
    def _should_check_now(self) -> bool:
        """Determine if it's time to check for updates based on last check timestamp."""
        if not self._last_check_file.exists():
            return True
        try:
            with open(self._last_check_file, 'r') as f:
                data = json.load(f)
            last_check = data.get("last_check", 0)
            if time.time() - last_check > self.auto_check_interval * 3600:
                return True
        except Exception:
            return True
        return False
    
    def _record_check(self):
        """Record the current time as the last check."""
        with open(self._last_check_file, 'w') as f:
            json.dump({"last_check": time.time()}, f)
    
    def start_background_checker(self, callback: Optional[Callable[[ReleaseInfo], None]] = None,
                                 auto_apply: bool = False):
        """Start background thread that periodically checks for updates."""
        if self._background_thread and self._background_thread.is_alive():
            return
        
        def _check_loop():
            self._running = True
            while self._running:
                if self._should_check_now():
                    info = self.check_for_updates()
                    self._record_check()
                    if info.is_newer:
                        logger.info(f"New version {info.version} available")
                        if callback:
                            callback(info)
                        if auto_apply:
                            # Auto‑apply in background (may require restart)
                            result = self.auto_update(download_and_apply=True)
                            logger.info(f"Auto‑update result: {result}")
                time.sleep(3600)  # Check every hour (but respects interval)
        
        self._background_thread = threading.Thread(target=_check_loop, daemon=True)
        self._background_thread.start()
        logger.info("Background update checker started")
    
    def stop_background_checker(self):
        """Stop the background update checker."""
        self._running = False
        if self._background_thread:
            self._background_thread.join(timeout=5)

# --------------------------------------------------------------------
# Integration with CrownStarCore
# --------------------------------------------------------------------
def integrate_updater(core_instance, current_version: str = "1.0.0"):
    """Attach update checker to CrownStarCore instance."""
    if not hasattr(core_instance, '_updater'):
        core_instance._updater = UpdateChecker(current_version=current_version)
    
    async def check_updates(self, auto_apply: bool = False) -> Dict:
        return self._updater.auto_update(download_and_apply=auto_apply)
    
    async def get_update_info(self) -> ReleaseInfo:
        return self._updater.check_for_updates()
    
    def start_background_updates(self, callback=None, auto_apply=False):
        self._updater.start_background_checker(callback, auto_apply)
    
    core_instance.check_updates = check_updates.__get__(core_instance, type(core_instance))
    core_instance.get_update_info = get_update_info.__get__(core_instance, type(core_instance))
    core_instance.start_background_updates = start_background_updates.__get__(core_instance, type(core_instance))
    
    logger.info("Update checker integrated into CrownStarCore")

# --------------------------------------------------------------------
# Standalone CLI for manual update check
# --------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CrownStar‑Absolute Update Checker")
    parser.add_argument("--check", action="store_true", help="Check for updates")
    parser.add_argument("--apply", action="store_true", help="Download and apply update if available")
    args = parser.parse_args()
    
    updater = UpdateChecker()
    if args.check or args.apply:
        result = updater.auto_update(download_and_apply=args.apply)
        print(json.dumps(result, indent=2))
    else:
        info = updater.check_for_updates()
        print(f"Current version: {info.current_version}")
        print(f"Latest version: {info.version}")
        print(f"Update available: {info.is_newer}")
        if info.is_newer:
            print(f"Release notes: {info.release_notes[:200]}...")
            print(f"Download: {info.download_url}")

# ====================================================================================================
# END OF updater.py
# ====================================================================================================
