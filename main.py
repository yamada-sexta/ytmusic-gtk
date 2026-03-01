import ytmusicapi
from reactivex.subject import BehaviorSubject
from lib.types import YTMusicSubject
from lib.ui.home import create_home_page
from lib.player import player
import logging
from utils import load_image_async
from typing import Optional
from lib.data import HomePageType
import logging
import os
import sys
import subprocess
import threading

# --- macOS Homebrew & Virtual Environment Fix ---
try:
    brew_prefix = subprocess.check_output(["brew", "--prefix"], text=True).strip()
    brew_lib_path = f"{brew_prefix}/lib"

    os.environ["GI_TYPELIB_PATH"] = f"{brew_lib_path}/girepository-1.0"
    current_dyld = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")

    if brew_lib_path not in current_dyld:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = f"{brew_lib_path}:{current_dyld}"
        os.execv(sys.executable, [sys.executable] + sys.argv)
except Exception as e:
    print(f"Warning: Could not configure Homebrew paths automatically: {e}")
# ------------------------------------------------

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")

from gi.repository import Gtk, Adw, Gst, GLib, Pango, Gio, GdkPixbuf, Gdk

# Assuming these are available in your project structure
from lib.data import ExploreData
from lib.client import auto_login

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


class YTMusicWindow(Adw.ApplicationWindow):

    def __init__(self, yt_subject: YTMusicSubject, **kwargs):
        super().__init__(**kwargs)
        logging.info("Initializing YT Music App UI...")
        self.set_default_size(900, 700)
        self.set_title("YT Music")

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        self.stack = Adw.ViewStack()
        self.switcher = Adw.ViewSwitcher()
        self.switcher.set_stack(self.stack)
        self.switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)

        header = Adw.HeaderBar()
        header.set_title_widget(self.switcher)
        main_box.append(header)

        main_box.append(self.stack)
        self.stack.set_vexpand(True)

        # Build specific UI containers
        # self.home_box = self.create_home_page()
        self.stack.add_titled_with_icon(
            create_home_page(yt_subject), "home", "Home", "go-home-symbolic"
        )
        self.explore_list = self.create_empty_list_page(
            "explore", "Explore", "find-location-symbolic"
        )

        self.build_play_bar()
        main_box.append(self.play_bar)

        self.now_playing_title.set_label("Loading data...")
        self.fetch_data_async(yt_subject)

    def create_empty_list_page(
        self, page_id: str, title: str, icon_name: str
    ) -> Gtk.ListBox:
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

    def fetch_data_async(self, yt_subject: YTMusicSubject):
        def task():
            try:
                yt = auto_login()

                if not yt:
                    GLib.idle_add(self.now_playing_title.set_label, "Login Failed")
                    return
                yt_subject.on_next(yt)
                # raw_home = yt.get_home(limit=5)
                # home_data = HomePage.validate_python(raw_home)

                raw_explore = yt.get_explore()
                explore_data = ExploreData.model_validate(raw_explore)

                GLib.idle_add(self.populate_ui, explore_data)
            except Exception as e:
                logging.error(f"Error fetching data: {e}")
                GLib.idle_add(self.now_playing_title.set_label, "Error loading data")

        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def populate_ui(self, explore_data: ExploreData) -> None:
        # self.now_playing_title.set_label("Ready")

        # --- Populate Home Page (Cards & Carousels) ---

        # --- Populate Explore Page (Kept as list for contrast/example) ---
        header_row = Adw.ActionRow(title="New Releases")
        header_row.add_css_class("title")
        header_row.set_activatable(False)
        self.explore_list.append(header_row)

        for release in explore_data.new_releases:
            creator = release.artists[0].name if release.artists else "Unknown"
            row = Adw.ActionRow(
                title=release.title, subtitle=f"{creator} • {release.type}"
            )

            play_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            play_btn.set_valign(Gtk.Align.CENTER)
            play_btn.add_css_class("circular")
            play_btn.add_css_class("flat")
            play_btn.connect("clicked", self.on_track_play_clicked, release.title)

            row.add_suffix(play_btn)
            self.explore_list.append(row)

    def build_play_bar(self) -> None:
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

    def on_track_play_clicked(
        self, button: Optional[Gtk.Button], track_name: str
    ) -> None:
        self.now_playing_title.set_label(track_name)
        player.set_state(Gst.State.NULL)

        sample_audio_url = (
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        )
        player.set_property("uri", sample_audio_url)

        player.set_state(Gst.State.PLAYING)
        self.play_pause_btn.set_icon_name("media-playback-pause-symbolic")

    def on_play_pause_toggled(self, button: Gtk.Button) -> None:
        player_state = player.get_state(0)[1]
        if player_state != Gst.State.PLAYING:
            player.set_state(Gst.State.PLAYING)
            self.play_pause_btn.set_icon_name("media-playback-pause-symbolic")
        else:
            player.set_state(Gst.State.PAUSED)
            self.play_pause_btn.set_icon_name("media-playback-start-symbolic")


class YTMusicApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        self.yt_subject = BehaviorSubject[ytmusicapi.YTMusic | None](None)
        self.win = YTMusicWindow(application=app, yt_subject=self.yt_subject)
        self.win.present()


if __name__ == "__main__":
    app = YTMusicApp(application_id="com.example.YTMusicApp")
    app.run(sys.argv)
