import itertools
from threading import Lock


class ThreadSafeCounter(itertools.count):
    def __init__(self):
        self._lock = Lock()

    def next(self):
        with self._lock:
            return super(ThreadSafeCounter, self).next()
