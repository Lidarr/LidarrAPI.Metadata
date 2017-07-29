import os

import peewee

from lidarrmetadata import config

database = peewee.SqliteDatabase(config.CONFIG.DB_FILE, threadlocals=True)


class BaseModel(peewee.Model):
    class Meta:
        database = database


class Album(BaseModel):
    mbId = peewee.CharField(null=False)
    title = peewee.CharField(null=False)
    release_date = peewee.DateTimeField(null=False)


class Artist(BaseModel):
    mbId = peewee.CharField(null=False)
    artist_name = peewee.CharField(null=False)
    overview = peewee.CharField(null=True)

    def __repr__(self):
        return '<{class_name} {artist_name}>'.format(class_name=self.__class__.__name__, artist_name=self.artist_name)


class Image(BaseModel):
    url = peewee.CharField(null=False)
    media_type = peewee.CharField(null=True)


class Track(BaseModel):
    mbId = peewee.CharField(null=False)
    title = peewee.CharField(null=False)
    explicit = peewee.BooleanField(null=True)
    track_number = peewee.IntegerField(null=True)
