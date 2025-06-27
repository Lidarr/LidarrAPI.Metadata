import time

import mockredis
import pytest

from lidarrmetadata import limit

# Patch our mock redis
limit.redis.Redis = mockredis.mock_redis_client


class BaseTestRateLimiter:
    
    def test_allowed(self):
        for _ in range(5):
            with self.limiter.limited():
                pass

    def test_error_raised(self):
        with pytest.raises(limit.RateLimitedError):
            for _ in range(6):
                with self.limiter.limited():
                    pass

    def test_queue_popped(self):
        for _ in range(10):
            with self.limiter.limited():
                time.sleep(1)


class TestSimpleRateLimiter(BaseTestRateLimiter):
    def setup_method(self, _):
        self.limiter = limit.SimpleRateLimiter(queue_size=5, time_delta=1000)


class TestRedisRateLimiter(BaseTestRateLimiter):
    def setup_method(self, method):
        print(method)
        self.limiter = limit.RedisRateLimiter(key=method.__name__, queue_size=5, time_delta=1000)

    def test_queue_popped(self):
        for _ in range(10):
            # Mock client doesn't support automatic expiration
            self.limiter._client.do_expire()
            with self.limiter.limited():
                time.sleep(1)
