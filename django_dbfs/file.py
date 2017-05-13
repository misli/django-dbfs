from __future__ import unicode_literals

import errno
import os

from django.conf import settings
from fuse import FuseOSError

from .models import Block

# 19 bits is 512kB
BLOCK_BITS = int(getattr(settings, 'DBFS_BLOCK_BITS', 19))
BLOCK_SIZE = 1 << BLOCK_BITS
BLOCK_MASK = BLOCK_SIZE - 1

BLOCKS_READ_AHEAD = int(getattr(settings, 'DBFS_BLOCKS_READ_AHEAD=', 10))


def block_offset(offset):
    return offset & BLOCK_MASK


class OpenFile(object):

    def __init__(self, inode, flags):
        self.inode = inode
        self.flags = flags

        if self.flags & os.O_APPEND:
            self.offset = self.inode.size
        else:
            self.offset = 0

        self._blocks = {}
        self._dirty_blocks = set()

        self.inode.inuse_increment()

    def _block(self):
        sequence = self.offset >> BLOCK_BITS
        if sequence not in self._blocks:
            self._load_blocks(sequence)
        if sequence not in self._blocks:
            block = Block()
            block.inode = self.inode
            block.sequence = sequence
            self._blocks[sequence] = block
        return self._blocks[sequence]

    def _load_blocks(self, sequence):
        for block in self.inode.blocks.filter(
            sequence__gte=sequence,
            sequence__lt=sequence + BLOCKS_READ_AHEAD,
        ):
            if block.sequence not in self._blocks:
                self._blocks[block.sequence] = block

    def seek(self, offset):
        self.offset = offset

    def read(self, length):
        if self.flags & os.O_WRONLY:
            raise FuseOSError(errno.EACCES)
        data = b''
        length = min(self.inode.size - self.offset, length)
        while length:
            block_offset = self.offset & BLOCK_MASK
            size = min(length, BLOCK_SIZE - block_offset)
            block = self._block()
            data += block.data[block_offset:block_offset + size].ljust(size, b'\x00')
            length -= size
            self.offset += size
        return data

    def write(self, buf):
        if self.flags == os.O_RDONLY:
            raise FuseOSError(errno.EACCES)
        length = len(buf)
        while buf:
            block_offset = self.offset & BLOCK_MASK
            size = min(len(buf), BLOCK_SIZE - block_offset)
            block = self._block()
            block.data = block.data[:block_offset].ljust(block_offset, b'\x00') + buf[:size]
            buf = buf[size:]
            self.offset += size
            self.inode.size = max(self.inode.size, self.offset)
            self._dirty_blocks.add(block)
        return length

    def flush(self, *args):
        if self._dirty_blocks:
            for block in self._dirty_blocks:
                block.save()
            self.inode.save_size()

    def truncate(self, length):
        if self.flags == os.O_RDONLY:
            raise FuseOSError(errno.EACCES)
        self.inode.size = length
        self.inode.save_size()

    def close(self, *args):
        self.inode.inuse_decrement()
