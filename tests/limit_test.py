import time

import pytest

from lidarrmetadata import limit

class TestSimpleRateLimiter(object):
    def setup(self):
        self.limiter = limit.SimpleRateLimiter(queue_size=5, time_delta=1000)

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
                time.sleep(0.5)