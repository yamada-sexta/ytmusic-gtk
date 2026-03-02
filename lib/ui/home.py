from lib.state.player_state import CurrentMusic
from utils import load_thumbnail
from typing import cast
from typing import Any
from lib.sys.env import CACHE_DIR
from reactivex import Subject
from typing import Tuple
from lib.data import Album, Artist, BaseMedia
from reactivex import operators as ops
import threading
import logging
import logging
from lib.types import YTMusicSubject
import ytmusicapi
from typing import Optional
from gi.repository import Gtk, GLib, Adw, Pango, Gio, GdkPixbuf, Gdk
from reactivex.subject import BehaviorSubject
from pydantic import TypeAdapter
from pydantic import BaseModel, Field
from typing import List, Optional
from lib.ui.play_bar import PlayerState
from lib.state.player_state import PlayState


class HomeItemData(BaseMedia):
    # Tracks & Quick Picks
    playlist_id: Optional[str] = Field(None, alias="playlistId")
    views: Optional[str] = None
    video_type: Optional[str] = Field(None, alias="videoType")
    is_explicit: Optional[bool] = Field(None, alias="isExplicit")
    album: Optional[Album] = None

    # Playlists & Mixes
    description: Optional[str] = None
    count: Optional[str] = None
    # Note: Playlists often use 'author' instead of 'artists',
    # but the data structure inside is identical to 'Artist'
    author: Optional[List[Artist]] = None


class HomeSectionData(BaseModel):
    title: str
    contents: List[HomeItemData]


# Since the root of the Home data is a List (not a dictionary),
# we use TypeAdapter just like you did for History.
HomePageTypeAdapter = TypeAdapter(List[HomeSectionData])

# Get type of HomePage for type hinting
HomePageType = List[HomeSectionData]


def HomeItemCard(
    item: HomeItemData, player_state: PlayerState, yt: ytmusicapi.YTMusic
) -> Gtk.Box:
    """
    Creates a card widget for a single item in the Home page.
    """
    # Deterministic size: 160x160 keeps it looking like standard album art/thumbnails
    IMAGE_SIZE = 160

    logging.debug(
        f"Creating card for item: {item.title} (Video ID: {item.video_id}) - Type: {item.video_type}"
    )

    # Calculate the aspect ratio of the thumbnail if available, otherwise default to 1:1
    aspect_ratio = 1.0
    if item.thumbnails and len(item.thumbnails) > 0:
        thumb = item.thumbnails[-1]  # Use the highest resolution thumbnail
        if thumb.width and thumb.height:
            aspect_ratio = thumb.width / thumb.height

    width = int(IMAGE_SIZE * aspect_ratio)
    height = IMAGE_SIZE

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    card.set_size_request(width, height + 100)  # Extra height for text below the image
    card.set_halign(Gtk.Align.START)
    card.set_valign(Gtk.Align.START)

    # Use Gtk.Picture but enforce a strict size and scaling
    img = Gtk.Picture()
    img.set_can_shrink(
        True
    )  # Crucial: Stops high-res network images from blowing up the UI
    img.set_content_fit(Gtk.ContentFit.COVER)
    img.set_size_request(width, height)  # Maintain aspect ratio
    img.add_css_class("card")  # Adds nice Adwaita rounding to the image

    load_thumbnail(img, item.thumbnails)

    # Wrap the image in an overlay for the play button
    overlay = Gtk.Overlay()
    overlay.set_child(img)

    # Create a proper container for the play button to prevent stretching
    play_box = Gtk.Box()
    play_box.set_halign(Gtk.Align.CENTER)
    play_box.set_valign(Gtk.Align.CENTER)
    play_box.set_size_request(64, 64)  # Force a strict square size
    play_box.set_visible(False)  # Hidden by default

    # Add the icon inside the box
    play_icon = Gtk.Image()
    play_icon.set_icon_size(Gtk.IconSize.LARGE)
    play_icon.set_halign(Gtk.Align.CENTER)
    play_icon.set_valign(Gtk.Align.CENTER)
    play_icon.set_hexpand(True)
    play_icon.set_vexpand(True)

    play_spinner = Adw.Spinner()
    play_spinner.set_halign(Gtk.Align.CENTER)
    play_spinner.set_valign(Gtk.Align.CENTER)
    play_spinner.set_hexpand(True)
    play_spinner.set_vexpand(True)
    play_spinner.set_size_request(32, 32)

    play_stack = Gtk.Stack()
    play_stack.add_named(play_icon, "icon")
    play_stack.add_named(play_spinner, "spinner")

    def update_play_icon(state: PlayState):
        def do_update_icon():
            if state == PlayState.LOADING:
                if hasattr(play_spinner, "start"):
                    play_spinner.start()
                play_stack.set_visible_child_name("spinner")
            else:
                if hasattr(play_spinner, "stop"):
                    play_spinner.stop()
                play_icon.set_from_icon_name(
                    "media-playback-pause-symbolic"
                    if state == PlayState.PLAYING
                    else "media-playback-start-symbolic"
                )
                play_stack.set_visible_child_name("icon")
            return GLib.SOURCE_REMOVE

        GLib.idle_add(do_update_icon)

    player_state.state.subscribe(update_play_icon)

    play_box.append(play_stack)
    overlay.add_overlay(play_box)

    text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    text_box.set_margin_start(4)  # Indents text slightly from the left edge
    text_box.set_margin_end(4)  # Prevents text from hitting the hard right edge
    # text_box.set_margin_bottom(24)  # Gives the bottom of the card some breathing room

    title_lbl = Gtk.Label(label=item.title)
    title_lbl.set_halign(Gtk.Align.START)
    title_lbl.set_xalign(0.0)

    # This combination forces the 2-line height
    title_lbl.set_wrap(True)
    title_lbl.set_lines(2)
    title_lbl.set_ellipsize(Pango.EllipsizeMode.END)

    # Ensure the label doesn't try to expand horizontally beyond the image
    title_lbl.set_width_chars(1)
    title_lbl.set_max_width_chars(1)

    title_lbl.add_css_class("heading")

    creator = item.artists[0].name if item.artists else "Unknown"
    subtitle_lbl = Gtk.Label(label=creator)

    # 1. Align the widget within its parent container to the left
    subtitle_lbl.set_halign(Gtk.Align.START)

    # 2. Align the text within the label's own allocation to the left
    subtitle_lbl.set_xalign(0.0)

    subtitle_lbl.add_css_class("dim-label")
    subtitle_lbl.add_css_class("caption")

    # 3. Handling overflow
    subtitle_lbl.set_ellipsize(Pango.EllipsizeMode.END)

    # 4. Ensure it doesn't push the card wider than the image
    subtitle_lbl.set_width_chars(1)
    subtitle_lbl.set_hexpand(True)
    subtitle_lbl.set_size_request(IMAGE_SIZE, -1)

    text_box.append(title_lbl)
    text_box.append(subtitle_lbl)

    card.append(overlay)  # Append the overlay here instead of 'img'
    card.append(text_box)

    click = Gtk.GestureClick.new()

    def on_card_click(gesture: Gtk.GestureClick, n_press: int, x: float, y: float):
        logging.info(f"Clicked on card: {item}")

        if (
            player_state.current.value
            and item.video_id
            and player_state.current.value.id == item.video_id
        ):
            # current_state = player_state.state.value
            if player_state.state.value == PlayState.PLAYING:
                player_state.state.on_next(PlayState.PAUSED)
                return
            elif player_state.state.value == PlayState.PAUSED:
                player_state.state.on_next(PlayState.PLAYING)
                return
            elif player_state.state.value == PlayState.LOADING:
                return

        if not item.video_id:
            logging.warning("Item has no video ID, cannot play.")
            player_state.state.on_next(PlayState.EMPTY)
            return

        title = item.title or "Unknown"
        creator = "Unknown"
        if item.artists:
            creator = item.artists[0].name
        elif item.author:
            creator = item.author[0].name

        album_name = item.album.name if item.album else "Unknown"

        thumb_url = ""
        if item.thumbnails:
            thumb_url = (
                item.thumbnails[-1].url
                if isinstance(item.thumbnails, list)
                else item.thumbnails
            )

        new_music = CurrentMusic(
            id=item.video_id,
            title=title,
            artist=creator,
            album_name=album_name,
            album_art=thumb_url,
            is_liked=BehaviorSubject(False),
            is_disliked=BehaviorSubject(False),
        )

        from lib.state.player_state import play_audio

        play_audio(
            state=player_state,
            video_id=item.video_id,
            yt=yt,
            playlist_id=item.playlist_id,
            initial_temp_music=new_music,
        )

    click.connect("pressed", on_card_click)
    card.add_controller(click)
    card.set_cursor(Gdk.Cursor.new_from_name("pointer"))

    def update_playing_state(playing_id: Optional[str]):
        def do_update():
            # Check if this card's video matches the currently playing ID
            if item.video_id and playing_id == item.video_id:
                play_box.set_visible(True)
                img.set_opacity(0.5)  # 0.5 looks a bit cleaner than 0.3
            else:
                play_box.set_visible(False)
                img.set_opacity(1.0)  # Restores original brightness
            return GLib.SOURCE_REMOVE

        GLib.idle_add(do_update)

    # Listen for changes in the player state ID
    # player_state.id.subscribe(on_next=update_playing_state)
    def on_current_changed(current: Optional[CurrentMusic]) -> None:
        if current and current.id:
            update_playing_state(current.id)
        else:
            update_playing_state(None)

    player_state.current.subscribe(on_current_changed)
    return card


# Leave HomeItemCard exactly as you have it!


def HomeRow(
    section: HomeSectionData, player_state: PlayerState, yt: ytmusicapi.YTMusic
) -> tuple[Gtk.Box, Gtk.Box]:
    """
    Creates a standard scrollable horizontal row for a given Home section.
    Returns both the parent container and the inner scrolling box.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

    header = Gtk.Label(label=section.title)
    header.set_halign(Gtk.Align.START)
    header.set_margin_start(12)
    header.set_margin_bottom(8)
    header.add_css_class("title-2")
    box.append(header)

    # 1. Create a native ScrolledWindow to replace the Carousel
    scrolled = Gtk.ScrolledWindow()
    # Horizontal scroll automatically, no vertical scrolling
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)

    # 2. Create the horizontal container for the items
    row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    # NEW: Add padding around the entire row of items
    row_box.set_margin_start(12)  # Space before the first item
    row_box.set_margin_end(12)  # Space after the last item
    row_box.set_margin_top(12)  # Slight gap below the section header
    row_box.set_margin_bottom(16)  # Prevents horizontal scrollbar from overlapping text

    for item in section.contents:
        row_box.append(HomeItemCard(item, player_state, yt))

    scrolled.set_child(row_box)
    box.append(scrolled)

    # Return both so the parent can inject new items later, exactly as before
    return box, row_box


def HomePage(
    yt_subject: YTMusicSubject,
    player_state: PlayerState,
) -> Gtk.ScrolledWindow:
    """
    Builds the Home page UI, which consists of multiple sections (e.g. "Recently Played", "Recommended Mixes").
    Each section is rendered as a HomeRow with a header and a horizontal carousel of HomeItemCards.
    The page also implements infinite scrolling by listening to the scroll position and fetching more data when the user reaches the bottom.
    """
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    # 1. THE CLAMP: This makes the UI look premium on widescreen monitors
    clamp = Adw.Clamp()
    clamp.set_maximum_size(1000)  # Max width before it centers
    clamp.set_margin_top(32)
    clamp.set_margin_bottom(32)
    clamp.set_margin_start(24)
    clamp.set_margin_end(24)
    scrolled.set_child(clamp)

    home_box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL, spacing=48
    )  # Increased spacing between rows
    clamp.set_child(home_box)

    current_limit = 5
    is_loading = False
    current_yt_instance = None
    row_cache = {}

    home_page_subject = BehaviorSubject[
        Tuple[HomePageType, bool, Optional[ytmusicapi.YTMusic]]
    ](([], True, None))
    scroll_subject = Subject()

    def update_ui(
        home: HomePageType, is_reset: bool, yt: Optional[ytmusicapi.YTMusic]
    ) -> bool:
        nonlocal is_loading

        if is_reset:
            while (child := home_box.get_first_child()) is not None:
                home_box.remove(child)
            row_cache.clear()

        # Beautiful Native Loading State
        if not yt:
            loading_page = Adw.StatusPage()
            loading_page.set_title("Waking up the music...")
            loading_page.set_description("Connecting to your library")

            spinner = Adw.Spinner()
            spinner.set_size_request(48, 48)
            spinner.set_halign(Gtk.Align.CENTER)
            spinner.add_css_class("margin-top-24")  # Push spinner down slightly

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.set_valign(Gtk.Align.CENTER)
            box.set_vexpand(True)
            box.append(loading_page)
            box.append(spinner)

            home_box.append(box)
            return GLib.SOURCE_REMOVE

        # Beautiful Native Error State
        if len(home) == 0 and is_reset:
            is_loading = False
            error_page = Adw.StatusPage()
            error_page.set_icon_name("network-error-symbolic")
            error_page.set_title("Nothing to show")
            error_page.set_description("Failed to load data. Please check your login.")
            home_box.append(error_page)
            return GLib.SOURCE_REMOVE

        for section in home:
            if section.title in row_cache:
                section_box, carousel, current_count = row_cache[section.title]
                if len(section.contents) > current_count:
                    new_items = section.contents[current_count:]
                    for item in new_items:
                        carousel.append(HomeItemCard(item, player_state, yt))
                    row_cache[section.title] = (
                        section_box,
                        carousel,
                        len(section.contents),
                    )
            else:
                section_box, carousel = HomeRow(section, player_state, yt)
                home_box.append(section_box)
                row_cache[section.title] = (
                    section_box,
                    carousel,
                    len(section.contents),
                )

        is_loading = False
        return GLib.SOURCE_REMOVE

    # --- RX CALLBACKS (No lambdas) ---
    def on_home_data_next(
        data_tuple: Tuple[HomePageType, bool, Optional[ytmusicapi.YTMusic]],
    ):
        home_data, is_reset, yt = data_tuple
        # Pass arguments explicitly to avoid lambda wrapping
        GLib.idle_add(update_ui, home_data, is_reset, yt)

    def on_rx_error(e):
        logging.error(f"Rx Error: {e}")

    home_page_subject.subscribe(
        on_next=on_home_data_next,
        on_error=on_rx_error,
    )

    # --- BACKGROUND FETCH LOGIC ---
    def fetch_home_data(yt: ytmusicapi.YTMusic, limit: int, is_reset: bool):
        try:
            raw_home = yt.get_home(limit=limit)
            # Write the raw response to a JSON file for debugging
            import json

            with open("debug_home_response.json", "w") as f:
                json.dump(raw_home, f, indent=4)
            home_data = HomePageTypeAdapter.validate_python(raw_home)
            home_page_subject.on_next((home_data, is_reset, yt))
        except Exception as e:
            logging.error(f"Failed to fetch home data: {e}")
            home_page_subject.on_next(([], is_reset, None))

    def trigger_load_more(dummy_value=None):
        nonlocal is_loading, current_limit
        logging.info("Fetching more data...")
        is_loading = True
        current_limit += 5
        threading.Thread(
            target=fetch_home_data,
            args=(current_yt_instance, current_limit, False),  # False = don't reset UI
            daemon=True,
        ).start()

    def on_edge_reached(sw: Gtk.ScrolledWindow, pos: Gtk.PositionType):
        if pos == Gtk.PositionType.BOTTOM:
            scroll_subject.on_next(None)

    scrolled.connect("edge-reached", on_edge_reached)

    def check_scroll_valid(dummy_value) -> bool:
        return not is_loading and current_yt_instance is not None

    scroll_subject.pipe(ops.filter(check_scroll_valid)).subscribe(
        on_next=trigger_load_more, on_error=on_rx_error
    )

    def on_yt_changed(yt: Optional[ytmusicapi.YTMusic]):
        nonlocal current_yt_instance, is_loading, current_limit
        current_yt_instance = yt

        if yt is None:
            logging.info("YT Music instance is None, showing error message.")
            return

        current_limit = 5
        is_loading = True

        # FIXED: Added the explicit `True` argument for `is_reset`
        threading.Thread(
            target=fetch_home_data, args=(yt, current_limit, True), daemon=True
        ).start()

    yt_subject.subscribe(on_next=on_yt_changed, on_error=on_rx_error)

    return scrolled
