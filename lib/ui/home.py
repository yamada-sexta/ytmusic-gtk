from typing import cast
from typing import Any
from lib.env import CACHE_DIR
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
from utils import load_image_async
from reactivex.subject import BehaviorSubject
from pydantic import TypeAdapter
from pydantic import BaseModel, Field
from typing import List, Optional
from lib.ui.play_bar import PlayerState


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
    This is used for both songs and playlists, with some conditional logic based on available data.
    """
    # Increased spacing from 8 to 12 for better visual breathing room
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    card.set_size_request(160, -1)
    card.set_halign(Gtk.Align.START)
    card.set_valign(Gtk.Align.START)
    # Adding native Adwaita rounding classes (requires standard Adwaita stylesheet)
    card.add_css_class("card")

    img = Gtk.Picture()
    img.set_can_shrink(True)
    img.set_content_fit(Gtk.ContentFit.COVER)

    if item.thumbnails:
        thumb_url = (
            item.thumbnails[-1].url
            if isinstance(item.thumbnails, list)
            else item.thumbnails
        )
        load_image_async(img, thumb_url)

    aspect = Gtk.AspectFrame()
    aspect.set_ratio(1.0)
    aspect.set_obey_child(False)
    aspect.set_child(img)
    aspect.set_size_request(160, 160)
    # Subtle polish: remove the border from the aspect frame so it doesn't look boxy
    aspect.add_css_class("view")

    # Cleaned up typography
    text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

    title_lbl = Gtk.Label(label=item.title)
    title_lbl.set_halign(Gtk.Align.START)
    title_lbl.set_wrap(True)
    title_lbl.set_lines(2)
    title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
    title_lbl.set_max_width_chars(1)
    # Make the title pop just a little bit more
    title_lbl.add_css_class("heading")

    creator = item.artists[0].name if item.artists else "Unknown"
    subtitle_lbl = Gtk.Label(label=creator)
    subtitle_lbl.set_halign(Gtk.Align.START)
    subtitle_lbl.add_css_class("dim-label")
    subtitle_lbl.add_css_class("caption")  # Slightly smaller text for metadata
    subtitle_lbl.set_ellipsize(Pango.EllipsizeMode.END)
    subtitle_lbl.set_max_width_chars(1)

    text_box.append(title_lbl)
    text_box.append(subtitle_lbl)

    card.append(aspect)
    card.append(text_box)

    click = Gtk.GestureClick.new()

    def on_card_click(gesture: Gtk.GestureClick, n_press: int, x: float, y: float):
        logging.info(f"Clicked on card: {item}")

        # 1. Update UI immediately with what we already have (Immediate Feedback)
        player_state.title.on_next(item.title)

        creator = "Unknown"
        if item.artists:
            creator = item.artists[0].name
        elif item.author:
            creator = item.author[0].name
        # player_state.subtitle.on_next(creator)
        player_state.artist.on_next(creator)
        player_state.album_name.on_next(item.album.name if item.album else "")

        if item.thumbnails:
            thumb_url = (
                item.thumbnails[-1].url
                if isinstance(item.thumbnails, list)
                else item.thumbnails
            )
            player_state.album_art.on_next(thumb_url)

        # 2. Background Fetch for additional details
        def fetch_details():
            try:
                data = None
                # Check if it's a standard playlist (not a Radio/Mix)
                if item.playlist_id and not item.playlist_id.startswith("RD"):
                    logging.info(f"Fetching playlist details for {item.playlist_id}")
                    data = yt.get_playlist(item.playlist_id)

                # If it's a song/video
                elif item.video_id:
                    logging.info(f"Fetching song details for {item.video_id}")
                    data = yt.get_song(item.video_id)

                if not data:
                    logging.warning("No additional details found for this item.")
                    return
                # If no video ID return
                if item.video_id is None:
                    logging.warning("Item has no video ID, cannot fetch details.")
                    return
                logging.info("Successfully fetched extra details")
                # Here you could update the player_state further if 'data'
                # contains higher quality info (like full lyrics or album name)
                # log data
                # logging.debug(f"Fetched data: {data}")
                # Dump to JSON
                import json

                with open("debug_fetched_data.json", "w") as f:
                    json.dump(data, f, indent=4)

                # Try to get the URL of the song
                url = data["microformat"]["microformatDataRenderer"]["urlCanonical"]
                logging.info(f"Canonical URL: {url}")
                # Get actual streaming URL using ytdlp
                from yt_dlp import YoutubeDL

                download_dir = CACHE_DIR / "songs" / item.video_id
                download_dir.mkdir(parents=True, exist_ok=True)

                logging.info(f"Downloading media to: {download_dir}")

                params: dict[str, Any] = {
                    "js_runtimes": {"bun": {}},
                    "paths": {"home": str(download_dir.absolute())},
                }
                marker_file = download_dir / "downloaded.txt"

                # If file doesn't exist, download it. This prevents re-downloading on every click.
                if not marker_file.exists():

                    with YoutubeDL(
                        params=cast(
                            Any,
                            {
                                "js_runtimes": {"bun": {}, "node": {}},
                                "paths": {"home": str(download_dir.absolute())},
                                "format": "bestaudio/best",  # Prioritize high-quality audio
                                "noplaylist": True,  # Ensure only the song is downloaded
                                "quiet": True,  # Reduce console noise if desired
                            },
                        )
                    ) as ydl:
                        ydl.download([url])
                        # Create a marker file to indicate this song has been downloaded
                        marker_file.touch()
                # Post-download, find the downloaded file (assuming only one new file appears)
                # And not the marker file
                downloaded_files = [
                    f
                    for f in download_dir.glob("*")
                    if f.is_file() and f.name != "downloaded.txt"
                ]
                # downloaded_files = list(download_dir.glob("*"))
                if not downloaded_files:
                    logging.warning(f"No files downloaded to {download_dir}")

                latest_file = max(downloaded_files, key=lambda f: f.stat().st_mtime)
                logging.info(f"Latest downloaded file: {latest_file}")
                # This file is usually in a .webm or .m4a format.
                # set the file
                player_state.audio_file.on_next(latest_file)
                # set play to true
                player_state.playing.on_next(True)

            except Exception as e:
                # This catches the 'contents' error you saw without crashing the app
                logging.error(f"Note: Could not fetch additional metadata: {e}")

        # Run the fetch in a thread so the UI doesn't stutter
        threading.Thread(target=fetch_details, daemon=True).start()

    click.connect("pressed", on_card_click)
    card.add_controller(click)

    # Optional: Change cursor to pointer on hover to indicate clickability
    card.set_cursor(Gdk.Cursor.new_from_name("pointer"))

    return card


# Leave HomeItemCard exactly as you have it!


def HomeRow(
    section: HomeSectionData, player_state: PlayerState, yt: ytmusicapi.YTMusic
) -> tuple[Gtk.Box, Adw.Carousel]:
    """
    Creates a horizontal carousel row for a given Home section, including the header and the carousel itself.
    Returns both the container box and the carousel so that we can append new items later if needed.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    header = Gtk.Label(label=section.title)
    header.set_halign(Gtk.Align.START)
    header.set_margin_start(12)
    header.set_margin_bottom(8)
    header.add_css_class("title-2")
    box.append(header)

    carousel = Adw.Carousel()
    carousel.set_spacing(16)
    carousel.set_allow_scroll_wheel(False)

    for item in section.contents:
        carousel.append(HomeItemCard(item, player_state, yt))

    dots = Adw.CarouselIndicatorDots()
    dots.set_carousel(carousel)

    box.append(carousel)
    box.append(dots)

    # Return both so the parent can inject new items later
    return box, carousel


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
