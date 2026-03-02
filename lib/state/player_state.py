import pathlib
from typing import Protocol
import enum
import logging
import pathlib
from dataclasses import dataclass, field, replace
from typing import Optional

from gi.repository import GLib, Gst
from reactivex.subject import BehaviorSubject, Subject
from reactivex import operators as ops


# Enum for the player state
class PlayState(enum.Enum):
    EMPTY = 0
    PLAYING = 1
    PAUSED = 2
    LOADING = 3


@dataclass
class CurrentMusic:
    id: str
    audio_file: pathlib.Path

    title: Optional[str] = field(default=None)
    artist: Optional[str] = field(default=None)
    album_name: Optional[str] = field(default=None)
    year: Optional[str] = field(default=None)
    album_art: Optional[str] = field(default=None)
    is_liked: bool = field(default=False)
    is_disliked: bool = field(default=False)


@dataclass
class StreamStatus:
    current_time: BehaviorSubject[int] = field(
        default_factory=lambda: BehaviorSubject(0)
    )

    total_time: BehaviorSubject[int] = field(default_factory=lambda: BehaviorSubject(0))
    volume: BehaviorSubject[float] = field(default_factory=lambda: BehaviorSubject(1.0))
    seek_request: Subject[int] = field(default_factory=Subject)


@dataclass
class PlayerState:
    """Holds all reactive state and playing logic for the app."""

    state: BehaviorSubject[PlayState] = field(
        default_factory=lambda: BehaviorSubject(PlayState.EMPTY)
    )

    current: BehaviorSubject[Optional[CurrentMusic]] = field(
        default_factory=lambda: BehaviorSubject[Optional[CurrentMusic]](None)
    )

    stream: StreamStatus = field(default_factory=StreamStatus)

    # Actions & System
    # volume: BehaviorSubject[float] = field(default_factory=lambda: BehaviorSubject(1.0))
    shuffle_on: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )
    repeat_on: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )


def setup_player(state: PlayerState) -> Gst.Element:
    """
    Initializes the GStreamer player and MPRIS controller, binding them to
    the given PlayerState via functional reactive streams.
    """
    from lib.sys.mpris import setup_mpris_controller

    if not Gst.is_initialized():
        Gst.init(None)

    import typing

    player = typing.cast(Gst.Element, Gst.ElementFactory.make("playbin", "player"))
    if not player:
        logging.error("Failed to create GStreamer playbin element.")
        raise RuntimeError("GStreamer initialization failed")

    flags = player.get_property("flags")
    # Disable video output since this is an audio player
    flags &= ~(1 << 0)
    player.set_property("flags", flags)

    def on_audio_file_changed(file_path: pathlib.Path | None) -> None:
        if file_path:
            player.set_state(Gst.State.READY)
            player.set_property("uri", file_path.as_uri())
            if state.state.value == PlayState.PLAYING:
                player.set_state(Gst.State.PLAYING)
        else:
            player.set_state(Gst.State.NULL)

    state.current.pipe(
        ops.map(lambda s: s.audio_file if s else None), ops.distinct_until_changed()
    ).subscribe(on_audio_file_changed)

    def on_state_changed(s: PlayState) -> None:
        has_audio = state.current.value and state.current.value.audio_file
        if not has_audio:
            if s == PlayState.EMPTY:
                player.set_state(Gst.State.NULL)
                state.current.on_next(None)
            return

        if s == PlayState.PLAYING:
            player.set_state(Gst.State.PLAYING)
        elif s == PlayState.PAUSED or s == PlayState.LOADING:
            player.set_state(Gst.State.PAUSED)
            if s == PlayState.LOADING and state.current.value:
                # Reset time to 0 when loading new track
                state.stream.current_time.on_next(0)

        elif s == PlayState.EMPTY:
            player.set_state(Gst.State.NULL)
            state.current.on_next(None)

    state.state.subscribe(on_state_changed)

    def on_volume_changed(vol: float) -> None:
        player.set_property("volume", vol)

    state.stream.volume.subscribe(on_volume_changed)

    def update_time_state() -> bool:
        # Only update time if we're currently playing, to avoid unnecessary queries when paused
        if not state.current.value:
            return True  # Keep timeout alive
        if state.state.value == PlayState.PLAYING:
            # Query position
            success_pos, pos = player.query_position(Gst.Format.TIME)
            if success_pos:
                state.stream.current_time.on_next(pos)

            # Query total duration
            success_dur, dur = player.query_duration(Gst.Format.TIME)
            if success_dur:
                state.stream.total_time.on_next(dur)
        return True  # Keep timeout alive

    GLib.timeout_add(500, update_time_state)

    bus = player.get_bus()
    if not bus:
        logging.error("Failed to get GStreamer bus.")
        raise RuntimeError("GStreamer bus initialization failed")
    bus.add_signal_watch()

    def on_bus_message(bus: Gst.Bus, message: Gst.Message) -> None:
        # If current is None, we have no track loaded, so ignore messages
        if not state.current.value:
            return
        if message.type == Gst.MessageType.EOS:
            state.state.on_next(PlayState.PAUSED)
            # state.current_time.on_next(0)
            state.stream.current_time.on_next(0)
            player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logging.error(f"GStreamer Error: {err}, {debug}")
            state.state.on_next(PlayState.PAUSED)

    bus.connect("message", on_bus_message)

    def on_seek_request(position_ns: int) -> None:
        if not state.current.value:
            return
        player.seek_simple(
            Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, position_ns
        )
        state.stream.current_time.on_next(position_ns)

    def on_current(current: Optional[CurrentMusic]) -> None:
        if not current:
            return
        state.stream.seek_request.subscribe(on_seek_request)

    # state.seek_request.subscribe(on_seek_request)
    state.current.subscribe(on_current)

    setup_mpris_controller(state)

    return player
