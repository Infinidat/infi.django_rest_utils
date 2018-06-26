"""Command line utility for plucking fields from a JSON file.

Usage:
    rest_utils pluck <json-filename> <path>...

Options:
    -h --help                show this screen.
    -v --version             show version.
"""

from __future__ import absolute_import
from __future__ import print_function
from logging import getLogger
from sys import argv
logger = getLogger(__name__)


def rest_utils(argv=argv[1:]):
    from docopt import docopt
    from logging import basicConfig, DEBUG
    from .__version__ import __version__
    args = docopt(__doc__, version=__version__, argv=argv)
    basicConfig(level=DEBUG)
    if args['pluck'] and args['<json-filename>'] and args['<path>']:
        return pluck(args['<json-filename>'], args['<path>'])


def pluck(json_filename, paths):
    from .pluck import traverse
    from json import loads
    with open(json_filename) as f:
        raw = loads(f.read())
        for path in paths:
            results = traverse(path, raw)
            for result in results:
                print('{}\t{}'.format(*result))
