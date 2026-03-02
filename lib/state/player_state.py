import pathlib
import enum
import logging
import pathlib
from dataclasses import dataclass, field, replace
from typing import Optional

from gi.repository import GLib, Gst
from reactivex.subject import BehaviorSubject, Subject
from reactivex import operators as ops
import ytmusicapi


# Enum for the player state
class PlayState(enum.Enum):
    EMPTY = 0
    PLAYING = 1
    PAUSED = 2
    LOADING = 3


class LikeStatus(enum.Enum):
    NONE = 0
    LIKE = 1
    DISLIKE = 2


@dataclass
class MediaStatus:
    id: str
    audio_file: BehaviorSubject[Optional[pathlib.Path]] = field(
        default_factory=lambda: BehaviorSubject[Optional[pathlib.Path]](None)
    )

    title: Optional[str] = field(default=None)
    artist: Optional[str] = field(default=None)
    album_name: Optional[str] = field(default=None)
    year: Optional[str] = field(default=None)
    album_art: Optional[str] = field(default=None)
    like_status: BehaviorSubject[LikeStatus] = field(
        default_factory=lambda: BehaviorSubject(LikeStatus.NONE)
    )
    # is_liked: BehaviorSubject[bool] = field(
    #     default_factory=lambda: BehaviorSubject(False)
    # )
    # is_disliked: BehaviorSubject[bool] = field(
    #     default_factory=lambda: BehaviorSubject(False)
    # )


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

    current: BehaviorSubject[Optional[MediaStatus]] = field(
        default_factory=lambda: BehaviorSubject[Optional[MediaStatus]](None)
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


def play_audio(
    state: PlayerState,
    video_id: str,
    yt: "ytmusicapi.YTMusic",
    playlist_id: Optional[str] = None,
    initial_temp_music: Optional[MediaStatus] = None,
) -> None:
    import threading
    from typing import cast, Any
    from lib.sys.env import CACHE_DIR

    state.state.on_next(PlayState.LOADING)
    new_music = initial_temp_music or MediaStatus(id=video_id)
    state.current.on_next(new_music)

    # related = yt.get_song_related(video_id)
    # logging.debug(f"Related: {related}")
    playlist = yt.get_watch_playlist(video_id)
    # logging.debug(f"Watch playlist: {playlist}")
    import json

    with open("debug_watch_playlist.json", "w") as f:
        json.dump(playlist, f, indent=4)

    # Try to get the next item in the playlist
    # tracks = playlist.get("tracks", [])
    # if tracks and len(tracks) > 1:
    #     logging.info(f"Next item: {tracks[1]}")

    #     # Get next item's video ID
    #     next_video_id = tracks[1].get("videoId", None)
    #     if next_video_id:
    #         logging.info(f"Next video ID: {next_video_id}")
    #         # play_audio(state, next_video_id, yt)
    #         # Check if the next video is in the same playlist
    #         next_playlist = yt.get_watch_playlist(next_video_id)
    #         if next_playlist.get("playlistId") == playlist_id:
    #             logging.info("Next video is in the same playlist")
    #         else:
    #             logging.info(
    #                 f"Next video is in a different playlist: {next_playlist.get('playlistId')}"
    #             )
    #             # play_audio(state, next_video_id, yt)
    # As it turns out, the playlist ID is not consistent between the watch playlist and the playlist details.
    def fetch_details() -> None:
        try:
            data = None
            if playlist_id and not playlist_id.startswith("RD"):
                logging.info(f"Fetching playlist details for {playlist_id}")
                data = yt.get_playlist(playlist_id)
            elif video_id:
                logging.info(f"Fetching song details for {video_id}")
                data = yt.get_song(video_id)

            if not data:
                logging.warning("No additional details found for this item.")
                return

            # If not provided, try to extract some metadata
            if not initial_temp_music:
                try:
                    video_details = data.get("videoDetails", {})
                    if video_details:
                        new_music.title = video_details.get("title", new_music.title)
                        new_music.artist = video_details.get("author", new_music.artist)
                        t_info = video_details.get("thumbnail", {}).get(
                            "thumbnails", []
                        )
                        if t_info:
                            new_music.album_art = t_info[-1].get(
                                "url", new_music.album_art
                            )
                except Exception as meta_e:
                    logging.warning(f"Failed to extract default metadata: {meta_e}")

            import json

            with open("debug_fetched_data.json", "w") as f:
                json.dump(data, f, indent=4)

            url = data["microformat"]["microformatDataRenderer"]["urlCanonical"]
            logging.info(f"Canonical URL: {url}")

            from yt_dlp import YoutubeDL

            download_dir = CACHE_DIR / "songs" / video_id
            download_dir.mkdir(parents=True, exist_ok=True)

            logging.info(f"Downloading media to: {download_dir}")

            marker_file = download_dir / "downloaded.txt"

            if not marker_file.exists():
                with YoutubeDL(
                    params=cast(
                        Any,
                        {
                            "js_runtimes": {"bun": {}, "node": {}},
                            "paths": {"home": str(download_dir.absolute())},
                            "format": "bestaudio/best",
                            "noplaylist": True,
                            "quiet": True,
                        },
                    )
                ) as ydl:
                    ydl.download([url])
                    marker_file.touch()

            downloaded_files = [
                f
                for f in download_dir.glob("*")
                if f.is_file() and f.name != "downloaded.txt"
            ]
            if not downloaded_files:
                logging.warning(f"No files downloaded to {download_dir}")
                return

            latest_file = max(downloaded_files, key=lambda f: f.stat().st_mtime)
            logging.info(f"Latest downloaded file: {latest_file}")

            new_music.audio_file.on_next(latest_file)
            state.state.on_next(PlayState.PLAYING)

        except Exception as e:
            logging.error(f"Could not fetch or download media: {e}")

    threading.Thread(target=fetch_details, daemon=True).start()


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

    import reactivex as rx

    state.current.pipe(
        ops.map(lambda s: s.audio_file if s else rx.just(None)),
        ops.switch_latest(),
        ops.distinct_until_changed(),
    ).subscribe(on_audio_file_changed)

    def on_state_changed(s: PlayState) -> None:
        has_audio = state.current.value and state.current.value.audio_file.value
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

    def on_current(current: Optional[MediaStatus]) -> None:
        if not current:
            return
        state.stream.seek_request.subscribe(on_seek_request)

    # state.seek_request.subscribe(on_seek_request)
    state.current.subscribe(on_current)

    setup_mpris_controller(state)

    return player
