import logging
import logging
import sys
from pathlib import Path


def set_macos_dock_icon() -> None:
    """Sets the macOS dock icon using NSApplication API."""
    # If not macOS, do nothing
    if sys.platform != "darwin":
        logging.info("Not macOS, skipping dock icon set.")
        return

    try:
        from AppKit import NSApplication, NSImage

        base_dir = Path(__file__).parent.parent.parent.resolve()
        icon_file = str(base_dir / "assets" / "app" / "com.yamadasexta.YTMusicApp.svg")
        ns_image = NSImage.alloc().initWithContentsOfFile_(icon_file)
        if ns_image:
            NSApplication.sharedApplication().setApplicationIconImage_(ns_image)
            logging.info("macOS dock icon set.")
    except ImportError:
        logging.warning("AppKit not available, dock icon not set.")
    except Exception as e:
        logging.warning(f"Could not set macOS dock icon: {e}")
