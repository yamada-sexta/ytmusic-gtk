from lib.ui.play_view import create_now_playing_view
from lib.ui.search_bar import create_search_bar
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
from gi.repository import Gtk, Adw, Gst, GLib, Pango, Gio, GdkPixbuf, Gdk, GObject
from lib.ui.explore import ExplorePage
from lib.ui.play_bar import PlayBar, PlayerState
from lib.state.player_state import setup_player
from lib.types import YTMusicSubject
from lib.ui.home import HomePage
from lib.net.client import auto_login

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")


class YTMusicWindow(Adw.ApplicationWindow):

    def __init__(self, yt_subject: YTMusicSubject, **kwargs):
        super().__init__(**kwargs)
        logging.info("Initializing YT Music App UI...")
        self.set_default_size(900, 700)
        self.set_title("YT Music")

        self.player_state = PlayerState()
        self._player, self._mpris = setup_player(self.player_state)

        # ---------------------------------------------------------
        # 1. ROOT CONTAINER (Anchors the PlayBar globally)
        # ---------------------------------------------------------
        root_toolbar_view = Adw.ToolbarView()
        self.set_content(root_toolbar_view)

        show_now_playing = BehaviorSubject(False)

        # The PlayBar is securely fastened to the bottom of the window
        root_toolbar_view.add_bottom_bar(PlayBar(self.player_state, show_now_playing))

        # ---------------------------------------------------------
        # 2. THE ANIMATED STACK (Slides up/down between Main and Now Playing)
        # ---------------------------------------------------------
        self.main_stack = Gtk.Stack()

        # Change SLIDE_UP_DOWN to OVER_UP_DOWN
        self.main_stack.set_transition_type(Gtk.StackTransitionType.OVER_UP_DOWN)
        self.main_stack.set_transition_duration(350)  # 350ms smooth transition

        # Set the stack as the content ABOVE the PlayBar
        root_toolbar_view.set_content(self.main_stack)

        # ---------------------------------------------------------
        # 3. MAIN APP VIEW (Home/Explore/Search)
        # ---------------------------------------------------------
        main_toolbar_view = Adw.ToolbarView()
        main_toolbar_view.set_top_bar_style(Adw.ToolbarStyle.FLAT)

        self.view_stack = Adw.ViewStack()
        self.switcher = Adw.ViewSwitcher(
            stack=self.view_stack, policy=Adw.ViewSwitcherPolicy.WIDE
        )

        header = Adw.HeaderBar()
        header.set_title_widget(self.switcher)

        self.search_btn = Gtk.ToggleButton(
            icon_name="system-search-symbolic", tooltip_text="Search"
        )
        header.pack_start(self.search_btn)

        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("About YT Music", "app.about")
        self.menu_btn = Gtk.MenuButton(
            icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Main Menu"
        )
        header.pack_end(self.menu_btn)

        main_toolbar_view.add_top_bar(header)

        # Search bar setup
        self.search_bar = create_search_bar(self, self.search_btn)
        main_toolbar_view.add_top_bar(self.search_bar)

        # Add pages to your ViewStack
        main_toolbar_view.set_content(self.view_stack)
        self.view_stack.add_titled_with_icon(
            HomePage(yt_subject, self.player_state), "home", "Home", "go-home-symbolic"
        )
        self.view_stack.add_titled_with_icon(
            ExplorePage(yt_subject), "explore", "Explore", "compass2-symbolic"
        )
        self.view_stack.add_titled_with_icon(
            Gtk.Label(label="Library Coming Soon!"),
            "library",
            "Library",
            "library-symbolic",
        )

        # Add the completed Main View to the Stack
        self.main_stack.add_named(main_toolbar_view, "main")

        # ---------------------------------------------------------
        # 4. DETAIL PAGE (Now Playing)
        # ---------------------------------------------------------
        now_playing_view = create_now_playing_view(
            self.player_state, show_now_playing=show_now_playing
        )
        self.main_stack.add_named(now_playing_view, "now_playing")

        # ---------------------------------------------------------
        # 5. REACTIVE NAVIGATION LOGIC
        # ---------------------------------------------------------
        def on_nav_state_changed(show: bool):
            target = "now_playing" if show else "main"
            GLib.idle_add(self.main_stack.set_visible_child_name, target)

        show_now_playing.subscribe(on_nav_state_changed)

        self.fetch_data_async(yt_subject)

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
        self.connect("startup", self.on_startup)
        self.connect("activate", self.on_activate)

    def on_startup(self, app: Gtk.Application):
        display = Gdk.Display.get_default()
        if not display:
            logging.warning("Could not get default display for icon theming.")
        else:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            base_dir = Path(__file__).parent.resolve()
            icons_path = str(base_dir / "assets" / "icons")

            logging.info(f"Looking for icons in: {icons_path}")
            if not os.path.exists(icons_path):
                logging.warning(f"Icons path does not exist: {icons_path}")

            icon_theme.add_search_path(icons_path)
            logging.info(f"Added custom icon path: {icons_path}")

        # ---------------------------------------------------------
        # Setup Application Actions (Menu connections)
        # ---------------------------------------------------------
        # 1. About Action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about_action)
        self.add_action(about_action)

        # 2. Preferences Action (Placeholder for now)
        pref_action = Gio.SimpleAction.new("preferences", None)
        pref_action.connect("activate", self.on_preferences_action)
        self.add_action(pref_action)
        # ---------------------------------------------------------

    def on_activate(self, app: Gtk.Application):
        self.yt_subject = BehaviorSubject[ytmusicapi.YTMusic | None](None)
        self.win = YTMusicWindow(application=app, yt_subject=self.yt_subject)
        self.win.present()

    # ---------------------------------------------------------
    # Menu Action Callbacks
    # ---------------------------------------------------------
    def on_about_action(self, action: Gio.SimpleAction, param: Gio.ActionGroup):
        """Displays the Adwaita About Window."""
        about = Adw.AboutWindow(
            application_name="YT Music",
            application_icon="com.example.YTMusicApp",  # Ensure you have an icon matching this ID
            developer_name="Your Name",
            version="1.0.0",
            copyright="© 2026 Your Name",
            website="https://github.com/yourusername/ytmusic",
            issue_url="https://github.com/yourusername/ytmusic/issues",
        )
        # Attach the about window to the main app window so it behaves as a modal
        about.set_transient_for(self.get_active_window())
        about.present()

    def on_preferences_action(self, action, param):
        """Placeholder for a preferences window."""
        logging.info("Preferences menu item clicked.")
        # E.g., Adw.PreferencesWindow().present()

    # ---------------------------------------------------------


if __name__ == "__main__":
    app = YTMusicApp(application_id="com.example.YTMusicApp")
    app.run(sys.argv)
