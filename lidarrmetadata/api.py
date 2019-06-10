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

async def get_artist_links_and_overview(mbid):
    link_providers = provider.get_providers_implementing(provider.ArtistLinkMixin)    
    links = await link_providers[0].get_artist_links(mbid)

    overview, expiry = await get_overview(links)
    
    return {'Links': links, 'Overview': overview}, expiry

async def get_overview(links):
    overview_providers = provider.get_providers_implementing(provider.ArtistOverviewMixin)    

    if overview_providers:
        wikidata_link = next(filter(
            lambda link: 'wikidata' in link.get('type', ''),
            links), None)
        wikipedia_link = next(filter(
            lambda link: 'wikipedia' in link.get('type', ''),
            links), None)

        if wikidata_link:
            return await overview_providers[0].get_artist_overview(wikidata_link['target'])
        elif wikipedia_link:
            return await overview_providers[0].get_artist_overview(wikipedia_link['target'])
        
    return '', provider.utcnow() + timedelta(days=365)

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
    pass

class MissingProviderException(Exception):
    """ Thown when we can't cope without a provider """

@postgres_cache(util.ARTIST_CACHE)
async def get_artist_info(mbid):
    
    expiry = provider.utcnow() + timedelta(seconds = CONFIG.CACHE_TTL['cloudflare'])
    
    # TODO A lot of repetitive code here. See if we can refactor
    artist_providers = provider.get_providers_implementing(provider.ArtistByIdMixin)
    artist_art_providers = provider.get_providers_implementing(provider.ArtistArtworkMixin)
    
    if not artist_providers:
        # 500 error if we don't have an artist provider since it's essential
        raise MissingProviderException('No artist provider available')

    # overviews are the slowest thing so set those going first, followed by images
    link_overview_task = asyncio.create_task(get_artist_links_and_overview(mbid))
    if artist_art_providers:
        images_task = asyncio.create_task(artist_art_providers[0].get_artist_images(mbid))
        
    # Await the overwiew and let the rest finish in meantime
    overview_data, overview_expiry = await link_overview_task
    
    artist = await artist_providers[0].get_artist_by_id(mbid)
    if not artist:
        raise ArtistNotFoundException(mbid)

    artist.update(overview_data)
    
    if artist_art_providers:
        images, image_expiry = await images_task
        artist['Images'] = images
    else:
        image_expiry = expiry
    
    expiry = min(expiry, overview_expiry, image_expiry)
        
    return artist, expiry

async def get_artist_albums(mbid):
    release_group_providers = provider.get_providers_implementing(
        provider.ReleaseGroupByArtistMixin)
    if release_group_providers:
        return await release_group_providers[0].get_release_groups_by_artist(mbid)
    else:
        return None

async def get_release_group_artists(release_group):
    
    start = timer()
    
    results = await asyncio.gather(*[get_artist_info(gid) for gid in release_group['artistids']])
                                   
    artists = [result[0] for result in results]
    expiry = min([result[1] for result in results])
    
    logger.debug(f"Got album artists in {(timer() - start) * 1000:.0f}ms ")
    
    return artists, expiry

class ReleaseGroupNotFoundException(Exception):
    pass

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
    
    # Do missing images
    if album_art_providers:
        release_groups_without_images = [x for x in release_groups if not x['data']['images']]
        results = await asyncio.gather(*[album_art_providers[0].get_album_images(x['data']['id']) for x in release_groups_without_images])
        
        for i, rg in enumerate(release_groups_without_images):
            images, expiry = results[i]
            rg['data']['images'] = images
            rg['expiry'] = min(rg['expiry'], expiry)
    else:
        for rg in release_groups_without_images:
            rg['images'] = []

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
