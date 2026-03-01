from lib.MPRISController import MPRISController
from typing import Optional
import pathlib
import logging
from dataclasses import dataclass, field
from gi.repository import Gtk, GLib, Adw, Pango, Gst
from reactivex.subject import BehaviorSubject
from reactivex import combine_latest


@dataclass
class PlayerState:
    """Holds all reactive state for the PlayBar."""

    playing: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )

    # Track Info
    title: BehaviorSubject[str] = field(
        default_factory=lambda: BehaviorSubject(
            "Nothing is playing. Click a song to get started!"
        )
    )
    # subtitle: BehaviorSubject[str] = field(
    #     default_factory=lambda: BehaviorSubject("MIMI • Science • 2024")
    # )
    artist: BehaviorSubject[str] = field(default_factory=lambda: BehaviorSubject(""))
    album_name: BehaviorSubject[str] = field(
        default_factory=lambda: BehaviorSubject("")
    )
    year: BehaviorSubject[str] = field(default_factory=lambda: BehaviorSubject(""))
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


def PlayBar(state: PlayerState = PlayerState()) -> Gtk.Widget:
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

    mpris_controller = MPRISController(state)

    # Rebuilding the PlayBar as a vertical Box to hold the progress bar on top
    play_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    play_bar.set_size_request(-1, 100)
    # Adding background class so it visually looks like a cohesive action bar
    play_bar.add_css_class("background")

    # --- PROGRESS BAR SETUP (Top) ---
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

    combine_latest(state.current_time, state.total_time).subscribe(update_progress_ui)

    def on_scale_changed(scale: Gtk.Scale) -> None:
        if is_updating_scale:
            return

        val_seconds = scale.get_value()
        new_pos_ns = int(val_seconds * 1e9)
        player.seek_simple(
            Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, new_pos_ns
        )
        state.current_time.on_next(new_pos_ns)

    progress_scale.connect("value-changed", on_scale_changed)
    play_bar.append(progress_scale)

    # --- ACTION AREA SETUP (Bottom) ---
    # CenterBox replaces ActionBar's layout capabilities to hold Left/Center/Right controls
    action_area = Gtk.CenterBox()
    action_area.set_margin_start(8)
    action_area.set_margin_end(8)
    action_area.set_margin_bottom(8)
    play_bar.append(action_area)

    # --- Helper to toggle GTK CSS classes reactively ---
    def toggle_css(widget: Gtk.Widget, class_name: str, active: bool) -> None:
        if active:
            widget.add_css_class(class_name)
        else:
            widget.remove_css_class(class_name)

    # --- Time Formatting Helper ---
    def format_time(ns: int) -> str:
        if ns == 0:
            return "0:00"
        if ns < 0:
            return "N/A"
        seconds = ns // 1_000_000_000
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"

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

    def on_bus_message(bus: Gst.Bus, message: Gst.Message):
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

    # Pack into our new CenterBox
    action_area.set_start_widget(controls_box)

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

    # Pack into our new CenterBox
    action_area.set_center_widget(center_box)

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
    # state.subtitle.subscribe(lambda st: subtitle_label.set_text(st))
    # Combine artist, album, and year into a single subtitle line
    combine_latest(state.artist, state.album_name, state.year).subscribe(
        lambda info: subtitle_label.set_text(
            " • ".join(filter(None, info))  # Join non-empty parts with bullets
        )
    )

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

    # Pack into our new CenterBox
    action_area.set_end_widget(right_box)

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
