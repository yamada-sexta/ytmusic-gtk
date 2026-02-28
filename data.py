
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
    id: str

class Song(BaseModel):
    video_id: str = Field(alias="videoId")
    title: str
    artists: List[Artist]
    duration: str
    played: str
    # You can add more fields here if you need them later (like 'album')

# This allows us to parse the whole list at once
class History(BaseModel):
    songs: List[Song]

Songs = TypeAdapter(List[Song])