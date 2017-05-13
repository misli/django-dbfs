import grp
import itertools
import pwd

from threading import Lock


class ThreadSafeCounter(itertools.count):
    def __init__(self):
        self._lock = Lock()

    def next(self):
        with self._lock:
            return super(ThreadSafeCounter, self).next()


_groups_cache = {}


def get_groups(uid, gid):
    if (uid, gid) not in _groups_cache:
        _groups_cache[(uid, gid)] = [
            g.gr_gid
            for g in grp.getgrall()
            if g.gr_gid == gid or pwd.getpwuid(uid).pw_name in g.gr_mem
        ]
    return _groups_cache[(uid, gid)]
