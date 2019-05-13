"""
Defines the custom redis cache backend which compresses pickle dumps
"""
import functools
import hashlib
import logging
from flask_caching import Cache
from flask_caching.backends.rediscache import RedisCache

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.info('Have provider logger')

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
