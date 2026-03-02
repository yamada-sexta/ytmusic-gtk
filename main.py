import logging
from pathlib import Path
import ytmusicapi
from reactivex.subject import BehaviorSubject
import logging
import os
import sys
import subprocess
import threading

# --- macOS Homebrew & Virtual Environment Fix ---
try:
    brew_prefix = subprocess.check_output(["brew", "--prefix"], text=True).strip()
    brew_lib_path = f"{brew_prefix}/lib"

    os.environ["GI_TYPELIB_PATH"] = f"{brew_lib_path}/girepository-1.0"
    current_dyld = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")

    if brew_lib_path not in current_dyld:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = f"{brew_lib_path}:{current_dyld}"
        os.execv(sys.executable, [sys.executable] + sys.argv)
except Exception as e:
    print(f"Warning: Could not configure Homebrew paths automatically: {e}")
# ------------------------------------------------

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
gi.require_version("Pango", "1.0")
gi.require_version("Gio", "2.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gtk, Adw, Gst, GLib, Pango, Gio, GdkPixbuf, Gdk


from lib.ui.explore import ExplorePage
from lib.ui.play_bar import PlayBar, PlayerState
from lib.types import YTMusicSubject
from lib.ui.home import HomePage

# Assuming these are available in your project structure
# from lib.data import ExploreData
from lib.net.client import auto_login

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")


class YTMusicWindow(Adw.ApplicationWindow):

    def __init__(self, yt_subject: YTMusicSubject, **kwargs):
        super().__init__(**kwargs)
        logging.info("Initializing YT Music App UI...")
        self.set_default_size(900, 700)
        self.set_title("YT Music")

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        self.stack = Adw.ViewStack()
        self.switcher = Adw.ViewSwitcher()
        self.switcher.set_stack(self.stack)
        self.switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)

        header = Adw.HeaderBar()
        header.set_title_widget(self.switcher)
        main_box.append(header)

        main_box.append(self.stack)
        self.stack.set_vexpand(True)

        # create a single shared state model for the player
        self.player_state = PlayerState()

        # Build specific UI containers
        self.stack.add_titled_with_icon(
            HomePage(yt_subject, self.player_state), "home", "Home", "go-home-symbolic"
        )
        self.stack.add_titled_with_icon(
            ExplorePage(yt_subject), "explore", "Explore", "compass2-symbolic"
        )

        # append playbar with the shared state instance
        main_box.append(PlayBar(self.player_state))

        self.fetch_data_async(yt_subject)

    def create_empty_list_page(
        self, page_id: str, title: str, icon_name: str
    ) -> Gtk.ListBox:
        scrolled = Gtk.ScrolledWindow()
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")
        list_box.set_margin_top(12)
        list_box.set_margin_bottom(12)
        list_box.set_margin_start(12)
        list_box.set_margin_end(12)

        scrolled.set_child(list_box)
        self.stack.add_titled_with_icon(scrolled, page_id, title, icon_name)
        return list_box

    def fetch_data_async(self, yt_subject: YTMusicSubject):
        def task():
            try:
                yt = auto_login()

                if not yt:
                    return
                yt_subject.on_next(yt)
            except Exception as e:
                logging.error(f"Error fetching data: {e}")

        thread = threading.Thread(target=task, daemon=True)
        thread.start()


class YTMusicApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Add startup connection
        self.connect("startup", self.on_startup)
        self.connect("activate", self.on_activate)

    def on_startup(self, app):
        # Grab the default display and icon theme
        display = Gdk.Display.get_default()
        if not display:
            logging.warning("Could not get default display for icon theming.")
            return
        icon_theme = Gtk.IconTheme.get_for_display(display)

        # Build the absolute path to your icons directory
        # Assuming this script is at the root of your project
        # base_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = Path(__file__).parent.resolve()  # Adjust as needed
        icons_path = str(base_dir / "assets" / "icons")

        logging.info(f"Looking for icons in: {icons_path}")
        if not os.path.exists(icons_path):
            logging.warning(f"Icons path does not exist: {icons_path}")

        # Tell GTK to look in this folder for icon names
        icon_theme.add_search_path(icons_path)
        logging.info(f"Added custom icon path: {icons_path}")

    def on_activate(self, app):
        self.yt_subject = BehaviorSubject[ytmusicapi.YTMusic | None](None)
        self.win = YTMusicWindow(application=app, yt_subject=self.yt_subject)
        self.win.present()


if __name__ == "__main__":
    app = YTMusicApp(application_id="com.example.YTMusicApp")
    app.run(sys.argv)
