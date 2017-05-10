from __future__ import unicode_literals

import errno
import os
import stat
from time import time

from django.db import transaction
from fuse import FuseOSError, Operations

from .file import BLOCK_SIZE, OpenFile
from .models import Inode, TreeNode
from .utils import ThreadSafeCounter

# for some reason you can't get umask without changing it
UMASK = os.umask(0)
os.umask(UMASK)


class DbFs(Operations):

    def __init__(self, volume):
        self.volume = volume

        self._nodes = {}
        self._fh_counter = ThreadSafeCounter()
        self._files = {}

        # create root node while in single thread
        self._root_node()

    # Helpers
    # =======

    def _root_node(self):
        try:
            root_node = TreeNode.objects.get(parent=None, name=self.volume)
        except TreeNode.DoesNotExist:
            root_node = self._mknod(None, self.volume, stat.S_IFDIR | (0777 & ~UMASK))
            self._link(root_node, '.', root_node.inode)
            self._link(root_node, '..', root_node.inode)
        return root_node

    def _resolve(self, path):
        node = self._root_node()
        for part in path[1:].split(os.path.sep):
            if part:
                node = self._resolve_subnode(node, part)
        return node

    def _resolve_subnode(self, node, name):
        try:
            return node.children.get(name=name)
        except:
            raise FuseOSError(errno.ENOENT)

    def _resolve_file(self, fh):
        try:
            return self._files[fh]
        except KeyError:
            raise FuseOSError(errno.ENOENT)

    # Filesystem methods
    # ==================

    def access(self, path, amode):
        return 0

    @transaction.atomic
    def chmod(self, path, mode):
        inode = self._resolve(path).inode
        inode.mode = mode
        inode.save_mode()
        return 0

    @transaction.atomic
    def chown(self, path, uid, gid):
        inode = self._resolve(path).inode
        if uid != -1:
            inode.uid = uid
        if gid != -1:
            inode.gid = gid
        inode.save_uid_gid()
        return 0

    def destroy(self, path):
        for f in self._files.values():
            f.close()
        print('destroyed')

    @transaction.atomic
    def getattr(self, path, fh=None):
        return self._resolve(path).inode.stat()

    def readdir(self, path, fh):
        node = self._resolve(path)
        for node in node.children.all():
            yield node.name

    @transaction.atomic
    def readlink(self, path):
        fh = self.open(path, os.O_RDONLY)
        try:
            return self.read(path, BLOCK_SIZE, 0, fh)
        finally:
            self.release(path, fh)

    @transaction.atomic
    def mknod(self, path, mode, dev):
        dirname, filename = os.path.split(path)
        self._mknod(self._resolve(dirname), filename, mode)

    def _mknod(self, parent, filename, mode):
        now = time()
        try:
            return TreeNode.objects.create(
                parent=parent,
                name=filename,
                inode=Inode.objects.create(
                    mode=mode,
                    uid=os.getuid(),
                    gid=os.getgid(),
                    atime=now,
                    mtime=now,
                    ctime=now,
                ),
            )
        except:
            raise FuseOSError(errno.EEXIST)

    @transaction.atomic
    def mkdir(self, path, mode):
        dirname, filename = os.path.split(path)
        node = self._mknod(self._resolve(dirname), filename, stat.S_IFDIR | mode)
        self._link(node, '.', node.inode)
        self._link(node, '..', node.parent.inode)

    @transaction.atomic
    def rmdir(self, path):
        node = self._resolve(path)
        if node.children.exclude(name__in=('.', '..')).exists():
            raise FuseOSError(errno.ENOTEMPTY)
        node.delete()

    @transaction.atomic
    def unlink(self, path):
        self._resolve(path).delete()

    @transaction.atomic
    def symlink(self, target, source):
        fh = self.create(target, stat.S_IFLNK | 0777)
        try:
            self.write(target, source, 0, fh)
            self.flush(target, fh)
        finally:
            self.release(target, fh)

    @transaction.atomic
    def rename(self, old, new):
        now = time()
        node = self._resolve(old)
        old_dirname, old_name = os.path.split(old)
        new_dirname, new_name = os.path.split(new)
        node.name = new_name
        # update parent's mtime
        node.parent.inode.mtime = now
        node.parent.inode.save_times()
        if old_dirname != new_dirname:
            # change parent
            node.parent = self._resolve(new_dirname)
            # update .. link to new parent
            node.children.filter(name='..').update(inode=node.parent.inode)
            # update new parent's mtime
            node.parent.inode.mtime = now
            node.parent.inode.save_times()
        node.save()

    @transaction.atomic
    def link(self, target, source):
        dirname, filename = os.path.split(target)
        self._link(self._resolve(dirname), filename, self._resolve(source))

    def _link(self, parent, name, inode):
        try:
            node = TreeNode.objects.create(parent=parent, name=name, inode=inode)
            inode.ctime = time()
            inode.save_times()
        except:
            raise FuseOSError(errno.EEXIST)
        return node

    @transaction.atomic
    def utimens(self, path, times=None):
        inode = self._resolve(path).inode
        if times:
            inode.atime, inode.mtime = times
        else:
            inode.atime = inode.mtime = time()
        inode.save_times()
        return 0

    # File methods
    # ============

    @transaction.atomic
    def create(self, path, mode, fi=None):
        self.mknod(path, mode, 0)
        return self.open(path, os.O_WRONLY)

    def open(self, path, flags):
        fh = next(self._fh_counter)
        node = self._resolve(path)
        self._files[fh] = OpenFile(node, flags)
        return fh

    def read(self, path, length, offset, fh):
        f = self._resolve_file(fh)
        f.seek(offset)
        return f.read(length)

    def write(self, path, buf, offset, fh):
        f = self._resolve_file(fh)
        f.seek(offset)
        return f.write(buf)

    @transaction.atomic
    def truncate(self, path, length, fh=None):
        if fh is None:
            fh = self.open(path, os.O_WRONLY)
        self._resolve_file(fh).truncate(length)

    @transaction.atomic
    def flush(self, path, fh):
        self._resolve_file(fh).flush()

    def release(self, path, fh):
        self._resolve_file(fh).close()
        del self._files[fh]

    @transaction.atomic
    def fsync(self, path, fdatasync, fh):
        self._resolve_file(fh).flush()
