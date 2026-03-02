from typing import Tuple
from typing import Any
from utils import load_thumbnail
from reactivex.subject import BehaviorSubject
import ytmusicapi
import threading
import logging
import logging
from lib.data import PodcastInfo
from lib.data import Album
from lib.data import BaseMedia
from lib.types import YTMusicSubject
from gi.repository import Gtk, Adw, GLib, Pango, Gdk, GdkPixbuf
from pydantic import BaseModel, Field
from typing import List, Optional


class NewVideo(BaseMedia):
    playlist_id: Optional[str] = Field(None, alias="playlistId")
    views: Optional[str] = None


class TrendingItem(BaseMedia):
    video_type: Optional[str] = Field(None, alias="videoType")
    is_explicit: Optional[bool] = Field(None, alias="isExplicit")
    playlist_id: Optional[str] = Field(None, alias="playlistId")
    album: Optional[Album] = None
    podcast: Optional[PodcastInfo] = None
    views: Optional[str] = None
    date: Optional[str] = None


class TopEpisode(BaseMedia):
    description: str
    duration: str
    video_type: str = Field(alias="videoType")
    date: str
    podcast: PodcastInfo


class NewRelease(BaseMedia):
    type: str  # e.g., "Album", "Single"
    audio_playlist_id: Optional[str] = Field(None, alias="audioPlaylistId")
    is_explicit: bool = Field(alias="isExplicit")


class Trending(BaseModel):
    playlist: str
    items: List[TrendingItem]


class MoodAndGenre(BaseModel):
    title: str
    params: str


class ExploreData(BaseModel):
    new_releases: List[NewRelease]
    moods_and_genres: List[MoodAndGenre]
    top_episodes: List[TopEpisode]
    trending: Trending
    new_videos: List[NewVideo]


def ExploreCard(item: BaseMedia, rank: Optional[int] = None) -> Gtk.Box:
    """
    Creates a card widget for a single item in the Explore page.
    If 'rank' is provided, it overlays the number on the thumbnail.
    """
    IMAGE_SIZE = 160

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    card.set_size_request(IMAGE_SIZE, IMAGE_SIZE + 60)
    card.set_halign(Gtk.Align.START)
    card.set_valign(Gtk.Align.START)

    # Image setup
    img = Gtk.Picture()
    img.set_can_shrink(True)
    img.set_content_fit(Gtk.ContentFit.COVER)
    img.set_size_request(IMAGE_SIZE, IMAGE_SIZE)
    img.add_css_class("card")

    if hasattr(item, "thumbnails") and item.thumbnails:
        load_thumbnail(img, item.thumbnails)

    overlay = Gtk.Overlay()
    overlay.set_child(img)

    # Add Rank Badge if it's a Trending item
    if rank is not None:
        rank_lbl = Gtk.Label(label=f"#{rank}")
        rank_lbl.add_css_class("title-2")

        # Use a dark, semi-transparent background for contrast
        bg_box = Gtk.Box()
        bg_box.add_css_class("osd")  # Adwaita's built-in On-Screen-Display class
        bg_box.set_halign(Gtk.Align.START)
        bg_box.set_valign(Gtk.Align.END)
        bg_box.set_margin_start(8)
        bg_box.set_margin_bottom(8)

        # Add a little padding around the text
        rank_lbl.set_margin_start(6)
        rank_lbl.set_margin_end(6)
        rank_lbl.set_margin_top(2)
        rank_lbl.set_margin_bottom(2)

        bg_box.append(rank_lbl)
        overlay.add_overlay(bg_box)

    text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    text_box.set_margin_start(4)
    text_box.set_margin_end(4)

    # Title
    title = getattr(item, "title", "Unknown Title")
    title_lbl = Gtk.Label(label=title)
    title_lbl.set_halign(Gtk.Align.START)
    title_lbl.set_xalign(0.0)
    title_lbl.set_wrap(True)
    title_lbl.set_lines(2)
    title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
    title_lbl.set_width_chars(1)
    title_lbl.add_css_class("heading")

    # Subtitle Extraction (handles Albums, Tracks, and Podcasts)
    creator = "Unknown"
    if hasattr(item, "artists") and item.artists:
        creator = item.artists[0].name
    elif hasattr(item, "podcast") and item.podcast:
        # Assuming PodcastInfo has a 'title' or 'name' attribute
        creator = getattr(
            item.podcast, "name", getattr(item.podcast, "title", "Podcast")
        )

    subtitle_lbl = Gtk.Label(label=creator)
    subtitle_lbl.set_halign(Gtk.Align.START)
    subtitle_lbl.set_xalign(0.0)
    subtitle_lbl.add_css_class("dim-label")
    subtitle_lbl.add_css_class("caption")
    subtitle_lbl.set_ellipsize(Pango.EllipsizeMode.END)
    subtitle_lbl.set_width_chars(1)
    subtitle_lbl.set_size_request(IMAGE_SIZE, -1)

    text_box.append(title_lbl)
    text_box.append(subtitle_lbl)

    card.append(overlay)
    card.append(text_box)

    # Cursor pointer
    card.set_cursor(Gdk.Cursor.new_from_name("pointer"))

    return card


def ExploreRow(title: str, items: List[Any], is_trending: bool = False) -> Gtk.Box:
    """
    Creates a scrollable horizontal row for standard Explore sections.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

    header = Gtk.Label(label=title)
    header.set_halign(Gtk.Align.START)
    header.set_margin_start(12)
    header.set_margin_bottom(8)
    header.add_css_class("title-2")
    box.append(header)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)

    row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    row_box.set_margin_start(12)
    row_box.set_margin_end(12)
    row_box.set_margin_bottom(16)

    for i, item in enumerate(items):
        rank = (i + 1) if is_trending else None
        row_box.append(ExploreCard(item, rank))

    scrolled.set_child(row_box)
    box.append(scrolled)

    return box


def MoodsAndGenresBadges(moods: List[MoodAndGenre]) -> Gtk.Box:
    """
    Creates a FlowBox filled with pill-shaped buttons for Moods and Genres.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

    header = Gtk.Label(label="Moods & Genres")
    header.set_halign(Gtk.Align.START)
    header.set_margin_start(12)
    header.set_margin_bottom(4)
    header.add_css_class("title-2")
    box.append(header)

    # FlowBox naturally wraps items to the next line when space runs out
    flowbox = Gtk.FlowBox()
    flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
    flowbox.set_max_children_per_line(15)  # Adjust based on how wide you want rows
    flowbox.set_margin_start(12)
    flowbox.set_margin_end(12)
    flowbox.set_row_spacing(10)
    flowbox.set_column_spacing(10)

    for mood in moods:
        btn = Gtk.Button(label=mood.title)
        btn.add_css_class("pill")  # Adwaita's rounded pill style

        # Optional: Add an action here when a mood badge is clicked
        # btn.connect("clicked", lambda b, m=mood: on_mood_clicked(m))

        flowbox.append(btn)

    box.append(flowbox)
    return box


def ExplorePage(
    yt_subject: YTMusicSubject,
) -> Gtk.ScrolledWindow:
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    # Widescreen container
    clamp = Adw.Clamp()
    clamp.set_maximum_size(1000)
    clamp.set_margin_top(32)
    clamp.set_margin_bottom(32)
    clamp.set_margin_start(24)
    clamp.set_margin_end(24)
    scrolled.set_child(clamp)

    explore_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=48)
    clamp.set_child(explore_box)

    explore_subject = BehaviorSubject[
        Tuple[Optional[ExploreData], Optional[ytmusicapi.YTMusic]]
    ]((None, None))

    def update_ui(
        data: Optional[ExploreData], yt: Optional[ytmusicapi.YTMusic]
    ) -> bool:
        # Clear existing content
        while (child := explore_box.get_first_child()) is not None:
            explore_box.remove(child)

        # Loading State
        if not yt or not data:
            loading_page = Adw.StatusPage()
            loading_page.set_title("Discovering music...")
            loading_page.set_description("Loading the latest hits and genres")

            spinner = Adw.Spinner()
            spinner.set_size_request(48, 48)
            spinner.set_halign(Gtk.Align.CENTER)
            spinner.add_css_class("margin-top-24")

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.set_valign(Gtk.Align.CENTER)
            box.set_vexpand(True)
            box.append(loading_page)
            box.append(spinner)

            explore_box.append(box)
            return GLib.SOURCE_REMOVE

        # 1. New Releases
        if data.new_releases:
            explore_box.append(ExploreRow("New Releases", data.new_releases))

        # 2. Moods & Genres (Badges)
        if data.moods_and_genres:
            explore_box.append(MoodsAndGenresBadges(data.moods_and_genres))

        # 3. Trending (Ranked)
        if data.trending and data.trending.items:
            # We pass is_trending=True to overlay the ranking badge
            explore_box.append(
                ExploreRow("Trending", data.trending.items, is_trending=True)
            )

        # 4. Top Episodes
        if data.top_episodes:
            explore_box.append(ExploreRow("Top Episodes", data.top_episodes))

        # 5. New Videos
        if data.new_videos:
            explore_box.append(ExploreRow("New Videos", data.new_videos))

        return GLib.SOURCE_REMOVE

    def on_explore_data_next(
        data_tuple: Tuple[Optional[ExploreData], Optional[ytmusicapi.YTMusic]],
    ):
        data, yt = data_tuple
        GLib.idle_add(update_ui, data, yt)

    def on_rx_error(e):
        logging.error(f"Rx Error in Explore: {e}")

    explore_subject.subscribe(
        on_next=on_explore_data_next,
        on_error=on_rx_error,
    )

    def fetch_explore_data(yt: ytmusicapi.YTMusic):
        try:
            raw_explore = yt.get_explore()
            # Use Pydantic's model_validate for v2 to parse the dictionary
            explore_data = ExploreData.model_validate(raw_explore)
            explore_subject.on_next((explore_data, yt))
        except Exception as e:
            logging.error(f"Failed to fetch explore data: {e}")
            # If fail, push empty data to trigger an error state or reset
            explore_subject.on_next((None, yt))

    def on_yt_changed(yt: Optional[ytmusicapi.YTMusic]):
        if yt is None:
            explore_subject.on_next((None, None))
            return

        # Start loading state
        explore_subject.on_next((None, yt))
        threading.Thread(target=fetch_explore_data, args=(yt,), daemon=True).start()

    yt_subject.subscribe(on_next=on_yt_changed, on_error=on_rx_error)

    return scrolled
