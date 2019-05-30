import asyncio
import datetime
from datetime import timedelta
import logging
from timeit import default_timer as timer

import aiohttp

import lidarrmetadata
from lidarrmetadata.config import get_config
from lidarrmetadata import provider
from lidarrmetadata import util
from lidarrmetadata import limit
from lidarrmetadata.api import get_artist_info, get_release_group_info_basic

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)
logger.info('Have crawler logger')

CONFIG = get_config()

async def update_wikipedia(count = 50, max_ttl = 60 * 60):
    
    # Use an aiohttp session which only allows a single concurrent connection per host to be nice
    # https://www.mediawiki.org/wiki/API:Etiquette
    # Only put timeout on sock_read - otherwise we can get timed out waiting for a connection from the pool.
    # Don't make these count towards rate limiting.
    async with aiohttp.ClientSession(timeout = aiohttp.ClientTimeout(sock_read = 2), connector = aiohttp.TCPConnector(limit_per_host=1)) as session:
        wikipedia_provider = provider.WikipediaProvider(session, limit.NullRateLimiter())

        while True:
            keys = await util.WIKI_CACHE.get_stale(count, provider.utcnow() + timedelta(seconds = max_ttl))
            logger.debug(f"Got {len(keys)} stale wikipedia items to refresh")

            start = timer()
            await asyncio.gather(*(wikipedia_provider.get_artist_overview(url, ignore_cache=True) for url in keys))
            logger.debug(f"Refreshed {len(keys)} wikipedia overviews in {timer() - start}s")

            # If there weren't any to update sleep, otherwise continue
            if not keys:
                await asyncio.sleep(60)

            
async def update_fanart(count = 500, max_ttl = 60 * 60):
    # Use an aiohttp session which only allows 10 concurrent connections per host to be (a little bit) nice
    # Only put timeout on sock_read - otherwise we can get timed out waiting for a connection from the pool.
    # Don't make these count towards rate limiting.
    async with aiohttp.ClientSession(
            timeout = aiohttp.ClientTimeout(sock_read = 2), 
            connector = aiohttp.TCPConnector(limit_per_host=10)
    ) as session:
        fanart_provider = provider.FanArtTvProvider(
            CONFIG.FANART_KEY, 
            session=session, 
            limiter=limit.NullRateLimiter()
        )

        while True:
            keys = await util.FANART_CACHE.get_stale(count, provider.utcnow() + timedelta(seconds = max_ttl))
            logger.debug(f"Got {len(keys)} stale fanart items to refresh")

            start = timer()
            await asyncio.gather(*(fanart_provider.refresh_images(mbid) for mbid in keys))
            logger.debug(f"Refreshed {len(keys)} fanart keys in {timer() - start}s")

            # If there weren't any to update sleep, otherwise continue
            if not keys:
                await asyncio.sleep(60)
            
async def initialize_artists():
    id_provider = provider.get_providers_implementing(provider.ArtistIdListMixin)[0]
    await id_provider._init()
    
    ids = await id_provider.get_all_artist_ids()
    
    pairs = [(id, None) for id in ids]
    
    await util.ARTIST_CACHE.clear()
    await util.ARTIST_CACHE.multi_set(pairs, ttl=0, timeout=None)
    
async def initialize_albums():
    id_provider = provider.get_providers_implementing(provider.ReleaseGroupIdListMixin)[0]
    await id_provider._init()
    
    ids = await id_provider.get_all_release_group_ids()
    
    pairs = [(id, None) for id in ids]
    
    await util.ALBUM_CACHE.clear()
    await util.ALBUM_CACHE.multi_set(pairs, ttl=0, timeout=None)
    
async def update_item(cached_function, mbid):
    function = cached_function.__wrapped__
    cache = cached_function.__cache__
    cache_key = f"{function.__name__}:{mbid}"
    
    result, expiry = await function(mbid)
    ttl = (expiry - provider.utcnow()).total_seconds()
    
    await cache.set(mbid, result, ttl)
            
async def update_artists(count = 100, max_ttl = 60 * 60):
    while True:
        keys = await util.ARTIST_CACHE.get_stale(count, provider.utcnow() + timedelta(seconds = max_ttl))
        logger.debug(f"Got {len(keys)} stale artists to refresh")

        start = timer()
        await asyncio.gather(*(update_item(get_artist_info, mbid) for mbid in keys))
        logger.debug(f"Refreshed {len(keys)} artists in {timer() - start}s")
        
        # If there weren't any to update sleep, otherwise continue
        if not keys:
            await asyncio.sleep(60)

async def update_albums(count = 100, max_ttl = 60 * 60):
    while True:
        keys = await util.ALBUM_CACHE.get_stale(count, provider.utcnow() + timedelta(seconds = max_ttl))
        logger.debug(f"Got {len(keys)} stale albums to refresh")

        start = timer()
        await asyncio.gather(*(update_item(get_release_group_info_basic, mbid) for mbid in keys))
        logger.debug(f"Refreshed {len(keys)} albums in {timer() - start}s")

        # If there weren't any to update sleep, otherwise continue
        if not keys:
            await asyncio.sleep(60)
        
async def crawl():
    async_providers = provider.get_providers_implementing(provider.AsyncInit)
    for prov in async_providers:
        await prov._init()
        
    await asyncio.gather(
        update_wikipedia(max_ttl = 60 * 60),
        update_fanart(max_ttl = 60 * 60),
        update_artists(max_ttl = 60 * 60),
        update_albums(max_ttl = 60 * 60)
    )
    
def main():
    asyncio.run(crawl())
    
if __name__ == "__main__":
    main()
        
        
