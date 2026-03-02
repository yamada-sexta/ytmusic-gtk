from typing import Optional
from lib.state.player_state import MediaStatus
from reactivex.subject import BehaviorSubject
from lib.ui.play_bar import PlayerState
from lib.state.player_state import PlayState
from gi.repository import Gtk, Adw, GLib, GObject, Pango


def create_now_playing_view(
    state: PlayerState, show_now_playing: BehaviorSubject[bool]
) -> Gtk.Widget:
    """
    Functional component for the Detail 'Now Playing' view.
    """
    view = Adw.ToolbarView()

    # Forces the view to have a solid background (matches light/dark mode automatically)
    view.add_css_class("background")

    # Manually recreate the header bar
    header = Adw.HeaderBar()
    header.set_show_title(False)

    # Create a close button with a flat style to look like a native nav button
    close_btn = Gtk.Button(icon_name="go-down-symbolic")
    close_btn.add_css_class("flat")
    close_btn.set_tooltip_text("Close Now Playing")

    # Reactively tell the state to close this view
    close_btn.connect("clicked", lambda *_: show_now_playing.on_next(False))
    header.pack_start(close_btn)

    view.add_top_bar(header)

    # Main Content Box
    split_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

    # --- Left Pane (Video / Art) ---
    left_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
    left_pane.set_valign(Gtk.Align.CENTER)
    left_pane.set_halign(Gtk.Align.CENTER)
    left_pane.set_hexpand(True)

    art_stack = Gtk.Stack()
    art_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

    art_fallback = Gtk.Image(icon_name="audio-x-generic-symbolic")
    art_fallback.set_pixel_size(256)
    art_fallback.add_css_class("dim-label")
    art_fallback.add_css_class("card")

    art_picture = Gtk.Picture()
    art_picture.set_can_shrink(True)
    art_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
    art_picture.add_css_class("card")

    art_stack.add_named(art_fallback, "fallback")
    art_stack.add_named(art_picture, "picture")

    # Make the art clickable to toggle play/pause
    click_ctrl = Gtk.GestureClick.new()

    def toggle_play(*args):
        current_state = state.state.value
        if current_state == PlayState.PLAYING:
            state.state.on_next(PlayState.PAUSED)
        elif current_state == PlayState.PAUSED:
            state.state.on_next(PlayState.PLAYING)

    click_ctrl.connect("pressed", toggle_play)
    art_stack.add_controller(click_ctrl)

    title_label = Gtk.Label(
        label="<span size='x-large' weight='bold'>Loading...</span>", use_markup=True
    )
    title_label.set_ellipsize(Pango.EllipsizeMode.END)
    title_label.set_lines(1)

    artist_label = Gtk.Label(label="Artist Name")
    artist_label.set_ellipsize(Pango.EllipsizeMode.END)
    artist_label.set_lines(1)

    left_pane.append(art_stack)
    left_pane.append(title_label)
    left_pane.append(artist_label)

    # --- Right Pane (Sidebar) ---
    right_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    right_pane.set_size_request(300, -1)
    right_pane.set_margin_start(16)
    right_pane.set_margin_end(16)
    right_pane.set_margin_top(16)
    right_pane.set_margin_bottom(16)

    # 1. Tabs Header
    tabs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
    tabs_box.set_halign(Gtk.Align.CENTER)
    for tab_name in ["UP NEXT", "LYRICS", "RELATED"]:
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
    context_text.append(playing_from)
    context_text.append(context_title)

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

    # 3. Filter Chips
    chips_scroll = Gtk.ScrolledWindow()
    chips_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
    chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    for chip in ["All", "Familiar", "Discover", "Popular"]:
        btn = Gtk.Button(label=chip)
        btn.add_css_class("pill")
        if chip == "All":
            btn.add_css_class("suggested-action")
        chips_box.append(btn)

    chips_scroll.set_child(chips_box)

    # 4. Queue List
    queue_scroll = Gtk.ScrolledWindow()
    queue_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    queue_scroll.set_vexpand(True)

    queue_list = Gtk.ListBox()
    queue_list.add_css_class("boxed-list")
    queue_list.add_css_class("transparent")
    queue_list.set_selection_mode(Gtk.SelectionMode.NONE)

    # Add dummy items
    for i in range(1, 10):
        row = Adw.ActionRow(title=f"Dummy Track {i}", subtitle="Dummy Artist")
        img = Gtk.Image(icon_name="audio-x-generic-symbolic")
        img.set_pixel_size(48)
        row.add_prefix(img)
        duration = Gtk.Label(label="3:00")
        row.add_suffix(duration)
        queue_list.append(row)

    queue_scroll.set_child(queue_list)

    # Assemble right pane
    right_pane.append(tabs_box)
    right_pane.append(context_box)
    right_pane.append(chips_scroll)
    right_pane.append(queue_scroll)

    split_box.append(left_pane)
    split_box.append(right_pane)

    view.set_content(split_box)

    # Reactive Bindings
    def update_title(title: Optional[str]):
        markup = f"<span size='x-large' weight='bold'>{GLib.markup_escape_text(title or '')}</span>"
        GLib.idle_add(title_label.set_markup, markup)

    def update_artist(artist: Optional[str]):
        GLib.idle_add(artist_label.set_text, artist or "")

    def _on_album_art_change(value: Optional[str]):
        if not value:
            GLib.idle_add(art_stack.set_visible_child_name, "fallback")
            return
        if isinstance(value, str) and value.startswith("http"):
            from utils import load_image_async

            load_image_async(art_picture, value)
            GLib.idle_add(art_stack.set_visible_child_name, "picture")
        else:
            GLib.idle_add(art_fallback.set_from_icon_name, value)
            GLib.idle_add(art_stack.set_visible_child_name, "fallback")

    def on_current(current: Optional[MediaStatus]) -> None:
        if not current:
            return
        update_title(current.title)
        update_artist(current.artist)
        _on_album_art_change(current.album_art)

    state.current.subscribe(on_current)

    return view
