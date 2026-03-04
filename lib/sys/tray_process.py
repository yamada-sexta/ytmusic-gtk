"""Standalone Qt system tray process.

This script runs as a separate process to avoid GTK/Qt GObject conflicts.
It communicates actions back to the parent via stdout.
"""

import sys
import threading

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon


def main() -> None:
    icon_path = sys.argv[1] if len(sys.argv) > 1 else ""

    qt_app = QApplication(sys.argv[:1])
    qt_app.setQuitOnLastWindowClosed(False)

    # Use theme icon on Linux for correct light/dark colors, file path elsewhere
    if sys.platform.startswith("linux"):
        icon = QIcon.fromTheme("folder-music-symbolic")
    elif icon_path:
        icon = QIcon(icon_path)
    else:
        icon = QIcon.fromTheme("folder-music-symbolic")
    tray = QSystemTrayIcon(icon)
    tray.setToolTip("YT Music")

    menu = QMenu()
    show_action = menu.addAction("Show Window")
    show_action.triggered.connect(lambda: _send("show"))
    exit_action = menu.addAction("Exit")
    exit_action.triggered.connect(lambda: _send("exit"))

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: (
            _send("show")
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
    )

    tray.show()

    # Quit when the parent process exits (stdin closes)
    def watch_parent() -> None:
        sys.stdin.read()
        qt_app.quit()

    threading.Thread(target=watch_parent, daemon=True).start()

    qt_app.exec()


def _send(action: str) -> None:
    """Send an action string to the parent process via stdout."""
    print(action, flush=True)


if __name__ == "__main__":
    main()
