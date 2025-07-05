import os
import uuid
import functools
import asyncio

import redis
import datetime
from datetime import timedelta
import time
import aiohttp
from timeit import default_timer as timer

import lidarrmetadata
from lidarrmetadata import config
from lidarrmetadata import provider
from lidarrmetadata import util
from lidarrmetadata.logging_config import get_logger

logger = get_logger(__name__)
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
            try:
                result = await overview_providers[0].get_artist_overview(wikidata_link['target'])
                if result and len(result) == 2:
                    overview, expiry = result
            except Exception as e:
                logger.warning(f"Failed to get overview from wikidata: {e}")
        elif wikipedia_link:
            try:
                result = await overview_providers[0].get_artist_overview(wikipedia_link['target'])
                if result and len(result) == 2:
                    overview, expiry = result
            except Exception as e:
                logger.warning(f"Failed to get overview from wikipedia: {e}")

        if len(overview_providers) > 1 and mbid and not overview:
            try:
                result = await overview_providers[1].get_artist_overview(mbid)
                if result and len(result) == 2:
                    overview, expiry = result
            except Exception as e:
                logger.warning(f"Failed to get overview from fallback provider: {e}")

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
        artist_provider = provider.get_providers_implementing(provider.ArtistByIdMixin)[0]
        new_id = await artist_provider.redirect_old_artist_id(mbid)
        artists = await get_artist_info_multi([new_id])
        
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
    
    # Start overviews with proper task-to-artist mapping
    overview_coroutines = [get_overview(artist['data']['links'], artist['data']['id']) for artist in artists]
    overview_tasks = [asyncio.create_task(coro) for coro in overview_coroutines]
    done, pending = await asyncio.wait(overview_tasks, timeout=10)
    logger.debug("Got artist overviews", extra={'results': len(done), 'pending': len(pending)})
    for task in pending:
        task.cancel()
    
    # Map completed tasks back to their corresponding artists
    task_to_index = {task: i for i, task in enumerate(overview_tasks)}
    overview_results = {}
    for task in done:
        if not task.cancelled():
            try:
                result = task.result()
                index = task_to_index[task]
                overview_results[index] = result
            except Exception as e:
                logger.warning(f"Overview task failed for artist {task_to_index.get(task, 'unknown')}: {e}")
                if task in task_to_index:
                    overview_results[task_to_index[task]] = (None, provider.utcnow())
    if artist_art_providers:
        # Create artist images tasks with proper mapping
        image_coroutines = [artist_art_providers[0].get_artist_images(x['data']['id']) for x in artists]
        # Filter out None values that might be returned by non-async methods
        image_coroutines = [coro for coro in image_coroutines if coro is not None]
        if image_coroutines:
            image_tasks = [asyncio.create_task(coro) for coro in image_coroutines]
            done, pending = await asyncio.wait(image_tasks, timeout=10)
            logger.debug("Got artist images", extra={'results': len(done), 'pending': len(pending)})
            for task in pending:
                task.cancel()
            
            # Map completed tasks back to their corresponding artists
            task_to_index = {task: i for i, task in enumerate(image_tasks)}
            image_results = {}
            for task in done:
                if not task.cancelled():
                    try:
                        result = task.result()
                        index = task_to_index[task]
                        image_results[index] = result
                    except Exception as e:
                        logger.warning(f"Artist image task failed for artist {task_to_index.get(task, 'unknown')}: {e}")
                        if task in task_to_index:
                            image_results[task_to_index[task]] = ([], provider.utcnow())
        else:
            logger.debug("No artist image coroutines to process")
            image_results = {}
        
        # Apply image results to artists
        for i, artist in enumerate(artists):
            if i in image_results:
                result = image_results[i]
                if result and len(result) == 2:
                    images, expiry = result
                    artist['data']['images'] = images
                    artist['expiry'] = min(artist['expiry'], expiry)
                else:
                    artist['data']['images'] = []
            else:
                artist['data']['images'] = []

        if len(artist_art_providers) > 1:
            image_types = {'Banner', 'Fanart', 'Logo', 'Poster'}
            artists_without_images = [x for x in artists if not x['data']['images'] or not image_types.issubset({i['CoverType'] for i in x['data']['images']})]
            if artists_without_images:
                # Get image coroutines and filter out None values
                image_coroutines = [artist_art_providers[1].get_artist_images(x['data']['id']) for x in artists_without_images]
                image_coroutines = [coro for coro in image_coroutines if coro is not None]
                
                if image_coroutines:
                    results = await asyncio.gather(*image_coroutines, return_exceptions=True)
                    
                    for i, artist in enumerate(artists_without_images):
                        if i < len(results):
                            result = results[i]
                            if not isinstance(result, Exception) and result is not None:
                                try:
                                    if len(result) == 2:
                                        images, expiry = result
                                        artist['data']['images'] = combine_images(artist['data']['images'], images)
                                        artist['expiry'] = min(artist['expiry'], expiry)
                                    else:
                                        logger.warning(f"Second artist art provider returned invalid result length for artist {i}: {result}")
                                except (TypeError, AttributeError):
                                    logger.warning(f"Second artist art provider returned non-sequence result for artist {i}: {type(result)}")
                            else:
                                if isinstance(result, Exception):
                                    logger.warning(f"Second artist art provider failed for artist {i}: {result}")
                                else:
                                    logger.warning(f"Second artist art provider returned invalid result for artist {i}: {result}")
    else:
        for artist in artists:
            artist['images'] = []

    # Apply overview results to artists
    for i, artist in enumerate(artists):
        if i in overview_results:
            overview, expiry = overview_results[i]
            artist['data']['overview'] = overview
            artist['expiry'] = min(artist['expiry'], expiry)
        else:
            artist['data']['overview'] = None
            
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
    
    if not release_group.get('artistids'):
        return [], provider.utcnow()
    
    # Use asyncio.gather with return_exceptions to handle failures
    results = await asyncio.gather(*[get_artist_info(gid) for gid in release_group['artistids']], 
                                   return_exceptions=True)
    
    # Filter out exceptions and validate results
    valid_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"Failed to get artist info for {release_group['artistids'][i]}: {result}")
        elif result and hasattr(result, '__len__') and len(result) == 2:
            valid_results.append(result)
        else:
            logger.warning(f"Invalid result from get_artist_info for {release_group['artistids'][i]}: {result}")
    
    if not valid_results:
        return [], provider.utcnow()
    
    artists = [result[0] for result in valid_results]
    expiry = min([result[1] for result in valid_results])
    
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

        album_provider = provider.get_providers_implementing(provider.ReleaseGroupByIdMixin)[0]
        new_id = await album_provider.redirect_old_release_group_id(mbid)
        release_groups = await get_release_group_info_multi([new_id])

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
    
    # Start overviews with timeout and error handling
    overview_coroutines = [get_overview(rg['data']['links']) for rg in release_groups]
    overview_tasks = [asyncio.create_task(coro) for coro in overview_coroutines if coro is not None]
    if overview_tasks:
        done, pending = await asyncio.wait(overview_tasks, timeout=10)
        for task in pending:
            task.cancel()
        
        # Map completed tasks back to their corresponding release groups
        task_to_index = {task: i for i, task in enumerate(overview_tasks)}
        overview_results = {}
        for task in done:
            if not task.cancelled():
                try:
                    result = task.result()
                    index = task_to_index[task]
                    if result and hasattr(result, '__len__') and len(result) == 2:
                        overview_results[index] = result
                    else:
                        overview_results[index] = (None, provider.utcnow())
                except Exception as e:
                    logger.warning(f"Overview task failed for release group {task_to_index.get(task, 'unknown')}: {e}")
                    if task in task_to_index:
                        overview_results[task_to_index[task]] = (None, provider.utcnow())
    else:
        overview_results = {}
    
    # Get fanart images (and prefer those if possible)
    if album_art_providers:
        image_coroutines = [album_art_providers[0].get_album_images(x['data']['id']) for x in release_groups]
        image_coroutines = [coro for coro in image_coroutines if coro is not None]
        if image_coroutines:
            image_tasks = [asyncio.create_task(coro) for coro in image_coroutines]
            done, pending = await asyncio.wait(image_tasks, timeout=10)
            for task in pending:
                task.cancel()
            
            # Map completed tasks back to their corresponding release groups
            task_to_index = {task: i for i, task in enumerate(image_tasks)}
            image_results = {}
            for task in done:
                if not task.cancelled():
                    try:
                        result = task.result()
                        index = task_to_index[task]
                        if result and hasattr(result, '__len__') and len(result) == 2:
                            image_results[index] = result
                        else:
                            image_results[index] = ([], provider.utcnow())
                    except Exception as e:
                        logger.warning(f"Image task failed for release group {task_to_index.get(task, 'unknown')}: {e}")
                        if task in task_to_index:
                            image_results[task_to_index[task]] = ([], provider.utcnow())
        else:
            image_results = {}
        
        # Apply image results to release groups
        for i, rg in enumerate(release_groups):
            if i in image_results:
                images, expiry = image_results[i]
                rg['data']['images'] = combine_images(images, rg['data']['images'])
                rg['expiry'] = min(rg['expiry'], expiry)

    # Apply overview results to release groups
    for i, rg in enumerate(release_groups):
        if i in overview_results:
            overview, expiry = overview_results[i]
            rg['data']['overview'] = overview
            rg['expiry'] = min(rg['expiry'], expiry)
        else:
            rg['data']['overview'] = None
    
    logger.debug(f"Got basic album info for {len(mbids)} albums in {(timer() - start) * 1000:.0f}ms ")

    return [(item['data'], item['expiry']) for item in release_groups]

async def get_release_group_info(mbid):

    release_group, rg_expiry = await get_release_group_info_basic(mbid)
    artists, artist_expiry = await get_release_group_artists(release_group)
    
    release_group['artists'] = artists
    del release_group['artistids']
    
    return release_group, min(rg_expiry, artist_expiry)
