from lib.data import HomePageType
from lib.data import HomePage
import logging
import logging
from lib.types import YTMusicSubject
import ytmusicapi
from typing import Optional
from gi.repository import Gtk, GLib, Adw, Pango
from utils import load_image_async
import reactivex as rx
from reactivex.subject import BehaviorSubject


def create_home_page(
    yt_subject: YTMusicSubject,
) -> Gtk.ScrolledWindow:
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    home_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=32)
    home_box.set_margin_top(24)
    home_box.set_margin_bottom(24)
    # home_box.set_margin_start(24)
    # home_box.set_margin_end(24)
    scrolled.set_child(home_box)

    def update_ui(home: HomePageType):
        # Clear any existing widgets from the container (GTK4 style)
        while True:
            child = home_box.get_first_child()
            if not child:
                break
            home_box.remove(child)

        if len(home) == 0:
            logging.info("YT Music instance is not available, showing error message.")
            error_label = Gtk.Label(
                label="Failed to load data. Please check your login."
            )
            home_box.append(error_label)
            return
        logging.info(f"Updating UI with {len(home)} sections.")
        for section in home:
            section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            # Add padding to the header
            header = Gtk.Label(label=section.title)
            header.set_halign(Gtk.Align.START)
            header.set_margin_start(12)
            header.set_margin_bottom(8)
            header.add_css_class("title-2")  # Makes the text large and bold
            section_box.append(header)

            # Horizontal Carousel for the cards
            carousel = Adw.Carousel()
            carousel.set_spacing(16)
            carousel.set_allow_scroll_wheel(True)

            for item in section.contents:
                # Build the Card
                card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                card.set_size_request(160, -1)
                card.add_css_class("card")

                # Thumbnail Picture
                img = Gtk.Picture()
                img.set_size_request(200, 160)
                img.set_can_shrink(True)
                img.set_content_fit(Gtk.ContentFit.COVER)

                # Try to fetch the thumbnail URL if it exists
                if hasattr(item, "thumbnails") and item.thumbnails:
                    # Usually better to pick a medium resolution thumbnail
                    thumb_url = (
                        item.thumbnails[-1].url
                        if isinstance(item.thumbnails, list)
                        else item.thumbnails
                    )
                    load_image_async(img, thumb_url)

                # Title under thumbnail
                title_lbl = Gtk.Label(label=item.title)
                title_lbl.set_halign(Gtk.Align.START)
                title_lbl.set_wrap(True)
                title_lbl.set_lines(2)
                title_lbl.set_ellipsize(Pango.EllipsizeMode.END)

                # Optional: Subtitle (Artist)
                creator = (
                    item.artists[0].name
                    if getattr(item, "artists", None)
                    else "Unknown"
                )
                subtitle_lbl = Gtk.Label(label=creator)
                subtitle_lbl.set_halign(Gtk.Align.START)
                subtitle_lbl.add_css_class("dim-label")
                subtitle_lbl.set_ellipsize(Pango.EllipsizeMode.END)

                card.append(img)
                card.append(title_lbl)
                card.append(subtitle_lbl)

                # Make the entire card clickable
                click = Gtk.GestureClick.new()

                def on_card_click(gesture, n_press, x, y, current_item=item):
                    # current_item is a fix to capture the correct item in the loop
                    logging.info(f"Clicked on card: {current_item}")
                    # Here you would implement the logic to play the track or open the album
                    # For example, you could emit a signal or call a function with the item's ID
                    # play_track(item.video_id)  # Example function call

                click.connect("pressed", on_card_click)
                card.add_controller(click)

                carousel.append(card)

            # The "circle click thing" (Carousel indicators below the items)
            dots = Adw.CarouselIndicatorDots()
            dots.set_carousel(carousel)

            section_box.append(carousel)
            section_box.append(dots)

            home_box.append(section_box)

    home_page_subject = BehaviorSubject[HomePageType]([])
    home_page_subject.subscribe(
        on_next=update_ui, on_error=lambda e: print(f"Rx Error: {e}")
    )

    def on_yt_changed(yt: Optional[ytmusicapi.YTMusic]):
        # ALWAYS update GTK UI on the main thread to prevent crashes
        # GLib.idle_add(update_ui, yt)
        if yt is None:
            logging.info("YT Music instance is None, showing error message.")
            return

        raw_home = yt.get_home(limit=5)
        home_data = HomePage.validate_python(raw_home)
        home_page_subject.on_next(home_data)

    yt_subject.subscribe(
        on_next=on_yt_changed, on_error=lambda e: print(f"Rx Error: {e}")
    )
    return scrolled
