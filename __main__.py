"""
__main__.py

Reads out settings and CLI params and runs bot with them
"""

import json
from src_constants  import SMO_GAMES
from smo_bot    import SMOLeaderboardBot
from data_models    import Credentials
from dacite         import from_dict
from argparse       import ArgumentParser, Namespace

# argparse
parser : ArgumentParser = ArgumentParser(
    description='SMO speedrun.com bot to reject faulty submissions',
    allow_abbrev=True
)
parser.add_argument(
    '-c', '--credentials',
    type=str,
    help='path to credentials.json file',
    default='./credentials.json'
)
parser.add_argument(
    '-t', '--timer',
    type=int,
    help='interval between polls',
    default=60
)
parser.add_argument(
    '-m', '--milliseconds',
    type=int,
    help='Toggle milliseconds instance.',
    default=0
)
args : Namespace = parser.parse_args()
# read out credentials.json dict and parse to class
with open(args.credentials) as file:
    creds_d : dict = json.loads(file.read())
creds = from_dict(
    data_class=Credentials,
    data=creds_d
)
# create and start bot
SMOLeaderboardBot(creds, SMO_GAMES, args.timer, args.milliseconds).start()
