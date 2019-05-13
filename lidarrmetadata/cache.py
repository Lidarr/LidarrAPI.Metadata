"""
Defines the custom redis cache backend which compresses pickle dumps
"""
from flask_caching.backends.rediscache import RedisCache

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
