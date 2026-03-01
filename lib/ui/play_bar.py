from typing import Optional
import pathlib
import logging
from dataclasses import dataclass, field
from gi.repository import Gtk, GLib, Adw, Pango, Gst
from reactivex.subject import BehaviorSubject
from reactivex import combine_latest


# ----------------------------------------------------
# STATE MODEL
# ----------------------------------------------------
@dataclass
class PlayerState:
    """Holds all reactive state for the PlayBar."""

    playing: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )

    # Track Info
    title: BehaviorSubject[str] = field(
        default_factory=lambda: BehaviorSubject(
            "サイエンス - Science (feat. KASANE TETO)"
        )
    )
    subtitle: BehaviorSubject[str] = field(
        default_factory=lambda: BehaviorSubject("MIMI • Science • 2024")
    )
    album_art: BehaviorSubject[str] = field(
        default_factory=lambda: BehaviorSubject("audio-x-generic-symbolic")
    )

    # Timing (Changed to integers for nanoseconds)
    current_time: BehaviorSubject[int] = field(
        default_factory=lambda: BehaviorSubject(0)
    )
    total_time: BehaviorSubject[int] = field(default_factory=lambda: BehaviorSubject(0))

    # Actions & System
    is_liked: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )
    is_disliked: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )
    shuffle_on: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )
    repeat_on: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )

    audio_file: BehaviorSubject[Optional[pathlib.Path]] = field(
        default_factory=lambda: BehaviorSubject[Optional[pathlib.Path]](None)
    )


def PlayBar(state: PlayerState = PlayerState()) -> Gtk.ActionBar:
    """
    A GStreamer-powered play bar with reactive bindings to the PlayerState.
    """
    # Ensure GStreamer is initialized (usually done at app startup)
    if not Gst.is_initialized():
        Gst.init(None)
    # Create a GStream-based play bar with reactive bindings to the PlayerState.
    _player = Gst.ElementFactory.make("playbin", "player")
    if not _player:
        logging.error("Failed to create GStreamer playbin element.")
        raise RuntimeError("GStreamer initialization failed")
    player = _player  # Type hint hack
    flags = player.get_property("flags")
    # Disable video output since this is an audio player
    flags &= ~(1 << 0)
    player.set_property("flags", flags)

    play_bar = Gtk.ActionBar()
    play_bar.set_size_request(-1, 80)

    # --- Helper to toggle GTK CSS classes reactively ---
    def toggle_css(widget: Gtk.Widget, class_name: str, active: bool):
        if active:
            widget.add_css_class(class_name)
        else:
            widget.remove_css_class(class_name)

    # --- Time Formatting Helper ---
    def format_time(ns: int) -> str:
        if ns <= 0:
            return "0:00"
        seconds = ns // 1_000_000_000
        m = seconds // 60
        s = seconds % 60
        return f"{m}:{s:02d}"

    def on_audio_file_changed(file_path: Optional[pathlib.Path]):
        if file_path:
            player.set_state(Gst.State.READY)
            player.set_property("uri", file_path.as_uri())
            if state.playing.value:
                player.set_state(Gst.State.PLAYING)
        else:
            player.set_state(Gst.State.NULL)

    state.audio_file.subscribe(on_audio_file_changed)

    def on_playing_changed(is_playing: bool):
        if not state.audio_file.value:
            return
        player.set_state(Gst.State.PLAYING if is_playing else Gst.State.PAUSED)

    state.playing.subscribe(on_playing_changed)

    def update_time_state():
        if state.playing.value:
            # Query position
            success_pos, pos = player.query_position(Gst.Format.TIME)
            if success_pos:
                state.current_time.on_next(pos)

            # Query total duration (only really changes on load, but safe to check)
            success_dur, dur = player.query_duration(Gst.Format.TIME)
            if success_dur:
                state.total_time.on_next(dur)
        return True  # Return True to keep the timeout alive

    # Poll every 500ms
    GLib.timeout_add(500, update_time_state)
    bus = player.get_bus()
    if not bus:
        logging.error("Failed to get GStreamer bus.")
        raise RuntimeError("GStreamer bus initialization failed")
    bus.add_signal_watch()

    def on_bus_message(bus, message):
        if message.type == Gst.MessageType.EOS:
            # Stop playing, reset time to 0, and rewind GStreamer
            state.playing.on_next(False)
            state.current_time.on_next(0)
            player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logging.error(f"GStreamer Error: {err}, {debug}")
            state.playing.on_next(False)

    bus.connect("message", on_bus_message)
    # ----------------------------------------------------
    # 1. PLAY CONTROLS (Left)
    # ----------------------------------------------------
    controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    controls_box.set_valign(Gtk.Align.CENTER)
    controls_box.set_margin_start(16)

    prev_btn = Gtk.Button(icon_name="media-skip-backward-symbolic")
    prev_btn.add_css_class("flat")

    play_icon = Gtk.Image()
    play_icon.set_pixel_size(32)

    play_pause_btn = Gtk.Button()
    play_pause_btn.set_child(play_icon)
    play_pause_btn.add_css_class("flat")
    play_pause_btn.add_css_class("suggested-action")
    play_pause_btn.set_size_request(48, 48)

    next_btn = Gtk.Button(icon_name="media-skip-forward-symbolic")
    next_btn.add_css_class("flat")

    time_label = Gtk.Label()
    time_label.add_css_class("dim-label")
    time_label.set_margin_start(8)

    # -> Reactive Bindings: Play Controls
    state.playing.subscribe(
        lambda is_playing: play_icon.set_from_icon_name(
            "media-playback-pause-symbolic"
            if is_playing
            else "media-playback-start-symbolic"
        )
    )
    play_pause_btn.connect(
        "clicked", lambda _: state.playing.on_next(not state.playing.value)
    )

    # Combine current and total time streams to update the label
    combine_latest(state.current_time, state.total_time).subscribe(
        lambda times: time_label.set_text(
            f"{format_time(times[0])} / {format_time(times[1])}"
        )
    )

    controls_box.append(prev_btn)
    controls_box.append(play_pause_btn)
    controls_box.append(next_btn)
    controls_box.append(time_label)
    play_bar.pack_start(controls_box)

    # ----------------------------------------------------
    # 2. SONG INFO & ACTIONS (Center)
    # ----------------------------------------------------
    center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    center_box.set_valign(Gtk.Align.CENTER)

    # album art display widget. we keep Gtk.Image for easy icon handling
    album_art = Gtk.Image()
    album_art.set_pixel_size(48)

    text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    text_vbox.set_valign(Gtk.Align.CENTER)

    title_label = Gtk.Label()
    title_label.set_halign(Gtk.Align.START)
    title_label.set_ellipsize(Pango.EllipsizeMode.END)

    subtitle_label = Gtk.Label()
    subtitle_label.set_halign(Gtk.Align.START)
    subtitle_label.set_ellipsize(Pango.EllipsizeMode.END)
    subtitle_label.add_css_class("dim-label")

    text_vbox.append(title_label)
    text_vbox.append(subtitle_label)

    actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    actions_box.set_valign(Gtk.Align.CENTER)
    actions_box.set_margin_start(16)

    dislike_btn = Gtk.Button(icon_name="face-sad-symbolic")
    dislike_btn.add_css_class("flat")
    like_btn = Gtk.Button(icon_name="face-smile-symbolic")
    like_btn.add_css_class("flat")
    more_btn = Gtk.Button(icon_name="view-more-symbolic")
    more_btn.add_css_class("flat")

    actions_box.append(dislike_btn)
    actions_box.append(like_btn)
    actions_box.append(more_btn)

    center_box.append(album_art)
    center_box.append(text_vbox)
    center_box.append(actions_box)
    play_bar.set_center_widget(center_box)

    # -> Reactive Bindings: Song Info & Actions
    # album_art may be an icon name (string) or a URL to fetch; handle both.
    def _on_album_art_change(value):
        if not value:
            return
        if isinstance(value, str) and value.startswith("http"):
            from utils import load_image_async

            load_image_async(album_art, value)
        else:
            album_art.set_from_icon_name(value)

    state.album_art.subscribe(_on_album_art_change)

    # Safely escape text before applying markup
    state.title.subscribe(
        lambda t: title_label.set_markup(f"<b>{GLib.markup_escape_text(t)}</b>")
    )
    state.subtitle.subscribe(lambda st: subtitle_label.set_text(st))

    # Toggle highlight on Like/Dislike (Using Adwaita's 'suggested-action' and 'error' classes)
    state.is_liked.subscribe(lambda val: toggle_css(like_btn, "suggested-action", val))
    like_btn.connect(
        "clicked", lambda _: state.is_liked.on_next(not state.is_liked.value)
    )

    state.is_disliked.subscribe(lambda val: toggle_css(dislike_btn, "error", val))
    dislike_btn.connect(
        "clicked", lambda _: state.is_disliked.on_next(not state.is_disliked.value)
    )

    # ----------------------------------------------------
    # 3. SYSTEM CONTROLS (Right)
    # ----------------------------------------------------
    right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    right_box.set_valign(Gtk.Align.CENTER)
    right_box.set_margin_end(16)

    vol_btn = Gtk.Button(icon_name="audio-volume-high-symbolic")
    vol_btn.add_css_class("flat")

    repeat_btn = Gtk.Button(icon_name="media-playlist-repeat-symbolic")
    repeat_btn.add_css_class("flat")

    shuffle_btn = Gtk.Button(icon_name="media-playlist-shuffle-symbolic")
    shuffle_btn.add_css_class("flat")

    expand_btn = Gtk.Button(icon_name="pan-up-symbolic")
    expand_btn.add_css_class("flat")

    right_box.append(vol_btn)
    right_box.append(repeat_btn)
    right_box.append(shuffle_btn)
    right_box.append(expand_btn)
    play_bar.pack_end(right_box)

    # -> Reactive Bindings: System Controls
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

    return play_bar
