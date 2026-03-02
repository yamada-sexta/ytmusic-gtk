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

from lib.sys.MPRISController import MPRISController


# Enum for the player state
class PlayState(enum.Enum):
    EMPTY = 0
    PLAYING = 1
    PAUSED = 2
    LOADING = 3


# CurrentMusic is a Protocol
class CurrentMusic(Protocol):
    id: BehaviorSubject[str]
    audio_file: BehaviorSubject[pathlib.Path]

    title: BehaviorSubject[Optional[str]]
    artist: BehaviorSubject[Optional[str]]
    album_name: BehaviorSubject[Optional[str]]
    year: BehaviorSubject[Optional[str]]
    album_art: BehaviorSubject[Optional[str]]

    current_time: BehaviorSubject[int]
    total_time: BehaviorSubject[int]
    is_liked: BehaviorSubject[bool]
    is_disliked: BehaviorSubject[bool]
    seek_request: Subject[int]


@dataclass
class CurrentMusicState:
    id: BehaviorSubject[Optional[str]] = field(
        default_factory=lambda: BehaviorSubject[Optional[str]](None)
    )

    # Track Info
    title: BehaviorSubject[str] = field(
        default_factory=lambda: BehaviorSubject(
            "Nothing is playing. Click a song to get started!"
        )
    )
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

    is_liked: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )
    is_disliked: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )

    audio_file: BehaviorSubject[Optional[pathlib.Path]] = field(
        default_factory=lambda: BehaviorSubject[Optional[pathlib.Path]](None)
    )

    seek_request: Subject[int] = field(default_factory=Subject)


@dataclass
class PlayerState:
    """Holds all reactive state and playing logic for the app."""

    state: BehaviorSubject[PlayState] = field(
        default_factory=lambda: BehaviorSubject(PlayState.EMPTY)
    )

    current_song: CurrentMusicState = field(default_factory=CurrentMusicState)

    # Actions & System
    volume: BehaviorSubject[float] = field(default_factory=lambda: BehaviorSubject(1.0))
    shuffle_on: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )
    repeat_on: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )


def setup_player(state: PlayerState) -> tuple[Gst.Element, MPRISController]:
    """
    Initializes the GStreamer player and MPRIS controller, binding them to
    the given PlayerState via functional reactive streams.
    """
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

    mpris_controller = MPRISController(state)

    def on_audio_file_changed(file_path: pathlib.Path | None) -> None:
        if file_path:
            player.set_state(Gst.State.READY)
            player.set_property("uri", file_path.as_uri())
            if state.state.value == PlayState.PLAYING:
                player.set_state(Gst.State.PLAYING)
        else:
            player.set_state(Gst.State.NULL)

    state.current_song.pipe(
        ops.map(lambda s: s.audio_file if s else None), ops.distinct_until_changed()
    ).subscribe(on_audio_file_changed)

    def on_state_changed(s: PlayState) -> None:
        has_audio = state.current_song.value and state.current_song.value.audio_file
        if not has_audio:
            if s == PlayState.EMPTY:
                player.set_state(Gst.State.NULL)
                state.current_time.on_next(0)
                state.total_time.on_next(0)
            return

        if s == PlayState.PLAYING:
            player.set_state(Gst.State.PLAYING)
        elif s == PlayState.PAUSED or s == PlayState.LOADING:
            player.set_state(Gst.State.PAUSED)
            if s == PlayState.LOADING:
                state.current_time.on_next(0)
                state.total_time.on_next(0)
        elif s == PlayState.EMPTY:
            player.set_state(Gst.State.NULL)
            state.current_time.on_next(0)
            state.total_time.on_next(0)

    state.state.subscribe(on_state_changed)

    def on_volume_changed(vol: float) -> None:
        player.set_property("volume", vol)

    state.volume.subscribe(on_volume_changed)

    def update_time_state() -> bool:
        if state.state.value == PlayState.PLAYING:
            # Query position
            success_pos, pos = player.query_position(Gst.Format.TIME)
            if success_pos:
                state.current_time.on_next(pos)

            # Query total duration
            success_dur, dur = player.query_duration(Gst.Format.TIME)
            if success_dur:
                state.total_time.on_next(dur)
        return True  # Keep timeout alive

    GLib.timeout_add(500, update_time_state)

    bus = player.get_bus()
    if not bus:
        logging.error("Failed to get GStreamer bus.")
        raise RuntimeError("GStreamer bus initialization failed")
    bus.add_signal_watch()

    def on_bus_message(bus: Gst.Bus, message: Gst.Message) -> None:
        if message.type == Gst.MessageType.EOS:
            state.state.on_next(PlayState.PAUSED)
            state.current_time.on_next(0)
            player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logging.error(f"GStreamer Error: {err}, {debug}")
            state.state.on_next(PlayState.PAUSED)

    bus.connect("message", on_bus_message)

    def on_seek_request(position_ns: int) -> None:
        player.seek_simple(
            Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, position_ns
        )
        state.current_time.on_next(position_ns)

    state.seek_request.subscribe(on_seek_request)

    return player, mpris_controller
