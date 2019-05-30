"""
Defines the custom redis cache backend which compresses pickle dumps
"""
import functools
import hashlib
import logging
import contextlib
import zlib
import asyncio
import asyncpg
import datetime

from aiocache.serializers import BaseSerializer, PickleSerializer
from aiocache.base import BaseCache

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)
logger.info('Have cache logger')

try:
    import cPickle as pickle
except ImportError:  # pragma: no cover
    import pickle
    
class CompressionSerializer(BaseSerializer):

    # This is needed because zlib works with bytes.
    # this way the underlying backend knows how to
    # store/retrieve values
    DEFAULT_ENCODING = None

    def dumps(self, value):
        return zlib.compress(pickle.dumps(value))

    def loads(self, value):
        if value is None:
            return None
        return pickle.loads(zlib.decompress(value))
    
class ExpirySerializer(PickleSerializer):
    """
    Allows an expiry time to be returned at the same time as the value
    """
    
    DEFAULT_ENCODING = None

    def loads(self, value):
        if value is None:
            return None, datetime.datetime.now(datetime.timezone.utc)
        return super().loads(value[0]), value[1]

def conn(func):
    @functools.wraps(func)
    async def wrapper(self, *args, _conn=None, **kwargs):
        if _conn is None:
            pool = await self._get_pool()
            async with pool.acquire() as _conn:
                return await func(self, *args, _conn=_conn, **kwargs)

        return await func(self, *args, _conn=_conn, **kwargs)

    return wrapper

class PostgresBackend:
    """
    Simple postgres cache.
    """

    def __init__(self,
                 endpoint='localhost',
                 port=5432,
                 user='abc',
                 password='abc',
                 db_name='lm_cache_db',
                 db_table='cache',
                 keep_expired=True,
                 loop=None,
                 **kwargs):
        
        self._db_host = endpoint
        self._db_port = port
        self._db_user = user
        self._db_password = password
        self._db_name = db_name
        self._db_table = db_table
        self._keep_expired = keep_expired

        self._pool = None
        self.__pool_lock = None
        self._loop = loop
        
        super().__init__(**kwargs)
        
    @property
    def _pool_lock(self):
        if self.__pool_lock is None:
            self.__pool_lock = asyncio.Lock()
        return self.__pool_lock
    
    async def _get_pool(self):
        async with self._pool_lock:
            if self._pool is None:
                
                # Initialize pool
                self._pool = await asyncpg.create_pool(host = self._db_host,
                                                       port = self._db_port,
                                                       user = self._db_user,
                                                       password = self._db_password,
                                                       database = self._db_name,
                                                       loop = self._loop,
                                                       statement_cache_size=0)
                
                # Make sure table is created
                async with self._pool.acquire() as _conn:
                    await self._create_table(_conn)
                
            return self._pool

    async def _close(self, *args, **kwargs):
        if self._pool is not None:
            await self._pool.close()
    
    async def _create_table(self, _conn=None):
        await _conn.execute(
            f"CREATE TABLE IF NOT EXISTS {self._db_table} (key varchar PRIMARY KEY, expires timestamp with time zone, value bytea);"
        )

        await _conn.execute(
            f"CREATE INDEX IF NOT EXISTS {self._db_table}_expires_idx ON {self._db_table}(expires);"
        )
            
    @conn
    async def _get(self, key, encoding="utf-8", _conn=None):
        try:
            logger.debug(f"getting {key}")
            result = await _conn.fetchrow(
                f"SELECT value, expires FROM {self._db_table} WHERE key = $1;",
                key
            )
            logger.debug(f"got {key}")
            if result is not None:
                return result
        except KeyError:
            return None
        return None

    @conn
    async def _set(self, key, value, ttl=None, _cas_token=None, _conn=None):
        if ttl is not None:
            expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds = ttl)
            await _conn.execute(
                f"INSERT INTO {self._db_table} (key, expires, value) "
                "VALUES ($1, $2, $3) "
                "ON CONFLICT(key) DO UPDATE "
                "SET expires = EXCLUDED.expires, "
                "value = EXCLUDED.value;",
                key, expiry, value
            )
        else:
            await _conn.execute(
                f"INSERT INTO {self._db_table} (key, expires, value) "
                "VALUES ($1, NULL, $2) "
                "ON CONFLICT(key) DO UPDATE "
                "SET expires = EXCLUDED.expires, "
                "value = EXCLUDED.value;",
                key, value
            )
        return True

    @conn
    async def _delete(self, key, _conn=None):
        await _conn.execute(
            f"DELETE FROM {self._db_table} WHERE key = %s;",
            key
        )
        return True

class PostgresCache(PostgresBackend, BaseCache):
    """
    Cache implementation using postgres table
    """
    
    NAME = "postgres"
    
    def __init__(self, serializer=None, **kwargs):
        super().__init__(**kwargs)
        self.serializer = serializer or ExpirySerializer()

class NullCache(BaseCache):
    """
    Dummy cache that doesn't store any data
    """
    
    NAME = "dummy"
    
    def __init__(self, serializer=None, **kwargs):
        super().__init__(**kwargs)
        self.serializer = serializer or PickleSerializer()
    
    async def _get(self, key, encoding="utf-8", _conn=None):
        return None
    
    async def _set(self, key, value, ttl=None, _cas_token=None, _conn=None):
        return True
