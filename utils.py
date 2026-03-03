from lib.sys.env import CACHE_DIR
from typing import List
from typing import Optional
from lib.data import Thumbnail
import threading
import logging
from gi.repository import Gtk, GdkPixbuf, GLib, Gio, Gdk
import urllib.request

IMG_CACHE = {}


def load_image_async(image_widget: Gtk.Widget, url: str):
    """Fetches an image from a URL in the background and updates the widget.

    Works with both `Gtk.Picture` (using `set_paintable`) and `Gtk.Image`
    (using `set_from_pixbuf`).
    """

    def fetch():
        try:
            img_cache_dir = CACHE_DIR / "images"
            img_cache_dir.mkdir(parents=True, exist_ok=True)
            img_filename = img_cache_dir / f"{hash(url)}.img"
            if url in IMG_CACHE:
                logging.debug(f"Loading image from in-memory cache: {url}")
                data = IMG_CACHE[url]
            elif img_filename.exists():
                logging.debug(f"Loading image from cache: {img_filename}")
                with open(img_filename, "rb") as f:
                    data = f.read()
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                response = urllib.request.urlopen(req)
                data = response.read()

                # Save to cache
                # with open(img_filename, "wb") as f:
                # f.write(data)
                # URL change all the time...
                # Add to in-memory cache to avoid re-downloading during the same session
                IMG_CACHE[url] = data

            # Convert network bytes to a GTK Texture or Pixbuf
            stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(data))
            pixbuf = GdkPixbuf.Pixbuf.new_from_stream(stream, None)
            if pixbuf:
                # Calculate ratio for AspectFrame if it's the parent
                ratio = pixbuf.get_width() / max(pixbuf.get_height(), 1)

                # update widget appropriately on the main thread
                def update_ui():
                    # We already know pixbuf is not None due to outer check, but Pyrefly needs explicit assurance inside the closure
                    if pixbuf is None:
                        return
                    if hasattr(image_widget, "set_paintable"):
                        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                        image_widget.set_paintable(texture)
                    elif hasattr(image_widget, "set_from_pixbuf"):
                        image_widget.set_from_pixbuf(pixbuf)
                    else:
                        logging.debug(
                            f"Widget {image_widget} does not support image updates"
                        )
                        return

                    parent = image_widget.get_parent()
                    if hasattr(Gtk, "AspectFrame") and isinstance(
                        parent, Gtk.AspectFrame
                    ):
                        parent.set_obey_child(False)
                        parent.set_ratio(ratio)

                GLib.idle_add(update_ui)
        except Exception as e:
            logging.debug(f"Failed to load image {url}: {e}")

    threading.Thread(target=fetch, daemon=True).start()


def load_thumbnail(image_widget: Gtk.Picture, thumbnails: Optional[List[Thumbnail]]):
    """Helper to load a thumbnail image with error handling."""
    if not thumbnails:
        logging.debug("No thumbnails provided for thumbnail loading.")
        return
    url = thumbnails[-1].url  # Use the last thumbnail (highest resolution)

    load_image_async(image_widget, url)
