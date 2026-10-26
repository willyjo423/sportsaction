"""Map PrizePicks team abbreviations to The Odds API full team names.
Several abbreviations are listed per team because sources disagree (e.g. SA/SAS, JAX/JAC)."""

NBA = {
    "Atlanta Hawks": ["ATL"], "Boston Celtics": ["BOS"], "Brooklyn Nets": ["BKN", "BRK", "BK"],
    "Charlotte Hornets": ["CHA", "CHO"], "Chicago Bulls": ["CHI"], "Cleveland Cavaliers": ["CLE"],
    "Dallas Mavericks": ["DAL"], "Denver Nuggets": ["DEN"], "Detroit Pistons": ["DET"],
    "Golden State Warriors": ["GSW", "GS"], "Houston Rockets": ["HOU"], "Indiana Pacers": ["IND"],
    "Los Angeles Clippers": ["LAC"], "Los Angeles Lakers": ["LAL"], "Memphis Grizzlies": ["MEM"],
    "Miami Heat": ["MIA"], "Milwaukee Bucks": ["MIL"], "Minnesota Timberwolves": ["MIN"],
    "New Orleans Pelicans": ["NOP", "NO"], "New York Knicks": ["NYK", "NY"], "Oklahoma City Thunder": ["OKC"],
    "Orlando Magic": ["ORL"], "Philadelphia 76ers": ["PHI"], "Phoenix Suns": ["PHX", "PHO"],
    "Portland Trail Blazers": ["POR"], "Sacramento Kings": ["SAC"], "San Antonio Spurs": ["SAS", "SA"],
    "Toronto Raptors": ["TOR"], "Utah Jazz": ["UTA", "UTAH"], "Washington Wizards": ["WAS", "WSH"],
}

NFL = {
    "Arizona Cardinals": ["ARI"], "Atlanta Falcons": ["ATL"], "Baltimore Ravens": ["BAL"],
    "Buffalo Bills": ["BUF"], "Carolina Panthers": ["CAR"], "Chicago Bears": ["CHI"],
    "Cincinnati Bengals": ["CIN"], "Cleveland Browns": ["CLE"], "Dallas Cowboys": ["DAL"],
    "Denver Broncos": ["DEN"], "Detroit Lions": ["DET"], "Green Bay Packers": ["GB", "GNB"],
    "Houston Texans": ["HOU"], "Indianapolis Colts": ["IND"], "Jacksonville Jaguars": ["JAX", "JAC"],
    "Kansas City Chiefs": ["KC", "KAN"], "Las Vegas Raiders": ["LV", "LVR"], "Los Angeles Chargers": ["LAC"],
    "Los Angeles Rams": ["LAR", "LA"], "Miami Dolphins": ["MIA"], "Minnesota Vikings": ["MIN"],
    "New England Patriots": ["NE", "NWE"], "New Orleans Saints": ["NO", "NOR"], "New York Giants": ["NYG"],
    "New York Jets": ["NYJ"], "Philadelphia Eagles": ["PHI"], "Pittsburgh Steelers": ["PIT"],
    "San Francisco 49ers": ["SF", "SFO"], "Seattle Seahawks": ["SEA"], "Tampa Bay Buccaneers": ["TB", "TAM"],
    "Tennessee Titans": ["TEN"], "Washington Commanders": ["WAS", "WSH"],
}

NHL = {
    "Anaheim Ducks": ["ANA"], "Boston Bruins": ["BOS"], "Buffalo Sabres": ["BUF"],
    "Calgary Flames": ["CGY"], "Carolina Hurricanes": ["CAR"], "Chicago Blackhawks": ["CHI"],
    "Colorado Avalanche": ["COL"], "Columbus Blue Jackets": ["CBJ", "CLS"], "Dallas Stars": ["DAL"],
    "Detroit Red Wings": ["DET"], "Edmonton Oilers": ["EDM"], "Florida Panthers": ["FLA"],
    "Los Angeles Kings": ["LAK", "LA"], "Minnesota Wild": ["MIN"], "Montréal Canadiens": ["MTL", "MON"],
    "Nashville Predators": ["NSH", "NAS"], "New Jersey Devils": ["NJD", "NJ"], "New York Islanders": ["NYI"],
    "New York Rangers": ["NYR"], "Ottawa Senators": ["OTT"], "Philadelphia Flyers": ["PHI"],
    "Pittsburgh Penguins": ["PIT"], "San Jose Sharks": ["SJS", "SJ"], "Seattle Kraken": ["SEA"],
    "St Louis Blues": ["STL"], "Tampa Bay Lightning": ["TBL", "TB"], "Toronto Maple Leafs": ["TOR"],
    "Utah Mammoth": ["UTA", "UTAH"], "Vancouver Canucks": ["VAN"], "Vegas Golden Knights": ["VGK", "VEG"],
    "Washington Capitals": ["WSH", "WAS"], "Winnipeg Jets": ["WPG", "WIN"],
}

MLB = {
    "Arizona Diamondbacks": ["ARI", "AZ"], "Athletics": ["ATH", "OAK"], "Atlanta Braves": ["ATL"],
    "Baltimore Orioles": ["BAL"], "Boston Red Sox": ["BOS"], "Chicago Cubs": ["CHC"],
    "Chicago White Sox": ["CWS", "CHW"], "Cincinnati Reds": ["CIN"], "Cleveland Guardians": ["CLE"],
    "Colorado Rockies": ["COL"], "Detroit Tigers": ["DET"], "Houston Astros": ["HOU"],
    "Kansas City Royals": ["KC", "KCR"], "Los Angeles Angels": ["LAA"], "Los Angeles Dodgers": ["LAD"],
    "Miami Marlins": ["MIA"], "Milwaukee Brewers": ["MIL"], "Minnesota Twins": ["MIN"],
    "New York Mets": ["NYM"], "New York Yankees": ["NYY"], "Philadelphia Phillies": ["PHI"],
    "Pittsburgh Pirates": ["PIT"], "San Diego Padres": ["SD", "SDP"], "San Francisco Giants": ["SF", "SFG"],
    "Seattle Mariners": ["SEA"], "St. Louis Cardinals": ["STL"], "Tampa Bay Rays": ["TB", "TBR"],
    "Texas Rangers": ["TEX"], "Toronto Blue Jays": ["TOR"], "Washington Nationals": ["WSH", "WSN"],
}

# PrizePicks league -> (Odds API sport key, team table, market used for the fade)
LEAGUES = {
    "NBA": ("basketball_nba", NBA, "spreads"),
    "NFL": ("americanfootball_nfl", NFL, "spreads"),
    "NHL": ("icehockey_nhl", NHL, "h2h"),
    "MLB": ("baseball_mlb", MLB, "h2h"),
}


def _norm(s: str) -> str:
    return s.lower().replace(".", "").replace("é", "e").strip()


def abbr_lookup(league: str) -> dict[str, str]:
    """abbreviation -> normalized full name"""
    table = LEAGUES[league][1]
    return {ab: _norm(full) for full, abbrs in table.items() for ab in abbrs}


def norm_name(full: str) -> str:
    return _norm(full)
