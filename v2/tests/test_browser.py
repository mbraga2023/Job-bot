"""Tests for Chrome lookup and browser launch fallback behavior."""

from __future__ import annotations

import contextlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from v2.core import browser


class TestBrowserServices(unittest.TestCase):
    def test_find_chrome_path_prefers_executable_on_path(self) -> None:
        with (
            patch.object(browser.shutil, "which", return_value="C:\\Chrome\\chrome.exe") as which,
            patch.object(browser.os.path, "isfile", return_value=True),
        ):
            result = browser.find_chrome_path()

        self.assertEqual(result, "C:\\Chrome\\chrome.exe")
        which.assert_called_once_with("chrome")

    def test_find_chrome_path_uses_registry_when_path_lookup_misses(self) -> None:
        registry_path = "C:\\Installed\\chrome.exe"
        registry_key = object()
        fake_registry = SimpleNamespace(
            HKEY_LOCAL_MACHINE="machine",
            OpenKey=MagicMock(return_value=contextlib.nullcontext(registry_key)),
            QueryValueEx=MagicMock(return_value=(registry_path, 0)),
        )
        with (
            patch.object(browser, "winreg", fake_registry),
            patch.object(browser.shutil, "which", return_value=None),
            patch.object(browser.os.path, "isfile", return_value=True),
        ):
            result = browser.find_chrome_path()

        self.assertEqual(result, registry_path)
        fake_registry.OpenKey.assert_called_once_with(
            "machine",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
        )

    def test_find_chrome_path_returns_none_when_registry_and_candidates_are_missing(self) -> None:
        with (
            patch.object(browser, "winreg", None),
            patch.object(browser.shutil, "which", return_value=None),
            patch.object(browser.os.path, "isfile", return_value=False),
        ):
            self.assertIsNone(browser.find_chrome_path())

    def test_open_urls_filters_empty_values_and_launches_chrome(self) -> None:
        urls = [" https://example.com/1 ", "", "https://example.com/2"]
        with (
            patch.object(browser, "find_chrome_path", return_value="chrome.exe"),
            patch.object(browser.subprocess, "Popen") as popen,
        ):
            result = browser.open_urls_in_chrome(urls)

        self.assertEqual(result, (True, "Opened 2 tab(s) in Google Chrome."))
        popen.assert_called_once_with([
            "chrome.exe",
            "--new-window",
            "https://example.com/1",
            "https://example.com/2",
        ])

    def test_open_urls_reports_direct_launch_failure(self) -> None:
        with (
            patch.object(browser, "find_chrome_path", return_value="chrome.exe"),
            patch.object(browser.subprocess, "Popen", side_effect=OSError("launch failed")),
        ):
            result = browser.open_urls_in_chrome(["https://example.com"])

        self.assertEqual(result, (False, "Failed to launch Chrome directly: launch failed"))

    def test_open_urls_uses_default_browser_when_chrome_is_missing(self) -> None:
        with (
            patch.object(browser, "find_chrome_path", return_value=None),
            patch.object(browser.webbrowser, "open_new_tab") as open_tab,
        ):
            result = browser.open_urls_in_chrome(["https://example.com/1", "https://example.com/2"])

        self.assertTrue(result[0])
        self.assertEqual(result[1], "Opened 2 tab(s) in default system browser (Chrome not found).")
        self.assertEqual(
            [call.args[0] for call in open_tab.call_args_list],
            ["https://example.com/1", "https://example.com/2"],
        )

    def test_open_urls_reports_default_browser_failure(self) -> None:
        with (
            patch.object(browser, "find_chrome_path", return_value=None),
            patch.object(browser.webbrowser, "open_new_tab", side_effect=RuntimeError("browser failed")),
        ):
            result = browser.open_urls_in_chrome(["https://example.com"])

        self.assertEqual(result, (False, "Failed to open browser tabs: browser failed"))

    def test_open_urls_rejects_empty_input_without_browser_lookup(self) -> None:
        with patch.object(browser, "find_chrome_path") as find_chrome:
            result = browser.open_urls_in_chrome(["", "  "])

        self.assertEqual(result, (False, "No valid URLs provided."))
        find_chrome.assert_not_called()


if __name__ == "__main__":
    unittest.main()
