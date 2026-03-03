import logging
import sys
import typing
from typing import Optional, Any
from gi.repository import GLib
from reactivex import combine_latest
from reactivex import operators as ops

if typing.TYPE_CHECKING:
    from lib.state.player_state import PlayerState, MediaStatus


def setup_mac_media_controller(state: "PlayerState") -> None:
    """Sets up the macOS media control (MPNowPlayingInfoCenter) using a functional, closure-based approach."""

    if sys.platform != "darwin":
        logging.info("Platform is not macOS. Mac media controller disabled.")
        return

    try:
        from Foundation import NSNumber, NSMutableDictionary  # type: ignore
        from AppKit import NSImage  # type: ignore
        from MediaPlayer import MPNowPlayingInfoCenter  # type: ignore
        from MediaPlayer import MPRemoteCommandCenter  # type: ignore
        from MediaPlayer import MPNowPlayingInfoPropertyElapsedPlaybackTime  # type: ignore
        from MediaPlayer import MPNowPlayingInfoPropertyPlaybackRate  # type: ignore
        from MediaPlayer import MPMediaItemPropertyTitle  # type: ignore
        from MediaPlayer import MPMediaItemPropertyArtist  # type: ignore
        from MediaPlayer import MPMediaItemPropertyPlaybackDuration  # type: ignore
        from MediaPlayer import MPMediaItemPropertyArtwork  # type: ignore
        from MediaPlayer import MPRemoteCommandHandlerStatusSuccess  # type: ignore
        from MediaPlayer import MPMediaItemArtwork  # type: ignore
    except ImportError:
        logging.error("macOS MediaPlayer framework or PyObjC not available.")
        return

    info_center = MPNowPlayingInfoCenter.defaultCenter()  # type: ignore
    command_center = MPRemoteCommandCenter.sharedCommandCenter()  # type: ignore

    _artwork_cache: dict[str, Any] = {}

    # --- Helper Functions (Closures over `state`) ---

    def update_now_playing_info() -> None:
        from lib.state.player_state import PlayState

        current = state.current_item
        if not current:
            info_center.setNowPlayingInfo_(None)
            return

        now_playing_info = NSMutableDictionary.alloc().init()

        if current.title:
            now_playing_info[MPMediaItemPropertyTitle] = current.title
        if current.artist:
            now_playing_info[MPMediaItemPropertyArtist] = current.artist
        if current.album_art and current.album_art in _artwork_cache:
            now_playing_info[MPMediaItemPropertyArtwork] = _artwork_cache[current.album_art]

        # MPRIS streams use nanoseconds. macOS uses seconds.
        total_time_s: float = state.stream.total_time.value / 1e9
        now_playing_info[MPMediaItemPropertyPlaybackDuration] = (
            NSNumber.numberWithDouble_(total_time_s)
        )

        current_time_s: float = state.stream.current_time.value / 1e9
        now_playing_info[MPNowPlayingInfoPropertyElapsedPlaybackTime] = (
            NSNumber.numberWithDouble_(current_time_s)
        )

        play_rate: float = 1.0 if state.state.value == PlayState.PLAYING else 0.0
        now_playing_info[MPNowPlayingInfoPropertyPlaybackRate] = (
            NSNumber.numberWithDouble_(play_rate)
        )

        info_center.setNowPlayingInfo_(now_playing_info)

    # --- MPRemoteCommandCenter Event Handlers ---

    def on_play(_event: Any) -> int:
        from lib.state.player_state import PlayState

        GLib.idle_add(lambda: state.state.on_next(PlayState.PLAYING))
        return MPRemoteCommandHandlerStatusSuccess

    def on_pause(_event: Any) -> int:
        from lib.state.player_state import PlayState

        GLib.idle_add(lambda: state.state.on_next(PlayState.PAUSED))
        return MPRemoteCommandHandlerStatusSuccess

    def on_toggle_play_pause(_event: Any) -> int:
        from lib.state.player_state import PlayState

        current_state = state.state.value

        def toggle() -> None:
            if current_state == PlayState.PLAYING:
                state.state.on_next(PlayState.PAUSED)
            elif current_state == PlayState.PAUSED:
                state.state.on_next(PlayState.PLAYING)

        GLib.idle_add(toggle)
        return MPRemoteCommandHandlerStatusSuccess

    def on_next_track(_event: Any) -> int:
        from lib.state.player_state import play_next

        GLib.idle_add(lambda: play_next(state))
        return MPRemoteCommandHandlerStatusSuccess

    def on_previous_track(_event: Any) -> int:
        from lib.state.player_state import play_previous

        GLib.idle_add(lambda: play_previous(state))
        return MPRemoteCommandHandlerStatusSuccess

    def on_change_playback_position(event: Any) -> int:
        position_s = event.positionTime()
        position_ns = int(position_s * 1e9)
        GLib.idle_add(lambda: state.stream.seek_request.on_next(position_ns))
        return MPRemoteCommandHandlerStatusSuccess

    # --- Add Targets ---
    command_center.playCommand().addTargetWithHandler_(on_play)
    command_center.pauseCommand().addTargetWithHandler_(on_pause)
    command_center.togglePlayPauseCommand().addTargetWithHandler_(on_toggle_play_pause)
    command_center.nextTrackCommand().addTargetWithHandler_(on_next_track)
    command_center.previousTrackCommand().addTargetWithHandler_(on_previous_track)
    command_center.changePlaybackPositionCommand().addTargetWithHandler_(on_change_playback_position)

    command_center.playCommand().setEnabled_(True)
    command_center.pauseCommand().setEnabled_(True)
    command_center.togglePlayPauseCommand().setEnabled_(True)
    command_center.nextTrackCommand().setEnabled_(True)
    command_center.previousTrackCommand().setEnabled_(True)
    command_center.changePlaybackPositionCommand().setEnabled_(True)

    # --- Reactive Subscriptions ---

    def on_playback_status_changed(_play_state: Any) -> None:
        update_now_playing_info()

    def on_metadata_changed(_: Any) -> None:
        update_now_playing_info()

    def on_current_changed(current: Optional["MediaStatus"]) -> None:
        if not current:
            update_now_playing_info()
            return

        art_url = current.album_art
        if art_url and art_url not in _artwork_cache:
            def _fetch_artwork(url: str) -> None:
                from lib.ui.thumbnail import _fetch_image_bytes

                try:
                    data = _fetch_image_bytes(url)
                    if data:
                        image = NSImage.alloc().initWithData_(data)
                        if image:
                            artwork = MPMediaItemArtwork.alloc().initWithBoundsSize_requestHandler_(
                                image.size(), lambda size: image
                            )
                            _artwork_cache[url] = artwork
                            GLib.idle_add(update_now_playing_info)
                except Exception as e:
                    logging.warning(f"Failed to fetch artwork for mac media: {e}")

            import threading
            threading.Thread(target=_fetch_artwork, args=(art_url,), daemon=True).start()

        combine_latest(
            state.current.pipe(ops.filter(lambda c: c is not None)),
            state.stream.total_time,
        ).subscribe(on_metadata_changed)

    def on_seek_request(_position: int) -> None:
        GLib.idle_add(update_now_playing_info)

    # Attach listeners to the state
    state.state.subscribe(on_playback_status_changed)
    state.current.subscribe(on_current_changed)
    state.stream.seek_request.subscribe(on_seek_request)
