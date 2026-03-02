from lib.state.player_state import CurrentMusic
from reactivex.subject import BehaviorSubject
from lib.ui.helpers import toggle_css
from lib.ui.helpers import toggle_icon
from lib.ui.helpers import format_time
from lib.state.player_state import PlayState
from typing import Optional
from gi.repository import Gtk, GLib, Adw, Pango, Gst
from reactivex import combine_latest
from lib.state.player_state import PlayerState


def ProgressBar(
    state: PlayerState,
) -> Gtk.Widget:
    progress_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.01)
    progress_scale.set_draw_value(False)
    progress_scale.set_hexpand(True)
    # Make it flush against the top edge
    progress_scale.set_margin_top(0)
    progress_scale.set_margin_bottom(0)
    # Add a bit of padding on the sides
    progress_scale.set_margin_start(8)
    progress_scale.set_margin_end(8)

    is_updating_scale = False

    def update_progress_ui(times: tuple[int, int]):
        nonlocal is_updating_scale
        current_ns, total_ns = times

        is_updating_scale = True
        if total_ns > 0:
            progress_scale.set_range(0, total_ns / 1e9)
        progress_scale.set_value(current_ns / 1e9)
        is_updating_scale = False

    # state.current.subscribe(on_current)
    combine_latest(state.stream.current_time, state.stream.total_time).subscribe(
        update_progress_ui
    )

    def on_scale_changed(scale: Gtk.Scale) -> None:
        if is_updating_scale or not state.current.value:
            return

        val_seconds = scale.get_value()
        new_pos_ns = int(val_seconds * 1e9)
        state.stream.seek_request.on_next(new_pos_ns)

    progress_scale.connect("value-changed", on_scale_changed)

    state.state.subscribe(lambda s: progress_scale.set_sensitive(s != PlayState.EMPTY))

    return progress_scale


def PlayControls(state: PlayerState) -> Gtk.Widget:
    controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    controls_box.set_valign(Gtk.Align.CENTER)
    controls_box.set_margin_start(16)

    prev_btn = Gtk.Button(icon_name="media-skip-backward-symbolic")
    prev_btn.add_css_class("flat")
    prev_btn.add_css_class("circular")
    prev_btn.set_size_request(16, 16)

    play_icon = Gtk.Image()
    play_icon.set_pixel_size(24)

    play_spinner = Adw.Spinner() if hasattr(Adw, "Spinner") else Gtk.Spinner()

    play_stack = Gtk.Stack()
    play_stack.add_named(play_icon, "icon")
    play_stack.add_named(play_spinner, "spinner")

    play_pause_btn = Gtk.Button()
    play_pause_btn.set_child(play_stack)
    play_pause_btn.add_css_class("circular")
    play_pause_btn.set_size_request(48, 48)

    next_btn = Gtk.Button(icon_name="media-skip-forward-symbolic")
    next_btn.add_css_class("flat")
    next_btn.add_css_class("circular")
    next_btn.set_size_request(16, 16)

    time_label = Gtk.Label()
    time_label.add_css_class("dim-label")
    time_label.add_css_class("numeric")
    time_label.set_margin_start(8)
    time_label.set_width_chars(14)
    time_label.set_xalign(0.0)

    def update_play_btn(s: PlayState):
        if s == PlayState.LOADING:
            if hasattr(play_spinner, "start"):
                play_spinner.start()
            play_stack.set_visible_child_name("spinner")
        else:
            if hasattr(play_spinner, "stop"):
                play_spinner.stop()
            play_icon.set_from_icon_name(
                "media-playback-pause-symbolic"
                if s == PlayState.PLAYING
                else "media-playback-start-symbolic"
            )
            play_stack.set_visible_child_name("icon")

        is_empty = s == PlayState.EMPTY
        prev_btn.set_sensitive(not is_empty)
        play_pause_btn.set_sensitive(not is_empty)
        next_btn.set_sensitive(not is_empty)

    state.state.subscribe(update_play_btn)

    def toggle_play(_):
        current = state.state.value
        if current == PlayState.PLAYING:
            state.state.on_next(PlayState.PAUSED)
        elif current == PlayState.PAUSED:
            state.state.on_next(PlayState.PLAYING)

    play_pause_btn.connect("clicked", toggle_play)

    # state.current.subscribe(on_current)
    combine_latest(state.stream.current_time, state.stream.total_time).subscribe(
        lambda times: time_label.set_text(
            f"{format_time(times[0])} / {format_time(times[1])}"
        )
    )

    controls_box.append(prev_btn)
    controls_box.append(play_pause_btn)
    controls_box.append(next_btn)
    controls_box.append(time_label)

    return controls_box


def SongInfo(state: PlayerState) -> Gtk.Widget:
    center_clamp = Adw.Clamp()
    center_clamp.set_maximum_size(600)
    center_clamp.set_tightening_threshold(600)

    center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    center_box.set_valign(Gtk.Align.CENTER)

    album_art = Gtk.Image()
    album_art.set_pixel_size(48)
    album_art.add_css_class("card")

    text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    text_vbox.set_valign(Gtk.Align.CENTER)
    text_vbox.set_hexpand(True)

    title_label = Gtk.Label()
    title_label.set_halign(Gtk.Align.START)
    title_label.set_xalign(0.0)
    title_label.set_ellipsize(Pango.EllipsizeMode.END)

    subtitle_label = Gtk.Label()
    subtitle_label.set_halign(Gtk.Align.START)
    subtitle_label.set_xalign(0.0)
    subtitle_label.set_ellipsize(Pango.EllipsizeMode.END)
    subtitle_label.add_css_class("dim-label")

    text_vbox.append(title_label)
    text_vbox.append(subtitle_label)

    actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    actions_box.set_valign(Gtk.Align.CENTER)

    dislike_btn = Gtk.Button(icon_name="thumbs-down-outline-symbolic")
    dislike_btn.add_css_class("flat")

    like_btn = Gtk.Button(icon_name="thumbs-up-outline-symbolic")
    like_btn.add_css_class("flat")

    more_btn = Gtk.Button(icon_name="view-more-symbolic")
    more_btn.add_css_class("flat")

    actions_box.append(dislike_btn)
    actions_box.append(like_btn)
    actions_box.append(more_btn)

    center_box.append(album_art)
    center_box.append(text_vbox)
    center_box.append(actions_box)

    center_clamp.set_child(center_box)

    def _on_album_art_change(value: Optional[str]):
        if not value:
            return
        if isinstance(value, str) and value.startswith("http"):
            from utils import load_image_async

            load_image_async(album_art, value)
        else:
            album_art.set_from_icon_name(value)

    def on_current(current: Optional[CurrentMusic]) -> None:
        if not current:
            return
        for btn in (dislike_btn, like_btn, more_btn):
            btn.set_sensitive(current != PlayState.EMPTY)
        current.is_liked.subscribe(
            lambda val: toggle_icon(
                like_btn,
                val,
                "thumbs-up-symbolic",
                "thumbs-up-outline-symbolic",
            )
        )
        current.is_disliked.subscribe(
            lambda val: toggle_icon(
                dislike_btn,
                val,
                "thumbs-down-symbolic",
                "thumbs-down-outline-symbolic",
            )
        )
        subtitle_label.set_text(
            " • ".join(filter(None, [current.artist, current.album_name, current.year]))
        )
        title_label.set_markup(f"<b>{GLib.markup_escape_text(current.title or '')}</b>")
        _on_album_art_change(current.album_art)

    state.current.subscribe(on_current)

    def on_like_clicked(_):
        current = state.current.value
        if not current:
            return
        current.is_liked.on_next(not current.is_liked.value)
        if current.is_liked.value and current.is_disliked.value:
            current.is_disliked.on_next(False)
        state.current.on_next(current)

    def on_dislike_clicked(_):
        current = state.current.value
        if not current:
            return
        current.is_disliked.on_next(not current.is_disliked.value)
        if current.is_disliked.value and current.is_liked.value:
            current.is_liked.on_next(False)
        state.current.on_next(current)

    def update_song_info_sensitivity(s: PlayState) -> None:
        for btn in (dislike_btn, like_btn, more_btn):
            btn.set_sensitive(s != PlayState.EMPTY)

    state.state.subscribe(update_song_info_sensitivity)

    return center_clamp


def SystemControls(
    state: PlayerState,
    show_now_playing: BehaviorSubject[bool],
) -> Gtk.Widget:
    right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    right_box.set_valign(Gtk.Align.CENTER)
    right_box.set_margin_end(16)

    vol_btn = Gtk.MenuButton(icon_name="audio-volume-high-symbolic")
    vol_btn.add_css_class("flat")

    vol_popover = Gtk.Popover()
    vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.VERTICAL, 0.0, 1.0, 0.01)
    vol_scale.set_inverted(True)
    vol_scale.set_size_request(-1, 150)
    vol_scale.set_draw_value(False)

    vol_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    vol_box.set_margin_top(4)
    vol_box.set_margin_bottom(4)
    vol_box.set_margin_start(0)
    vol_box.set_margin_end(0)
    vol_box.append(vol_scale)

    vol_popover.set_child(vol_box)
    vol_btn.set_popover(vol_popover)

    repeat_btn = Gtk.Button(icon_name="media-playlist-repeat-symbolic")
    repeat_btn.add_css_class("flat")

    shuffle_btn = Gtk.Button(icon_name="media-playlist-shuffle-symbolic")
    shuffle_btn.add_css_class("flat")

    expand_btn = Gtk.Button(icon_name="pan-up-symbolic")
    expand_btn.add_css_class("flat")

    show_now_playing.subscribe(
        lambda val: expand_btn.set_icon_name(
            "pan-down-symbolic" if val else "pan-up-symbolic"
        )
    )

    expand_btn.connect(
        "clicked",
        lambda *_: show_now_playing.on_next(not show_now_playing.value),
    )

    right_box.append(vol_btn)
    right_box.append(repeat_btn)
    right_box.append(shuffle_btn)
    right_box.append(expand_btn)

    def on_vol_state_changed(vol: float):
        if abs(vol_scale.get_value() - vol) > 0.001:
            vol_scale.set_value(vol)

        if vol == 0:
            vol_btn.set_icon_name("audio-volume-muted-symbolic")
        elif vol < 0.33:
            vol_btn.set_icon_name("audio-volume-low-symbolic")
        elif vol < 0.66:
            vol_btn.set_icon_name("audio-volume-medium-symbolic")
        else:
            vol_btn.set_icon_name("audio-volume-high-symbolic")

    state.stream.volume.subscribe(on_vol_state_changed)

    def on_vol_scale_changed(scale: Gtk.Scale):
        val = scale.get_value()
        if abs(state.stream.volume.value - val) > 0.001:
            state.stream.volume.on_next(val)

    vol_scale.connect("value-changed", on_vol_scale_changed)

    state.repeat_on.subscribe(
        lambda val: toggle_css(repeat_btn, "suggested-action", val)
    )
    repeat_btn.connect(
        "clicked", lambda _: state.repeat_on.on_next(not state.repeat_on.value)
    )

    state.shuffle_on.subscribe(
        lambda val: toggle_css(shuffle_btn, "suggested-action", val)
    )
    shuffle_btn.connect(
        "clicked", lambda _: state.shuffle_on.on_next(not state.shuffle_on.value)
    )

    def update_system_sensitivity(s: PlayState) -> None:
        for btn in (vol_btn, repeat_btn, shuffle_btn, expand_btn):
            btn.set_sensitive(s != PlayState.EMPTY)

    state.state.subscribe(update_system_sensitivity)

    return right_box


def PlayBar(
    state: PlayerState,
    show_now_playing: BehaviorSubject[bool],
) -> Gtk.Widget:
    """
    A GStreamer-powered play bar built using functional components.
    """
    # Main PlayBar vertical Box
    play_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    play_bar.set_size_request(-1, 100)
    play_bar.add_css_class("background")

    # Add components
    play_bar.append(ProgressBar(state))

    action_area = Gtk.CenterBox()
    action_area.set_margin_start(8)
    action_area.set_margin_end(8)
    action_area.set_margin_bottom(8)
    play_bar.append(action_area)

    action_area.set_start_widget(PlayControls(state))
    action_area.set_center_widget(SongInfo(state))
    action_area.set_end_widget(SystemControls(state, show_now_playing))

    return play_bar
