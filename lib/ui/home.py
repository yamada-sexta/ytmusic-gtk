from lib.data import HomeItem
from lib.data import HomeSection
import threading
from lib.data import HomePageType
from lib.data import HomePage
import logging
import logging
from lib.types import YTMusicSubject
import ytmusicapi
from typing import Optional
from gi.repository import Gtk, GLib, Adw, Pango
from utils import load_image_async
from reactivex.subject import BehaviorSubject


def home_item_card(item: HomeItem) -> Gtk.Box:
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


def home_page_section(section: HomeSection) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    header = Gtk.Label(label=section.title)
    header.set_halign(Gtk.Align.START)
    header.set_margin_start(12)
    header.set_margin_bottom(8)
    header.add_css_class("title-2")  # Makes the text large and bold
    box.append(header)

    carousel = Adw.Carousel()
    carousel.set_spacing(16)
    carousel.set_allow_scroll_wheel(True)

    for item in section.contents:
        card = home_item_card(item)
        carousel.append(card)

    dots = Adw.CarouselIndicatorDots()
    dots.set_carousel(carousel)

    box.append(carousel)
    box.append(dots)

    return box


def create_home_page(
    yt_subject: YTMusicSubject,
) -> Gtk.ScrolledWindow:
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    home_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=32)
    home_box.set_margin_top(24)
    home_box.set_margin_bottom(24)
    scrolled.set_child(home_box)

    # State management for pagination
    current_limit = 5
    is_loading = False
    current_yt_instance = None

    def on_edge_reached(sw, pos):
        nonlocal is_loading, current_limit, current_yt_instance

        # Check if the edge we hit is the bottom
        if pos == Gtk.PositionType.BOTTOM:
            logging.info("Reached the bottom edge! Checking if we can load more...")

            if is_loading:
                logging.info("Already loading data, ignoring scroll.")
                return
            if not current_yt_instance:
                logging.info("YT instance not ready, ignoring scroll.")
                return

            logging.info("Fetching more data...")
            is_loading = True
            current_limit += 5

            # Fetch data in a background thread
            threading.Thread(
                target=fetch_home_data,
                args=(current_yt_instance, current_limit),
                daemon=True,
            ).start()

    # Connect directly to the ScrolledWindow, not its adjustment
    scrolled.connect("edge-reached", on_edge_reached)

    def update_ui(home: HomePageType):
        nonlocal is_loading

        # Clear any existing widgets from the container (GTK4 style)
        while True:
            child = home_box.get_first_child()
            if not child:
                break
            home_box.remove(child)

        if len(home) == 0:
            is_loading = False
            logging.info("YT Music instance is not available, showing error message.")
            error_label = Gtk.Label(
                label="Failed to load data. Please check your login."
            )
            home_box.append(error_label)
            return
        logging.info(f"Updating UI with {len(home)} sections.")
        for section in home:
            section_box = home_page_section(section)
            home_box.append(section_box)

        is_loading = False

    home_page_subject = BehaviorSubject[HomePageType]([])

    def on_home_data_next(data: HomePageType):
        GLib.idle_add(update_ui, data)

    home_page_subject.subscribe(
        on_next=on_home_data_next,
        on_error=lambda e: print(f"Rx Error: {e}"),
    )

    # --- 2. BACKGROUND FETCH LOGIC ---
    def fetch_home_data(yt: ytmusicapi.YTMusic, limit: int):
        try:
            # Network calls MUST be off the main GTK thread
            raw_home = yt.get_home(limit=limit)
            home_data = HomePage.validate_python(raw_home)
            # Emitting to the subject will trigger update_ui via GLib.idle_add
            home_page_subject.on_next(home_data)
        except Exception as e:
            logging.error(f"Failed to fetch home data: {e}")
            nonlocal is_loading
            is_loading = False

    def on_yt_changed(yt: Optional[ytmusicapi.YTMusic]):
        nonlocal current_yt_instance, is_loading, current_limit
        current_yt_instance = yt
        # ALWAYS update GTK UI on the main thread to prevent crashes
        # GLib.idle_add(update_ui, yt)
        if yt is None:
            logging.info("YT Music instance is None, showing error message.")
            return
        current_limit = 5
        is_loading = True

        # raw_home = yt.get_home(limit=5)
        # home_data = HomePage.validate_python(raw_home)
        # home_page_subject.on_next(home_data)
        threading.Thread(
            target=fetch_home_data, args=(yt, current_limit), daemon=True
        ).start()

    yt_subject.subscribe(
        on_next=on_yt_changed, on_error=lambda e: print(f"Rx Error: {e}")
    )
    return scrolled
