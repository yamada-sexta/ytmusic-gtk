from reactivex import Subject
from typing import Tuple
from lib.data import Album
from lib.data import Artist
from lib.data import BaseMedia
from reactivex import operators as ops

# from lib.data import HomePageTypeAdapter
# from lib.data import HomeItemData
# from lib.data import HomeSectionData
import threading

# from lib.data import HomePageType
import logging
import logging
from lib.types import YTMusicSubject
import ytmusicapi
from typing import Optional
from gi.repository import Gtk, GLib, Adw, Pango
from utils import load_image_async
from reactivex.subject import BehaviorSubject
from pydantic import TypeAdapter
from pydantic import BaseModel, Field
from typing import List, Optional


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


def HomeItemCard(item: HomeItemData) -> Gtk.Box:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    card.set_size_request(160, -1)
    card.set_halign(Gtk.Align.START)
    card.set_valign(Gtk.Align.START)
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

    # 1. CAGE THE IMAGE: Force a strict 1:1 square
    aspect = Gtk.AspectFrame()
    aspect.set_ratio(1.0)
    aspect.set_obey_child(False)
    aspect.set_child(img)
    aspect.set_size_request(160, 160)

    # 2. CAGE THE TEXT: Stop the text from stretching the grey card!
    title_lbl = Gtk.Label(label=item.title)
    title_lbl.set_halign(Gtk.Align.START)
    title_lbl.set_wrap(True)
    title_lbl.set_lines(2)
    title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
    # This line is the magic fix for the stretching card:
    title_lbl.set_max_width_chars(1)

    creator = item.artists[0].name if item.artists else "Unknown"
    subtitle_lbl = Gtk.Label(label=creator)
    subtitle_lbl.set_halign(Gtk.Align.START)
    subtitle_lbl.add_css_class("dim-label")
    subtitle_lbl.set_ellipsize(Pango.EllipsizeMode.END)
    # Also cage the subtitle:
    subtitle_lbl.set_max_width_chars(1)

    card.append(aspect)
    card.append(title_lbl)
    card.append(subtitle_lbl)

    click = Gtk.GestureClick.new()

    def on_card_click(gesture, n_press, x, y):
        logging.info(f"Clicked on card: {item}")

    click.connect("pressed", on_card_click)
    card.add_controller(click)

    return card


# Leave HomeItemCard exactly as you have it!


def HomeRow(section: HomeSectionData) -> tuple[Gtk.Box, Adw.Carousel]:
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
        carousel.append(HomeItemCard(item))

    dots = Adw.CarouselIndicatorDots()
    dots.set_carousel(carousel)

    box.append(carousel)
    box.append(dots)

    # Return both so the parent can inject new items later
    return box, carousel


def HomePage(
    yt_subject: YTMusicSubject,
) -> Gtk.ScrolledWindow:
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    home_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=32)
    home_box.set_margin_top(24)
    home_box.set_margin_bottom(24)
    scrolled.set_child(home_box)

    # --- STATE MANAGEMENT ---
    current_limit = 5
    is_loading = False
    current_yt_instance = None

    # Cache mapping: section.title -> (Gtk.Box, Adw.Carousel, current_item_count)
    row_cache = {}

    # Subject payload: (HomePageType data, is_reset boolean)
    home_page_subject = BehaviorSubject[Tuple[HomePageType, bool]](([], True))
    scroll_subject = Subject()

    # Explicit function to satisfy GLib.idle_add
    def update_ui(home: HomePageType, is_reset: bool) -> bool:
        nonlocal is_loading

        if is_reset:
            # Wipe UI entirely only when switching accounts or reloading from scratch
            while (child := home_box.get_first_child()) is not None:
                home_box.remove(child)
            row_cache.clear()

        if len(home) == 0 and is_reset:
            is_loading = False
            error_label = Gtk.Label(
                label="Failed to load data. Please check your login."
            )
            home_box.append(error_label)
            return GLib.SOURCE_REMOVE  # Stop GLib from calling this again

        for section in home:
            if section.title in row_cache:
                # UPDATE EXISTING ROW: Only append items we haven't rendered yet
                section_box, carousel, current_count = row_cache[section.title]
                if len(section.contents) > current_count:
                    new_items = section.contents[current_count:]
                    for item in new_items:
                        carousel.append(HomeItemCard(item))
                    # Update cache with the new count
                    row_cache[section.title] = (
                        section_box,
                        carousel,
                        len(section.contents),
                    )
            else:
                # CREATE NEW ROW
                section_box, carousel = HomeRow(section)
                home_box.append(section_box)
                row_cache[section.title] = (
                    section_box,
                    carousel,
                    len(section.contents),
                )

        is_loading = False
        return GLib.SOURCE_REMOVE  # Standard practice for idle_add callbacks

    # --- RX CALLBACKS (No lambdas) ---
    def on_home_data_next(data_tuple: Tuple[HomePageType, bool]):
        home_data, is_reset = data_tuple
        # Pass arguments explicitly to avoid lambda wrapping
        GLib.idle_add(update_ui, home_data, is_reset)

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
            home_page_subject.on_next((home_data, is_reset))
        except Exception as e:
            logging.error(f"Failed to fetch home data: {e}")
            home_page_subject.on_next(([], is_reset))

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
