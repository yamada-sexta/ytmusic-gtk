
from pydantic import TypeAdapter
from pydantic import BaseModel, Field
from typing import List, Optional

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
    artists: Optional[List[Artist]] = None
    thumbnails: Optional[List[Thumbnail]] = None

class Song(BaseMedia):
    duration: str
    played: str

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
    type: str # e.g., "Album", "Single"
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

class History(BaseModel):
    songs: List[Song]

Songs = TypeAdapter(List[Song])

class HomeItem(BaseMedia):
    # Tracks & Quick Picks
    playlist_id: Optional[str] = Field(None, alias="playlistId")
    views: Optional[str] = None
    video_type: Optional[str] = Field(None, alias="videoType")
    is_explicit: Optional[bool] = Field(None, alias="isExplicit")
    album: Optional[Album] = None
    
    # Playlists & Mixes
    description: Optional[str] = None
    count: Optional[str] = None
    # Note: Playlists often use 'author' instead of 'artists', 
    # but the data structure inside is identical to 'Artist'
    author: Optional[List[Artist]] = None 

class HomeSection(BaseModel):
    title: str
    contents: List[HomeItem]

# Since the root of the Home data is a List (not a dictionary), 
# we use TypeAdapter just like you did for History.
HomePage = TypeAdapter(List[HomeSection])