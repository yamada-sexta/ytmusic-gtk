from lib.net.client import YTClient
from lib.data import AlbumData, AlbumTrack
from lib.ui.thumbnail import ThumbnailWidget
from lib.ui.play_bar import PlayerState
from lib.state.player_state import start_play
from typing import Optional, Literal
import reactivex as rx
import ytmusicapi
import threading
import logging
from gi.repository import Gtk, Adw, GLib, Pango, Gdk


def CollectionDetailPage(
    item_id: str,
    item_type: Literal["album", "playlist"],
    player_state: PlayerState,
    yt: YTClient,
) -> Adw.NavigationPage:
    """
    Creates a detail page for an album/single/EP that slides in from the right.
    Left pane: artwork, metadata, action buttons.
    Right pane: scrollable track list.
    """

    page = Adw.NavigationPage(title="Loading...")

    # Outer toolbar view with a header bar for the back button
    toolbar = Adw.ToolbarView()
    page.set_child(toolbar)

    header = Adw.HeaderBar()
    toolbar.add_top_bar(header)

    # Main content area — starts with a loading spinner
    content_stack = Gtk.Stack()
    content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
    toolbar.set_content(content_stack)

    # Loading state
    loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    loading_box.set_valign(Gtk.Align.CENTER)
    loading_box.set_vexpand(True)

    loading_page = Adw.StatusPage()
    loading_page.set_title(f"Loading {item_type}...")
    loading_page.set_description("Fetching track list")

    spinner = Adw.Spinner()
    spinner.set_size_request(48, 48)
    spinner.set_halign(Gtk.Align.CENTER)

    loading_box.append(loading_page)
    loading_box.append(spinner)
    content_stack.add_named(loading_box, "loading")

    # Content (built after fetch)
    detail_box = Gtk.Box()
    content_stack.add_named(detail_box, "content")

    content_stack.set_visible_child_name("loading")

    def build_detail_ui(album: AlbumData) -> bool:
        page.set_title(album.title)

        # Use a ScrolledWindow for the entire detail view
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        # Clamp for max width and centered layout
        clamp = Adw.Clamp()
        clamp.set_maximum_size(1000)
        clamp.set_margin_top(32)
        clamp.set_margin_bottom(32)
        clamp.set_margin_start(24)
        clamp.set_margin_end(24)
        scrolled.set_child(clamp)

        # Root container: horizontal layout (left info + right tracks)
        root_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=48)
        root_box.set_valign(Gtk.Align.START)
        clamp.set_child(root_box)

        # Left pane: artwork + metadata + action buttons
        left_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        left_pane.set_halign(Gtk.Align.CENTER)
        left_pane.set_valign(Gtk.Align.START)
        left_pane.set_size_request(240, -1)

        # Album art
        img = ThumbnailWidget(rx.of(album.thumbnails))
        img.set_size_request(240, 240)

        img_clip = Gtk.Box()
        img_clip.set_size_request(240, 240)
        img_clip.set_overflow(Gtk.Overflow.HIDDEN)
        img_clip.set_halign(Gtk.Align.CENTER)
        img_clip.append(img)
        left_pane.append(img_clip)

        # Title
        title_lbl = Gtk.Label(label=album.title)
        title_lbl.set_halign(Gtk.Align.CENTER)
        title_lbl.set_wrap(True)
        title_lbl.set_justify(Gtk.Justification.CENTER)
        title_lbl.add_css_class("title-1")
        left_pane.append(title_lbl)

        # Type and Year
        meta_parts: list[str] = []
        if album.type:
            meta_parts.append(album.type)
        if album.year:
            meta_parts.append(album.year)
        meta_lbl = Gtk.Label(label=" • ".join(meta_parts))
        meta_lbl.set_halign(Gtk.Align.CENTER)
        meta_lbl.add_css_class("dim-label")
        left_pane.append(meta_lbl)

        # Track count and duration
        info_parts: list[str] = []
        if album.track_count:
            info_parts.append(f"{album.track_count} songs")
        if album.duration:
            info_parts.append(album.duration)
        if info_parts:
            info_lbl = Gtk.Label(label=" • ".join(info_parts))
            info_lbl.set_halign(Gtk.Align.CENTER)
            info_lbl.add_css_class("dim-label")
            info_lbl.add_css_class("caption")
            left_pane.append(info_lbl)

        # Action buttons row
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(8)

        # Bookmark button (placeholder)
        bookmark_btn = Gtk.Button(icon_name="bookmark-new-symbolic")
        bookmark_btn.add_css_class("flat")
        bookmark_btn.add_css_class("circular")
        bookmark_btn.set_tooltip_text("Save to library")
        bookmark_btn.set_size_request(48, 48)
        btn_box.append(bookmark_btn)

        # Play button (functional)
        play_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
        play_btn.add_css_class("suggested-action")
        play_btn.add_css_class("circular")
        play_btn.set_tooltip_text("Play album")
        play_btn.set_size_request(56, 56)

        def on_play_clicked(_btn: Gtk.Button) -> None:
            playlist_id = album.audio_playlist_id or album.id
            if not playlist_id:
                logging.warning("Collection has no playlist ID, cannot play.")
                return
            logging.info(f"Playing collection: {album.title} ({playlist_id})")
            start_play(state=player_state, playlist_id=playlist_id)

        play_btn.connect("clicked", on_play_clicked)
        btn_box.append(play_btn)

        # More button (placeholder)
        more_btn = Gtk.Button(icon_name="view-more-symbolic")
        more_btn.add_css_class("flat")
        more_btn.add_css_class("circular")
        more_btn.set_tooltip_text("More options")
        more_btn.set_size_request(48, 48)
        btn_box.append(more_btn)

        left_pane.append(btn_box)

        root_box.append(left_pane)

        # Right pane: track list
        right_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_pane.set_hexpand(True)
        right_pane.set_valign(Gtk.Align.START)

        track_list = Gtk.ListBox()
        track_list.add_css_class("boxed-list")
        track_list.set_selection_mode(Gtk.SelectionMode.NONE)

        for i, track in enumerate(album.tracks):
            artist_name = track.artists[0].name if track.artists else ""
            views_text = track.views or ""

            subtitle_parts = []
            if views_text:
                subtitle_parts.append(views_text)
            subtitle = " • ".join(subtitle_parts)

            row = Adw.ActionRow(
                title=GLib.markup_escape_text(track.title),
                subtitle=GLib.markup_escape_text(subtitle) if subtitle else "",
            )

            # Track number
            num_lbl = Gtk.Label(label=f"{i + 1}")
            num_lbl.set_margin_start(8)
            num_lbl.set_margin_end(8)
            num_lbl.add_css_class("dim-label")
            num_lbl.set_size_request(24, -1)
            row.add_prefix(num_lbl)

            # Duration on the right
            if track.duration:
                dur_lbl = Gtk.Label(label=track.duration)
                dur_lbl.add_css_class("dim-label")
                dur_lbl.add_css_class("caption")
                dur_lbl.set_margin_end(8)
                row.add_suffix(dur_lbl)

            # Make row clickable to play that specific track
            if track.video_id:
                row.set_activatable(True)
                vid = track.video_id

                def make_track_handler(video_id: str, playlist_id: Optional[str]):
                    def handler(_row: Adw.ActionRow) -> None:
                        logging.info(f"Playing track: {video_id}")
                        start_play(
                            state=player_state,
                            video_id=video_id,
                            playlist_id=playlist_id,
                        )

                    return handler

                row.connect(
                    "activated",
                    make_track_handler(vid, album.audio_playlist_id or album.id),
                )

            track_list.append(row)

        right_pane.append(track_list)
        root_box.append(right_pane)

        # Swap the detail_box content
        while (child := detail_box.get_first_child()) is not None:
            detail_box.remove(child)
        detail_box.append(scrolled)

        content_stack.set_visible_child_name("content")

        return GLib.SOURCE_REMOVE

    def fetch_data() -> None:
        try:
            if item_type == "playlist":
                raw_data = yt.get_playlist(item_id)
            else:
                raw_data = yt.get_album(item_id)
            album = AlbumData.model_validate(raw_data)
            GLib.idle_add(build_detail_ui, album)
        except Exception as e:
            logging.error(f"Failed to fetch {item_type} {item_id}: {e}")
            error_msg = str(e)

            def show_error() -> bool:
                error_page = Adw.StatusPage()
                error_page.set_icon_name("dialog-error-symbolic")
                error_page.set_title(f"Failed to load {item_type}")
                error_page.set_description(error_msg)
                content_stack.add_named(error_page, "error")
                content_stack.set_visible_child_name("error")
                return GLib.SOURCE_REMOVE

            GLib.idle_add(show_error)

    threading.Thread(target=fetch_data, daemon=True).start()

    return page
