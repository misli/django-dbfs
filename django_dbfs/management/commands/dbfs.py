from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from fuse import FUSE

from ...fs import DbFs


class Command(BaseCommand):

    help = (
        'Mount specified virtual volume. The volume is automaticaly created, when used for the first time. '
        'The mount point may be specified as an optional parameter or taken from settings.DBFS_MOUNTPOINTS[volume]. '
        'If not overriden by settings.DBFS_MOUNTPOINTS, default mount point for volume MEDIA is settings.MEDIA_ROOT. '
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--allow-other',
            action='store_true',
            dest='allow_other',
            default=False,
            help=(
                'This option overrides the security measure restricting '
                'file access to the user mounting the filesystem. '
                'So all users (including root) can access the files. '
                'This option is by default only allowed to root, '
                'but this restriction can be removed with a configuration option `user_allow_other`. '
                'See fuse manual page for further information.'
            ),
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            dest='debug',
            default=False,
            help='Turns on debug information printing by the library.',
        )
        parser.add_argument(
            '--foreground',
            action='store_true',
            dest='foreground',
            default=False,
            help=(
                'Do not fork to background. '
                'This is usefull when debugging or for use with supervisord.'
            ),
        )
        parser.add_argument(
            '--nonempty',
            action='store_true',
            dest='nonempty',
            default=False,
            help=(
                'Allows mounts over a non-empty file or directory. '
                'By default these mounts are rejected to prevent accidental covering up of data, '
                'which could for example prevent automatic backup.'
            ),
        )
        parser.add_argument(
            '--nothreads',
            action='store_true',
            dest='nothreads',
            default=False,
            help=(
                'Do not use threads. Use this option if you use sqlite database backend. '
                'Bud note that you should avoid using sqlite database backend in production.'
            ),
        )
        parser.add_argument(
            '--options',
            action='store',
            dest='options',
            default='',
            help=(
                'Specify additional fuse options (comma separated). '
                'See fuse manual page for further information.'
            ),
        )
        parser.add_argument('volume', help='name of the virtual volume')
        parser.add_argument('mountpoint', nargs='?', help='mount point')

    def _parse_fuse_options(self, options):
        ''' parse fuse options given as one string
            'opt1=val1,opt2' => {'opt1': 'val1', 'opt2': True}
            '' => {}
        '''
        return {
            o[0]: o[1] if len(o) == 2 else True
            for o in [o.split('=', 1) for o in options.split(',')]
            if o[0]
        }

    def handle(self, volume, mountpoint, **options):
        if mountpoint is None:
            try:
                mountpoint = settings.DBFS_MOUNTPOINTS[volume]
            except (AttributeError, KeyError):
                if volume == 'MEDIA':
                    mountpoint = settings.MEDIA_ROOT
                else:
                    raise CommandError('Mountpoint for volume {} was not found in settings.DBFS_MOUNTPOINTS'.format(
                        volume,
                    ))

        FUSE(
            DbFs(volume),
            mountpoint,
            debug=options['debug'],
            foreground=options['foreground'],
            nothreads=options['nothreads'],
            allow_other=options['allow_other'],
            nonempty=options['nonempty'],
            **self._parse_fuse_options(options['options'])
        )
