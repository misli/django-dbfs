from __future__ import unicode_literals

from time import time

from django.db import models


class Inode(models.Model):
    inuse = models.IntegerField(default=0)
    mode = models.IntegerField(default=0)
    uid = models.IntegerField(default=0)
    gid = models.IntegerField(default=0)
    atime = models.IntegerField(default=0)
    mtime = models.IntegerField(default=0)
    ctime = models.IntegerField(default=0)
    size = models.BigIntegerField(default=0)

    def stat(self):
        return {
            'st_mode': self.mode,
            'st_uid': self.uid,
            'st_gid': self.gid,
            'st_atime': self.ctime,
            'st_mtime': self.mtime,
            'st_ctime': self.ctime,
            'st_size': self.size,
            'st_nlink': self.nodes.count(),
        }

    def inuse_increment(self):
        Inode.objects.filter(pk=self.pk).update(inuse=models.F('inuse') + 1)

    def inuse_decrement(self):
        Inode.objects.filter(pk=self.pk).update(inuse=models.F('inuse') - 1)
        self.try_delete()

    def save_mode(self):
        self.ctime = time()
        Inode.objects.filter(pk=self.pk).update(mode=self.mode, ctime=self.ctime)

    def save_uid_gid(self):
        self.ctime = time()
        Inode.objects.filter(pk=self.pk).update(uid=self.uid, gid=self.gid, ctime=self.ctime)

    def save_times(self):
        Inode.objects.filter(pk=self.pk).update(atime=self.atime, ctime=self.ctime, mtime=self.mtime)

    def save_size(self):
        self.ctime = time()
        self.mtime = time()
        Inode.objects.filter(pk=self.pk).update(size=self.size, ctime=self.ctime, mtime=self.mtime)

    def try_delete(self):
        if self.nodes.count() == 0:
            Inode.objects.filter(pk=self.pk, inuse=0).delete()


class Block(models.Model):
    inode = models.ForeignKey(Inode, on_delete=models.CASCADE, related_name='blocks')
    sequence = models.BigIntegerField()
    data = models.BinaryField()

    class Meta:
        unique_together = (('inode', 'sequence'),)

    def __hash__(self):
        return hash((self.inode, self.sequence))


class TreeNode(models.Model):
    parent = models.ForeignKey('self', null=True, on_delete=models.CASCADE, related_name='children')
    name = models.CharField(max_length=255)
    inode = models.ForeignKey(Inode, on_delete=models.CASCADE, related_name='nodes')

    class Meta:
        unique_together = (('parent', 'name'),)

    def delete(self):
        super(TreeNode, self).delete()
        self.inode.try_delete()
