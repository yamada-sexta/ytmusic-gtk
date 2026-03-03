from typing import Optional
from lib.data import Thumbnail
from lib.sys.env import CACHE_DIR
import threading
import logging
import urllib.request
from gi.repository import Gtk, GdkPixbuf, GLib, Gio, Gdk, Adw
from reactivex import Observable

# In-memory cache: url -> raw image bytes
_IMG_CACHE: dict[str, bytes] = {}
_PIXBUF_CACHE: dict[str, GdkPixbuf.Pixbuf] = {}

# CSS provider applied once to force internal stack/card minimum sizes to 0.
# Without this, Gtk.Stack unions its children's natural sizes as its minimum,
# which causes the stack to refuse to be measured below the image's pixel height.
_THUMBNAIL_CSS: Gtk.CssProvider | None = None


def _apply_thumbnail_css() -> None:
    """Register the thumbnail min-size CSS override once per display."""
    global _THUMBNAIL_CSS
    if _THUMBNAIL_CSS is not None:
        return
    _THUMBNAIL_CSS = Gtk.CssProvider()
    _THUMBNAIL_CSS.load_from_string(
        ".thumbnail-stack { min-width: 0px; min-height: 0px; }"
        " .thumbnail-card { min-width: 0px; min-height: 0px; }"
    )
    display = Gdk.Display.get_default()
    if display:
        Gtk.StyleContext.add_provider_for_display(
            display, _THUMBNAIL_CSS, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


def _pick_best_thumbnail(thumbnails: Optional[list[Thumbnail]]) -> Optional[str]:
    """Pure function: returns the URL of the highest-resolution thumbnail, or None."""
    if not thumbnails:
        return None
    with_dims = [t for t in thumbnails if t.width and t.height]
    if with_dims:
        best = max(with_dims, key=lambda t: (t.width or 0) * (t.height or 0))
        return best.url
    return thumbnails[-1].url


def _fetch_image_bytes(url: str) -> Optional[bytes]:
    """Pure function: fetch image bytes from cache or network. Returns None on error."""
    if url in _IMG_CACHE:
        logging.debug(f"Image cache hit: {url}")
        return _IMG_CACHE[url]

    img_cache_dir = CACHE_DIR / "images"
    img_cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        response = urllib.request.urlopen(req)
        data: bytes = response.read()
        _IMG_CACHE[url] = data
        return data
    except Exception as e:
        logging.warning(f"Failed to fetch image {url}: {e}")
        return None


def _bytes_to_pixbuf(data: bytes) -> Optional[GdkPixbuf.Pixbuf]:
    """Pure function: convert raw image bytes to a GdkPixbuf. Returns None on error."""
    try:
        stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(data))
        return GdkPixbuf.Pixbuf.new_from_stream(stream, None)
    except Exception as e:
        logging.warning(f"Failed to decode image bytes: {e}")
        return None


def ThumbnailWidget(
    thumbnails_stream: Observable[Optional[list[Thumbnail]]],
) -> Gtk.Widget:
    """Reactive functional component that displays a thumbnail image.

    Subscribes to thumbnails_stream and reacts to each new value:
    - Shows a spinner while the image is loading.
    - Once loaded, adjusts the AspectFrame to the image's natural ratio (no padding, no cropping).
    - Falls back to a generic music icon when there is no thumbnail or the fetch fails.
    - In-flight fetches are cancelled (via generation counter) when a new value arrives.
    - Results are cached in-memory so the same URL is only fetched once.

    The widget has 'card' styling (rounded corners + Adwaita shadow).
    The PARENT is responsible for all sizing via set_size_request or layout constraints.

    Args:
        thumbnails_stream: Observable emitting Optional[list[Thumbnail]] whenever the
                           displayed thumbnail should change.
    """
    # Register the CSS override for min-size enforcement (no-op after first call)
    _apply_thumbnail_css()

    # AspectFrame: outermost widget, ratio updated dynamically once an image loads.
    # halign=FILL means it fills whatever width its parent allocates — the parent
    # controls size via a clipping Gtk.Box with overflow=HIDDEN.
    frame = Gtk.AspectFrame()
    frame.set_obey_child(False)
    frame.set_ratio(1.0)
    frame.set_halign(Gtk.Align.FILL)
    frame.set_valign(Gtk.Align.CENTER)
    # Minimum size 0 — the PARENT controls size via a clip box or layout constraint.
    frame.set_size_request(0, 0)

    # card_box provides rounded corners + Adwaita card shadow.
    # thumbnail-card CSS class + set_size_request(0,0) enforce zero minimum size.
    card_box = Gtk.Box()
    card_box.add_css_class("card")
    card_box.add_css_class("thumbnail-card")
    card_box.set_hexpand(True)
    card_box.set_vexpand(True)
    card_box.set_size_request(0, 0)
    # Clip children to the card's rounded corners at the GTK render level.
    # CSS overflow:hidden does not clip child widgets in GTK4 — this API does.
    card_box.set_overflow(Gtk.Overflow.HIDDEN)
    frame.set_child(card_box)

    stack = Gtk.Stack()
    stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
    stack.set_hexpand(True)
    stack.set_vexpand(True)
    # Minimum size 0 so the parent clip box controls the actual rendered size.
    # The CSS class also sets min-height/min-width: 0 at the CSS level as a
    # belt-and-suspenders override, since Gtk.Stack unions its children's minimums.
    stack.set_size_request(0, 0)
    stack.add_css_class("thumbnail-stack")
    card_box.append(stack)

    spinner = Adw.Spinner()
    spinner.set_halign(Gtk.Align.CENTER)
    spinner.set_valign(Gtk.Align.CENTER)
    stack.add_named(spinner, "spinner")

    fallback = Gtk.Image(icon_name="audio-x-generic-symbolic")
    fallback.set_pixel_size(32)
    fallback.set_halign(Gtk.Align.CENTER)
    fallback.set_valign(Gtk.Align.CENTER)
    stack.add_named(fallback, "fallback")

    stack.set_visible_child_name("spinner")

    # Generation counter: incremented each time a new thumbnail value arrives,
    # so any in-flight thread from a previous value can self-cancel.
    _gen = [0]

    def _show_fallback() -> None:
        stack.set_visible_child_name("fallback")

    def _show_picture(pixbuf: GdkPixbuf.Pixbuf) -> None:
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)

        picture = Gtk.Picture()
        picture.set_paintable(texture)
        picture.set_can_shrink(True)
        # Minimum size 0 so the Stack doesn't inherit the image's natural pixel size.
        picture.set_size_request(0, 0)
        # FILL: picture fills the AspectFrame exactly — no letterboxing, no cropping
        picture.set_content_fit(Gtk.ContentFit.FILL)

        # Remove any previous "picture" child before adding the new one
        prev = stack.get_child_by_name("picture")
        if prev:
            stack.remove(prev)
        stack.add_named(picture, "picture")

        # Adjust the AspectFrame ratio to match the real image dimensions
        # The parent is responsible for the overall size; we only update the ratio
        # so unconstrained parents (e.g. the play view) get the natural aspect ratio.
        img_w = pixbuf.get_width()
        img_h = max(pixbuf.get_height(), 1)
        frame.set_ratio(img_w / img_h)
        frame.set_obey_child(False)

        stack.set_visible_child_name("picture")

    def on_thumbnails(thumbnails: Optional[list[Thumbnail]]) -> None:
        # Bump generation to cancel any previous in-flight fetch
        _gen[0] += 1
        gen = _gen[0]

        # Show the spinner while we go off-thread
        GLib.idle_add(stack.set_visible_child_name, "spinner")

        url = _pick_best_thumbnail(thumbnails)

        if url is None:
            GLib.idle_add(_show_fallback)
            return

        def _load() -> None:
            assert url is not None
            if gen != _gen[0]:
                # Superseded by a newer thumbnail value — abort
                return
            if url in _PIXBUF_CACHE:
                GLib.idle_add(_show_picture, _PIXBUF_CACHE[url])
                return
            data = _fetch_image_bytes(url)
            if gen != _gen[0]:
                return
            if data is None:
                GLib.idle_add(_show_fallback)
                return
            pixbuf = _bytes_to_pixbuf(data)
            if gen != _gen[0]:
                return
            if pixbuf is None:
                GLib.idle_add(_show_fallback)
                return
            _PIXBUF_CACHE[url] = pixbuf
            GLib.idle_add(_show_picture, pixbuf)

        threading.Thread(target=_load, daemon=True).start()

    # Subscribe on the calling (GTK) thread — each emission dispatches a daemon thread
    thumbnails_stream.subscribe(on_next=on_thumbnails)

    return frame


def ThumbnailWidgetFromUrl(
    url_stream: Observable[Optional[str]],
) -> Gtk.Widget:
    """Convenience wrapper: accepts an Observable[Optional[str]] URL instead of thumbnails.

    Converts each emitted URL to a single-element Thumbnail list and delegates to
    ThumbnailWidget, so all caching, spinner, and fallback logic is shared.
    The PARENT is responsible for all sizing via set_size_request or layout constraints.
    """
    from reactivex import operators as ops

    thumbnails_stream: Observable[Optional[list[Thumbnail]]] = url_stream.pipe(
        ops.map(lambda url: [Thumbnail(url=url)] if url else None),
    )
    return ThumbnailWidget(thumbnails_stream)
