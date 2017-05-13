from __future__ import unicode_literals

import errno
import os
import stat
from time import time

from django.db import transaction
from fuse import FuseOSError, Operations, fuse_get_context

from .file import BLOCK_SIZE, OpenFile
from .models import Inode, TreeNode
from .utils import ThreadSafeCounter, get_groups

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

    def _resolve(self, path, context=None):
        context = context or fuse_get_context()
        node = self._root_node()
        for part in path[1:].split(os.path.sep):
            if part:
                self._access(node.inode, os.X_OK, context)
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
        self._access(self._resolve(path).inode, amode)

    def _access(self, inode, amode, context=None):
        # others
        if (inode.mode & amode) == amode:
            return  # OK
        uid, gid, pid = context or fuse_get_context()
        # root
        if uid == 0:
            return  # OK
        # owner
        if inode.uid == uid and ((inode.mode >> 6) & amode) == amode:
            return  # OK
        # group
        if inode.gid in get_groups(uid, gid) and ((inode.mode >> 3) & amode) == amode:
            return  # OK
        raise FuseOSError(errno.EACCES)

    @transaction.atomic
    def chmod(self, path, mode):
        inode = self._resolve(path).inode
        if fuse_get_context()[0] not in (0, inode.uid):
            raise FuseOSError(errno.EACCES)
        inode.mode = mode
        inode.save_mode()
        return 0

    @transaction.atomic
    def chown(self, path, uid, gid):
        inode = self._resolve(path).inode
        if fuse_get_context()[0] != 0:
            raise FuseOSError(errno.EACCES)
        if uid != -1:
            inode.uid = uid
        if gid != -1:
            inode.gid = gid
        inode.save_uid_gid()
        return 0

    def destroy(self, path):
        for f in self._files.values():
            f.close()

    @transaction.atomic
    def getattr(self, path, fh=None):
        context = fuse_get_context()
        node = self._resolve(path, context)
        if node.parent:
            self._access(node.parent.inode, os.R_OK, context)
        return self._resolve(path).inode.stat()

    def readdir(self, path, fh):
        context = fuse_get_context()
        node = self._resolve(path, context)
        self._access(node.inode, os.R_OK, context)
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
        uid, gid, pid = fuse_get_context()
        if parent is not None:
            self._access(parent.inode, os.X_OK | os.W_OK, (uid, gid, pid))
        try:
            return TreeNode.objects.create(
                parent=parent,
                name=filename,
                inode=Inode.objects.create(
                    mode=mode,
                    uid=uid,
                    gid=gid,
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
        context = fuse_get_context()
        node = self._resolve(path, context)
        self._access(node.parent.inode, os.W_OK, context)
        if node.children.exclude(name__in=('.', '..')).exists():
            raise FuseOSError(errno.ENOTEMPTY)
        node.delete()

    @transaction.atomic
    def unlink(self, path):
        context = fuse_get_context()
        node = self._resolve(path, context)
        self._access(node.parent.inode, os.W_OK, context)
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
        context = fuse_get_context()
        node = self._resolve(old, context)
        self._access(node.parent.inode, os.W_OK, context)
        old_dirname, old_name = os.path.split(old)
        new_dirname, new_name = os.path.split(new)
        now = time()
        if old_dirname != new_dirname:
            new_parent = self._resolve(new_dirname, context)
            self._access(new_parent.inode, os.W_OK, context)
        node.name = new_name
        # update parent's mtime
        node.parent.inode.mtime = now
        node.parent.inode.save_times()
        if old_dirname != new_dirname:
            # change parent
            node.parent = new_parent
            if stat.S_ISDIR(node.inode.mode):
                # update .. link to new parent
                node.children.filter(name='..').update(inode=new_parent.inode)
            # update new parent's mtime
            new_parent.inode.mtime = now
            new_parent.inode.save_times()
        node.save()

    @transaction.atomic
    def link(self, target, source):
        dirname, filename = os.path.split(target)
        context = fuse_get_context()
        parent = self._resolve(dirname, context)
        self._access(parent.inode, os.W_OK, context)
        self._link(parent, filename, self._resolve(source, context))

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
        context = fuse_get_context()
        inode = self._resolve(path, context).inode
        self._access(inode, os.W_OK, context)
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
        context = fuse_get_context()
        inode = self._resolve(path, context).inode
        if flags == os.O_RDONLY:
            self._access(inode, os.R_OK, context)
        else:
            self._access(inode, os.W_OK, context)
        return self._open(inode, flags)

    def opendir(self, path):
        context = fuse_get_context()
        inode = self._resolve(path, context).inode
        self._access(inode, os.X_OK, context)
        return self._open(inode, os.O_RDONLY)

    def _open(self, inode, flags):
        fh = next(self._fh_counter)
        self._files[fh] = OpenFile(inode, flags)
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

    releasedir = release

    @transaction.atomic
    def fsync(self, path, fdatasync, fh):
        self._resolve_file(fh).flush()
