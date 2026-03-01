import logging
import os
import sys
import subprocess

# --- macOS Homebrew & Virtual Environment Fix ---
try:
    # Find Homebrew's root path dynamically
    brew_prefix = subprocess.check_output(['brew', '--prefix'], text=True).strip()
    brew_lib_path = f"{brew_prefix}/lib"

    # 1. Tell PyGObject where to find the metadata (.typelib files)
    os.environ['GI_TYPELIB_PATH'] = f"{brew_lib_path}/girepository-1.0"

    # 2. Tell macOS where to find the actual C libraries (.dylib files)
    current_dyld = os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')
    if brew_lib_path not in current_dyld:
        # Set the path and immediately restart the Python process with the new environment
        os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = f"{brew_lib_path}:{current_dyld}"
        os.execv(sys.executable, [sys.executable] + sys.argv)

except Exception as e:
    print(f"Warning: Could not configure Homebrew paths automatically: {e}")
# ------------------------------------------------

import threading
from data import HomePage,ExploreData
import logging
from client import auto_login
from data import Songs, AccountInfo
import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gst', '1.0')
log = logging.getLogger(__name__)

from gi.repository import Gtk, Adw, Gst, GLib

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logging.info("Starting YT Music App...")
class YTMusicWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging.info("Initializing YT Music App UI...")
        self.set_default_size(800, 700)
        self.set_title("YT Music")

        # GStreamer init
        Gst.init(None)
        self.player = Gst.ElementFactory.make("playbin", "player")
        self.is_playing = False

        # Layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Top Bar
        self.stack = Adw.ViewStack()
        self.switcher = Adw.ViewSwitcher()
        self.switcher.set_stack(self.stack)
        self.switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)

        header = Adw.HeaderBar()
        header.set_title_widget(self.switcher)
        main_box.append(header)

        # Main Area
        main_box.append(self.stack)
        self.stack.set_vexpand(True)

        # Build empty UI containers
        self.home_list = self.create_empty_list_page("home", "Home", "go-home-symbolic")
        self.explore_list = self.create_empty_list_page("explore", "Explore", "find-location-symbolic")

        # Bottom Bar
        self.build_play_bar()
        main_box.append(self.play_bar)

        # Start fetching data in the background
        self.now_playing_title.set_label("Loading data...")
        self.fetch_data_async()

    def create_empty_list_page(self, page_id: str, title: str, icon_name: str) -> Gtk.ListBox:
        scrolled = Gtk.ScrolledWindow()
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")
        list_box.set_margin_top(12)
        list_box.set_margin_bottom(12)
        list_box.set_margin_start(12)
        list_box.set_margin_end(12)
        
        scrolled.set_child(list_box)
        self.stack.add_titled_with_icon(scrolled, page_id, title, icon_name)
        return list_box

    def fetch_data_async(self):
        """Runs the ytmusicapi network calls in a separate thread to prevent UI freezing."""
        def task():
            try:
                yt = auto_login()
                if not yt:
                    GLib.idle_add(self.now_playing_title.set_label, "Login Failed")
                    return

                # Fetch and validate using your Pydantic models
                raw_home = yt.get_home(limit=5)
                home_data = HomePage.validate_python(raw_home)

                raw_explore = yt.get_explore()
                explore_data = ExploreData.model_validate(raw_explore)

                # Safely update UI on the main GTK thread
                GLib.idle_add(self.populate_ui, home_data, explore_data)
            except Exception as e:
                print(f"Error fetching data: {e}")
                GLib.idle_add(self.now_playing_title.set_label, "Error loading data")

        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def populate_ui(self, home_data, explore_data):
        self.now_playing_title.set_label("Ready")

        # Populate Home Page
        for section in home_data:
            # Add a section header
            # Add a section header
            header_row = Adw.ActionRow(title=section.title)
            # Add a CSS class to make it look distinct, and make it unclickable
            header_row.add_css_class("title")
            header_row.set_activatable(False)
            self.home_list.append(header_row)

            # Add the tracks/playlists for this section
            for item in section.contents:
                creator = item.artists[0].name if item.artists else (item.author[0].name if item.author else "Unknown")
                row = Adw.ActionRow(title=item.title, subtitle=creator)
                
                # Add a play button
                play_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
                play_btn.set_valign(Gtk.Align.CENTER)
                play_btn.add_css_class("circular")
                play_btn.add_css_class("flat")
                play_btn.connect("clicked", self.on_track_play_clicked, item.title)
                
                row.add_suffix(play_btn)
                self.home_list.append(row)

        # Populate Explore Page (using New Releases as an example)
        header_row = Adw.ActionRow(title="New Releases")
        header_row.add_css_class("title")
        header_row.set_activatable(False)
        self.explore_list.append(header_row)

        for release in explore_data.new_releases:
            creator = release.artists[0].name if release.artists else "Unknown"
            row = Adw.ActionRow(title=release.title, subtitle=f"{creator} • {release.type}")
            
            play_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            play_btn.set_valign(Gtk.Align.CENTER)
            play_btn.add_css_class("circular")
            play_btn.add_css_class("flat")
            play_btn.connect("clicked", self.on_track_play_clicked, release.title)
            
            row.add_suffix(play_btn)
            self.explore_list.append(row)

    def build_play_bar(self):
        self.play_bar = Gtk.ActionBar()
        
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_box.set_valign(Gtk.Align.CENTER)
        self.now_playing_title = Gtk.Label(label="Not Playing")
        self.now_playing_title.set_halign(Gtk.Align.START)
        self.now_playing_title.add_css_class("heading")
        info_box.append(self.now_playing_title)
        self.play_bar.pack_start(info_box)

        controls_box = Gtk.Box(spacing=10)
        controls_box.set_valign(Gtk.Align.CENTER)
        
        prev_btn = Gtk.Button(icon_name="media-skip-backward-symbolic")
        prev_btn.add_css_class("circular")
        
        self.play_pause_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
        self.play_pause_btn.add_css_class("circular")
        self.play_pause_btn.add_css_class("suggested-action")
        self.play_pause_btn.connect("clicked", self.on_play_pause_toggled)
        
        next_btn = Gtk.Button(icon_name="media-skip-forward-symbolic")
        next_btn.add_css_class("circular")

        controls_box.append(prev_btn)
        controls_box.append(self.play_pause_btn)
        controls_box.append(next_btn)
        
        self.play_bar.set_center_widget(controls_box)

    def on_track_play_clicked(self, button, track_name):
        if not self.player:
            logging.warning("Player not initialized (on_track_play_clicked)")
            return
        self.now_playing_title.set_label(track_name)
        self.player.set_state(Gst.State.NULL)
        
        # Placeholder stream URL - needs a raw audio link to play real YT music
        sample_audio_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        self.player.set_property("uri", sample_audio_url)
        
        self.player.set_state(Gst.State.PLAYING)
        self.is_playing = True
        self.play_pause_btn.set_icon_name("media-playback-pause-symbolic")

    def on_play_pause_toggled(self, button):
        if not self.player:
            logging.warning("Player not initialized (on_play_pause_toggled)")
            return
        if not self.is_playing:
            self.player.set_state(Gst.State.PLAYING)
            self.play_pause_btn.set_icon_name("media-playback-pause-symbolic")
            self.is_playing = True
        else:
            self.player.set_state(Gst.State.PAUSED)
            self.play_pause_btn.set_icon_name("media-playback-start-symbolic")
            self.is_playing = False

class YTMusicApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        self.win = YTMusicWindow(application=app)
        self.win.present()

if __name__ == '__main__':
    app = YTMusicApp(application_id="com.example.YTMusicApp")
    app.run(sys.argv)