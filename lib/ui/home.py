from lib.ui.components.item_card import PlayItemCard
from lib.ui.loading import LoadingUI
from lib.data import HomeSectionData
from lib.data import HomeItemData
from lib.net.client import YTClient
from lib.ui.thumbnail import ThumbnailWidget
from reactivex import Subject
from reactivex import operators as ops
import logging
from typing import Optional
from gi.repository import Gtk, GLib, Adw, Pango, Gio, GdkPixbuf, Gdk
from reactivex.subject import BehaviorSubject
from typing import List, Optional
from lib.ui.play_bar import PlayerState

# Leave HomeItemCard exactly as you have it!


def HomeRow(
    section: HomeSectionData,
    player_state: PlayerState,
    client: YTClient,
    nav_view: Adw.NavigationView,
) -> tuple[Gtk.Box, Gtk.Box]:
    """
    Creates a standard scrollable horizontal row for a given Home section.
    Returns both the parent container and the inner scrolling box.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

    header = Gtk.Label(label=section.title)
    header.set_halign(Gtk.Align.START)
    header.set_margin_start(12)
    header.set_margin_bottom(4)
    header.add_css_class("title-2")
    box.append(header)

    # 1. Create a native ScrolledWindow to replace the Carousel
    scrolled = Gtk.ScrolledWindow()
    # Horizontal scroll automatically, no vertical scrolling
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)

    # 2. Create the horizontal container for the items
    row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    # Align children to the top so all cards pin to the top regardless of height
    row_box.set_valign(Gtk.Align.START)
    # NEW: Add padding around the entire row of items
    row_box.set_margin_start(12)  # Space before the first item
    row_box.set_margin_end(12)  # Space after the last item
    row_box.set_margin_top(4)  # Slight gap below the section header
    row_box.set_margin_bottom(8)  # Prevents horizontal scrollbar from overlapping text
    from lib.ui.components.item_card import PlayItemCard

    for item in section.contents:
        row_box.append(PlayItemCard(item, player_state, client, nav_view))

    scrolled.set_child(row_box)
    box.append(scrolled)

    # Return both so the parent can inject new items later, exactly as before
    return box, row_box


def HomePage(
    client: YTClient,
    player_state: PlayerState,
    nav_view: Adw.NavigationView,
) -> Gtk.Widget:  # Changed return type to Gtk.Widget to accommodate the Stack
    """
    Builds the Home page UI, which consists of multiple sections (e.g. "Recently Played", "Recommended Mixes").
    Shows a loading screen until the initial data is fetched.
    """
    # 1. Create a Stack to manage "Loading" vs "Content" states
    root_stack = Gtk.Stack()
    root_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

    # 2. Add the Loading UI
    loading_view = LoadingUI(primary_text="Waking up the music...")
    root_stack.add_named(loading_view, "loading")

    # 3. Setup the main scrollable content
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    clamp = Adw.Clamp()
    clamp.set_maximum_size(1000)
    clamp.set_margin_top(32)
    clamp.set_margin_bottom(32)
    clamp.set_margin_start(24)
    clamp.set_margin_end(24)
    scrolled.set_child(clamp)

    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    clamp.set_child(main_box)

    home_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=48)
    main_box.append(home_box)

    bottom_spinner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    bottom_spinner_box.set_margin_top(24)
    bottom_spinner_box.set_margin_bottom(24)
    bottom_spinner = Adw.Spinner()
    bottom_spinner.set_size_request(32, 32)
    bottom_spinner.set_halign(Gtk.Align.CENTER)
    bottom_spinner_box.append(bottom_spinner)
    bottom_spinner_box.set_visible(False)
    main_box.append(bottom_spinner_box)

    # Add the content view to the stack
    root_stack.add_named(scrolled, "content")

    # Start by showing the loading screen
    root_stack.set_visible_child_name("loading")

    current_limit = BehaviorSubject(5)
    is_loading = BehaviorSubject(False)
    has_more = BehaviorSubject(True)
    row_cache = {}

    home_page_subject = client.get_home(limit=current_limit)
    scroll_subject = Subject()

    def update_ui(home: list[HomeSectionData]) -> bool:
        # Switch from loading screen to content screen once we have a response
        if root_stack.get_visible_child_name() == "loading":
            root_stack.set_visible_child_name("content")

        # Beautiful Native Error State
        if len(home) == 0:
            is_loading.on_next(False)
            error_page = Adw.StatusPage()
            error_page.set_icon_name("network-error-symbolic")
            error_page.set_title("Nothing to show")
            error_page.set_description(
                "Failed to load data. Please check your connection."
            )

            # Clear existing content just in case
            while (child := home_box.get_first_child()) is not None:
                home_box.remove(child)

            home_box.append(error_page)
            return GLib.SOURCE_REMOVE

        for section in home:
            if section.title in row_cache:
                section_box, carousel, current_count = row_cache[section.title]
                if len(section.contents) > current_count:
                    new_items = section.contents[current_count:]
                    for item in new_items:
                        carousel.append(
                            PlayItemCard(item, player_state, client, nav_view)
                        )
                    row_cache[section.title] = (
                        section_box,
                        carousel,
                        len(section.contents),
                    )
            else:
                section_box, carousel = HomeRow(section, player_state, client, nav_view)
                home_box.append(section_box)
                row_cache[section.title] = (
                    section_box,
                    carousel,
                    len(section.contents),
                )

        bottom_spinner_box.set_visible(False)
        is_loading.on_next(False)

        if client and len(home) < current_limit.value:
            has_more.on_next(False)

        return GLib.SOURCE_REMOVE

    def on_home_data_next(data: Optional[tuple[list[HomeSectionData], dict]]):
        if data is None:
            logging.error("Received None data for home page, skipping update.")
            return
        home_data, _ = data
        GLib.idle_add(update_ui, home_data)

    def on_rx_error(e):
        logging.error(f"Rx Error: {e}")
        # Optionally, you could transition the stack to an error UI here
        GLib.idle_add(lambda: root_stack.set_visible_child_name("content"))

    home_page_subject.subscribe(
        on_next=on_home_data_next,
        on_error=on_rx_error,
    )

    def trigger_load_more(dummy_value=None):
        if is_loading.value:
            return
        logging.info("Fetching more data...")
        is_loading.on_next(True)
        bottom_spinner_box.set_visible(True)
        current_limit.on_next(current_limit.value + 5)

    def on_edge_reached(sw: Gtk.ScrolledWindow, pos: Gtk.PositionType):
        if pos == Gtk.PositionType.BOTTOM:
            scroll_subject.on_next(None)

    scrolled.connect("edge-reached", on_edge_reached)

    def check_scroll_valid(dummy_value) -> bool:
        return not is_loading.value and has_more.value

    scroll_subject.pipe(ops.filter(check_scroll_valid)).subscribe(
        on_next=trigger_load_more, on_error=on_rx_error
    )

    # Return the root stack instead of just the ScrolledWindow
    return root_stack
