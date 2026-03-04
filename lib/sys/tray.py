import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lib.ui.app import YTMusicApp


def setup_tray(app: "YTMusicApp") -> None:
    """Spawns a separate Qt process for the system tray icon."""

    if not sys.platform.startswith("linux"):
        logging.info("Platform is not Linux. System tray disabled.")
        return

    from gi.repository import GLib

    tray_script = str(Path(__file__).parent / "tray_process.py")

    def show_window() -> bool:
        if not app.win:
            return False
        app.win.set_visible(True)
        app.win.present()
        return False

    def exit_app() -> bool:
        app.quit()
        return False

    def monitor_tray(proc: subprocess.Popen[str]) -> None:
        """Reads stdout from the tray subprocess and dispatches actions."""
        if not proc.stdout:
            return
        for line in proc.stdout:
            action = line.strip()
            if action == "show":
                GLib.idle_add(show_window)
            elif action == "exit":
                GLib.idle_add(exit_app)

    try:
        proc = subprocess.Popen(
            [sys.executable, tray_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        app._tray_process = proc

        thread = threading.Thread(target=monitor_tray, args=(proc,), daemon=True)
        thread.start()

        import atexit

        atexit.register(proc.terminate)

        logging.info("System tray subprocess started.")
    except Exception as e:
        logging.warning(f"Could not start system tray subprocess: {e}")
