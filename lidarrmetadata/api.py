import os
import uuid
import functools
import asyncio

import redis
import datetime
from datetime import timedelta
import time
import logging
import aiohttp
from timeit import default_timer as timer

import lidarrmetadata
from lidarrmetadata import config
from lidarrmetadata import provider
from lidarrmetadata import util

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.info('Have api logger')

CONFIG = config.get_config()

# Set up providers
for provider_name, (args, kwargs) in CONFIG.PROVIDERS.items():
    provider_key = list(filter(lambda k: k.upper() == provider_name,
                               provider.PROVIDER_CLASSES.keys()))[0]
    lower_kwargs = {k.lower(): v for k, v in kwargs.items()}
    provider.PROVIDER_CLASSES[provider_key](*args, **lower_kwargs)

def validate_mbid(mbid, check_blacklist=True):
    """
    Validates Musicbrainz ID and returns flask response in case of error
    :param mbid: Musicbrainz ID to verify
    :param check_blacklist: Checks blacklist for blacklisted ids. Defaults to True
    :return: Flask response if error, None if valid
    """
    try:
        uuid.UUID(mbid, version=4)
    except ValueError:
        return jsonify(error='Invalid UUID'), 400

    if check_blacklist and mbid in config.get_config().BLACKLISTED_ARTISTS:
        return jsonify(error='Blacklisted artist'), 403

async def get_overview(links, mbid=None):

    overview = ''
    expiry = provider.utcnow() + timedelta(days=365)
    overview_providers = provider.get_providers_implementing(provider.ArtistOverviewMixin)    

    if overview_providers:
        wikidata_link = next(filter(
            lambda link: 'wikidata' in link.get('type', ''),
            links), None)
        wikipedia_link = next(filter(
            lambda link: 'wikipedia' in link.get('type', ''),
            links), None)

        if wikidata_link:
            overview, expiry = await overview_providers[0].get_artist_overview(wikidata_link['target'])
        elif wikipedia_link:
            overview, expiry = await overview_providers[0].get_artist_overview(wikipedia_link['target'])

        if len(overview_providers) > 1 and mbid and not overview:
            overview, expiry = await overview_providers[1].get_artist_overview(mbid)

    return overview, expiry

# Decorator to cache in redis and postgres
def postgres_cache(cache):
    def decorator(function):
        @functools.wraps(function)
        async def wrapper(*args, **kwargs):
            
            mbid = args[0]
            
            now = provider.utcnow()

            cached, expiry = await cache.get(mbid)
            if cached and expiry > now:
                return cached, expiry
            
            result, expiry = await function(*args, **kwargs)
            ttl = (expiry - now).total_seconds()
            
            await cache.set(mbid, result, ttl=ttl)
            return result, expiry

        wrapper.__cache__ = cache
        return wrapper
    return decorator

class ArtistNotFoundException(Exception):
    def __init__(self, mbid):
        super().__init__(f"Artist not found: {mbid}")
        self.mbid = mbid

class MissingProviderException(Exception):
    """ Thown when we can't cope without a provider """

@postgres_cache(util.ARTIST_CACHE)
async def get_artist_info(mbid):

    artists = await get_artist_info_multi([mbid])
    if not artists:
        raise ArtistNotFoundException(mbid)
    
    return artists[0]

async def get_artist_info_multi(mbids):
    
    start = timer()

    artist_providers = provider.get_providers_implementing(provider.ArtistByIdMixin)
    artist_art_providers = provider.get_providers_implementing(provider.ArtistArtworkMixin)
    
    if not artist_providers:
        # 500 error if we don't have an artist provider since it's essential
        raise MissingProviderException('No artist provider available')
    
    expiry = provider.utcnow() + timedelta(seconds = CONFIG.CACHE_TTL['cloudflare'])
    
    # Do the main DB query
    artists = await artist_providers[0].get_artists_by_id(mbids)
    if not artists:
        return None
    
    # Add in default expiry
    artists = [{'data': artist, 'expiry': expiry} for artist in artists]
    
    # Start overviews
    overviews_task = asyncio.gather(*[get_overview(artist['data']['links'], artist['data']['id']) for artist in artists])
    
    if artist_art_providers:
        results = await asyncio.gather(*[artist_art_providers[0].get_artist_images(x['data']['id']) for x in artists])
        
        for i, artist in enumerate(artists):
            images, expiry = results[i]
            artist['data']['images'] = images
            artist['expiry'] = min(artist['expiry'], expiry)

        if len(artist_art_providers) > 1:
            image_types = {'Banner', 'Fanart', 'Logo', 'Poster'}
            artists_without_images = [x for x in artists if not x['data']['images'] or not image_types.issubset({i['CoverType'] for i in x['data']['images']})]
            results = await asyncio.gather(*[artist_art_providers[1].get_artist_images(x['data']['id']) for x in artists_without_images])

            for i, artist in enumerate(artists_without_images):
                images, expiry = results[i]
                artist['data']['images'] = combine_images(artist['data']['images'], images)
                artist['expiry'] = min(artist['expiry'], expiry)
    else:
        for artist in artists:
            artist['images'] = []

    # Get overview results
    results = await overviews_task
    for i, artist in enumerate(artists):
        overview, expiry = results[i]
        artist['data']['overview'] = overview
        artist['expiry'] = min(artist['expiry'], expiry)
            
    logger.debug(f"Got basic artist info for {len(mbids)} artists in {(timer() - start) * 1000:.0f}ms ")

    return [(item['data'], item['expiry']) for item in artists]

def combine_images(a, b):
    result = a
    extra_types = {i['CoverType'] for i in b} - {i['CoverType'] for i in a}
    extra_images = [i for i in b if i['CoverType'] in extra_types]
    result.extend(extra_images)

    return result

async def get_artist_albums(mbid):
    release_group_providers = provider.get_providers_implementing(
        provider.ReleaseGroupByArtistMixin)
    if release_group_providers and not mbid in CONFIG.BLACKLISTED_ARTISTS:
        return await release_group_providers[0].get_release_groups_by_artist(mbid)
    else:
        return []

async def get_release_group_artists(release_group):
    
    start = timer()
    
    results = await asyncio.gather(*[get_artist_info(gid) for gid in release_group['artistids']])
                                   
    artists = [result[0] for result in results]
    expiry = min([result[1] for result in results])
    
    logger.debug(f"Got album artists in {(timer() - start) * 1000:.0f}ms ")
    
    return artists, expiry

class ReleaseGroupNotFoundException(Exception):
    def __init__(self, mbid):
        super().__init__(f"Album not found: {mbid}")
        self.mbid = mbid

@postgres_cache(util.ALBUM_CACHE)
async def get_release_group_info_basic(mbid):
    
    release_groups = await get_release_group_info_multi([mbid])
    if not release_groups:
        raise ReleaseGroupNotFoundException(mbid)
    
    return release_groups[0]

async def get_release_group_info_multi(mbids):
    
    start = timer()
    
    release_group_providers = provider.get_providers_implementing(provider.ReleaseGroupByIdMixin)
    album_art_providers = provider.get_providers_implementing(provider.AlbumArtworkMixin)
    
    if not release_group_providers:
        raise MissingProviderException('No album provider available')

    expiry = provider.utcnow() + timedelta(seconds = CONFIG.CACHE_TTL['cloudflare'])

    # Do the main DB query
    release_groups = await release_group_providers[0].get_release_groups_by_id(mbids)
    if not release_groups:
        return None

    # Add in default expiry
    release_groups = [{'data': rg, 'expiry': expiry} for rg in release_groups]
    
    # Start overviews
    overviews_task = asyncio.gather(*[get_overview(rg['data']['links']) for rg in release_groups])
    
    # Get fanart images (and prefer those if possible)
    if album_art_providers:
        results = await asyncio.gather(*[album_art_providers[0].get_album_images(x['data']['id']) for x in release_groups])
        
        for i, rg in enumerate(release_groups):
            images, expiry = results[i]
            rg['data']['images'] = combine_images(images, rg['data']['images'])
            rg['expiry'] = min(rg['expiry'], expiry)

    # Get overview results
    results = await overviews_task
    for i, rg in enumerate(release_groups):
        overview, expiry = results[i]
        rg['data']['overview'] = overview
        rg['expiry'] = min(rg['expiry'], expiry)
    
    logger.debug(f"Got basic album info for {len(mbids)} albums in {(timer() - start) * 1000:.0f}ms ")

    return [(item['data'], item['expiry']) for item in release_groups]

async def get_release_group_info(mbid):

    release_group, rg_expiry = await get_release_group_info_basic(mbid)
    artists, artist_expiry = await get_release_group_artists(release_group)
    
    release_group['artists'] = artists
    del release_group['artistids']
    
    return release_group, min(rg_expiry, artist_expiry)
