from django.core.management.base import BaseCommand
from fuse import FUSE

from ...fs import DbFs


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--debug',
            action='store_true',
            dest='debug',
            default=False,
            help='enter debug mode',
        )
        parser.add_argument(
            '--foreground',
            action='store_true',
            dest='foreground',
            default=False,
            help='do not detach',
        )
        parser.add_argument(
            '--nothreads',
            action='store_true',
            dest='nothreads',
            default=False,
            help='no threads',
        )
        parser.add_argument(
            '--options',
            action='store',
            dest='options',
            default='',
            help='fuse mount options',
        )
        parser.add_argument('volume')
        parser.add_argument('mountpoint')


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
        FUSE(
            DbFs(volume),
            mountpoint,
            debug=options['debug'],
            foreground=options['foreground'],
            nothreads=options['nothreads'],
            **self._parse_fuse_options(options['options'])
        )
