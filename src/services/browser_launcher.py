import os
import shutil
import subprocess
import webbrowser

try:
    import winreg
except ImportError:
    winreg = None


def find_chrome_path() -> str | None:
    """
    Finds the Google Chrome executable on Windows or other OS.
    """
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

    # 3. Common Windows directories
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


def open_in_chrome(urls: list[str]) -> tuple[bool, str]:
    """
    Opens a list of URLs in separate tabs within Google Chrome.
    Falls back to the system default browser if Chrome is unavailable.
    """
    if not urls:
        return False, "No URLs provided."

    chrome_path = find_chrome_path()

    if chrome_path:
        try:
            subprocess.Popen([chrome_path, "--new-window", *urls])
            return True, f"Opened {len(urls)} tab(s) in a new Google Chrome window."
        except Exception as error:
            return False, f"Failed to launch Chrome directly: {error}"

    # Fallback to webbrowser module
    try:
        for url in urls:
            webbrowser.open_new_tab(url)
        return True, f"Opened {len(urls)} tab(s) in the default system browser (Chrome not located)."
    except Exception as error:
        return False, f"Failed to open browser tabs: {error}"
