import sys
from optparse import OptionParser

from django.conf import settings
from django.core.management import get_commands, load_command_class
from django.core.management.base import (BaseCommand, handle_default_options,
                                         CommandError)
from django.db import connections


from raven import Client
from raven.transport.requests import RequestsHTTPTransport

from django_maven.compat import OutputWrapper


class Command(BaseCommand):

    help = 'Capture exceptions and send in Sentry'
    args = '<command>'

    def _get_subcommand_class(self, command):
        commands = get_commands()
        app_name = commands[command]
        return load_command_class(app_name, command)

    def run_from_argv(self, argv):
        """ Modified version of parent class to send errors in the command to Sentry.
        """
        if len(argv) <= 2 or argv[2] in ['-h', '--help']:
            print(self.usage(argv[1]))
            sys.exit(1)

        subcommand_class = self._get_subcommand_class(argv[2])
        parser = self.create_parser(argv[0], argv[2])
        subcommand_class.add_arguments(parser)
        options = parser.parse_args(argv[3:])
        cmd_options = vars(options)
        args = cmd_options.pop('args', ())
            
            
        self._called_from_command_line = True

        handle_default_options(options)
        try:
            subcommand_class.execute(*args, **cmd_options)
        except Exception as e:
            if options.traceback or not isinstance(e, CommandError):
                if hasattr(settings, 'SENTRY_DSN'):
                    dsn = settings.SENTRY_DSN
                elif hasattr(settings, 'RAVEN_CONFIG'):
                    dsn = settings.RAVEN_CONFIG.get('dsn')
                else:
                    raise
                # Force sync transport to avoid race condition with the process exiting
                sentry = Client(dsn, transport=RequestsHTTPTransport)
                sentry.get_ident(sentry.captureException())
                
            # SystemCheckError takes care of its own formatting.
            if isinstance(e, SystemCheckError):
                self.stderr.write(str(e), lambda x: x)
            else:
                self.stderr.write('%s: %s' % (e.__class__.__name__, e))
            sys.exit(1)
        finally:
            connections.close_all()
