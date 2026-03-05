from requests import Response
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

import ytmusicapi
import reactivex as rx
from reactivex import operators, Observable
from reactivex.scheduler import ThreadPoolScheduler
from pydantic import BaseModel
import time
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


class HTTPResponse(BaseModel, arbitrary_types_allowed=True):
    response: Response


def _make_hashable(obj: Any) -> Any:
    """Recursively converts mutable types to immutable types for cache hashing."""
    if isinstance(obj, list):
        return tuple(_make_hashable(e) for e in obj)
    if isinstance(obj, dict):
        return frozenset((k, _make_hashable(v)) for k, v in obj.items())
    return obj


def rx_fetch(
    parser: type[T] | TypeAdapter[T],
    *,
    scheduler: Optional[ThreadPoolScheduler] = None,
    use_cache: bool = True,
    ttl: float = 60.0,  # Added TTL parameter, defaults to 60 seconds
) -> Callable[
    [Callable[P, Any]],
    Callable[P, Observable[Optional[tuple[T, Any]]]],
]:
    """
    Decorator to wrap client methods, allowing them to accept both raw values and Observables as arguments.
    The decorated method will return an Observable that emits the parsed result whenever any of the input Observables emit a new value.
    The return value will be a tuple of (parsed_result, raw_data) where parsed_result is the output of the provided parser and raw_data is the original data returned by the API method.
    If `blocking=True` is passed as a keyword argument, the method will execute synchronously and block until the result is available. It will still return an Observable, but it will emit the result immediately and complete.
    If `force_refresh=True` is passed as a keyword argument, the method will bypass the cache and fetch fresh data from the API, even if a cached value exists for the given arguments.
    """
    adapter = parser if isinstance(parser, TypeAdapter) else TypeAdapter(parser)

    def decorator(
        func: Callable[P, Any],
    ) -> Callable[P, Observable[Optional[tuple[T, Any]]]]:

        # Method-level cache store now stores: {cache_key: (timestamp, parsed_data)}
        cache_store: dict[tuple, tuple[float, Optional[tuple[T, Any]]]] = {}

        @wraps(func)
        def wrapper(
            *args: P.args, **kwargs: P.kwargs
        ) -> Observable[Optional[tuple[T, Any]]]:
            blocking = cast(bool, kwargs.get("blocking", False))

            has_observable = any(isinstance(a, Observable) for a in args) or any(
                isinstance(v, Observable) for v in kwargs.values()
            )

            # --- Synchronous Path ---
            if blocking:
                if has_observable:
                    raise ValueError("Cannot use blocking=True with Observables.")

                force_refresh = cast(bool, kwargs.get("force_refresh", False))

                cache_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if k not in ("blocking", "force_refresh")
                }
                cache_key = (
                    tuple(_make_hashable(a) for a in args),
                    frozenset((k, _make_hashable(v)) for k, v in cache_kwargs.items()),
                )

                # 1. Cache Hit & TTL Check
                if use_cache and not force_refresh and cache_key in cache_store:
                    cached_time, cached_value = cache_store[cache_key]
                    if time.monotonic() - cached_time < ttl:
                        return rx.just(cached_value)

                # 2. Cache Miss / Expired / Force Refresh
                raw_data = func(*args, **kwargs)
                parsed = (
                    (adapter.validate_python(raw_data), raw_data) if raw_data else None
                )

                # 3. Store in cache with current timestamp
                if use_cache:
                    cache_store[cache_key] = (time.monotonic(), parsed)
                return rx.just(parsed)

            # --- Reactive Path ---
            obs_args = [a if isinstance(a, Observable) else rx.just(a) for a in args]
            kwarg_keys = list(kwargs.keys())
            obs_kwargs = [
                kwargs[k] if isinstance(kwargs[k], Observable) else rx.just(kwargs[k])
                for k in kwarg_keys
            ]

            all_observables = cast(list[Observable[Any]], obs_args + obs_kwargs)

            if all_observables:
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

                force_refresh = cast(bool, resolved_kwargs.get("force_refresh", False))

                cache_kwargs = {
                    k: v
                    for k, v in resolved_kwargs.items()
                    if k not in ("blocking", "force_refresh")
                }
                cache_key = (
                    tuple(_make_hashable(a) for a in resolved_args),
                    frozenset((k, _make_hashable(v)) for k, v in cache_kwargs.items()),
                )

                def fetch_work() -> Optional[tuple[T, Any]]:
                    # 1. Cache Hit & TTL Check
                    if use_cache and not force_refresh and cache_key in cache_store:
                        cached_time, cached_value = cache_store[cache_key]
                        if time.monotonic() - cached_time < ttl:
                            return cached_value

                    # 2. Cache Miss / Expired / Force Refresh
                    raw_data = func(*resolved_args, **resolved_kwargs)  # type: ignore
                    parsed = (
                        (adapter.validate_python(raw_data), raw_data)
                        if raw_data
                        else None
                    )

                    # 3. Store in cache with current timestamp
                    if use_cache:
                        cache_store[cache_key] = (time.monotonic(), parsed)
                    return parsed

                return rx.from_callable(fetch_work).pipe(
                    operators.subscribe_on(scheduler or thread_pool_scheduler)
                )

            return trigger.pipe(
                operators.switch_map(create_fetch_observable),
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
        force_refresh: bool = False,
        blocking: bool = False,
    ) -> Optional[dict]:

        raw = self.api.get_song(unwrap(video_id), unwrap(signature_timestamp))
        import json

        with open("debug_song.json", "w") as f:
            json.dump(raw, f)
        return raw

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
        force_refresh: bool = False,
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
        force_refresh: bool = False,
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
        self,
        video_id: RxVal[str],
        *,
        blocking: bool = False,
        force_refresh: bool = False,
    ) -> Optional[dict]:
        from lib.net.utils import get_audio_file

        path = get_audio_file(self.api, unwrap(video_id))
        return {
            "path": path,
        }

    @rx_fetch(HomePageTypeAdapter)
    def get_home(
        self,
        limit: RxVal[int] = 100,
        *,
        blocking: bool = False,
        force_refresh: bool = False,
    ) -> Optional[list]:
        return self.api.get_home(limit=unwrap(limit))

    @rx_fetch(AlbumData)
    def get_album(
        self,
        browse_id: RxVal[str],
        *,
        blocking: bool = False,
        force_refresh: bool = False,
    ) -> Optional[dict]:
        return self.api.get_album(unwrap(browse_id))

    @rx_fetch(RateSongResponse, use_cache=False)
    def rate_song(
        self,
        video_id: RxVal[str],
        rating: RxVal[LikeStatus],
        *,
        blocking: bool = False,
        force_refresh: bool = False,
    ) -> Optional[dict]:
        logging.debug(
            f"Client: Rating song {unwrap(video_id)} as {unwrap(cast(RxVal[LikeStatus], rating))}"
        )
        self.api.rate_song(
            unwrap(video_id),
            ytmusicapi.LikeStatus(unwrap(cast(RxVal[LikeStatus], rating))),
        )

    @rx_fetch(TypeAdapter(list[AlbumData]))
    def get_library_playlists(
        self,
        limit: RxVal[int] = 100,
        *,
        blocking: bool = False,
        force_refresh: bool = False,
    ) -> Optional[list[dict]]:
        res = self.api.get_library_playlists(limit=unwrap(limit))

        return res

    @rx_fetch(HTTPResponse, use_cache=False)
    def add_history_item(
        self,
        song: RxVal[SongDetail],
        *,
        blocking: bool = False,
        force_refresh: bool = False,
    ) -> Optional[dict]:
        res = self.api.add_history_item(unwrap(song).model_dump(by_alias=True))
        return {"response": res}

    @rx_fetch(TypeAdapter(list[Any]))
    def search(
        self,
        query: RxVal[str],
        filter: RxVal[Optional[str]] = None,
        scope: RxVal[Optional[str]] = None,
        limit: RxVal[int] = 20,
        ignore_spelling: RxVal[bool] = False,
        *,
        blocking: bool = False,
        force_refresh: bool = False,
    ) -> Optional[list[dict]]:
        res = self.api.search(
            unwrap(query),
            unwrap(filter),
            unwrap(scope),
            unwrap(limit),
            unwrap(ignore_spelling),
        )
        import json

        with open("debug_search.json", "w") as f:
            json.dump(res, f)
        return res
