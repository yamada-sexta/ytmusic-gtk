from lib.state.player_state import play_watch_playlist
from typing import Optional
from lib.state.player_state import PlayState
from lib.ui.thumbnail import ThumbnailWidget
from lib.ui.play_bar import PlayerState
from lib.net.client import YTClient
from lib.state.player_state import MediaStatus
from lib.ui.collection_detail import CollectionDetailPage
from lib.data import HomeItemData

# from lib.ui.play_watch_playlist import play_watch_playlist
from gi.repository import Gtk, Adw, GLib, Gdk, Pango, GdkPixbuf, Graphene
from reactivex.subject import BehaviorSubject
import reactivex as rx
import logging


def PlayItemCard(
    item: HomeItemData,
    player: PlayerState,
    client: YTClient,
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

    player.state.subscribe(update_play_icon)

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
            from gi.repository import Graphene

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
                        play_watch_playlist(state=player, playlist_id=playlist_id)
                    return

        logging.info(f"Clicked on card: {item}")

        def is_current_playing():
            return (
                player.current_item
                and item.video_id
                and player.current_item.id == item.video_id
            )

        if is_current_playing():
            if player.state.value == PlayState.PLAYING:
                player.state.on_next(PlayState.PAUSED)
                return
            elif player.state.value == PlayState.PAUSED:
                player.state.on_next(PlayState.PLAYING)
                return
            elif player.state.value == PlayState.LOADING:
                return

        if item.video_id:
            logging.info(f"Playing song with playlist: {item.title}")
            placeholder_music = MediaStatus(
                id=item.video_id,
                title=item.title,
                artist=item.artists[0].name if item.artists else None,
                album_name=item.album.name if item.album else None,
                album_art=item.thumbnails[-1].url if item.thumbnails else None,
                like_status=BehaviorSubject("INDIFFERENT"),
            )

            play_watch_playlist(
                state=player,
                playlist_id=item.playlist_id,
                video_id=item.video_id,
                placeholder_music=placeholder_music,
            )
            return

        else:
            # No video_id — this is a collection (album, playlist, etc.)
            if item.browse_id and item.browse_id.startswith("MPRE"):
                logging.info(f"Opening detail page for album {item.browse_id}")
                detail_page = CollectionDetailPage(
                    item.browse_id, "album", player, client
                )
                nav_view.push(detail_page)
                return

            if item.playlist_id:
                logging.info(f"Opening detail page for playlist {item.playlist_id}")

                detail_page = CollectionDetailPage(
                    item.playlist_id, "playlist", player, client
                )
                nav_view.push(detail_page)
                return
            if item.audio_playlist_id:
                logging.info(
                    f"Opening detail page for single/album style {item.audio_playlist_id}"
                )

                detail_page = CollectionDetailPage(
                    item.audio_playlist_id, "playlist", player, client
                )
                nav_view.push(detail_page)
                return

            logging.warning("Item has no video ID or audio playlist ID, cannot play.")
            logging.debug(f"Item: {item}")
            player.state.on_next(PlayState.EMPTY)
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
        placeholder_music: Optional[MediaStatus] = None

        if item.video_id:
            placeholder_music = MediaStatus(
                id=item.video_id,
                title=title,
                artist=creator,
                album_name=album_name,
                album_art=thumb_url,
                like_status=BehaviorSubject("INDIFFERENT"),
            )

        play_watch_playlist(
            state=player,
            video_id=item.video_id,
            playlist_id=item.playlist_id,
            placeholder_music=placeholder_music,
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

    player.current.subscribe(on_current_changed)
    return card
