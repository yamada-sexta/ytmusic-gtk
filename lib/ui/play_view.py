from typing import Optional
from lib.state.player_state import CurrentMusic
from reactivex.subject import BehaviorSubject
from lib.ui.play_bar import PlayerState
from gi.repository import Gtk, Adw, GLib, GObject


def create_now_playing_view(
    state: PlayerState, show_now_playing: BehaviorSubject[bool]
) -> Gtk.Widget:
    """
    Functional component for the Detail 'Now Playing' view.
    """
    view = Adw.ToolbarView()

    # --- ADD THIS LINE ---
    # Forces the view to have a solid background (matches light/dark mode automatically)
    view.add_css_class("background")
    # ---------------------

    # Manually recreate the header bar
    header = Adw.HeaderBar()
    header.set_show_title(False)

    # Create a close button with a flat style to look like a native nav button
    # Note: Use "go-previous-symbolic" if you prefer a `<` back arrow
    close_btn = Gtk.Button(icon_name="go-down-symbolic")
    close_btn.add_css_class("flat")
    close_btn.set_tooltip_text("Close Now Playing")

    # Reactively tell the state to close this view
    close_btn.connect("clicked", lambda *_: show_now_playing.on_next(False))
    header.pack_start(close_btn)

    view.add_top_bar(header)

    # Main Content Box
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
    content.set_valign(Gtk.Align.CENTER)
    content.set_halign(Gtk.Align.CENTER)

    # UI Elements
    art_placeholder = Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=256)
    title_label = Gtk.Label(
        label="<span size='x-large' weight='bold'>Loading...</span>", use_markup=True
    )
    artist_label = Gtk.Label(label="Artist Name")

    content.append(art_placeholder)
    content.append(title_label)
    content.append(artist_label)

    view.set_content(content)

    # --- Reactive Bindings ---
    def update_title(title: Optional[str]):
        markup = f"<span size='x-large' weight='bold'>{GLib.markup_escape_text(title or "")}</span>"
        GLib.idle_add(title_label.set_markup, markup)

    def update_artist(artist: Optional[str]):
        GLib.idle_add(artist_label.set_text, artist or "")

    # state.current_song.title.subscribe(update_title)
    # state.current_song.artist.subscribe(update_artist)
    def on_current(current: Optional[CurrentMusic]) -> None:
        if not current:
            return
        # update_title(current.title)
        # update_artist(current.artist)
        # current.title.subscribe(update_title)
        # current.artist.subscribe(update_artist)
        update_title(current.title)
        update_artist(current.artist)

    state.current.subscribe(on_current)

    return view
