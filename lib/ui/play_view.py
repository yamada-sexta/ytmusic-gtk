from lib.ui.thumbnail import ThumbnailWidget, ThumbnailWidgetFromUrl, Thumbnail
from typing import Optional
from lib.state.player_state import MediaStatus
from reactivex.subject import BehaviorSubject
from lib.ui.play_bar import PlayerState
from lib.state.player_state import PlayState
from gi.repository import Gtk, Adw, GLib, GObject, Pango
from reactivex import operators as ops
import reactivex as rx


def NowPlayingView(
    state: PlayerState,
) -> Adw.ToolbarView:
    """
    Functional component for the Detail 'Now Playing' view.
    """
    view = Adw.ToolbarView()
    view.add_css_class("background")

    # Main Content Box
    split_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    split_box.set_margin_start(32)
    split_box.set_margin_end(32)
    split_box.set_margin_top(32)
    split_box.set_margin_bottom(32)

    # --- Left Pane (Video / Art) ---
    left_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=32)
    left_pane.set_valign(Gtk.Align.CENTER)
    left_pane.set_halign(Gtk.Align.FILL)
    left_pane.set_margin_start(32)
    left_pane.set_margin_end(32)

    # Large album art — fed by a reactive stream from state.current

    art_thumbnails_stream = state.current.pipe(
        ops.map(
            lambda c: ([Thumbnail(url=c.album_art)] if c and c.album_art else None)
        ),
    )
    art_widget = ThumbnailWidget(art_thumbnails_stream)
    # Tell the widget to fill its new square container
    art_widget.set_halign(Gtk.Align.FILL)
    art_widget.set_valign(Gtk.Align.FILL)

    # 1. Force a perfect 1:1 square, ignoring the image's actual dimensions
    aspect_frame = Gtk.AspectFrame(ratio=1.0, obey_child=False)
    aspect_frame.set_child(art_widget)
    aspect_frame.set_halign(Gtk.Align.CENTER)
    aspect_frame.set_valign(Gtk.Align.CENTER)
    aspect_frame.set_hexpand(True)
    aspect_frame.set_vexpand(True)

    # 2. Wrap it in a clamp so it never exceeds a specific width
    art_clamp = Adw.Clamp(orientation=Gtk.Orientation.HORIZONTAL)
    art_clamp.set_maximum_size(400)  # Adjust this max width to fit your design
    art_clamp.set_child(aspect_frame)

    click_ctrl = Gtk.GestureClick.new()

    def toggle_play(*args):
        current_state = state.state.value
        if current_state == PlayState.PLAYING:
            state.state.on_next(PlayState.PAUSED)
        elif current_state == PlayState.PAUSED:
            state.state.on_next(PlayState.PLAYING)

    click_ctrl.connect("pressed", toggle_play)

    # You can attach the click controller directly to the clamp or aspect frame
    art_clamp.add_controller(click_ctrl)

    title_label = Gtk.Label(
        label="<span size='x-large' weight='bold'>Loading...</span>", use_markup=True
    )
    title_label.set_ellipsize(Pango.EllipsizeMode.END)
    title_label.set_lines(1)
    # Add these three lines:
    title_label.set_halign(Gtk.Align.FILL)  # Fill the available width
    title_label.set_xalign(0.5)  # Center the text internally
    title_label.set_max_width_chars(
        30
    )  # Stop the label from requesting endless natural width

    artist_label = Gtk.Label(label="Artist Name")
    artist_label.set_ellipsize(Pango.EllipsizeMode.END)
    artist_label.set_lines(1)
    # Add these three lines:
    artist_label.set_halign(Gtk.Align.FILL)
    artist_label.set_xalign(0.5)
    artist_label.set_max_width_chars(30)

    left_pane.append(art_clamp)
    left_pane.append(title_label)
    left_pane.append(artist_label)

    # --- Right Pane (Sidebar) ---
    right_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
    right_pane.set_size_request(300, -1)
    right_pane.set_margin_start(16)
    right_pane.set_margin_end(16)
    right_pane.set_margin_top(16)
    right_pane.set_margin_bottom(16)

    # 1. Tabs Header
    tabs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
    tabs_box.set_halign(Gtk.Align.CENTER)
    for tab_name in ("UP NEXT", "LYRICS", "RELATED"):
        btn = Gtk.Button(label=tab_name)
        btn.add_css_class("flat")
        if tab_name != "UP NEXT":
            btn.add_css_class("dim-label")
        tabs_box.append(btn)

    # 2. Context Metadata
    context_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    context_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    playing_from = Gtk.Label(label="Playing from")
    playing_from.add_css_class("dim-label")
    playing_from.set_halign(Gtk.Align.START)
    context_title = Gtk.Label(label="Queue")
    context_title.set_halign(Gtk.Align.START)
    context_title.add_css_class("title-2")
    context_text.append(playing_from)
    context_text.append(context_title)

    state.playlist.name.subscribe(
        on_next=lambda name: (
            context_title.set_label(GLib.markup_escape_text(name))
            if name
            else context_title.set_label("Queue")
        )
    )

    save_btn = Gtk.Button()
    save_btn.add_css_class("pill")
    save_btn.set_valign(Gtk.Align.CENTER)

    save_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    save_btn_icon = Gtk.Image(icon_name="list-add-symbolic")
    save_btn_label = Gtk.Label(label="Save")
    save_btn_box.append(save_btn_icon)
    save_btn_box.append(save_btn_label)
    save_btn.set_child(save_btn_box)

    context_box.append(context_text)
    spacer = Gtk.Box()
    spacer.set_hexpand(True)
    context_box.append(spacer)
    context_box.append(save_btn)

    # # 3. Filter Chips
    # chips_scroll = Gtk.ScrolledWindow()
    # chips_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
    # chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    # for chip in ["All", "Familiar", "Discover", "Popular"]:
    #     btn = Gtk.Button(label=chip)
    #     btn.add_css_class("pill")
    #     if chip == "All":
    #         btn.add_css_class("suggested-action")
    #     chips_box.append(btn)

    # chips_scroll.set_child(chips_box)

    # 4. Queue List
    queue_scroll = Gtk.ScrolledWindow()
    queue_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    queue_scroll.set_vexpand(True)

    queue_list = Gtk.ListBox()
    queue_list.add_css_class("boxed-list")
    queue_list.add_css_class("transparent")
    queue_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
    queue_list.set_valign(Gtk.Align.START)

    def _on_row_activated(box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        state.playlist.index.on_next(row.get_index())

    queue_list.connect("row-activated", _on_row_activated)

    queue_scroll.set_child(queue_list)

    # Assemble right pane
    right_pane.append(tabs_box)
    right_pane.append(context_box)
    # right_pane.append(chips_scroll)
    right_pane.append(queue_scroll)

    split_box.append(left_pane)
    split_box.append(right_pane)

    view.set_content(split_box)

    import reactivex as rx

    def update_title(title: Optional[str]):
        markup = f"<span size='x-large' weight='bold'>{GLib.markup_escape_text(title or '')}</span>"
        GLib.idle_add(title_label.set_markup, markup)

    def update_artist(artist: Optional[str]):
        GLib.idle_add(artist_label.set_text, artist or "")

    def on_current(current: Optional[MediaStatus]) -> None:
        if not current:
            return
        update_title(current.title)
        update_artist(current.artist)

    def _update_queue(media_list: list[MediaStatus]) -> None:
        while child := queue_list.get_first_child():
            queue_list.remove(child)

        for media in media_list:
            row = Adw.ActionRow(
                title=GLib.markup_escape_text(media.title or "Unknown Title"),
                subtitle=GLib.markup_escape_text(media.artist or "Unknown Artist"),
            )

            row.set_title_lines(1)
            row.set_subtitle_lines(1)
            row.set_activatable(True)

            thumb = ThumbnailWidgetFromUrl(rx.of(media.album_art or None))
            thumb.set_size_request(48, 48)
            h_clamp = Adw.Clamp(orientation=Gtk.Orientation.HORIZONTAL)
            h_clamp.set_maximum_size(48)
            h_clamp.set_tightening_threshold(0)
            h_clamp.set_hexpand(False)
            h_clamp.set_halign(Gtk.Align.START)
            h_clamp.set_overflow(Gtk.Overflow.HIDDEN)
            v_clamp = Adw.Clamp(orientation=Gtk.Orientation.VERTICAL)
            v_clamp.set_maximum_size(48)
            v_clamp.set_tightening_threshold(0)
            v_clamp.set_vexpand(False)
            v_clamp.set_valign(Gtk.Align.START)
            v_clamp.set_overflow(Gtk.Overflow.HIDDEN)
            v_clamp.set_child(thumb)
            h_clamp.set_child(v_clamp)

            v_clamp.set_margin_top(8)
            v_clamp.set_margin_bottom(8)

            row.add_prefix(h_clamp)

            queue_list.append(row)

        _highlight_current_index(state.playlist.index.value)

    def _highlight_current_index(idx: int) -> None:
        row = queue_list.get_row_at_index(idx)
        if row:
            queue_list.select_row(row)

    def _idle_update_queue(media_list: list[MediaStatus]) -> None:
        GLib.idle_add(_update_queue, media_list)

    def _idle_highlight(idx: int) -> None:
        GLib.idle_add(_highlight_current_index, idx)

    state.current.subscribe(on_current)
    state.playlist.media.subscribe(_idle_update_queue)
    state.playlist.index.subscribe(_idle_highlight)

    return view
