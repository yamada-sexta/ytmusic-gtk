from lib.ui.play_bar import PlayerState
from gi.repository import Gtk, Adw, GLib, GObject


def create_now_playing_view(state: PlayerState) -> Gtk.Widget:
    """
    Functional component for the Detail 'Now Playing' view.
    """
    view = Adw.ToolbarView()

    # Adw.HeaderBar automatically adds a back button when inside a NavigationView
    header = Adw.HeaderBar()
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
    def update_title(title: str):
        markup = f"<span size='x-large' weight='bold'>{GLib.markup_escape_text(title)}</span>"
        GLib.idle_add(title_label.set_markup, markup)

    def update_artist(artist: str):
        GLib.idle_add(artist_label.set_text, artist)

    state.title.subscribe(update_title)
    state.artist.subscribe(update_artist)

    return view
