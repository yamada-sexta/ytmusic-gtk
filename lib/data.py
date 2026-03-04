from ytmusicapi import LikeStatus
from pydantic import TypeAdapter
from pydantic import BaseModel, Field
from typing import Literal, Optional


class AccountInfo(BaseModel):
    # Field aliases map the JSON key to your Python variable
    account_name: str = Field(alias="accountName")
    channel_handle: str = Field(alias="channelHandle")
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
    like_status: Optional[Literal["LIKE", "DISLIKE", "INDIFFERENT"]] = Field(None, alias="likeStatus")
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


import unittest
import ytmusicapi


class TestYtMusicDataParsing(unittest.TestCase):
    yt: ytmusicapi.YTMusic

    @classmethod
    def setUpClass(cls):
        from lib.net.client import auto_login

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


if __name__ == "__main__":
    from lib.net.client import auto_login

    unittest.main()
