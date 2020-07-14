import argparse
import asyncio
import datetime
from datetime import timedelta
import logging
from timeit import default_timer as timer
import sys

import aiohttp
import sentry_sdk

import lidarrmetadata
from lidarrmetadata.config import get_config
from lidarrmetadata import provider
from lidarrmetadata import util
from lidarrmetadata import limit
from lidarrmetadata.api import get_artist_info_multi, ArtistNotFoundException, get_release_group_info_multi, ReleaseGroupNotFoundException

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)
logger.info('Have crawler logger')

CONFIG = get_config()

if CONFIG.SENTRY_DSN:
    if CONFIG.SENTRY_REDIS_HOST is not None:
        processor = util.SentryRedisTtlProcessor(redis_host=CONFIG.SENTRY_REDIS_HOST,
                                                 redis_port=CONFIG.SENTRY_REDIS_PORT,
                                                 ttl=CONFIG.SENTRY_TTL)
    else:
        processor = util.SentryTtlProcessor(ttl=CONFIG.SENTRY_TTL)
        
    sentry_sdk.init(dsn=CONFIG.SENTRY_DSN,
                    before_send=processor.create_event,
                    send_default_pii=True)

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
            logger.debug(f"Refreshed {len(keys)} wikipedia overviews in {timer() - start:.1f}s")

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
            logger.debug(f"Refreshed {len(keys)} fanart keys in {timer() - start:.1f}s")

            # If there weren't any to update sleep, otherwise continue
            if not keys:
                await asyncio.sleep(60)

async def update_tadb(count = 500, max_ttl = 60 * 60):
    # Use an aiohttp session which only allows 10 concurrent connections per host to be (a little bit) nice
    # Only put timeout on sock_read - otherwise we can get timed out waiting for a connection from the pool.
    # Don't make these count towards rate limiting.
    # TADB is slow as balls so put in a big timeout.
    async with aiohttp.ClientSession(
            timeout = aiohttp.ClientTimeout(sock_read = 10), 
            connector = aiohttp.TCPConnector(limit_per_host=20)
    ) as session:
        tadb_provider = provider.TheAudioDbProvider(
            CONFIG.TADB_KEY, 
            session=session, 
            limiter=limit.NullRateLimiter()
        )

        while True:
            keys = await util.TADB_CACHE.get_stale(count, provider.utcnow() + timedelta(seconds = max_ttl))
            logger.debug(f"Got {len(keys)} stale tadb items to refresh")

            start = timer()
            await asyncio.gather(*(tadb_provider.refresh_data(mbid) for mbid in keys))
            logger.debug(f"Refreshed {len(keys)} tadb keys in {timer() - start:.1f}s")

            # If there weren't any to update sleep, otherwise continue
            if not keys:
                await asyncio.sleep(60)
            
async def initialize_artists():
    id_provider = provider.get_providers_implementing(provider.ArtistIdListMixin)[0]
    
    ids = await id_provider.get_all_artist_ids()
    
    pairs = [(id, None) for id in ids]
    
    await util.ARTIST_CACHE.clear()
    await util.ARTIST_CACHE.multi_set(pairs, ttl=0, timeout=None)

async def initialize_tadb():
    id_provider = provider.get_providers_implementing(provider.ArtistIdListMixin)[0]
    
    ids = await id_provider.get_all_artist_ids()
    
    pairs = [(id, None) for id in ids]
    
    await util.TADB_CACHE.clear()
    await util.TADB_CACHE.multi_set(pairs, ttl=0, timeout=None)
    
async def initialize_albums():
    id_provider = provider.get_providers_implementing(provider.ReleaseGroupIdListMixin)[0]
    
    ids = await id_provider.get_all_release_group_ids()
    
    pairs = [(id, None) for id in ids]
    
    await util.ALBUM_CACHE.clear()
    await util.ALBUM_CACHE.multi_set(pairs, ttl=0, timeout=None)

async def initialize_spotify():
    link_provider = provider.get_providers_implementing(provider.ReleaseGroupByIdMixin)[0]

    maps = await link_provider.get_all_spotify_mappings()

    pairs = [(item['spotifyid'], item['mbid']) for item in maps]

    await util.SPOTIFY_CACHE.clear()
    await util.SPOTIFY_CACHE.multi_set(pairs, ttl=None, timeout=None)

async def update_items(multi_function, cache, name, count = 100, max_ttl = 60 * 60):
    while True:
        keys = await cache.get_stale(count, provider.utcnow() + timedelta(seconds = max_ttl))
        logger.debug(f"Got {len(keys)} stale {name}s to refresh")
        
        if keys:
            start = timer()
            results = await multi_function(keys)
            
            if not results:
                missing = keys
            else:
                missing = set(keys) - set(item['id'] for item, _ in results)
                
            if missing:
                logger.debug(f"Removing deleted {name}s:\n{missing}")
                await asyncio.gather(*(cache.delete(id) for id in missing))
                
            await asyncio.gather(*(cache.set(result['id'], result, ttl=(expiry - provider.utcnow()).total_seconds()) for result, expiry in results))
                
            logger.debug(f"Refreshed {len(keys)} {name}s in {timer() - start:.1f}s")

        else:
            # If there weren't any to update sleep, otherwise continue
            await asyncio.sleep(60)
    
async def crawl():
    await asyncio.gather(
        # Look further ahead for wiki and fanart so external data is ready before we refresh artist/album
        update_wikipedia(count = CONFIG.CRAWLER_BATCH_SIZE['wikipedia'], max_ttl = 60 * 60 * 2),
        update_fanart(count = CONFIG.CRAWLER_BATCH_SIZE['fanart'], max_ttl = 60 * 60 * 2),
        update_tadb(count = CONFIG.CRAWLER_BATCH_SIZE['tadb'], max_ttl = 60 * 60 * 2),
        update_items(get_artist_info_multi, util.ARTIST_CACHE, "artist", count = CONFIG.CRAWLER_BATCH_SIZE['artist']),
        update_items(get_release_group_info_multi, util.ALBUM_CACHE, "album", count = CONFIG.CRAWLER_BATCH_SIZE['album'])
    )
    
async def initialize():
    await asyncio.gather(
        initialize_artists(),
        initialize_albums()
    )
    
def main():
    
    parser = argparse.ArgumentParser(prog="lidarr-metadata-crawler")
    parser.add_argument("--initialize-artists", action="store_true")
    parser.add_argument("--initialize-albums", action="store_true")
    parser.add_argument("--initialize-spotify", action="store_true")
    
    args = parser.parse_args()
    
    if args.initialize_artists:
        asyncio.run(initialize_artists())
        sys.exit()

    if args.initialize_albums:
        asyncio.run(initialize_albums())
        sys.exit()

    if args.initialize_spotify:
        asyncio.run(initialize_spotify())
        sys.exit()
    
    asyncio.run(crawl())
    
if __name__ == "__main__":
    main()
