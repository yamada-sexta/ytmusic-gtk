from typing import Any
from lib.state.player_state import MediaStatus
from typing import Optional
from lib.state.player_state import play_next
from lib.state.player_state import RepeatMode
from lib.state.player_state import PlayState
from lib.state.player_state import PlayerState
import mpv
import reactivex as rx
from reactivex import operators as ops
import pathlib
import logging
import sys
import threading
from gi.repository import Gtk, Adw, GLib


def setup_player(state: PlayerState) -> mpv.MPV:
    """
    Initializes the MPV player and binds it to
    the given PlayerState via functional reactive streams.
    """
    import locale

    locale.setlocale(locale.LC_NUMERIC, "C")
    # Initialize MPV for background audio only
    player = mpv.MPV(ytdl=False, video=False)

    def on_audio_file_changed(audio_file_path: pathlib.Path | None) -> None:
        if audio_file_path and audio_file_path.exists():
            player.play(str(audio_file_path))
            if state.state.value == PlayState.PLAYING:
                player.pause = False
            else:
                player.pause = True
        else:
            player.stop()

    # Subscribe to the audio file path instead of raw bytes
    state.current.pipe(
        ops.map(lambda s: s.audio_file if s else rx.just(None)),
        ops.switch_latest(),
        ops.distinct_until_changed(),
    ).subscribe(on_audio_file_changed)

    def on_state_changed(s: PlayState) -> None:
        has_audio = state.current_item and state.current_item.audio_file.value

        if not has_audio:
            if s == PlayState.EMPTY:
                player.stop()
                state.playlist.media.on_next([])
                state.playlist.index.on_next(0)
            return

        if s == PlayState.PLAYING:
            player.pause = False
        elif s == PlayState.PAUSED or s == PlayState.LOADING:
            player.pause = True
            if s == PlayState.LOADING and state.current_item:
                state.stream.current_time.on_next(0)
        elif s == PlayState.EMPTY:
            player.stop()
            state.playlist.media.on_next([])
            state.playlist.index.on_next(0)

    state.state.subscribe(on_state_changed)

    def on_volume_changed(vol: float) -> None:
        # MPV volume is generally 0-100+
        player.volume = vol * 100

    state.stream.volume.subscribe(on_volume_changed)

    is_seeking = False

    def update_time_state() -> bool:
        if not state.current_item:
            return True  # Keep timeout alive

        # Skip pushing updates to the stream if we are in the middle of a seek.
        # This breaks the loop between the player updating the UI and the UI updating the player.
        if state.state.value == PlayState.PLAYING and not is_seeking:
            pos = player.time_pos
            if pos is not None:
                state.stream.current_time.on_next(int(pos * 1e9))

            dur = player.duration
            if dur is not None:
                state.stream.total_time.on_next(int(dur * 1e9))

        return True

    GLib.timeout_add(500, update_time_state)

    # Watch for End of File (EOS) via MPV's property observer
    @player.property_observer("eof-reached")
    def on_eof(name, value):
        if value:  # True when the track finishes naturally

            def handle_eos() -> bool:
                if state.repeat_mode.value == RepeatMode.ONE:
                    player.time_pos = 0
                    player.pause = False
                    state.stream.current_time.on_next(0)
                    return False

                play_next(state)
                return False

            GLib.idle_add(handle_eos)

    def on_seek_request(position_ns: int) -> None:
        nonlocal is_seeking
        if not state.current_item:
            return

        is_seeking = True

        # Convert nanoseconds to seconds for MPV
        pos_sec = position_ns / 1e9
        player.time_pos = pos_sec

        # REMOVED: state.stream.current_time.on_next(position_ns)
        # Reason: Let the player naturally report its new time on the next tick.

        # Create a tiny delay to let MPV actually process the seek
        # before we start polling and pushing current_time again.
        def release_seek_lock():
            nonlocal is_seeking
            is_seeking = False
            return False  # Return False so GLib only runs this once

        GLib.timeout_add(250, release_seek_lock)

    def on_current(current: Optional[MediaStatus]) -> None:
        logging.info(f"Current: {current}")
        if not current or current.audio_file.value or current.is_placeholder_music:
            return

        client = state.client
        state.state.on_next(PlayState.LOADING)
        current_id = current.id

        if not current_id:
            return

        def on_audio_file(audio_file: Optional[tuple[Any, Any]]) -> None:
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

            # Note: Populating bytes is no longer strictly needed for playback,
            # but kept intact in case your app relies on it elsewhere (e.g. streaming to clients).
            def read_file_bytes(path: pathlib.Path):
                try:
                    if not current:
                        return
                    audio_bytes = path.read_bytes()
                    GLib.idle_add(lambda: current.bytes.on_next(audio_bytes) or False)
                except Exception as e:
                    logging.error(f"Failed to read audio file bytes: {e}")

            current.audio_file.on_next(file)
            threading.Thread(target=read_file_bytes, args=(file,)).start()

            # Trigger play state
            GLib.idle_add(lambda: state.state.on_next(PlayState.PLAYING) or False)

        client.get_audio_file(current_id).subscribe(
            on_next=on_audio_file,
            on_error=lambda e: logging.error(
                f"Could not fetch audio for {current_id}: {e}"
            ),
        )

        def on_song_detail(data: Optional[tuple[Any, Any]]) -> None:
            if not current:
                raise RuntimeError("Current item changed during song detail fetch")
            if not data:
                return
            song_detail, raw_data = data
            if not state.current_item or not state.current_item.id == current_id:
                logging.warning(
                    "Current item changed during song detail fetch, discarding"
                )
                return

            current.song = song_detail

            def delayed_history_add():
                if state.current_item and state.current_item.id == current_id:
                    client.add_history_item(rx.just(song_detail)).subscribe(
                        on_next=lambda _: logging.info(
                            f"Added {current_id} to history"
                        ),
                        on_error=lambda e: logging.error(
                            f"Could not add {current_id} to history: {e}"
                        ),
                    )
                return False

            GLib.timeout_add(10 * 1000, delayed_history_add)

        client.get_song(current_id).subscribe(
            on_next=on_song_detail,
            on_error=lambda e: logging.error(
                f"Could not fetch song detail for {current_id}: {e}"
            ),
        )

    state.current.subscribe(on_current)

    if sys.platform.startswith("linux"):
        from lib.sys.mpris import setup_mpris_controller

        setup_mpris_controller(state)
    elif sys.platform == "darwin":
        from lib.sys.mac_media import setup_mac_media_controller

        setup_mac_media_controller(state)

    return player
