"""Unified Browser Services for v2 (Playwright & Chrome Launcher)."""

from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Sequence

try:
    import winreg
except ImportError:
    winreg = None

from v2.config import config


def find_chrome_path() -> str | None:
    """Locate the Google Chrome executable on Windows or other OS."""
    # 1. PATH environment lookup
    for binary in ("chrome", "google-chrome", "chrome.exe"):
        path = shutil.which(binary)
        if path and os.path.isfile(path):
            return path

    # 2. Windows Registry lookup
    if winreg is not None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
            ) as key:
                reg_path, _ = winreg.QueryValueEx(key, "")
                if reg_path and os.path.isfile(reg_path):
                    return reg_path
        except (OSError, FileNotFoundError):
            pass

    # 3. Common Windows directory candidates
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


def open_urls_in_chrome(urls: Sequence[str]) -> tuple[bool, str]:
    """Open a list of URLs in separate tabs within Google Chrome.

    Falls back to the system default browser if Chrome is unavailable.
    """
    valid_urls = [u.strip() for u in urls if u and u.strip()]
    if not valid_urls:
        return False, "No valid URLs provided."

    chrome_path = find_chrome_path()

    if chrome_path:
        try:
            subprocess.Popen([chrome_path, "--new-window", *valid_urls])
            return True, f"Opened {len(valid_urls)} tab(s) in Google Chrome."
        except Exception as error:
            return False, f"Failed to launch Chrome directly: {error}"

    # Fallback to webbrowser module
    try:
        for url in valid_urls:
            webbrowser.open_new_tab(url)
        return True, f"Opened {len(valid_urls)} tab(s) in default system browser (Chrome not found)."
    except Exception as error:
        return False, f"Failed to open browser tabs: {error}"
