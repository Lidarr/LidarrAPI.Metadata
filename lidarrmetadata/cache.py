"""
Defines the custom redis cache backend which compresses pickle dumps
"""
import functools
import hashlib
import logging
import contextlib
import psycopg2
import psycopg2.extensions
from psycopg2 import sql

from flask_caching import Cache
from flask_caching.backends.rediscache import RedisCache
from flask_caching.backends.base import BaseCache

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.info('Have cache logger')

try:
    import cPickle as pickle
except ImportError:  # pragma: no cover
    import pickle

# always get strings from database in unicode
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

class RedisGzipCache(RedisCache):
    def dump_object(self, value):
        return super(RedisGzipCache, self).dump_object(value).encode('zlib')
    
    def load_object(self, value):
        if value is None:
            return None
        return super(RedisGzipCache, self).load_object(value.decode('zlib'))

## https://github.com/sh4nks/flask-caching/blob/master/flask_caching/backends/__init__.py#L68
def redis_gzip(app, config, args, kwargs):
    try:
        from redis import from_url as redis_from_url
    except ImportError:
        raise RuntimeError("no redis module found")

    kwargs.update(
        dict(
            host=config.get("CACHE_REDIS_HOST", "localhost"),
            port=config.get("CACHE_REDIS_PORT", 6379),
        )
    )
    password = config.get("CACHE_REDIS_PASSWORD")
    if password:
        kwargs["password"] = password

    key_prefix = config.get("CACHE_KEY_PREFIX")
    if key_prefix:
        kwargs["key_prefix"] = key_prefix

    db_number = config.get("CACHE_REDIS_DB")
    if db_number:
        kwargs["db"] = db_number

    redis_url = config.get("CACHE_REDIS_URL")
    if redis_url:
        kwargs["host"] = redis_from_url(redis_url, db=kwargs.pop("db", None))

    return RedisGzipCache(*args, **kwargs)

class LidarrCache(Cache):
    def memoize_variable_timeout(
        self,
        make_name=None,
        unless=None,
        forced_update=None,
        hash_method=hashlib.md5,
    ):
        def memoize(f):
            @functools.wraps(f)
            def decorated_function(*args, **kwargs):
                #: bypass cache
                if self._bypass_cache(unless, f, *args, **kwargs):
                    return f(*args, **kwargs)

                try:
                    cache_key = decorated_function.make_cache_key(
                        f, *args, **kwargs
                    )

                    if callable(forced_update) and forced_update() is True:
                        rv, cache_timeout = None, 0
                    else:
                        result = self.cache.get(cache_key)
                        if result is not None:
                            rv, cache_timeout = result
                        else:
                            rv, cache_timeout = None, 0
                except Exception:
                    if self.app.debug:
                        raise
                    logger.exception(
                        "Exception possibly due to cache backend."
                    )
                    return f(*args, **kwargs)

                if rv is None:
                    rv, cache_timeout = f(*args, **kwargs)
                    if cache_timeout > 0:
                        try:
                            self.cache.set(
                                cache_key,
                                (rv, cache_timeout),
                                timeout=cache_timeout,
                            )
                        except Exception:
                            if self.app.debug:
                                raise
                            logger.exception(
                                "Exception possibly due to cache backend."
                            )
                return (rv, cache_timeout)

            decorated_function.uncached = f
            decorated_function.cache_timeout = -1
            decorated_function.make_cache_key = self._memoize_make_cache_key(
                make_name=make_name,
                timeout=decorated_function,
                forced_update=forced_update,
                hash_method=hash_method,
            )
            decorated_function.delete_memoized = lambda: self.delete_memoized(f)

            return decorated_function

        return memoize

class PostgresCache(BaseCache):
    """
    Simple postgres cache.
    """

    def __init__(self,
                 host='localhost',
                 port=5432,
                 user='abc',
                 password='abc',
                 db_name='lm_cache_db',
                 db_table='cache',
                 default_timeout=300,
                 keep_expired=True,
                 ignore_errors=False):
        super(PostgresCache, self).__init__(default_timeout)
        
        self._db_host = host
        self._db_port = port
        self._db_user = user
        self._db_password = password
        self._db_name = db_name
        self._db_table = db_table
        self._keep_expired = keep_expired
        self.ignore_errors = ignore_errors
        
        self._create_table()

    @contextlib.contextmanager
    def _cursor(self):
        connection = psycopg2.connect(host=self._db_host,
                                      port=self._db_port,
                                      dbname=self._db_name,
                                      user=self._db_user,
                                      password=self._db_password,
                                      connect_timeout=5)
        cursor = connection.cursor()
        yield cursor
        connection.commit()
        cursor.close()
        connection.close()
        
    def _create_table(self):
        with self._cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE TABLE IF NOT EXISTS {table} (key varchar PRIMARY KEY, expires timestamp with time zone, value bytea);")
                .format(table=sql.Identifier(self._db_table)
                )
            )
            cursor.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {index} ON {table}(expires);")
                .format(
                    index=sql.Identifier("{}_expires_idx".format(self._db_table)),
                    table=sql.Identifier(self._db_table)
                )
            )
            
    def _prune(self):
        if not self._keep_expired:
            with self._cursor() as cursor:
                cursor.execute(
                    sql.SQL("DELETE FROM {table} WHERE expires IS NOT NULL AND expires < NOW();")
                    .format(table=sql.Identifier(self._db_table))
                )
                
    def clear(self):
        return True

    def get(self, key):
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT value, expires < NOW() as expired FROM {table} WHERE key = %s;")
                    .format(table=sql.Identifier(self._db_table)),
                    (key,)
                );
                result = cursor.fetchone()
                if result is not None:
                    return pickle.loads(str(result[0])), result[1]
        except (KeyError, pickle.PickleError):
            return None, True
        return None, True

    def set(self, key, value, timeout=None):
        timeout = self._normalize_timeout(timeout)
        self._prune()
        with self._cursor() as cursor:
            if timeout > 0:
                cursor.execute(
                    sql.SQL("INSERT INTO {table} (key, expires, value) "
                            "VALUES (%s, NOW() + interval '%s seconds', %s) "
                            "ON CONFLICT(key) DO UPDATE "
                            "SET expires = EXCLUDED.expires, "
                            "value = EXCLUDED.value;")
                    .format(table=sql.Identifier(self._db_table)),
                    (key, timeout, psycopg2.Binary(pickle.dumps(value, pickle.HIGHEST_PROTOCOL)))
                )
            else:
                cursor.execute(
                    sql.SQL("INSERT INTO {table} (key, expires, value) "
                            "VALUES (%s, NULL, %s) "
                            "ON CONFLICT(key) DO UPDATE "
                            "SET expires = EXCLUDED.expires, "
                            "value = EXCLUDED.value;")
                    .format(table=sql.Identifier(self._db_table)),
                    (key, psycopg2.Binary(pickle.dumps(value, pickle.HIGHEST_PROTOCOL)))
                )
        return True

    def add(self, key, value, timeout=None):
        raise Exception('Add not implemented')

    def delete(self, key):
        with self._cursor() as cursor:
            cursor.execute(
                sql.SQL("DELETE FROM {table} WHERE key = %s;")
                .format(table=sql.Identifier(self._db_table)),
                (key,)
            )
        return True

    def has(self, key):
        raise Exception('Has not implemented')

def postgres(app, config, args, kwargs):
    kwargs.update(
        dict(
            host=config.get("CACHE_HOST", "localhost"),
            port=config.get("CACHE_PORT", 5432),
        )
    )
    
    user = config.get("CACHE_USER")
    if user:
        kwargs["user"] = user
    
    password = config.get("CACHE_PASSWORD")
    if password:
        kwargs["password"] = password

    db_name = config.get("CACHE_DATABASE")
    if db_name:
        kwargs["db_name"] = db_name

    db_table = config.get("CACHE_TABLE")
    if db_table:
        kwargs["db_table"] = db_table
        
    keep_expired = config.get("CACHE_KEEP_EXPIRED")
    if keep_expired:
        kwargs["keep_expired"] = keep_expired

    return PostgresCache(*args, **kwargs)
