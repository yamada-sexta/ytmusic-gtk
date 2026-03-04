import ytmusicapi
from typing import Optional
import threading
from lib.ui.play_view import NowPlayingView
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
        self.set_icon_name("com.example.YTMusicApp")

        self.player_state = PlayerState(yt=yt_subject)
        self._player = setup_player(self.player_state)

        show_now_playing = BehaviorSubject(False)

        # ROOT CONTAINER (Anchors the PlayBar globally)
        root_toolbar_view = Adw.ToolbarView()
        self.set_content(root_toolbar_view)

        # The PlayBar is securely fastened to the bottom of the window
        root_toolbar_view.add_bottom_bar(PlayBar(self.player_state, show_now_playing))

        # NavigationView sits above the play bar, below the window chrome
        self.nav_view = Adw.NavigationView()
        root_toolbar_view.set_content(self.nav_view)

        # Root navigation page holds the header + main content
        root_nav_page = Adw.NavigationPage(title="YT Music")
        self.nav_view.add(root_nav_page)

        # Inner toolbar holds the global header bar and the main stack
        inner_toolbar_view = Adw.ToolbarView()
        root_nav_page.set_child(inner_toolbar_view)

        # The animated stack (slides up/down between Main and Now Playing)
        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.OVER_UP_DOWN)
        self.main_stack.set_transition_duration(350)
        inner_toolbar_view.set_content(self.main_stack)

        # Global HeaderBar (on inner_toolbar_view so it stays persistent)
        self.header = Adw.HeaderBar()
        inner_toolbar_view.add_top_bar(self.header)

        # Stack for center title widget
        self.title_stack = Gtk.Stack()
        self.title_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self.view_stack = Adw.ViewStack()
        self.switcher = Adw.ViewSwitcher(
            stack=self.view_stack, policy=Adw.ViewSwitcherPolicy.WIDE
        )
        self.title_stack.add_named(self.switcher, "main")
        self.title_stack.add_named(Gtk.Box(), "now_playing")
        self.header.set_title_widget(self.title_stack)

        # Stack for start buttons
        self.start_stack = Gtk.Stack()
        self.start_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self.search_btn = Gtk.ToggleButton(
            icon_name="system-search-symbolic", tooltip_text="Search"
        )
        self.start_stack.add_named(self.search_btn, "main")

        close_btn = Gtk.Button(
            icon_name="go-down-symbolic", tooltip_text="Close Now Playing"
        )
        close_btn.add_css_class("flat")
        close_btn.connect("clicked", lambda *_: show_now_playing.on_next(False))
        self.start_stack.add_named(close_btn, "now_playing")

        self.header.pack_start(self.start_stack)

        # Stack for end buttons
        self.end_stack = Gtk.Stack()
        self.end_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("About YT Music", "app.about")
        self.menu_btn = Gtk.MenuButton(
            icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Main Menu"
        )
        self.end_stack.add_named(self.menu_btn, "main")
        self.end_stack.add_named(Gtk.Box(), "now_playing")

        self.header.pack_end(self.end_stack)

        # MAIN APP VIEW (Home/Explore/Search)
        main_toolbar_view = Adw.ToolbarView()

        # Search bar setup
        self.search_bar = create_search_bar(self, self.search_btn)
        main_toolbar_view.add_top_bar(self.search_bar)

        # Add pages to your ViewStack
        main_toolbar_view.set_content(self.view_stack)
        self.view_stack.add_titled_with_icon(
            HomePage(yt_subject, self.player_state, self.nav_view),
            "home",
            "Home",
            "go-home-symbolic",
        )
        self.view_stack.add_titled_with_icon(
            ExplorePage(yt_subject, self.nav_view),
            "explore",
            "Explore",
            "compass2-symbolic",
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
        now_playing_view = NowPlayingView(self.player_state)
        self.main_stack.add_named(now_playing_view, "now_playing")

        # REACTIVE NAVIGATION LOGIC
        def on_nav_state_changed(show: bool):
            def _update():
                # Pop any pushed pages so Now Playing is never covered
                if show:
                    self.nav_view.pop_to_page(root_nav_page)
                target = "now_playing" if show else "main"
                self.main_stack.set_visible_child_name(target)
                self.title_stack.set_visible_child_name(target)
                self.start_stack.set_visible_child_name(target)
                self.end_stack.set_visible_child_name(target)
            GLib.idle_add(_update)

        show_now_playing.subscribe(on_nav_state_changed)

        self.connect("close-request", self._on_close_request)

        self.fetch_data_async(yt_subject)

    def _on_close_request(self, window: Adw.ApplicationWindow) -> bool:
        """Hide the window instead of destroying it to keep running in the tray."""
        app = self.get_application()
        if app and getattr(app, "_tray_process", None):
            logging.info("Hiding window, keeping process alive for tray.")
            self.set_visible(False)
            return True
        return False

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
