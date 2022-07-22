"""
src_constants.py

holds global speedrun.com API constants
"""

from data_models    import SMOGames
from dacite         import from_dict

SMO_GAMES : SMOGames = from_dict(
    data_class=SMOGames,
    data={
        "games" : [
            {
                "id"      : "76r55vd8",
                "name"    : "Super Mario Odyssey",
                "pending" : {
                    "pending_id"      : "N/A",
                    "category_var_id" : "N/A"
                }
            },
            {
                "id"      : "m1mxxw46",
                "name"    : "Super Mario Odyssey Category Extensions",
                "pending" : {
                    "pending_id"      : "9d84we7k",
                    "category_var_id" : "rn14rmpn"
                }
            }
        ]
    }
)
