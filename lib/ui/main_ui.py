from lib.net.client import YTClient
from lib.state.player_state import PlayerState
from lib.state.setup_player import setup_player
from lib.ui.play_bar import PlayBar
from lib.ui.now_playing import NowPlayingView
from lib.ui.search_bar import create_search_bar
from lib.ui.home import HomePage
from reactivex.subject import BehaviorSubject
import reactivex as rx
import gi
from gi.repository import Gtk, Adw, Gio, GLib, Gtk


def MainUI(
    client: "YTClient", app_name: str, window: Adw.ApplicationWindow
) -> Gtk.Widget:
    """Constructs and returns the main application UI widget."""
    player_state = PlayerState(client=client)
    player = setup_player(player_state)
    show_now_playing = BehaviorSubject(False)

    root_toolbar_view = Adw.ToolbarView()

    # We attach the player to the root widget to prevent it from being garbage collected
    # since it's not a GTK widget in the UI tree.
    # root_toolbar_view._player = player

    root_toolbar_view.add_bottom_bar(PlayBar(player_state, show_now_playing))

    nav_view = Adw.NavigationView()
    root_toolbar_view.set_content(nav_view)

    root_nav_page = Adw.NavigationPage(title=app_name)
    nav_view.add(root_nav_page)

    inner_toolbar_view = Adw.ToolbarView()
    root_nav_page.set_child(inner_toolbar_view)

    main_stack = Gtk.Stack()
    main_stack.set_transition_type(Gtk.StackTransitionType.OVER_UP_DOWN)
    main_stack.set_transition_duration(350)
    inner_toolbar_view.set_content(main_stack)

    header = Adw.HeaderBar()
    inner_toolbar_view.add_top_bar(header)

    title_stack = Gtk.Stack()
    title_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

    view_stack = Adw.ViewStack()
    switcher = Adw.ViewSwitcher(stack=view_stack, policy=Adw.ViewSwitcherPolicy.WIDE)
    title_stack.add_named(switcher, "main")
    title_stack.add_named(Gtk.Box(), "now_playing")
    header.set_title_widget(title_stack)

    start_stack = Gtk.Stack()
    start_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

    search_btn = Gtk.ToggleButton(
        icon_name="system-search-symbolic", tooltip_text="Search"
    )
    start_stack.add_named(search_btn, "main")

    close_btn = Gtk.Button(
        icon_name="go-down-symbolic", tooltip_text="Close Now Playing"
    )
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: show_now_playing.on_next(False))
    start_stack.add_named(close_btn, "now_playing")

    header.pack_start(start_stack)

    end_stack = Gtk.Stack()
    end_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

    menu = Gio.Menu()
    menu.append("Preferences", "app.preferences")
    menu.append("About YT Music", "app.about")
    menu_btn = Gtk.MenuButton(
        icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Main Menu"
    )
    end_stack.add_named(menu_btn, "main")
    end_stack.add_named(Gtk.Box(), "now_playing")

    header.pack_end(end_stack)

    main_inner_toolbar_view = Adw.ToolbarView()

    # Pass the parent window to the search bar creator if it still requires it
    search_bar = create_search_bar(window, search_btn)
    main_inner_toolbar_view.add_top_bar(search_bar)

    main_inner_toolbar_view.set_content(view_stack)
    view_stack.add_titled_with_icon(
        HomePage(client, player_state, nav_view), "home", "Home", "go-home-symbolic"
    )
    view_stack.add_titled_with_icon(
        Gtk.Label(label="Explore Coming Soon!"),
        "explore",
        "Explore",
        "compass2-symbolic",
    )
    view_stack.add_titled_with_icon(
        Gtk.Label(label="Library Coming Soon!"),
        "library",
        "Library",
        "library-symbolic",
    )

    main_stack.add_named(main_inner_toolbar_view, "main")

    now_playing_view = NowPlayingView(player_state)
    main_stack.add_named(now_playing_view, "now_playing")

    # REACTIVE NAVIGATION LOGIC
    def on_nav_state_changed(show: bool):
        def _update():
            if show:
                nav_view.pop_to_page(root_nav_page)
            target = "now_playing" if show else "main"
            main_stack.set_visible_child_name(target)
            title_stack.set_visible_child_name(target)
            start_stack.set_visible_child_name(target)
            end_stack.set_visible_child_name(target)

        GLib.idle_add(_update)

    show_now_playing.subscribe(on_nav_state_changed)

    return root_toolbar_view
