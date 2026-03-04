"""macOS dock icon click observer.

Uses NSApplicationDelegate to intercept dock icon clicks and show the window.
"""

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lib.ui.app import YTMusicApp


def setup_macos_dock_handler(app: "YTMusicApp") -> None:
    """Observes macOS dock icon clicks to restore the hidden window."""

    if sys.platform != "darwin":
        return

    try:
        import objc  # type: ignore
        from AppKit import NSApplication, NSObject
        from gi.repository import GLib

        ns_app = NSApplication.sharedApplication()
        original_delegate = ns_app.delegate()

        # Subclass to intercept applicationShouldHandleReopen:hasVisibleWindows:
        class DockClickDelegate(NSObject):
            def applicationShouldHandleReopen_hasVisibleWindows_(
                self, sender: NSApplication, has_visible: bool
            ) -> bool:
                if not has_visible:

                    def _show() -> bool:
                        if not app.win:
                            return False
                        app.win.set_visible(True)
                        app.win.present()
                        return False

                    GLib.idle_add(_show)
                return True

        delegate = DockClickDelegate.alloc().init()
        ns_app.setDelegate_(delegate)

        # Keep a reference so it doesn't get garbage collected
        app._dock_delegate = delegate  # type: ignore

        logging.info("macOS dock click handler installed.")
    except ImportError:
        logging.warning("AppKit not available, dock click handler not installed.")
    except Exception as e:
        logging.warning(f"Could not install dock click handler: {e}")
