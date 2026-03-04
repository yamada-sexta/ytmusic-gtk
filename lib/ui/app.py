import ytmusicapi
from reactivex.subject import BehaviorSubject
from lib.ui.main_window import YTMusicWindow
from pathlib import Path
import logging
from gi.repository import Gtk, Adw, Gst, GLib, Pango, Gio, GdkPixbuf, Gdk, GObject

import os
import subprocess


class YTMusicApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.win: YTMusicWindow | None = None
        self._tray_icon = None
        self._tray_process: subprocess.Popen[str] | None = None
        self.connect("startup", self.on_startup)
        self.connect("activate", self.on_activate)

    def on_startup(self, app: Gtk.Application):
        display = Gdk.Display.get_default()
        if not display:
            logging.warning("Could not get default display for icon theming.")
        else:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            base_dir = Path(__file__).parent.parent.parent.resolve()
            icons_path = str(base_dir / "assets" / "icons")

            logging.info(f"Looking for icons in: {icons_path}")
            if not os.path.exists(icons_path):
                logging.warning(f"Icons path does not exist: {icons_path}")

            icon_theme.add_search_path(icons_path)
            logging.info(f"Added custom icon path: {icons_path}")

        # About Action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about_action)
        self.add_action(about_action)

        # Preferences Action (Placeholder for now)
        pref_action = Gio.SimpleAction.new("preferences", None)
        pref_action.connect("activate", self.on_preferences_action)
        self.add_action(pref_action)

        # System tray icon
        from lib.sys.tray import setup_tray

        setup_tray(self)

    def on_activate(self, app: Gtk.Application):
        self.yt_subject = BehaviorSubject[ytmusicapi.YTMusic | None](None)
        self.win = YTMusicWindow(application=app, yt_subject=self.yt_subject)
        self.win.present()

    def on_about_action(self, action: Gio.SimpleAction, param: Gio.ActionGroup):
        """Displays the Adwaita About Window."""
        about = Adw.AboutWindow(
            application_name="YT Music GTK",
            application_icon="com.example.YTMusicApp",  # Ensure you have an icon matching this ID
            developer_name="Yamada Sexta",
            version="1.0.0",
            copyright="© 2026 Yamada Sexta\nThis application comes with absolutely no warranty. See the GNU General Public License, version 2 or later for details.",
            website="https://github.com/yamada-sexta/ytmusic-gtk",
            issue_url="https://github.com/yamada-sexta/ytmusic-gtk/issues",
        )
        # Attach the about window to the main app window so it behaves as a modal
        about.set_transient_for(self.get_active_window())
        about.present()

    def on_preferences_action(self, action, param):
        """Placeholder for a preferences window."""
        logging.info("Preferences menu item clicked.")
        # E.g., Adw.PreferencesWindow().present()
