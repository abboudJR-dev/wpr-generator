"""Launcher entrypoint for the PyInstaller-bundled Windows EXE.

Starts the Streamlit server programmatically against the bundled `app.py`,
picks an available port (default 8765, falls back automatically) and pops
the default browser open at the right URL.

Run directly during dev (`python launcher.py`) — same behaviour, just
imports from the source tree.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _bundle_root() -> Path:
    """Folder where bundled assets and app.py live.

    PyInstaller --onedir: alongside the EXE in `_internal/`. PyInstaller --onefile:
    extracted to `sys._MEIPASS`. Dev: directory of this file.
    """
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def _pick_free_port(preferred: int = 8765, max_tries: int = 20) -> int:
    """Return `preferred` if free, else scan upward."""
    for offset in range(max_tries):
        port = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred  # fall through and let Streamlit complain


def _open_browser(port: int) -> None:
    """Wait for the Streamlit server to actually answer, then open the browser.

    Polls /_stcore/health (or just `/`) until it responds 200, with a 60-second
    cap. This avoids the "WebSocket onclose" / connection-refused symptom you
    get when Chrome hits the URL before Streamlit has finished spinning up.
    """
    import urllib.request

    def _wait_and_open() -> None:
        url = f"http://localhost:{port}"
        health = f"{url}/_stcore/health"
        deadline = time.time() + 60.0
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(health, timeout=2) as r:
                    if r.status == 200:
                        break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            # Even if health never came up, try opening anyway
            pass
        # Tiny grace period for the browser to receive the index after server says ready
        time.sleep(0.3)
        webbrowser.open(url)

    threading.Thread(target=_wait_and_open, daemon=True).start()


def main() -> int:
    base = _bundle_root()
    app_path = base / "app.py"

    # When frozen, prepend the bundle root to sys.path so `import builder, extractors`
    # resolves to bundled source (PyInstaller compiles them in too, but having the
    # path makes runtime debugging easier).
    sys.path.insert(0, str(base))

    port = _pick_free_port(8765)

    print(f"WPR Generator — starting on http://localhost:{port}")
    print("First launch can take 20-40 seconds (Windows scans the bundle).")
    print("The browser will open automatically once the server is ready.")
    print("To stop, close this window or press Ctrl+C.\n", flush=True)

    _open_browser(port)

    import streamlit.web.cli as stcli  # type: ignore[import-untyped]

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]
    return stcli.main()


if __name__ == "__main__":
    sys.exit(main())
