"""
data_models.py

Dataclasses related to configuration
"""

from dataclasses    import dataclass
from typing         import List


#################
## CREDENTIALS ##
#################


@dataclass(frozen=True)
class SpeedrunCredentials:
    """speedrun.com API credentials"""

    csrf: str
    session: str


@dataclass(frozen=True)
class TwitchCredentials:
    """Twitch API credentials"""

    client: str
    secret: str


@dataclass(frozen=True)
class Credentials:
    """Representation of API credentials used by bot"""

    src: SpeedrunCredentials
    twitch: TwitchCredentials


###############
## GAME INFO ##
###############

@dataclass(frozen=True)
class PendingValues:
    """Representation of data for Pending submissions."""
    pending_id: str
    category_var_id: str


@dataclass(frozen=True)
class Game:
    """speedrun.com game representation"""

    id: str
    name: str
    pending: PendingValues


@dataclass(frozen=True)
class SMOGames:
    """Repesentation of data for collection of all SMO games"""

    games: List[Game]
