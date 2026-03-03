from typing import Tuple
from typing import Any
from lib.utils import ThumbnailWidget
from reactivex.subject import BehaviorSubject
import ytmusicapi
import threading
import logging
import logging
from lib.data import PodcastInfo
from lib.data import Album
from lib.data import BaseMedia
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


def build_trending_list(trending_data: Trending) -> Adw.PreferencesGroup:
    """Builds a partial visible list with an inline 'Show more' button for remaining Trending items."""
    group = Adw.PreferencesGroup()
    group.set_title("Trending")

    if not trending_data.items:
        return group

    # Create a visible list box for items
    visible_list = Gtk.ListBox()
    visible_list.add_css_class("boxed-list")
    visible_list.set_selection_mode(Gtk.SelectionMode.NONE)
    visible_list.set_margin_bottom(12)
    group.add(visible_list)

    all_rows = []

    for i, item in enumerate(trending_data.items):
        creator = item.artists[0].name if item.artists else "Unknown"
        if item.views:
            creator += f" • {item.views}"

        row = Adw.ActionRow(title=item.title, subtitle=creator)

        # 1. Rank Number
        rank_lbl = Gtk.Label(label=f"{i + 1}")
        rank_lbl.set_margin_start(8)
        rank_lbl.set_margin_end(8)
        rank_lbl.add_css_class("title-4")
        rank_lbl.add_css_class("dim-label")
        row.add_prefix(rank_lbl)

        import reactivex as rx

        img = ThumbnailWidget(rx.of(item.thumbnails))
        img.set_size_request(48, 48)

        # Wrap image in a box for margin
        img_box = Gtk.Box()
        img_box.set_margin_top(8)
        img_box.set_margin_bottom(8)
        img_box.set_margin_end(12)
        img_box.append(img)
        row.add_prefix(img_box)

        all_rows.append(row)

    # Add the first 3 items
    for row in all_rows[:3]:
        visible_list.append(row)

    # Only add the "Show more" button if there are more than 3 items
    if len(all_rows) > 3:
        show_more_row = Adw.ActionRow(
            title="Show more", subtitle="See all trending hits"
        )
        show_more_row.set_activatable(True)

        icon = Gtk.Image.new_from_icon_name("go-down-symbolic")
        icon.set_valign(Gtk.Align.CENTER)
        show_more_row.add_suffix(icon)

        def on_show_more_clicked(_):
            show_more_row.set_visible(False)
            for r in all_rows[3:]:
                visible_list.append(r)

        show_more_row.connect("activated", on_show_more_clicked)
        visible_list.append(show_more_row)

    return group


def build_video_carousel(title: str, videos: List[NewVideo]) -> Gtk.Box:
    """Builds a horizontal scrolling carousel tailored for 16:9 video thumbnails."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

    header = Gtk.Label(label=title)
    header.set_halign(Gtk.Align.START)
    header.set_margin_start(12)
    header.add_css_class("title-2")
    box.append(header)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)

    row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    row_box.set_margin_start(12)
    row_box.set_margin_end(12)
    row_box.set_margin_bottom(16)

    for video in videos:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        # 16:9 Aspect Ratio
        width, height = 240, 135
        card.set_size_request(width, height + 50)

        import reactivex as rx

        img = ThumbnailWidget(rx.of(video.thumbnails))
        img.set_size_request(width, height)

        # Video metadata
        lbl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        v_title = Gtk.Label(label=video.title)
        v_title.set_halign(Gtk.Align.START)
        v_title.set_ellipsize(Pango.EllipsizeMode.END)
        v_title.set_max_width_chars(30)
        v_title.add_css_class("heading")

        creator = video.artists[0].name if video.artists else "Unknown"
        views = f" • {video.views}" if video.views else ""
        v_sub = Gtk.Label(label=f"{creator}{views}")
        v_sub.set_halign(Gtk.Align.START)
        v_sub.set_ellipsize(Pango.EllipsizeMode.END)
        v_sub.set_max_width_chars(30)
        v_sub.add_css_class("caption")
        v_sub.add_css_class("dim-label")

        lbl_box.append(v_title)
        lbl_box.append(v_sub)

        card.append(img)
        card.append(lbl_box)
        row_box.append(card)

    scrolled.set_child(row_box)
    box.append(scrolled)
    return box


def build_releases_carousel(title: str, releases: List[NewRelease]) -> Gtk.Box:
    """Standard 1:1 square album carousel for New Releases."""
    # (This is structurally similar to your original ExploreRow, but optimized for Albums)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    header = Gtk.Label(label=title)
    header.set_halign(Gtk.Align.START)
    header.set_margin_start(12)
    header.add_css_class("title-2")
    box.append(header)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
    row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    row_box.set_margin_start(12)
    row_box.set_margin_end(12)
    row_box.set_margin_bottom(16)

    for item in releases:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.set_size_request(160, 210)

        import reactivex as rx

        img = ThumbnailWidget(rx.of(item.thumbnails))
        img.set_size_request(160, 160)

        title_lbl = Gtk.Label(label=item.title)
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_lbl.set_max_width_chars(20)
        title_lbl.add_css_class("heading")

        creator = item.artists[0].name if item.artists else "Unknown"
        sub_lbl = Gtk.Label(label=creator)
        sub_lbl.set_halign(Gtk.Align.START)
        sub_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        sub_lbl.set_max_width_chars(20)
        sub_lbl.add_css_class("caption")
        sub_lbl.add_css_class("dim-label")

        card.append(img)
        card.append(title_lbl)
        card.append(sub_lbl)
        row_box.append(card)

    scrolled.set_child(row_box)
    box.append(scrolled)
    return box


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

    import reactivex as rx

    img = ThumbnailWidget(
        rx.of(item.thumbnails if hasattr(item, "thumbnails") else None)
    )
    img.set_size_request(IMAGE_SIZE, IMAGE_SIZE)

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
    Creates a horizontally scrollable carousel of Moods and Genres.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

    header = Gtk.Label(label="Moods & Genres")
    header.set_halign(Gtk.Align.START)
    header.set_margin_start(12)
    header.add_css_class("title-2")
    box.append(header)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)

    # Use a FlowBox with a horizontal orientation to allow columns
    # but since we want a true single-line carousel we use a Box
    row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row_box.set_margin_start(12)
    row_box.set_margin_end(12)
    row_box.set_margin_bottom(16)

    for mood in moods:
        btn = Gtk.Button(label=mood.title)
        btn.add_css_class("pill")
        row_box.append(btn)

    scrolled.set_child(row_box)
    box.append(scrolled)
    return box


def ExplorePage(
    yt_subject: BehaviorSubject[Optional[ytmusicapi.YTMusic]],
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
            explore_box.append(
                build_releases_carousel("New Releases", data.new_releases)
            )

        # 2. Moods & Genres (Pill Badges in a FlowBox)
        if data.moods_and_genres:
            explore_box.append(MoodsAndGenresBadges(data.moods_and_genres))

        # 3. Trending (Native Adwaita Boxed List with Ranks)
        if data.trending and data.trending.items:
            explore_box.append(build_trending_list(data.trending))

        # 4. New Videos (16:9 Aspect Ratio)
        if data.new_videos:
            explore_box.append(build_video_carousel("New Videos", data.new_videos))

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
