"""
Models for music-related data (artists, albums, etc.).
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ArtistImage(BaseModel):
    """Artist image information"""
    url: str = Field(..., description="Image URL")
    width: Optional[int] = Field(None, description="Image width in pixels")
    height: Optional[int] = Field(None, description="Image height in pixels")
    image_type: Optional[str] = Field(None, alias="type", description="Image type (front, back, etc.)")


class Album(BaseModel):
    """Album/Release Group information"""
    id: str = Field(..., alias="Id", description="MusicBrainz release group ID")
    title: str = Field(..., alias="Title", description="Album title")
    primary_type: Optional[str] = Field(None, alias="Type", description="Primary release group type")
    secondary_types: List[str] = Field(default_factory=list, alias="SecondaryTypes", description="Secondary release group types")
    release_statuses: List[str] = Field(default_factory=list, alias="ReleaseStatuses", description="Release statuses")
    disambiguation: Optional[str] = Field(None, alias="Disambiguation", description="Disambiguation comment")
    release_date: Optional[str] = Field(None, alias="ReleaseDate", description="Release date")
    
    class Config:
        allow_population_by_field_name = True
        extra = "allow"


class Artist(BaseModel):
    """Artist information response"""
    id: str = Field(..., alias="Id", description="MusicBrainz artist ID")
    name: str = Field(..., alias="Name", description="Artist name")
    sort_name: Optional[str] = Field(None, alias="SortName", description="Artist sort name")
    disambiguation: Optional[str] = Field(None, alias="Disambiguation", description="Disambiguation comment")
    artist_type: Optional[str] = Field(None, alias="Type", description="Artist type")
    gender: Optional[str] = Field(None, alias="Gender", description="Artist gender")
    area: Optional[str] = Field(None, alias="Area", description="Artist area/location")
    begin_date: Optional[str] = Field(None, alias="BeginDate", description="Artist begin date")
    end_date: Optional[str] = Field(None, alias="EndDate", description="Artist end date")
    ended: bool = Field(default=False, alias="Ended", description="Whether the artist has ended")
    
    # Additional fields that might be present
    links: List[Dict[str, Any]] = Field(default_factory=list, alias="Links", description="External links")
    images: List[ArtistImage] = Field(default_factory=list, alias="Images", description="Artist images")
    albums: List[Album] = Field(default_factory=list, alias="Albums", description="Artist albums")
    
    class Config:
        allow_population_by_field_name = True
        extra = "allow"


class ArtistFilterParams(BaseModel):
    """Query parameters for artist endpoint filtering"""
    primary_types: Optional[str] = Field(None, alias="primTypes", description="Primary release group types (pipe-separated)")
    secondary_types: Optional[str] = Field(None, alias="secTypes", description="Secondary release group types (pipe-separated)")
    release_statuses: Optional[str] = Field(None, alias="releaseStatuses", description="Release statuses (pipe-separated)")
    
    class Config:
        allow_population_by_field_name = True