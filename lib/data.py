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
    id: str


class PodcastInfo(BaseModel):
    id: str
    name: str


class BaseMedia(BaseModel):
    title: str
    video_id: Optional[str] = Field(None, alias="videoId")
    browse_id: Optional[str] = Field(None, alias="browseId")
    artists: Optional[list[Artist]] = None
    thumbnails: Optional[list[Thumbnail]] = None


class Song(BaseMedia):
    duration: str
    played: str


class Track(BaseMedia):
    length: str
    like_status: Optional[Literal["INDIFFERENT", "LIKE", "DISLIKE"]] = Field(
        None, alias="likeStatus"
    )
    video_type: Optional[str] = Field(None, alias="videoType")
    in_library: Optional[bool] = Field(None, alias="inLibrary")
    album: Optional[Album] = None
    year: Optional[str] = None
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


def test():
    import logging


import unittest
import ytmusicapi


class TestYtMusicDataParsing(unittest.TestCase):
    yt: ytmusicapi.YTMusic

    @classmethod
    def setUpClass(cls):
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


if __name__ == "__main__":
    from lib.net.client import auto_login

    unittest.main()
