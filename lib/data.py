import logging
from pydantic import TypeAdapter
from pydantic import BaseModel, Field
from typing import Literal, Optional

import unittest
import ytmusicapi

LikeStatus = Literal["INDIFFERENT", "LIKE", "DISLIKE"]


class AccountInfo(BaseModel):
    # Field aliases map the JSON key to your Python variable
    account_name: str = Field(alias="accountName")
    channel_handle: Optional[str] = Field(alias="channelHandle")
    account_photo_url: str = Field(alias="accountPhotoUrl")


class Artist(BaseModel):
    name: str
    id: Optional[str] = None


class Thumbnail(BaseModel):
    url: str
    width: Optional[int] = None
    height: Optional[int] = None


class Album(BaseModel):
    name: str
    id: Optional[str] = None


class PodcastInfo(BaseModel):
    id: str
    name: str


class BaseMedia(BaseModel):
    """
    Base class for media items
    New media types should inherit from this
    """

    title: str
    video_id: Optional[str] = Field(None, alias="videoId")
    browse_id: Optional[str] = Field(None, alias="browseId")
    artists: Optional[list[Artist]] = Field(None, alias="artists")
    thumbnails: Optional[list[Thumbnail]] = Field(None, alias="thumbnails")

    # Common fields across various media types
    like_status: Optional[LikeStatus] = Field(None, alias="likeStatus")
    in_library: Optional[bool] = Field(None, alias="inLibrary")
    video_type: Optional[str] = Field(None, alias="videoType")
    is_explicit: bool = Field(False, alias="isExplicit")


class Song(BaseMedia):
    duration: str
    played: str


class Track(BaseMedia):
    length: str
    album: Optional[Album] = None
    year: Optional[str] = None
    # Track-specific alias for thumbnails
    thumbnails: Optional[list[Thumbnail]] = Field(None, alias="thumbnail")


class History(BaseModel):
    songs: list[Song]


class WatchPlaylist(BaseModel):
    tracks: list[Track]
    lyrics: Optional[str] = None
    playlist_id: Optional[str] = Field(None, alias="playlistId")
    related: Optional[str] = None


Songs = TypeAdapter(list[Song])


class ThumbnailContainer(BaseModel):
    thumbnails: list[Thumbnail]


class VideoDetails(BaseModel):
    video_id: str = Field(alias="videoId")
    title: str
    length_seconds: str = Field(alias="lengthSeconds")
    channel_id: str = Field(alias="channelId")
    author: str
    thumbnail: ThumbnailContainer
    music_video_type: Optional[str] = Field(None, alias="musicVideoType")
    view_count: Optional[str] = Field(None, alias="viewCount")


class MicroformatDataRenderer(BaseModel):
    url_canonical: str = Field(alias="urlCanonical")
    title: str
    description: str
    thumbnail: ThumbnailContainer


class Microformat(BaseModel):
    microformat_data_renderer: MicroformatDataRenderer = Field(
        alias="microformatDataRenderer"
    )


class SongDetail(BaseModel):
    video_details: VideoDetails = Field(alias="videoDetails")
    microformat: Microformat


class AlbumTrack(BaseMedia):
    duration_seconds: Optional[int] = Field(None, alias="duration_seconds")
    duration: Optional[str] = None
    views: Optional[str] = None
    is_available: bool = Field(True, alias="isAvailable")
    album: Optional[str | Album] = None  # Playlist tracks sometimes have album as dict
    feedback_tokens: Optional[dict[str, str]] = Field(None, alias="feedbackTokens")
    track_number: Optional[int] = Field(None, alias="trackNumber")


class AlbumData(BaseModel):
    title: str
    type: Optional[str] = None
    thumbnails: list[Thumbnail]
    artists: Optional[list[Artist]] = None
    author: Optional[Artist | list[Artist]] = None
    year: Optional[str] = None
    track_count: Optional[int] = Field(None, alias="trackCount")
    duration: Optional[str] = None
    duration_seconds: Optional[int] = Field(None, alias="duration_seconds")
    audio_playlist_id: Optional[str] = Field(None, alias="audioPlaylistId")
    id: Optional[str] = None
    tracks: list[AlbumTrack] = []
    description: Optional[str] = None
    other_versions: Optional[list[dict]] = Field(None, alias="other_versions")
    is_explicit: bool = Field(False, alias="isExplicit")
    like_status: Optional[str] = Field(None, alias="likeStatus")


class HomeItemData(BaseMedia):
    # Tracks & Quick Picks
    playlist_id: Optional[str] = Field(None, alias="playlistId")
    views: Optional[str] = None
    video_type: Optional[str] = Field(None, alias="videoType")
    album: Optional[Album] = None

    # Albums & Singles
    audio_playlist_id: Optional[str] = Field(None, alias="audioPlaylistId")

    # Playlists & Mixes
    description: Optional[str] = None
    count: Optional[str] = None
    # Note: Playlists often use 'author' instead of 'artists',
    # but the data structure inside is identical to 'Artist'
    author: Optional[list[Artist]] = None


class HomeSectionData(BaseModel):
    title: str
    contents: list[HomeItemData]


HomePageTypeAdapter = TypeAdapter(list[HomeSectionData])


# Reusable Utility Models
class Param(BaseModel):
    key: str
    value: str


class ServiceTrackingParam(BaseModel):
    service: str
    params: list[Param]


class ConsistencyTokenJar(BaseModel):
    encrypted_token_jar_contents: str = Field(alias="encryptedTokenJarContents")
    expiration_seconds: str = Field(alias="expirationSeconds")


class ResponseContext(BaseModel):
    service_tracking_params: list[ServiceTrackingParam] = Field(
        alias="serviceTrackingParams"
    )
    consistency_token_jar: Optional[ConsistencyTokenJar] = Field(
        None, alias="consistencyTokenJar"
    )


class Run(BaseModel):
    text: str


class FormattedText(BaseModel):
    runs: list[Run]


class BrowseEndpoint(BaseModel):
    browse_id: str = Field(alias="browseId")


class NavigationEndpoint(BaseModel):
    click_tracking_params: Optional[str] = Field(None, alias="clickTrackingParams")
    browse_endpoint: Optional[BrowseEndpoint] = Field(None, alias="browseEndpoint")


# Action and Renderer Models
class ButtonRenderer(BaseModel):
    style: Optional[str] = None
    is_disabled: bool = Field(False, alias="isDisabled")
    text: Optional[FormattedText] = None
    navigation_endpoint: Optional[NavigationEndpoint] = Field(
        None, alias="navigationEndpoint"
    )
    tracking_params: Optional[str] = Field(None, alias="trackingParams")


class ActionButton(BaseModel):
    button_renderer: ButtonRenderer = Field(alias="buttonRenderer")


class NotificationActionRenderer(BaseModel):
    response_text: Optional[FormattedText] = Field(None, alias="responseText")
    action_button: Optional[ActionButton] = Field(None, alias="actionButton")
    tracking_params: Optional[str] = Field(None, alias="trackingParams")


class NotificationTextRenderer(BaseModel):
    success_response_text: Optional[FormattedText] = Field(
        None, alias="successResponseText"
    )
    tracking_params: Optional[str] = Field(None, alias="trackingParams")


class ToastItem(BaseModel):
    # Both renderers are optional since YouTube swaps them out depending on the action
    notification_action_renderer: Optional[NotificationActionRenderer] = Field(
        None, alias="notificationActionRenderer"
    )
    notification_text_renderer: Optional[NotificationTextRenderer] = Field(
        None, alias="notificationTextRenderer"
    )


class AddToToastAction(BaseModel):
    item: ToastItem


class Action(BaseModel):
    click_tracking_params: Optional[str] = Field(None, alias="clickTrackingParams")
    add_to_toast_action: Optional[AddToToastAction] = Field(
        None, alias="addToToastAction"
    )


# Like Response Models
class RateSongResponse(BaseModel):
    """
    Handles LIKE, DISLIKE, and INDIFFERENT responses.
    Actions array will be None when removing a rating (INDIFFERENT).
    """

    response_context: Optional[ResponseContext] = Field(None, alias="responseContext")
    actions: Optional[list[Action]] = None


class TestYtMusicDataParsing(unittest.TestCase):
    yt: ytmusicapi.YTMusic

    @classmethod
    def setUpClass(cls):
        from lib.net.api import auto_login

        yt = auto_login()
        if yt is None:
            raise unittest.SkipTest("Failed to login to YT Music")
        cls.yt = yt

    def test_history_parsing(self):
        history_data = self.yt.get_history()
        songs = Songs.validate_python(history_data)
        self.assertGreater(len(songs), 0, "History parsed no songs")
        self.assertIsNotNone(songs[0].video_id, "Returned song missing video_id")

    def test_song_detail_parsing(self):
        history_data = self.yt.get_history()
        songs = Songs.validate_python(history_data)

        self.assertGreater(len(songs), 0, "Need history to test song detail")
        self.assertIsNotNone(
            songs[0].video_id, "Need a video_id from history to test song detail"
        )
        video_id = songs[0].video_id

        song_data = self.yt.get_song(video_id)
        song_detail = SongDetail.model_validate(song_data)
        self.assertTrue(
            song_detail.video_details.title, "Parsed SongDetail missing title"
        )
        self.assertEqual(
            song_detail.video_details.video_id, video_id, "Mismatch in video ID"
        )

    def test_watch_playlist_parsing(self):
        history_data = self.yt.get_history()
        songs = Songs.validate_python(history_data)

        self.assertGreater(len(songs), 0, "Need history to test watch playlist")
        self.assertIsNotNone(
            songs[0].video_id, "Need a video_id from history to test watch playlist"
        )
        video_id = songs[0].video_id

        playlist_data = self.yt.get_watch_playlist(videoId=video_id)
        watch_playlist = WatchPlaylist.model_validate(playlist_data)
        self.assertGreater(
            len(watch_playlist.tracks), 0, "WatchPlaylist parsing returned no tracks"
        )

    def test_album_parsing(self):
        import json

        # Use a known album browseId (Petal Lament by MIMI)
        browse_id = "MPREb_cTw5MfVwmhd"
        raw_album = self.yt.get_album(browse_id)

        # Log the raw response for inspection
        with open("debug_album_response.json", "w") as f:
            json.dump(raw_album, f, indent=2)

        album = AlbumData.model_validate(raw_album)
        self.assertTrue(album.title, "Album title is empty")
        self.assertGreater(len(album.tracks), 0, "Album has no tracks")
        self.assertIsNotNone(album.audio_playlist_id, "Album missing audioPlaylistId")
        self.assertGreater(len(album.thumbnails), 0, "Album has no thumbnails")
        # Fix artists length check since artists can be empty for playlists
        self.assertIsNotNone(album.artists, "Album missing artists")
        if album.artists:
            self.assertGreater(len(album.artists), 0, "Album has empty artists list")

        # Validate first track has essential fields
        first_track = album.tracks[0]
        self.assertTrue(first_track.title, "First track title is empty")
        self.assertIsNotNone(first_track.video_id, "First track missing video_id")

    def test_playlist_parsing(self):
        playlist_id = "PLtj8j4LeQJtlhTHiGP_hv4Jf1teVoeKqJ"
        raw_playlist = self.yt.get_playlist(playlist_id)
        playlist = AlbumData.model_validate(raw_playlist)
        self.assertTrue(playlist.title, "Playlist title is empty")
        self.assertGreater(len(playlist.tracks), 0, "Playlist has no tracks")
        self.assertIsNotNone(playlist.id, "Playlist missing id")
        self.assertGreater(len(playlist.thumbnails), 0, "Playlist has no thumbnails")
        self.assertIsNotNone(playlist.author, "Playlist has no author")

    def test_rate_song(self):

        # This test will like and then dislike a song, then reset to indifferent
        history_data = self.yt.get_history()
        songs = Songs.validate_python(history_data)

        self.assertGreater(len(songs), 0, "Need history to test rate song")
        self.assertIsNotNone(
            songs[0].video_id, "Need a video_id from history to test rate song"
        )
        video_id = songs[0].video_id

        # Like the song
        res = self.yt.rate_song(video_id, ytmusicapi.LikeStatus.LIKE)
        logging.info(f"Like response: {res}")
        import json

        with open("debug_like_response.json", "w") as f:
            json.dump(res, f, indent=2)
        val = RateSongResponse.model_validate(res)
        self.assertIsNotNone(
            val.response_context, "Like response missing responseContext"
        )
        self.assertIsNotNone(val.actions, "Like response missing actions")
        self.assertGreater(len(val.actions), 0, "Like response has empty actions list")
        # Dislike the song
        res = self.yt.rate_song(video_id, ytmusicapi.LikeStatus.DISLIKE)
        logging.info(f"Dislike response: {res}")
        with open("debug_dislike_response.json", "w") as f:
            json.dump(res, f, indent=2)
        val = RateSongResponse.model_validate(res)
        self.assertIsNotNone(
            val.response_context, "Dislike response missing responseContext"
        )
        self.assertIsNotNone(val.actions, "Dislike response missing actions")
        self.assertGreater(
            len(val.actions), 0, "Dislike response has empty actions list"
        )

        # Reset to indifferent
        res = self.yt.rate_song(video_id, ytmusicapi.LikeStatus.INDIFFERENT)
        logging.info(f"Indifferent response: {res}")
        with open("debug_indifferent_response.json", "w") as f:
            json.dump(res, f, indent=2)
        val = RateSongResponse.model_validate(res)
        self.assertIsNotNone(
            val.response_context, "Indifferent response missing responseContext"
        )


if __name__ == "__main__":
    # from lib.net.client import auto_login
    import sys
    import os
    from pathlib import Path

    # Add parent directory to sys.path for imports
    # sys.path.append(str(Path(__file__).parent.parent.parent.resolve()))
    dir = Path(__file__).parent.parent.resolve()
    print(f"Adding {dir} to sys.path for imports")
    sys.path.append(str(dir))

    from lib.net.api import auto_login

    unittest.main()
