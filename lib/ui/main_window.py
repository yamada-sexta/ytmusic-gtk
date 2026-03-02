import ytmusicapi
from typing import Optional
import threading
from lib.ui.play_view import create_now_playing_view
from lib.ui.search_bar import create_search_bar
from reactivex.subject import BehaviorSubject
import logging
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
from lib.ui.home import HomePage
from lib.net.client import auto_login


class YTMusicWindow(Adw.ApplicationWindow):

    def __init__(
        self, yt_subject: BehaviorSubject[Optional[ytmusicapi.YTMusic]], **kwargs
    ):
        super().__init__(**kwargs)
        logging.info("Initializing YT Music App UI...")
        self.set_default_size(900, 700)
        self.set_title("YT Music")

        self.player_state = PlayerState()
        self._player = setup_player(self.player_state)

        # ROOT CONTAINER (Anchors the PlayBar globally)
        root_toolbar_view = Adw.ToolbarView()
        self.set_content(root_toolbar_view)

        show_now_playing = BehaviorSubject(False)

        # The PlayBar is securely fastened to the bottom of the window
        root_toolbar_view.add_bottom_bar(PlayBar(self.player_state, show_now_playing))

        # The animated stack (Slides up/down between Main and Now Playing)
        self.main_stack = Gtk.Stack()

        # Change SLIDE_UP_DOWN to OVER_UP_DOWN
        self.main_stack.set_transition_type(Gtk.StackTransitionType.OVER_UP_DOWN)
        self.main_stack.set_transition_duration(350)  # 350ms smooth transition

        # Set the stack as the content ABOVE the PlayBar
        root_toolbar_view.set_content(self.main_stack)

        # MAIN APP VIEW (Home/Explore/Search)
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

        # DETAIL PAGE (Now Playing)
        now_playing_view = create_now_playing_view(
            self.player_state, show_now_playing=show_now_playing
        )
        self.main_stack.add_named(now_playing_view, "now_playing")

        # REACTIVE NAVIGATION LOGIC
        def on_nav_state_changed(show: bool):
            target = "now_playing" if show else "main"
            GLib.idle_add(self.main_stack.set_visible_child_name, target)

        show_now_playing.subscribe(on_nav_state_changed)

        self.fetch_data_async(yt_subject)

    def fetch_data_async(
        self, yt_subject: BehaviorSubject[Optional[ytmusicapi.YTMusic]]
    ):
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
