from lib.state.player_state import LikeStatus, start_play
from lib.state.player_state import MediaStatus
from lib.ui.thumbnail import ThumbnailWidget
from reactivex import Subject
from typing import Tuple
from lib.data import Album, Artist, BaseMedia
from reactivex import operators as ops
import threading
import logging
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
    album: Optional[Album] = None

    # Albums & Singles
    audio_playlist_id: Optional[str] = Field(None, alias="audioPlaylistId")

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
    item: HomeItemData,
    player_state: PlayerState,
    yt: ytmusicapi.YTMusic,
    nav_view: Adw.NavigationView,
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

    import reactivex as rx

    img = ThumbnailWidget(rx.of(item.thumbnails))

    # Clip to the card's intended pixel dimensions.
    # halign=CENTER prevents img_clip from expanding beyond width.
    img_clip = Gtk.Box()
    img_clip.set_size_request(width, height)
    img_clip.set_overflow(Gtk.Overflow.HIDDEN)
    img_clip.set_halign(Gtk.Align.CENTER)
    img_clip.append(img)

    # Wrap the clipped image in an overlay for the play button
    overlay = Gtk.Overlay()
    overlay.set_child(img_clip)

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
    # Reserve a fixed minimum height so all cards are the same size regardless of title length.
    # set_lines(2) is a maximum – a 1-line title would otherwise shrink the card.
    text_box.set_size_request(-1, 72)

    title_lbl = Gtk.Label(label=item.title)
    title_lbl.set_halign(Gtk.Align.START)
    title_lbl.set_xalign(0.0)

    # set_lines(2) caps wrapping at 2 lines; valign=START pins content to the top
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

    # Add a small play button on the bottom-right for collection items
    is_collection = not item.video_id
    collection_play_btn: Optional[Gtk.Button] = None
    if is_collection:
        collection_play_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
        collection_play_btn.add_css_class("osd")
        collection_play_btn.add_css_class("circular")
        collection_play_btn.add_css_class("collection-play-btn")
        collection_play_btn.set_size_request(48, 48)
        collection_play_btn.set_halign(Gtk.Align.END)
        collection_play_btn.set_valign(Gtk.Align.END)
        collection_play_btn.set_margin_end(8)
        collection_play_btn.set_margin_bottom(8)
        collection_play_btn.set_tooltip_text("Play")
        collection_play_btn.set_opacity(0.0)
        collection_play_btn.set_can_target(False)
        overlay.add_overlay(collection_play_btn)

        # ReactiveX hover state
        hover_subject = BehaviorSubject(False)

        hover_ctrl = Gtk.EventControllerMotion()
        hover_ctrl.connect("enter", lambda *_: hover_subject.on_next(True))
        hover_ctrl.connect("leave", lambda *_: hover_subject.on_next(False))
        overlay.add_controller(hover_ctrl)

        def on_hover_changed(is_hovered: bool) -> None:
            def animate() -> int:
                if not collection_play_btn:
                    return GLib.SOURCE_REMOVE
                target_opacity = 1.0 if is_hovered else 0.0
                current_opacity = collection_play_btn.get_opacity()
                anim_target = Adw.CallbackAnimationTarget.new(
                    lambda val: collection_play_btn.set_opacity(val)
                )
                anim = Adw.TimedAnimation.new(
                    collection_play_btn,
                    current_opacity,
                    target_opacity,
                    200,
                    anim_target,
                )
                anim.set_easing(Adw.Easing.EASE_IN_OUT_CUBIC)
                anim.play()
                return GLib.SOURCE_REMOVE

            GLib.idle_add(animate)

        hover_subject.subscribe(on_hover_changed)

    card.append(overlay)
    card.append(text_box)

    click = Gtk.GestureClick.new()

    def on_card_click(gesture: Gtk.GestureClick, n_press: int, x: float, y: float):
        # Check if click landed on the play button area
        if collection_play_btn and collection_play_btn.get_opacity() > 0.5:
            from gi.repository import Graphene  # type: ignore

            point = Graphene.Point()
            point.x = x
            point.y = y
            success, out_point = card.compute_point(collection_play_btn, point)
            if success:
                bw = collection_play_btn.get_width()
                bh = collection_play_btn.get_height()
                if 0 <= out_point.x <= bw and 0 <= out_point.y <= bh:
                    playlist_id = item.audio_playlist_id or item.playlist_id
                    if playlist_id:
                        logging.info(
                            f"Quick-playing collection: {item.title} ({playlist_id})"
                        )
                        start_play(state=player_state, playlist_id=playlist_id)
                    return

        logging.info(f"Clicked on card: {item}")

        def is_current_playing():
            return (
                player_state.current_item
                and item.video_id
                and player_state.current_item.id == item.video_id
            ) or (
                player_state.playlist.playlist_id.value
                and item.playlist_id
                and player_state.playlist.playlist_id.value == item.playlist_id
            )

        if is_current_playing():
            if player_state.state.value == PlayState.PLAYING:
                player_state.state.on_next(PlayState.PAUSED)
                return
            elif player_state.state.value == PlayState.PAUSED:
                player_state.state.on_next(PlayState.PLAYING)
                return
            elif player_state.state.value == PlayState.LOADING:
                return

        if item.video_id:
            if item.playlist_id:
                logging.info(f"Playing song with playlist: {item.title}")
                start_play(
                    state=player_state,
                    playlist_id=item.playlist_id,
                    video_id=item.video_id,
                )
                return
        else:
            # No video_id — this is a collection (album, playlist, etc.)
            if item.browse_id and item.browse_id.startswith("MPRE"):
                logging.info(f"Opening detail page for album {item.browse_id}")
                from lib.ui.collection_detail import CollectionDetailPage

                detail_page = CollectionDetailPage(
                    item.browse_id, "album", player_state, yt
                )
                nav_view.push(detail_page)
                return

            if item.playlist_id:
                logging.info(f"Opening detail page for playlist {item.playlist_id}")
                from lib.ui.collection_detail import CollectionDetailPage

                detail_page = CollectionDetailPage(
                    item.playlist_id, "playlist", player_state, yt
                )
                nav_view.push(detail_page)
                return

            if item.audio_playlist_id:
                logging.info(
                    f"Playing album/single via audioPlaylistId: {item.audio_playlist_id}"
                )
                start_play(state=player_state, playlist_id=item.audio_playlist_id)
                return

            logging.warning("Item has no video ID or audio playlist ID, cannot play.")
            logging.debug(f"Item: {item}")
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
        # if hasattr(item, "like_status"):
        #     like_status = item.like_status
        new_music = MediaStatus(
            id=item.video_id,
            title=title,
            artist=creator,
            album_name=album_name,
            album_art=thumb_url,
            like_status=BehaviorSubject("INDIFFERENT"),
        )

        start_play(
            state=player_state,
            video_id=item.video_id,
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
    def on_current_changed(current: Optional[MediaStatus]) -> None:
        if current and current.id:
            update_playing_state(current.id)
        else:
            update_playing_state(None)

    player_state.current.subscribe(on_current_changed)
    return card


# Leave HomeItemCard exactly as you have it!


def HomeRow(
    section: HomeSectionData,
    player_state: PlayerState,
    yt: ytmusicapi.YTMusic,
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

    for item in section.contents:
        row_box.append(HomeItemCard(item, player_state, yt, nav_view))

    scrolled.set_child(row_box)
    box.append(scrolled)

    # Return both so the parent can inject new items later, exactly as before
    return box, row_box


def HomePage(
    yt_subject: BehaviorSubject[Optional[ytmusicapi.YTMusic]],
    player_state: PlayerState,
    nav_view: Adw.NavigationView,
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

    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    clamp.set_child(main_box)

    home_box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL, spacing=48
    )  # Increased spacing between rows
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

    current_limit = BehaviorSubject(5)
    is_loading = BehaviorSubject(False)
    has_more = BehaviorSubject(True)
    # current_yt_instance = BehaviorSubject[Optional[ytmusicapi.YTMusic]](None)
    row_cache = {}

    home_page_subject = BehaviorSubject[
        Tuple[HomePageType, bool, Optional[ytmusicapi.YTMusic]]
    ](([], True, None))
    scroll_subject = Subject()

    def update_ui(
        home: HomePageType, is_reset: bool, yt: Optional[ytmusicapi.YTMusic]
    ) -> bool:

        if is_reset:
            while (child := home_box.get_first_child()) is not None:
                home_box.remove(child)
            row_cache.clear()
            has_more.on_next(True)

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
            is_loading.on_next(False)
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
                        carousel.append(HomeItemCard(item, player_state, yt, nav_view))
                    row_cache[section.title] = (
                        section_box,
                        carousel,
                        len(section.contents),
                    )
            else:
                section_box, carousel = HomeRow(section, player_state, yt, nav_view)
                home_box.append(section_box)
                row_cache[section.title] = (
                    section_box,
                    carousel,
                    len(section.contents),
                )

        bottom_spinner_box.set_visible(False)
        is_loading.on_next(False)

        if yt and len(home) < current_limit.value:
            has_more.on_next(False)

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
            if is_reset:
                home_page_subject.on_next(([], is_reset, None))
            else:
                home_page_subject.on_next(([], False, yt))

    def trigger_load_more(dummy_value=None):
        if is_loading.value:
            return
        logging.info("Fetching more data...")
        is_loading.on_next(True)
        bottom_spinner_box.set_visible(True)
        new_limit = current_limit.value + 5
        current_limit.on_next(new_limit)
        threading.Thread(
            target=fetch_home_data,
            args=(
                yt_subject.value,
                new_limit,
                False,
            ),  # False = don't reset UI
            daemon=True,
        ).start()

    def on_edge_reached(sw: Gtk.ScrolledWindow, pos: Gtk.PositionType):
        if pos == Gtk.PositionType.BOTTOM:
            scroll_subject.on_next(None)

    scrolled.connect("edge-reached", on_edge_reached)

    def check_scroll_valid(dummy_value) -> bool:
        return not is_loading.value and yt_subject.value is not None and has_more.value

    scroll_subject.pipe(ops.filter(check_scroll_valid)).subscribe(
        on_next=trigger_load_more, on_error=on_rx_error
    )

    def on_yt_changed(yt: Optional[ytmusicapi.YTMusic]):
        if yt is None:
            logging.info("YT Music instance is None, showing error message.")
            return

        current_limit.on_next(5)
        is_loading.on_next(True)

        # FIXED: Added the explicit `True` argument for `is_reset`
        threading.Thread(
            target=fetch_home_data, args=(yt, current_limit.value, True), daemon=True
        ).start()

    yt_subject.subscribe(on_next=on_yt_changed, on_error=on_rx_error)

    return scrolled
