from lib.data import SongDetail
import logging
from lib.data import AlbumData
from lib.net.client import LocalAudio
from lib.data import LikeStatus
from lib.net.client import YTClient
from typing import Any
from lib.data import WatchPlaylist
from reactivex import combine_latest
import pathlib
import enum
import logging
import pathlib
from dataclasses import dataclass, field, replace
from typing import Optional

from gi.repository import GLib, Gst, GstApp
from reactivex.subject import BehaviorSubject, Subject
from reactivex import operators as ops
import reactivex as rx


# Enum for the player state
class PlayState(enum.Enum):
    EMPTY = 0
    PLAYING = 1
    PAUSED = 2
    LOADING = 3


class RepeatMode(enum.Enum):
    OFF = 0
    ALL = 1
    ONE = 2


@dataclass
class MediaStatus:
    id: str
    # URL of the song
    url: Optional[str] = field(default=None)
    audio_file: BehaviorSubject[Optional[pathlib.Path]] = field(
        default_factory=lambda: BehaviorSubject[Optional[pathlib.Path]](None)
    )
    is_placeholder_music: bool = field(default=False)

    title: Optional[str] = field(default=None)
    artist: Optional[str] = field(default=None)
    album_name: Optional[str] = field(default=None)
    year: Optional[str] = field(default=None)
    album_art: Optional[str] = field(default=None)
    like_status: BehaviorSubject[LikeStatus] = field(
        default_factory=lambda: BehaviorSubject[LikeStatus]("INDIFFERENT")
    )
    bytes: BehaviorSubject[Optional[bytes]] = field(
        default_factory=lambda: BehaviorSubject[Optional[bytes]](None)
    )

    song: Optional[SongDetail] = field(default=None)


@dataclass
class StreamStatus:
    current_time: BehaviorSubject[int] = field(
        default_factory=lambda: BehaviorSubject(0)
    )

    total_time: BehaviorSubject[int] = field(default_factory=lambda: BehaviorSubject(0))
    volume: BehaviorSubject[float] = field(default_factory=lambda: BehaviorSubject(1.0))
    seek_request: Subject[int] = field(default_factory=Subject)


@dataclass
class CurrentPlaylist:
    media: BehaviorSubject[list[MediaStatus]] = field(
        default_factory=lambda: BehaviorSubject([])
    )
    playlist_id: BehaviorSubject[Optional[str]] = field(
        default_factory=lambda: BehaviorSubject[Optional[str]](None)
    )
    index: BehaviorSubject[int] = field(default_factory=lambda: BehaviorSubject(0))
    name: BehaviorSubject[Optional[str]] = field(
        default_factory=lambda: BehaviorSubject[Optional[str]](None)
    )


@dataclass
class PlayerState:
    """Holds all reactive state and playing logic for the app."""

    client: YTClient
    state: BehaviorSubject[PlayState] = field(
        default_factory=lambda: BehaviorSubject(PlayState.EMPTY)
    )

    stream: StreamStatus = field(default_factory=StreamStatus)

    # Actions & System
    # volume: BehaviorSubject[float] = field(default_factory=lambda: BehaviorSubject(1.0))
    shuffle_on: BehaviorSubject[bool] = field(
        default_factory=lambda: BehaviorSubject(False)
    )
    repeat_mode: BehaviorSubject[RepeatMode] = field(
        default_factory=lambda: BehaviorSubject(RepeatMode.OFF)
    )

    playlist: CurrentPlaylist = field(default_factory=CurrentPlaylist)

    @property
    def current(self) -> "rx.Observable[Optional[MediaStatus]]":
        return combine_latest(self.playlist.media, self.playlist.index).pipe(
            ops.map(lambda x: x[0][x[1]] if 0 <= x[1] < len(x[0]) else None),
            ops.distinct_until_changed(),
        )

    @property
    def current_item(self) -> Optional[MediaStatus]:
        media_list = self.playlist.media.value
        idx = self.playlist.index.value
        if 0 <= idx < len(media_list):
            return media_list[idx]
        return None


def play_watch_playlist(
    state: PlayerState,
    video_id: Optional[str] = None,
    playlist_id: Optional[str] = None,
    placeholder_music: Optional[MediaStatus] = None,
    playlist_title: Optional[str] = None,
) -> None:
    client = state.client

    # If there is no video_id nor playlist_id, we can't play anything
    if not video_id and not playlist_id:
        logging.warning("No video_id nor playlist_id provided.")
        return
    logging.info(f"Playing song with playlist: {playlist_id} {video_id}")

    state.state.on_next(PlayState.LOADING)
    if placeholder_music:
        logging.info("Playing placeholder music")
        placeholder_music.is_placeholder_music = True
        state.playlist.media.on_next([placeholder_music])
        state.playlist.index.on_next(0)
        state.playlist.playlist_id.on_next(playlist_id)
        state.playlist.name.on_next(playlist_title)
    else:
        state.playlist.media.on_next([])
        state.playlist.index.on_next(0)
        state.playlist.playlist_id.on_next(playlist_id)
        state.playlist.name.on_next(playlist_title)

    playlist = client.get_watch_playlist(playlist_id=playlist_id, video_id=video_id)
    # try to get playlist title
    if playlist_id:

        def on_playlist(data: Optional[tuple[AlbumData, dict]]):
            if data is None:
                return
            logging.info("Got playlist title")
            album_data, _ = data
            state.playlist.name.on_next(album_data.title)
            state.playlist.playlist_id.on_next(playlist_id)

        client.get_playlist(playlist_id).subscribe(
            on_next=on_playlist,
            on_error=lambda e: logging.error(f"Could not get playlist title: {e}"),
        )

    def on_playlist(data: Optional[tuple[WatchPlaylist, dict]]):
        if data is None:
            return
        watch_playlist, _ = data

        media_list: list[MediaStatus] = []
        for track in watch_playlist.tracks:
            id = track.video_id
            if not id:
                continue
            media_list.append(
                MediaStatus(
                    id=id,
                    title=track.title,
                    artist=track.artists[0].name if track.artists else None,
                    album_name=track.album.name if track.album else None,
                    year=track.year,
                    album_art=track.thumbnails[-1].url if track.thumbnails else None,
                    like_status=(
                        BehaviorSubject[LikeStatus](track.like_status)
                        if track.like_status
                        else BehaviorSubject[LikeStatus]("INDIFFERENT")
                    ),
                )
            )
        state.playlist.media.on_next(media_list)
        state.playlist.index.on_next(0)
        state.playlist.playlist_id.on_next(watch_playlist.playlist_id)

    playlist.subscribe(
        on_next=on_playlist,
        on_error=lambda e: logging.error(f"Could not fetch or download media: {e}"),
    )


def play_next(state: PlayerState) -> None:
    media_list = state.playlist.media.value
    if not media_list:
        return
    idx = state.playlist.index.value
    if state.shuffle_on.value:
        import random

        next_idx = random.randint(0, len(media_list) - 1)
    else:
        next_idx = idx + 1
        if next_idx >= len(media_list):
            if state.repeat_mode.value == RepeatMode.ALL:
                next_idx = 0
            else:
                state.state.on_next(PlayState.PAUSED)
                state.stream.current_time.on_next(0)
                return
    state.playlist.index.on_next(next_idx)


def play_previous(state: PlayerState) -> None:
    media_list = state.playlist.media.value
    if not media_list:
        return
    idx = state.playlist.index.value
    if state.shuffle_on.value:
        import random

        next_idx = random.randint(0, len(media_list) - 1)
    else:
        next_idx = idx - 1
        if next_idx < 0:
            if state.repeat_mode.value == RepeatMode.ALL:
                next_idx = len(media_list) - 1
            else:
                next_idx = 0
    state.playlist.index.on_next(next_idx)


def setup_player(state: PlayerState) -> Gst.Element:
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
    # Allow loading the entire music into the RAM (Max 256MB)
    player.set_property("ring-buffer-max-size", 256 * 1024 * 1024)

    class MemoryPlayerState:
        def __init__(self):
            self.bytes: bytes = b""
            self.offset: int = 0

    memory_player = MemoryPlayerState()

    def on_need_data(source: Gst.Element, length: int) -> None:
        if length > 2 * 1024 * 1024 or length <= 0:
            length = 64 * 1024

        data = memory_player.bytes
        offset = memory_player.offset

        end_offset = min(offset + length, len(data))
        chunk = data[offset:end_offset]

        if chunk:
            # Important: Update offset BEFORE emitting to avoid recursive call loops
            memory_player.offset = end_offset
            buf = Gst.Buffer.new_wrapped(chunk)

            # Tag buffer with offset mapping for accurate seeking
            buf.offset = offset
            buf.offset_end = end_offset

            source.emit("push-buffer", buf)
        else:
            source.emit("end-of-stream")

    def on_seek_data(source: Gst.Element, offset: int) -> bool:
        # Avoid out-of-bounds seeking
        if offset >= len(memory_player.bytes):
            return False

        memory_player.offset = max(0, min(offset, len(memory_player.bytes)))
        return True

    def on_source_setup(player: Gst.Element, source: Gst.Element) -> None:
        factory = source.get_factory()
        if factory and factory.get_name() == "appsrc":
            source.set_property("format", Gst.Format.BYTES)
            source.set_property("stream-type", GstApp.AppStreamType.RANDOM_ACCESS)

            # Explicitly force size so the pipeline can calculate seek offsets
            total_bytes = len(memory_player.bytes)
            source.set_property("size", total_bytes)

            source.connect("need-data", on_need_data)
            source.connect("seek-data", on_seek_data)

    player.connect("source-setup", on_source_setup)

    def on_audio_bytes_changed(audio_bytes: bytes | None) -> None:
        if audio_bytes:
            memory_player.bytes = audio_bytes
            memory_player.offset = 0

            player.set_state(Gst.State.READY)
            player.set_property("uri", "appsrc://")

            if state.state.value == PlayState.PLAYING:
                player.set_state(Gst.State.PLAYING)
        else:
            player.set_state(Gst.State.NULL)

    import reactivex as rx

    state.current.pipe(
        ops.map(lambda s: s.bytes if s else rx.just(None)),
        ops.switch_latest(),
        ops.distinct_until_changed(),
    ).subscribe(on_audio_bytes_changed)

    def on_state_changed(s: PlayState) -> None:
        has_audio = state.current_item and state.current_item.bytes.value
        if not has_audio:
            if s == PlayState.EMPTY:
                player.set_state(Gst.State.NULL)
                state.playlist.media.on_next([])
                state.playlist.index.on_next(0)
            return

        if s == PlayState.PLAYING:
            player.set_state(Gst.State.PLAYING)
        elif s == PlayState.PAUSED or s == PlayState.LOADING:
            player.set_state(Gst.State.PAUSED)
            if s == PlayState.LOADING and state.current_item:
                # Reset time to 0 when loading new track
                state.stream.current_time.on_next(0)

        elif s == PlayState.EMPTY:
            player.set_state(Gst.State.NULL)
            state.playlist.media.on_next([])
            state.playlist.index.on_next(0)

    state.state.subscribe(on_state_changed)

    def on_volume_changed(vol: float) -> None:
        player.set_property("volume", vol)

    state.stream.volume.subscribe(on_volume_changed)

    def update_time_state() -> bool:
        # Only update time if we're currently playing, to avoid unnecessary queries when paused
        if not state.current_item:
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
        if not state.current_item:
            return
        if message.type == Gst.MessageType.EOS:
            # Defer all state changes out of the GStreamer bus callback.
            def handle_eos() -> bool:
                if state.repeat_mode.value == RepeatMode.ONE:
                    player.seek_simple(
                        Gst.Format.TIME,
                        Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                        0,
                    )
                    player.set_state(Gst.State.PLAYING)
                    state.stream.current_time.on_next(0)
                    return False

                play_next(state)
                return False

            GLib.idle_add(handle_eos)
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logging.error(f"GStreamer Error: {err}, {debug}")
            GLib.idle_add(lambda: state.state.on_next(PlayState.PAUSED) or False)

    bus.connect("message", on_bus_message)

    def on_seek_request(position_ns: int) -> None:
        if not state.current_item:
            return

        # Attempt to map time domain seek safely back into the pipeline
        player.seek_simple(
            Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, position_ns
        )

        state.stream.current_time.on_next(position_ns)

    state.stream.seek_request.subscribe(on_seek_request)

    def on_current(current: Optional[MediaStatus]) -> None:
        logging.info(f"Current: {current}")
        if not current or current.audio_file.value or current.is_placeholder_music:
            return

        client = state.client
        state.state.on_next(PlayState.LOADING)
        import threading

        current_id = current.id
        if not current_id:
            return

        def on_audio_file(audio_file: Optional[tuple[LocalAudio, Any]]) -> None:
            if not current:
                raise RuntimeError("Current item changed during audio file fetch")
            if not audio_file:
                return
            file = audio_file[0].path
            if not file.exists():
                raise RuntimeError(f"Audio file not found: {file}")
            if not state.current_item or not state.current_item.id == current_id:
                logging.warning(
                    "Current item changed during audio file fetch, discarding result"
                )
                return

            def read_file_bytes(path: pathlib.Path):
                try:
                    if not current:
                        return
                    audio_bytes = path.read_bytes()

                    def _update_state():
                        if current is not None:
                            current.bytes.on_next(audio_bytes)
                            state.state.on_next(PlayState.PLAYING)
                        return False

                    GLib.idle_add(_update_state)
                except Exception as e:
                    logging.error(f"Failed to read audio file bytes: {e}")

            current.audio_file.on_next(file)
            threading.Thread(target=read_file_bytes, args=(file,)).start()

            # client.add
            # Only change state if this is still the active track

        client.get_audio_file(current_id).subscribe(
            on_next=on_audio_file,
            on_error=lambda e: logging.error(
                f"Could not fetch audio for {current_id}: {e}"
            ),
        )

        def on_song_detail(data: Optional[tuple[SongDetail, Any]]) -> None:
            if not current:
                raise RuntimeError("Current item changed during song detail fetch")
            if not data:
                return
            song_detail, raw_data = data
            if not state.current_item or not state.current_item.id == current_id:
                logging.warning(
                    "Current item changed during song detail fetch, discarding result"
                )
                return
            current.song = song_detail

            # Temporary test to see difference between parsed item and original
            parsed_dict = song_detail.model_dump(by_alias=True)
            raw_keys = set((raw_data or {}).keys())
            parsed_keys = set(parsed_dict.keys())
            missing_in_parsed = raw_keys - parsed_keys
            logging.info(f"Dict diff for {current_id} - Keys in raw but not parsed:")
            for key in sorted(list(missing_in_parsed)):
                logging.info(f"  - {key}")
            if "playbackTracking" in missing_in_parsed:
                logging.info(f"  (confirming playbackTracking was missing in parsed)")

            client.add_history_item(rx.just(song_detail)).subscribe(
                on_next=lambda _: logging.info(f"Added {current_id} to history"),
                on_error=lambda e: logging.error(
                    f"Could not add {current_id} to history: {e}"
                ),
            )

        client.get_song(current_id).subscribe(
            on_next=on_song_detail,
            on_error=lambda e: logging.error(
                f"Could not fetch song detail for {current_id}: {e}"
            ),
        )

    state.current.subscribe(on_current)

    import sys

    if sys.platform.startswith("linux"):
        from lib.sys.mpris import setup_mpris_controller

        setup_mpris_controller(state)
    elif sys.platform == "darwin":
        from lib.sys.mac_media import setup_mac_media_controller

        setup_mac_media_controller(state)

    return player
