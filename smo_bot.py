"""
smo_bot.py
"""

from time               import sleep
from datetime           import datetime
from enum               import IntEnum
from data_models        import Credentials, PendingValues, SMOGames
from random             import randint, random
from requests.models    import Response
from urllib.parse       import ParseResult, urlparse
from twitch             import TwitchHelix
from twitch.exceptions  import TwitchAttributeException, TwitchOAuthException, TwitchAuthException
from twitch.constants   import OAUTH_SCOPE_ANALYTICS_READ_EXTENSIONS
import requests
import ms_remover
import asyncio
import re

__version__ = "1.1"

# funny API cache hack, SRC admins hate him
QUERY_TABLE : dict = {
    0 : "game",
    1 : "category",
    2 : "level",
    3 : "platform",
    4 : "region",
    5 : "emulated",
    6 : "date",
    7 : "submitted",
    8 : "status",
    9 : "verify-date"
}


def print_with_timestamp(out: str) -> None:
    print(datetime.today().strftime("%d.%m.%Y %H:%M:%S").ljust(24) + str(out))


class SubmissionErrors(IntEnum):
    ERROR_ICLOUD_VIDEO    = 0
    ERROR_TWITCH_BROADCAST= 1
    ERROR_INVALID_PENDING = 2


class SMOLeaderboardBot:
    """Class for leaderboard bot, interacting with speedrun.com API."""

    AGENT        : str = f'smo-lb-bot{__version__}'
    REASON_TEXT  : dict = {
        0 : "iCloud videos are not permanent videos. Please use another file hosting provider to submit runs.",
        1 : "This video is not highlighted and will expire in a few weeks. Please highlight the run and resubmit.",
        2 : "The \"Pending\" category is only to be utilized for categories that have been added by moderators. Please check the category rules for details on category submissions."
    }
    # regex for twitch videos ids, from my observation they are always 10 digits but leaving some leeway for potential backwards/forward compatibility
    TWITCH_ID_MATCH: re.Pattern = re.compile("^\d{9,11}$")

    def __init__(self, credentials: Credentials, games: SMOGames, timer: float, milliseconds: bool) -> None:
        self.q_counter  : int = 0
        self.CREDS      : Credentials  = credentials
        self.GAMES      : SMOGames     = games
        self.TIMER      : int          = int(timer)
        self.MS_CLIENT  : bool = (int(milliseconds) == 1)
        self.TTV_CLIENT : TwitchHelix = TwitchHelix(
            scopes        = [OAUTH_SCOPE_ANALYTICS_READ_EXTENSIONS],
            client_id     = self.CREDS.twitch.client,
            client_secret = self.CREDS.twitch.secret
        )

    def reject_run(self, run_id: str, reason: str = None) -> None:
        """Rejects a run given by ID. Also posts reason if given."""
        if reason is None:
            reason = ""  # avoid mutable defaults footpistol
        # make POST request to endpoint used by webinterface
        # actual PUT API endpoint is broken (again, suck a phat one, speedrun.com ...)
        res = requests.post(
            f"https://www.speedrun.com/run/{run_id}/reject",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            cookies={"PHPSESSID": self.CREDS.src.session},
            data={"csrftoken": self.CREDS.src.csrf, "answer": reason},
        )
        res.raise_for_status()

    @staticmethod
    def invalid_pending(run: dict, values: PendingValues) -> bool:
        """Checks if run breaks Pending rules, returns False if so."""
        if run['category'] == values.pending_id:
            for i, x in enumerate(run['values']):
                if x == values.category_var_id:
                    return True
            return False
        return True
        
    @staticmethod
    def has_milliseconds(run: dict) -> bool:
        """Checks if run has Milliseconds, returns False if so."""
        return "." not in str(run["times"]["primary_t"])

    @staticmethod
    def icloud_vod(run: dict) -> bool:
        """Checks if submitted VOD is an iCloud drive upload, returns False if so."""
        try:
            link_list : list = run["videos"]["links"]
            for i, x in enumerate(link_list):
                par : ParseResult = urlparse(x["uri"])
                if 'icloud.com' in par.netloc:
                    return False
            return True
        except KeyError:
            return True

    @staticmethod
    def valid_persistent_vod(run: dict, client: TwitchHelix, matcher: re.Pattern) -> bool:
        """Checks if submitted VOD is a past broadcast, returns False if so."""
        try:
            link_list: list = run["videos"]["links"]
            ttv_index: int = -1
            par_res: ParseResult
            for i, x in enumerate(link_list):
                par: ParseResult = urlparse(x["uri"])
                if "twitch.tv" in par.netloc:
                    ttv_index = i
                    par_res = par
                    break
            # only check for twitch uri's
            if ttv_index == -1:
                return True
            else:
                try:
                    # comprehend new list of all parts of the URI after the domainname that match the ID regex, then pick the 0th element
                    # if there is no element, it will throw an IndexError, which is caught below
                    vid_id: int = int(
                        [ele for ele in par_res.path.split("/") if matcher.match(ele)][0]
                    )
                    vid_data: dict = client.get_videos(video_ids=[vid_id])[0]
                    if vid_data["type"] == "archive":
                        return False
                    else:
                        return True
                # catch potential errors with exctracting vid id
                except IndexError:
                    return True
                except ValueError:
                    return True
        # just in case there is no video
        except KeyError:
            return True
        # catch httperror locally
        except (
            TwitchAttributeException,
            TwitchOAuthException,
            TwitchAuthException,
            requests.exceptions.HTTPError,
        ) as error:
            print_with_timestamp(
                f"There was an error with a request on Twitch API: {error}"
            )
            return True

    def main(self, cache: list = []) -> list:
        """
            Main function.

            Checks for the validity of any new submission and rejects them if necessary.
            Doesn't check cached runs, given as list of IDs, and returns list of new cached runs of all runs that were cleared.
        """
        print_with_timestamp('Executing main method')
        new_cache : list = []
        # get new oauth
        try:
            self.TTV_CLIENT.get_oauth()
        except (TwitchAttributeException, TwitchOAuthException, TwitchAuthException) as error:
            print_with_timestamp(f'There was an error with getting a Twitch OAuth token: {error}')
        # loop over all games
        for game in self.GAMES.games:
            faulty_runs_of_game : list = []
            # retrieve all new runs, added query params to try and circumvent caching (suck a phat one speedrun.com ...)
            try:
                rand_d : str = 'desc' if random() < 0.5 else 'asc'
                runs_res : Response = requests.get(
                    f'https://www.speedrun.com/api/v1/runs?game={game.id}&status=new&direction={rand_d}&orderby={QUERY_TABLE[self.q_counter]}&max={randint(100, 200)}',  # they hate me :^)
                    headers={
                        'User-Agent'    : SMOLeaderboardBot.AGENT,
                        'Cache-Control' : "no-cache"
                    }
                )
                # throw error if not 200 OK
                if runs_res.status_code != 200:
                    raise Exception(f'Response did not complete with 200 but instead with {runs_res.status_code}')
                new_runs : dict = runs_res.json()["data"]
            except Exception as e:
                print_with_timestamp(f'Could not retrieve runs for game {game.name} from API with the following error: {e}')
                continue
            # loop over all new runs of a given game
            for this_run in new_runs:
                # skip if already cached
                if this_run['id'] in cache:
                    new_cache.append(this_run['id'])
                    continue
                # validity checks
                invalid_run : dict = {
                    "id"     : this_run["id"],
                    "faults" : []
                }
                if not self.MS_CLIENT:
                    if not SMOLeaderboardBot.icloud_vod(this_run):
                        invalid_run["faults"].append(SubmissionErrors.ERROR_ICLOUD_VIDEO)
                    if not SMOLeaderboardBot.valid_persistent_vod(this_run, self.TTV_CLIENT, self.TWITCH_ID_MATCH):
                        invalid_run["faults"].append(SubmissionErrors.ERROR_TWITCH_BROADCAST)
                    if not SMOLeaderboardBot.invalid_pending(this_run, game.pending):
                        invalid_run["faults"].append(SubmissionErrors.ERROR_INVALID_PENDING)
                else:
                    if not SMOLeaderboardBot.has_milliseconds(this_run):
                        print_with_timestamp(f'Found problem with run <{this_run["id"]}>: Has Milliseconds')
                        if this_run["game"] == self.GAMES.games[0].id:
                            game_string = 'smo'
                        else:
                            game_string = 'smoce'
                        asyncio.get_event_loop().run_until_complete(ms_remover.remove_milliseconds(self.CREDS.src.session, game_string, this_run["id"]))
                        print_with_timestamp(f'Corrected run: <{this_run["id"]}>')
                # push to list of faulty runs if an error was found, otherwise append to cache
                if len(invalid_run["faults"]) > 0:
                    faulty_runs_of_game.append(invalid_run)
                else:
                    new_cache.append(this_run['id'])
            # loop over all invalid runs of this game
            for this_run in faulty_runs_of_game:
                # build reason string
                full_reason : str
                full_reason = SMOLeaderboardBot.REASON_TEXT[this_run["faults"][0]]
                print_with_timestamp(f'Found problem with run <{this_run["id"]}>: {this_run["faults"]}')
                # reject run
                try:
                    self.reject_run(this_run["id"], full_reason)
                    print_with_timestamp(f'Rejected run <{this_run["id"]}>')
                except requests.exceptions.RequestException as error:
                    print_with_timestamp(error)
        # increment query counter for anti-cache and return cached runs
        self.q_counter = (self.q_counter + 1) % len(QUERY_TABLE.keys())
        return new_cache

    def start(self) -> None:
        """Start bot, blocking calling thread."""
        print_with_timestamp('Started bot')
        try:
            cached_runs : list = []
            while True:
                cached_runs = self.main(cached_runs)
                # loop sleeps instead of one big sleep or threading solution to allow for easier exiting
                # application isn't time or accuracy critical so this type of interval implementation is sufficient
                c = 0
                while c <= self.TIMER:
                    sleep(1)
                    c = c+1
        except KeyboardInterrupt:
            print_with_timestamp('Stopped bot')
        except Exception as e:
            print_with_timestamp(f'Stopped bot because of uncaught error: {e}')
