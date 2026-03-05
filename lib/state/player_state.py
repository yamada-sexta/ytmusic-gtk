import sys
import threading
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
