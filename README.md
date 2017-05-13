# django-dbfs
Fuse filesystem stored in database

Mount specified virtual volume. The volume is automaticaly created, when used for the first time.
The mount point may be specified as an optional parameter or taken from `settings.DBFS_MOUNTPOINTS[volume]`.
If not overriden by `settings.DBFS_MOUNTPOINTS`, default mount point for volume `MEDIA` is `settings.MEDIA_ROOT`.

## Examples

```bash
# mount virtual volume MEDIA under directory specified in settings.MEDIA_ROOT
./manage.py dbfs --allow-other --foreground MEDIA

# mount virtual volume my_volume under directory ./mnt
./manage.py dbfs --allow-other my_volume ./mnt

# umount fuse filesystem under under directory ./mnt
fusermount -u ./mnt
```
