from gi.repository import Gtk, GLib, Adw
from lib.ui.loading import LoadingUI
from lib.ui.components.item_card import PlayItemCard
from lib.data import HomeItemData
from lib.state.player_state import PlayerState
from lib.net.client import YTClient
from reactivex.subject import BehaviorSubject, Subject
from reactivex import operators as ops
import logging
from typing import Optional


def SearchPage(
    query: str,
    player_state: PlayerState,
    client: YTClient,
    nav_view: Adw.NavigationView,
) -> Adw.NavigationPage:
    page = Adw.NavigationPage(title=f"Search: {query}")

    toolbar = Adw.ToolbarView()
    page.set_child(toolbar)

    header = Adw.HeaderBar()
    toolbar.add_top_bar(header)

    content_stack = Gtk.Stack()
    content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
    toolbar.set_content(content_stack)

    loading_view = LoadingUI(
        primary_text=f"Searching for '{query}'...", show_header=False
    )
    content_stack.add_named(loading_view, "loading")

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    clamp = Adw.Clamp()
    clamp.set_maximum_size(1000)
    clamp.set_margin_top(32)
    clamp.set_margin_bottom(32)
    clamp.set_margin_start(24)
    clamp.set_margin_end(24)
    scrolled.set_child(clamp)

    flowbox = Gtk.FlowBox()
    flowbox.set_valign(Gtk.Align.START)
    flowbox.set_max_children_per_line(10)
    flowbox.set_min_children_per_line(2)
    flowbox.set_column_spacing(16)
    flowbox.set_row_spacing(16)

    # We don't want selection
    flowbox.set_selection_mode(Gtk.SelectionMode.NONE)

    # Spinner box
    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    clamp.set_child(main_box)

    main_box.append(flowbox)

    bottom_spinner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    bottom_spinner_box.set_margin_top(24)
    bottom_spinner_box.set_margin_bottom(24)
    bottom_spinner = Adw.Spinner()
    bottom_spinner.set_size_request(32, 32)
    bottom_spinner.set_halign(Gtk.Align.CENTER)
    bottom_spinner_box.append(bottom_spinner)
    bottom_spinner_box.set_visible(False)
    main_box.append(bottom_spinner_box)

    content_stack.add_named(scrolled, "content")
    content_stack.set_visible_child_name("loading")

    current_limit = BehaviorSubject(20)
    is_loading = BehaviorSubject(False)
    scroll_subject = Subject()

    search_obs = client.search(query=query, limit=current_limit)

    rendered_items = set()

    def on_search_results(data: Optional[tuple[list[dict], dict]]):
        if not data:
            return
        results_raw, _ = data

        def update_ui() -> bool:
            for raw_item in results_raw:
                try:
                    # Adjust dictionary for HomeItemData parsing
                    if "artist" in raw_item and "title" not in raw_item:
                        raw_item["title"] = raw_item["artist"]
                    elif (
                        "title" not in raw_item
                        and "artists" in raw_item
                        and isinstance(raw_item["artists"], list)
                        and len(raw_item["artists"]) > 0
                    ):
                        raw_item["title"] = raw_item["artists"][0]["name"]
                    elif "title" not in raw_item:
                        raw_item["title"] = "Unknown"

                    # Handle browseId for artist nodes
                    if (
                        raw_item.get("resultType") == "artist"
                        and "browseId" in raw_item
                    ):
                        raw_item["audioPlaylistId"] = raw_item["browseId"]

                    # Handle playlist items
                    if (
                        raw_item.get("resultType") == "playlist"
                        and "browseId" in raw_item
                    ):
                        raw_item["playlistId"] = raw_item["browseId"]

                    # Ensure artists object exists if author is present since our card expects it
                    if "author" in raw_item and isinstance(raw_item["author"], str):
                        author_data = [{"name": raw_item["author"], "id": None}]
                        raw_item["artists"] = author_data
                        raw_item["author"] = author_data

                    item_data = HomeItemData.model_validate(raw_item)

                    # Create a unique key for the item to prevent duplicates
                    item_key = f"{item_data.title}_{item_data.video_id}_{item_data.playlist_id}_{item_data.audio_playlist_id}"

                    if item_key not in rendered_items:
                        rendered_items.add(item_key)
                        card = PlayItemCard(item_data, player_state, client, nav_view)
                        flowbox.append(card)
                except Exception as e:
                    logging.warning(f"Failed to parse search item: {e} -> {raw_item}")

            bottom_spinner_box.set_visible(False)
            is_loading.on_next(False)
            content_stack.set_visible_child_name("content")
            return GLib.SOURCE_REMOVE

        GLib.idle_add(update_ui)

    search_obs.subscribe(
        on_next=on_search_results,
        on_error=lambda e: logging.error(f"Search fetch error: {e}"),
    )

    def trigger_load_more(_=None):
        if is_loading.value:
            return
        logging.info("Fetching more search results...")
        is_loading.on_next(True)
        bottom_spinner_box.set_visible(True)
        current_limit.on_next(current_limit.value + 20)

    def on_edge_reached(sw: Gtk.ScrolledWindow, pos: Gtk.PositionType):
        if pos == Gtk.PositionType.BOTTOM:
            scroll_subject.on_next(None)

    scrolled.connect("edge-reached", on_edge_reached)

    def check_scroll_valid(_=None) -> bool:
        return not is_loading.value

    scroll_subject.pipe(ops.filter(check_scroll_valid)).subscribe(
        on_next=trigger_load_more,
        on_error=lambda e: logging.error(f"Scroll loop error: {e}"),
    )

    return page
