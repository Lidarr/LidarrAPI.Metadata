import os
from peewee import *

DATABASE_PATH = os.path.abspath('./music.db')
database = SqliteDatabase(DATABASE_PATH, threadlocals=True)

class BaseModel(Model):
	class Meta:
		database = database

class Album(BaseModel):
	mbId = CharField(null=False)
	title = CharField(null=False)
	release_date = DateTimeField(null=False)

class Artist(BaseModel):
	mbId = CharField(null=False)
	artist_name = CharField(null=False)
	overview = CharField(null=True)
	#expires = TimestampField(null=False)

class Image(BaseModel):
	url = CharField(null=False)
	media_type = CharField(null=True)

class Track(BaseModel):
	mbId = CharField(null=False)
	title = CharField(null=False)
	explicit = BooleanField(null=True)
	track_number = IntegerField(null=True)