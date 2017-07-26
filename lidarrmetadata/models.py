import os

import peewee

DATABASE_PATH = os.path.abspath('./music.db')
database = peewee.SqliteDatabase(DATABASE_PATH, threadlocals=True)


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
    #expires = TimestampField(null=False)


class Image(BaseModel):
    url = peewee.CharField(null=False)
    media_type = peewee.CharField(null=True)


class Track(BaseModel):
    mbId = peewee.CharField(null=False)
    title = peewee.CharField(null=False)
    explicit = peewee.BooleanField(null=True)
    track_number = peewee.IntegerField(null=True)
