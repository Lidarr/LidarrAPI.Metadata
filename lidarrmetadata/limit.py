import atexit
from contextlib import contextmanager
from multiprocessing import Queue, Process, Value

import time

class RateLimitedError(Exception):
    pass

class QueueRateLimiter(object):
    """
    Rate limiter that limits by having a queue of items. A background progress is used to expire items from the queue
    at a predetermined interval. The call is allowed to proceed and an item is added to the queue if there is room
    and a ``RateLimitedError`` is raised if not. This approach is more flexible that a plain time difference as bursts
    of events can be allowed.
    """
    def __init__(self, queue_size=60, time_delta=10):
        self.queue_size = queue_size
        self.time_delta = time_delta

    def _allowed(self):
        pass

    def _put(self):
        pass

    @contextmanager
    def limited(self):
        if self._allowed():
            self._put()
            yield
        else:
            raise RateLimitedError()

class RedisRateLimiter(QueueRateLimiter):
    """
    TODO Implement this for handling rate limiting across server instances
    """
    pass

class SimpleRateLimiter(QueueRateLimiter):
    """
    Simple queue-based rate limiter that uses a ``multiprocessing.Queue``
    """
    QUEUE_STOP = 'stop'

    def __init__(self, queue_size=60, time_delta=100):
        super(SimpleRateLimiter, self).__init__(queue_size, time_delta)

        self._queue = Queue(queue_size)
        self._running = Value('b', True)

        self._pop_process = Process(target=self._pop_old)
        self._pop_process.start()

        # Register to be closed at the end. This isn't ideal, but flask doesn't give us a shutdown hook
        atexit.register(self.close)


    def close(self):
        # Poison pill the queue
        self._running.value = False
        self._pop_process.join()

    def _put(self):
        self._queue.put(time.time())

    def _pop_old(self):
        while self._running.value:
            if not self._queue.empty():
                self._queue.get()

            time.sleep(self.time_delta / 1000)

    def _allowed(self):
        return not self._queue.full()


if __name__ == '__main__':
    rl = SimpleRateLimiter(5, 100)

    last = time.time()
    for _ in range(20):
        try:
            with rl.limited():
                time.sleep(0.01)
                now = time.time()
                print(now - last)
                last = now
        except RateLimitedError:
                print('Rate limited')