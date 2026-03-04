from lib.state.player_state import RepeatMode
import logging
import ytmusicapi
from lib.ui.thumbnail import ThumbnailWidgetFromUrl
from lib.state.player_state import LikeStatus
from lib.state.player_state import MediaStatus
from reactivex.subject import BehaviorSubject
from lib.ui.helpers import toggle_css
from lib.ui.helpers import toggle_icon
from lib.ui.helpers import format_time
from lib.state.player_state import PlayState
from typing import Optional
from gi.repository import Gtk, GLib, Adw, Pango, Gst, Gio, Gdk
from reactivex import combine_latest
from lib.state.player_state import PlayerState, play_next, play_previous


def PlayerProgressBar(
    state: PlayerState,
) -> Gtk.Widget:
    progress_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.01)
    progress_scale.set_draw_value(False)
    progress_scale.set_hexpand(True)
    progress_scale.set_margin_top(0)
    progress_scale.set_margin_bottom(0)
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

    combine_latest(state.stream.current_time, state.stream.total_time).subscribe(
        update_progress_ui
    )

    def on_scale_changed(scale: Gtk.Scale) -> None:
        if is_updating_scale or not state.current_item:
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

    play_spinner = Adw.Spinner()
    play_spinner.set_size_request(24, 24)

    play_stack = Gtk.Stack()
    play_stack.add_named(play_icon, "icon")
    play_stack.add_named(play_spinner, "spinner")

    play_pause_btn = Gtk.Button()
    play_pause_btn.set_child(play_stack)
    play_pause_btn.add_css_class("circular")
    play_pause_btn.add_css_class("flat")
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
    prev_btn.connect("clicked", lambda _: play_previous(state))
    next_btn.connect("clicked", lambda _: play_next(state))

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

    # Derive a URL stream from the current-track observable and feed it into
    # ThumbnailWidgetFromUrl — the widget handles all spinner / load / fallback logic
    from reactivex import operators as ops

    album_art_url_stream = state.current.pipe(
        ops.map(lambda c: c.album_art if c else None),
    )
    thumbnail_widget = ThumbnailWidgetFromUrl(album_art_url_stream)
    # Set the size to 48x48 to minimum
    thumbnail_widget.set_size_request(48, 48)

    # Two nested Adw.Clamp widgets clamp the thumbnail to 48×48px in both
    # dimensions. Adw.Clamp supports orientation, so one horizontal + one vertical
    # clamp together act as a true 2-D maximum-size constraint.
    h_clamp = Adw.Clamp(orientation=Gtk.Orientation.HORIZONTAL)
    h_clamp.set_maximum_size(48)
    h_clamp.set_tightening_threshold(0)
    h_clamp.set_hexpand(False)
    h_clamp.set_halign(Gtk.Align.CENTER)

    v_clamp = Adw.Clamp(orientation=Gtk.Orientation.VERTICAL)
    v_clamp.set_maximum_size(48)
    v_clamp.set_tightening_threshold(0)
    v_clamp.set_vexpand(False)
    v_clamp.set_valign(Gtk.Align.CENTER)
    v_clamp.set_child(thumbnail_widget)

    h_clamp.set_child(v_clamp)

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

    more_popover = Gtk.Popover()
    more_popover.set_has_arrow(True)

    more_menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    # more_menu_box.set_margin_top(4)
    # more_menu_box.set_margin_bottom(4)
    # more_menu_box.set_margin_start(4)
    # more_menu_box.set_margin_end(4)

    open_in_browser_content = Adw.ButtonContent()
    open_in_browser_content.set_icon_name("folder-globe-legacy-symbolic")
    open_in_browser_content.set_label("Open in Browser")

    open_in_browser_btn = Gtk.Button()
    open_in_browser_btn.set_child(open_in_browser_content)
    open_in_browser_btn.add_css_class("flat")

    def on_open_in_browser(_btn: Gtk.Button) -> None:
        current = state.current_item
        if not current:
            return
        more_popover.popdown()
        url = f"https://music.youtube.com/watch?v={current.id}"
        Gtk.show_uri(None, url, Gdk.CURRENT_TIME)

    open_in_browser_btn.connect("clicked", on_open_in_browser)
    more_menu_box.append(open_in_browser_btn)

    more_popover.set_child(more_menu_box)

    more_btn = Gtk.MenuButton(icon_name="view-more-symbolic")
    more_btn.add_css_class("flat")
    more_btn.set_popover(more_popover)

    actions_box.append(dislike_btn)
    actions_box.append(like_btn)
    actions_box.append(more_btn)

    center_box.append(h_clamp)
    center_box.append(text_vbox)
    center_box.append(actions_box)

    center_clamp.set_child(center_box)

    def on_current(current: Optional[MediaStatus]) -> None:
        if not current:
            return
        for btn in (dislike_btn, like_btn, more_btn):
            btn.set_sensitive(current != PlayState.EMPTY)
        current.like_status.subscribe(
            lambda val: toggle_icon(
                like_btn,
                val == "LIKE",
                "thumbs-up-symbolic",
                "thumbs-up-outline-symbolic",
            )
        )
        current.like_status.subscribe(
            lambda val: toggle_icon(
                dislike_btn,
                val == "DISLIKE",
                "thumbs-down-symbolic",
                "thumbs-down-outline-symbolic",
            )
        )
        subtitle_label.set_text(
            " • ".join(filter(None, [current.artist, current.album_name, current.year]))
        )
        title_label.set_markup(f"<b>{GLib.markup_escape_text(current.title or '')}</b>")

    state.current.subscribe(on_current)

    def _rate_song_remote(
        yt: "ytmusicapi.YTMusic", video_id: str, new_status: str
    ) -> None:
        import threading
        from ytmusicapi.models.content.enums import LikeStatus as YTLikeStatus

        yt_status = YTLikeStatus(new_status)

        def do_rate() -> None:
            try:
                yt.rate_song(video_id, yt_status)
                logging.debug(f"Rated {video_id} as {new_status}")
            except Exception as e:
                logging.error(f"Failed to rate song {video_id}: {e}")

        threading.Thread(target=do_rate, daemon=True).start()

    def on_like_clicked(_) -> None:
        current = state.current_item
        if not current:
            return

        new_status: LikeStatus = (
            "INDIFFERENT" if current.like_status.value == "LIKE" else "LIKE"
        )
        current.like_status.on_next(new_status)

        yt = state.client
        # if yt:
        #     _rate_song_remote(yt, current.id, new_status)
        yt.rate_song(current.id, new_status)

    def on_dislike_clicked(_) -> None:
        current = state.current_item
        if not current:
            return

        new_status: LikeStatus = (
            "INDIFFERENT" if current.like_status.value == "DISLIKE" else "DISLIKE"
        )
        current.like_status.on_next(new_status)

        yt = state.client
        # if yt:
        #     _rate_song_remote(yt, current.id, new_status)
        yt.rate_song(current.id, new_status)

    like_btn.connect("clicked", on_like_clicked)
    dislike_btn.connect("clicked", on_dislike_clicked)

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

    repeat_btn = Gtk.Button(icon_name="media-playlist-consecutive-symbolic")
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

    def on_repeat_changed(val: RepeatMode) -> None:
        # toggle_icon(
        #     repeat_btn,
        #     val == RepeatMode.ALL,
        #     "media-playlist-repeat-symbolic",
        #     "media-playlist-consecutive-symbolic",
        # )
        if val == RepeatMode.OFF:
            repeat_btn.set_icon_name("media-playlist-consecutive-symbolic")
        elif val == RepeatMode.ALL:
            repeat_btn.set_icon_name("media-playlist-repeat-symbolic")
        elif val == RepeatMode.ONE:
            repeat_btn.set_icon_name("media-playlist-repeat-song-symbolic")
        # toggle_css(repeat_btn, "suggested-action", val)

    state.repeat_mode.subscribe(on_repeat_changed)
    repeat_btn.connect(
        "clicked",
        lambda _: state.repeat_mode.on_next(
            RepeatMode((state.repeat_mode.value.value + 1) % 3)
        ),
    )

    def on_shuffle_changed(val: bool) -> None:
        toggle_css(shuffle_btn, "suggested-action", val)
        shuffle_btn.set_opacity(1.0 if val else 0.4)

    state.shuffle_on.subscribe(on_shuffle_changed)
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
    play_bar.append(PlayerProgressBar(state))

    action_area = Gtk.CenterBox()
    action_area.set_margin_start(8)
    action_area.set_margin_end(8)
    action_area.set_margin_bottom(8)
    play_bar.append(action_area)

    action_area.set_start_widget(PlayControls(state))
    action_area.set_center_widget(SongInfo(state))
    action_area.set_end_widget(SystemControls(state, show_now_playing))

    return play_bar
