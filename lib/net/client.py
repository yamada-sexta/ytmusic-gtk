import logging
from reactivex.scheduler.mainloop.gtkscheduler import GtkScheduler
from lib.data import LikeStatus
from lib.data import RateSongResponse
from lib.data import HomePageTypeAdapter
from pydantic import TypeAdapter
import pathlib
from lib.data import WatchPlaylist
from typing import Any
import multiprocessing
from functools import wraps
from typing import Optional, Callable, TypeVar, ParamSpec, cast
from reactivex import operators as ops

import ytmusicapi
import reactivex as rx
from reactivex import operators, Observable
from reactivex.scheduler import ThreadPoolScheduler
from pydantic import BaseModel

from lib.data import AlbumData, AccountInfo, SongDetail

logger = logging.getLogger(__name__)

thread_pool_scheduler = ThreadPoolScheduler(max_workers=multiprocessing.cpu_count())
download_scheduler = ThreadPoolScheduler(max_workers=1)

T = TypeVar("T")
P = ParamSpec("P")

type RxVal[V] = V | Observable[V]

V = TypeVar("V")


class LocalAudio(BaseModel):
    path: pathlib.Path


def rx_fetch(
    parser: type[T] | TypeAdapter[T],
    *,
    scheduler: Optional[ThreadPoolScheduler] = None,
) -> Callable[
    [Callable[P, Any]],
    # The return type is now strictly an Observable
    Callable[P, Observable[Optional[tuple[T, Any]]]],
]:
    adapter = parser if isinstance(parser, TypeAdapter) else TypeAdapter(parser)

    def decorator(
        func: Callable[P, Any],
    ) -> Callable[P, Observable[Optional[tuple[T, Any]]]]:
        @wraps(func)
        def wrapper(
            *args: P.args, **kwargs: P.kwargs
        ) -> Observable[Optional[tuple[T, Any]]]:
            blocking = cast(bool, kwargs.get("blocking", False))

            has_observable = any(isinstance(a, Observable) for a in args) or any(
                isinstance(v, Observable) for v in kwargs.values()
            )

            # 1. Synchronous Path: Wrap the result in rx.just to keep the return type consistent
            if blocking:
                if has_observable:
                    raise ValueError("Cannot use blocking=True with Observables.")

                raw_data = func(*args, **kwargs)
                parsed = (
                    (adapter.validate_python(raw_data), raw_data) if raw_data else None
                )
                return rx.just(parsed)

            # 2. Reactive Path
            obs_args = [a if isinstance(a, Observable) else rx.just(a) for a in args]
            kwarg_keys = list(kwargs.keys())
            obs_kwargs = [
                kwargs[k] if isinstance(kwargs[k], Observable) else rx.just(kwargs[k])
                for k in kwarg_keys
            ]

            all_observables = cast(list[Observable[Any]], obs_args + obs_kwargs)

            if all_observables:
                # Type ignore required for unpacking into overloads
                trigger = cast(
                    Observable[tuple[Any, ...]],
                    rx.combine_latest(*all_observables),  # type: ignore
                )
            else:
                trigger = rx.just(())

            def create_fetch_observable(
                combined_vals: tuple,
            ) -> Observable[Optional[tuple[T, Any]]]:
                if all_observables:
                    resolved_args = combined_vals[: len(args)]
                    resolved_kwargs = dict(zip(kwarg_keys, combined_vals[len(args) :]))
                else:
                    resolved_args, resolved_kwargs = (), {}

                def fetch_work() -> Optional[tuple[T, Any]]:
                    raw_data = func(*resolved_args, **resolved_kwargs)  # type: ignore
                    return (
                        (adapter.validate_python(raw_data), raw_data)
                        if raw_data
                        else None
                    )

                return rx.from_callable(fetch_work).pipe(
                    operators.subscribe_on(scheduler or thread_pool_scheduler)
                )

            return trigger.pipe(
                operators.switch_map(create_fetch_observable),
                # Start with None so subscribers get an immediate emission while loading
                operators.start_with(cast(Optional[tuple[T, Any]], None)),
            )

        return wrapper

    return decorator


def unwrap(val: RxVal[V]) -> V:
    """
    Bypasses static type errors for arguments intercepted by @rx_fetch.
    At runtime, @rx_fetch ensures this is already the raw value (V).
    """
    # Ensure that the value is not an Observable
    if isinstance(val, Observable):
        raise ValueError("unwrap() should only be called on non-Observable values.")
    return val


class YTClient:
    def __init__(self, api: ytmusicapi.YTMusic):
        self.api = api

    # 4. Add `*, blocking: bool = False` back to the signatures so your IDE knows it exists
    @rx_fetch(SongDetail)
    def get_song(
        self,
        video_id: RxVal[str],
        signature_timestamp: RxVal[Optional[int]] = None,
        *,
        blocking: bool = False,
    ) -> Optional[dict]:

        return self.api.get_song(unwrap(video_id), unwrap(signature_timestamp))

    @rx_fetch(AccountInfo)
    def get_account_info(self, *, blocking: bool = False) -> Optional[dict]:
        return self.api.get_account_info()

    @rx_fetch(AlbumData)
    def get_playlist(
        self,
        playlist_id: RxVal[str],
        limit: RxVal[int] = 100,
        related: RxVal[bool] = False,
        suggestions_limit: RxVal[int] = 0,
        *,
        blocking: bool = False,
    ) -> Optional[dict]:
        return self.api.get_playlist(
            unwrap(playlist_id),
            unwrap(limit),
            unwrap(related),
            unwrap(suggestions_limit),
        )

    @rx_fetch(WatchPlaylist)
    def get_watch_playlist(
        self,
        video_id: RxVal[Optional[str]] = None,
        playlist_id: RxVal[Optional[str]] = None,
        limit: RxVal[int] = 100,
        radio: RxVal[bool] = False,
        shuffle: RxVal[bool] = False,
        *,
        blocking: bool = False,
    ) -> Optional[dict]:
        logging.debug(
            f"Client: Getting watch playlist: {unwrap(video_id)}, {unwrap(playlist_id)}"
        )
        res = self.api.get_watch_playlist(
            unwrap(video_id),
            unwrap(playlist_id),
            unwrap(limit),
            unwrap(radio),
            unwrap(shuffle),
        )
        import json

        with open("watch_playlist.json", "w") as f:
            json.dump(res, f)
        return res

    @rx_fetch(LocalAudio, scheduler=download_scheduler)
    def get_audio_file(
        self, video_id: RxVal[str], *, blocking: bool = False
    ) -> Optional[dict]:
        from lib.net.utils import get_audio_file

        path = get_audio_file(self.api, unwrap(video_id))
        return {
            "path": path,
        }

    @rx_fetch(HomePageTypeAdapter)
    def get_home(
        self, limit: RxVal[int] = 100, *, blocking: bool = False
    ) -> Optional[list]:
        return self.api.get_home(limit=unwrap(limit))

    @rx_fetch(AlbumData)
    def get_album(
        self,
        browse_id: RxVal[str],
        *,
        blocking: bool = False,
    ) -> Optional[dict]:
        return self.api.get_album(unwrap(browse_id))

    @rx_fetch(RateSongResponse)
    def rate_song(
        self, video_id: RxVal[str], rating: RxVal[LikeStatus], *, blocking: bool = False
    ) -> Optional[dict]:
        logging.debug(
            f"Client: Rating song {unwrap(video_id)} as {unwrap(cast(RxVal[LikeStatus], rating))}"
        )
        self.api.rate_song(
            unwrap(video_id),
            ytmusicapi.LikeStatus(unwrap(cast(RxVal[LikeStatus], rating))),
        )
