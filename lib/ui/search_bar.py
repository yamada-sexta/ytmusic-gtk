import logging
from gi.repository import Gtk, Adw, GObject
from typing import Callable


def create_search_bar(
    window: Gtk.Window,
    toggle_button: Gtk.ToggleButton,
    on_search: Callable[[str], None],
) -> Gtk.SearchBar:
    """
    Functional factory for the SearchBar.
    'window' is needed for key capture.
    'toggle_button' is needed for the property binding.
    'on_search' is the callback triggered when a search is run.
    """
    search_bar = Gtk.SearchBar()
    search_entry = Gtk.SearchEntry()
    search_entry.set_placeholder_text("Search songs, artists, or albums...")
    search_entry.set_hexpand(True)

    # UI Layout
    clamp = Adw.Clamp()
    clamp.set_maximum_size(450)
    clamp.set_child(search_entry)

    search_bar.set_child(clamp)
    search_bar.connect_entry(search_entry)

    search_bar.set_key_capture_widget(window)

    # Logic
    def on_search_activated(entry: Gtk.SearchEntry) -> None:
        query = entry.get_text()
        if query.strip():
            logging.info(f"Searching for: {query}")
            on_search(query)

    search_entry.connect("activate", on_search_activated)

    # Sync the ToggleButton and SearchBar visibility
    search_bar.bind_property(
        "search-mode-enabled",
        toggle_button,
        "active",
        GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
    )

    return search_bar
