"""
Multi-source prediction fetchers for DK Edge Finder.

Each fetch function returns a dict keyed by "AWAY_ABBR@HOME_ABBR":
{
    "away_abbr": str,
    "home_abbr": str,
    "away_score": float,
    "home_score": float,
    "margin": float,  # home_score - away_score (positive = home favored)
}

Sources:
1. Massey Ratings — masseyratings.com/SPORT/games (all sports)
2. OddsShark Computer Picks — oddsshark.com/SPORT/computer-picks (all sports)
3. Club Elo — api.clubelo.com (soccer only, CSV API)
4. Forebet — forebet.com (soccer only, scrape)
5. Sagarin Ratings — sagarin.com (NBA, NHL, NFL — power ratings → scores)
6. FanGraphs — fangraphs.com (MLB only — team projections)
7. Accuscore — accuscore.com (all sports, scrape)
"""

import json
import math
import re
import ssl
import sys
import urllib.request
import http.cookiejar
from datetime import datetime, timedelta

# ── Shared config ──

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# Full browser headers to bypass Cloudflare / anti-bot
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "Sec-CH-UA": '"Chromium";v="125", "Google Chrome";v="125", "Not.A/Brand";v="24"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
}

# SSL context that doesn't verify certs (some sports sites have expired certs)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# Cookie jar for session persistence
_cookie_jar = http.cookiejar.CookieJar()
_cookie_handler = urllib.request.HTTPCookieProcessor(_cookie_jar)
_opener = urllib.request.build_opener(_cookie_handler, urllib.request.HTTPSHandler(context=_ssl_ctx))

# Typical game totals by sport (for converting margin → score predictions)
TYPICAL_TOTALS = {
    "nba": 224.0,
    "nhl": 6.0,
    "mlb": 8.5,
    "nfl": 44.0,
    "epl": 2.6,
    "la_liga": 2.5,
    "serie_a": 2.4,
    "bundesliga": 3.0,
    "ligue_1": 2.4,
    "mls": 2.8,
    "ucl": 2.6,
}

# Home advantage in points/goals by sport (for Sagarin/Elo rating conversions)
HOME_ADVANTAGE = {
    "nba": 3.0,
    "nhl": 0.25,
    "mlb": 0.3,
    "nfl": 2.5,
    "epl": 0.35,
    "la_liga": 0.40,
    "serie_a": 0.40,
    "bundesliga": 0.35,
    "ligue_1": 0.35,
    "mls": 0.30,
    "ucl": 0.25,
}


def _fetch_html(url: str, timeout: int = 20, headers: dict = None) -> str:
    """Fetch HTML with full browser headers and cookie/SSL support."""
    hdrs = {**BROWSER_HEADERS, **(headers or {})}
    req = urllib.request.Request(url, headers=hdrs)
    with _opener.open(req, timeout=timeout) as resp:
        data = resp.read()
        # Handle gzip/deflate encoding
        encoding = resp.headers.get("Content-Encoding", "")
        if encoding == "gzip":
            import gzip
            data = gzip.decompress(data)
        elif encoding == "deflate":
            import zlib
            data = zlib.decompress(data)
        elif encoding == "br":
            try:
                import brotli
                data = brotli.decompress(data)
            except ImportError:
                pass  # brotli not installed, try raw
        return data.decode("utf-8", errors="ignore")


def _margin_to_scores(margin: float, sport: str) -> tuple[float, float]:
    """Convert a margin (home - away) to predicted (away_score, home_score).
    Splits around the sport's typical total."""
    total = TYPICAL_TOTALS.get(sport.lower(), 220.0)
    home_score = round((total + margin) / 2, 1)
    away_score = round((total - margin) / 2, 1)
    return away_score, home_score


# ══════════════════════════════════════════════════════
# 1. MASSEY RATINGS
# ══════════════════════════════════════════════════════

# Massey uses full team names. Map to ESPN abbreviations.
MASSEY_TEAM_MAP = {
    # NBA
    "Atlanta": "ATL", "Boston": "BOS", "Brooklyn": "BKN", "Charlotte": "CHA",
    "Chicago": "CHI", "Cleveland": "CLE", "Dallas": "DAL", "Denver": "DEN",
    "Detroit": "DET", "GoldenState": "GS", "Golden State": "GS",
    "Houston": "HOU", "Indiana": "IND", "LAClippers": "LAC", "LA Clippers": "LAC",
    "LALakers": "LAL", "LA Lakers": "LAL", "Memphis": "MEM", "Miami": "MIA",
    "Milwaukee": "MIL", "Minnesota": "MIN", "NewOrleans": "NO", "New Orleans": "NO",
    "NewYork": "NY", "New York": "NY", "NYKnicks": "NY",
    "OklahomaCity": "OKC", "Oklahoma City": "OKC", "Orlando": "ORL",
    "Philadelphia": "PHI", "Phoenix": "PHX", "Portland": "POR",
    "Sacramento": "SAC", "SanAntonio": "SA", "San Antonio": "SA",
    "Toronto": "TOR", "Utah": "UTA", "Washington": "WSH",
    # NHL
    "Anaheim": "ANA", "Arizona": "ARI", "Buffalo": "BUF", "Calgary": "CGY",
    "Carolina": "CAR", "Colorado": "COL", "Columbus": "CBJ",
    "Edmonton": "EDM", "Florida": "FLA", "LosAngeles": "LAK", "Los Angeles": "LAK",
    "Montreal": "MTL", "Nashville": "NSH", "NewJersey": "NJ", "New Jersey": "NJ",
    "NYIslanders": "NYI", "NY Islanders": "NYI", "NYRangers": "NYR", "NY Rangers": "NYR",
    "Ottawa": "OTT", "Pittsburgh": "PIT", "SanJose": "SJ", "San Jose": "SJ",
    "Seattle": "SEA", "St.Louis": "STL", "St. Louis": "STL",
    "TampaBay": "TB", "Tampa Bay": "TB", "Vancouver": "VAN",
    "Vegas": "VGK", "Winnipeg": "WPG",
    # MLB
    "Cubs": "CHC", "WhiteSox": "CWS", "White Sox": "CWS", "Guardians": "CLE",
    "Tigers": "DET", "Royals": "KC", "Twins": "MIN", "Yankees": "NYY",
    "Mets": "NYM", "Athletics": "OAK", "Orioles": "BAL", "RedSox": "BOS",
    "Red Sox": "BOS", "Angels": "LAA", "Astros": "HOU", "Mariners": "SEA",
    "Rangers": "TEX", "BlueJays": "TOR", "Blue Jays": "TOR",
    "Braves": "ATL", "Marlins": "MIA", "Brewers": "MIL", "Phillies": "PHI",
    "Pirates": "PIT", "Cardinals": "STL", "Reds": "CIN", "Rockies": "COL",
    "Diamondbacks": "ARI", "Dodgers": "LAD", "Padres": "SD", "Giants": "SF",
    "Nationals": "WSH", "Rays": "TB",
    # NFL
    "Bills": "BUF", "Dolphins": "MIA", "Patriots": "NE", "Jets": "NYJ",
    "Ravens": "BAL", "Bengals": "CIN", "Browns": "CLE", "Steelers": "PIT",
    "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX", "Titans": "TEN",
    "Broncos": "DEN", "Chiefs": "KC", "Raiders": "LV", "Chargers": "LAC",
    "Cowboys": "DAL", "Eagles": "PHI", "Commanders": "WSH", "49ers": "SF",
    "Bears": "CHI", "Lions": "DET", "Packers": "GB", "Vikings": "MIN",
    "Falcons": "ATL", "Panthers": "CAR", "Saints": "NO", "Buccaneers": "TB",
    "Cardinals": "ARI", "Rams": "LAR", "Seahawks": "SEA",
    # Soccer — use city/club short names
    "Liverpool": "LIV", "Arsenal": "ARS", "ManCity": "MCI", "Man City": "MCI",
    "Manchester City": "MCI", "ManUnited": "MUN", "Man United": "MUN",
    "Manchester United": "MUN", "Chelsea": "CHE", "Tottenham": "TOT",
    "Newcastle": "NEW", "Brighton": "BHA", "AstonVilla": "AVL", "Aston Villa": "AVL",
    "WestHam": "WHU", "West Ham": "WHU", "Bournemouth": "BOU",
    "Fulham": "FUL", "Crystal Palace": "CRY", "Brentford": "BRE",
    "Nottingham": "NFO", "Nottm Forest": "NFO", "Wolves": "WOL",
    "Everton": "EVE", "Leicester": "LEI", "Ipswich": "IPS",
    "Southampton": "SOU", "Burnley": "BUR", "Sheffield": "SHU",
    "Luton": "LUT",
    "Barcelona": "BAR", "RealMadrid": "RMA", "Real Madrid": "RMA",
    "AtlMadrid": "ATM", "Atletico Madrid": "ATM", "Atl Madrid": "ATM",
    "Sevilla": "SEV", "Villarreal": "VIL", "RealSociedad": "RSO",
    "Real Sociedad": "RSO", "RealBetis": "BET", "Real Betis": "BET",
    "AthBilbao": "ATH", "Athletic Bilbao": "ATH", "Athletic": "ATH",
    "Valencia": "VAL", "Girona": "GIR", "Osasuna": "OSA",
    "Celta": "CEL", "Getafe": "GET", "Mallorca": "MAL", "Alaves": "ALA",
    "LasPalmas": "LPA", "Las Palmas": "LPA", "Cadiz": "CAD",
    "Juventus": "JUV", "Inter": "INT", "Milan": "MIL", "ACMilan": "MIL",
    "Napoli": "NAP", "Roma": "ROM", "Lazio": "LAZ", "Atalanta": "ATA",
    "Fiorentina": "FIO", "Bologna": "BOL", "Torino": "TOR",
    "Monza": "MON", "Genoa": "GEN", "Cagliari": "CAG",
    "Lecce": "LEC", "Empoli": "EMP", "Sassuolo": "SAS",
    "Verona": "VER", "Frosinone": "FRO", "Salernitana": "SAL", "Udinese": "UDI",
    "BayernMunich": "BAY", "Bayern Munich": "BAY", "Bayern": "BAY",
    "Dortmund": "DOR", "Leverkusen": "LEV", "Leipzig": "RBL", "RBLeipzig": "RBL",
    "Frankfurt": "FRA", "Wolfsburg": "WOB", "Freiburg": "FRE",
    "Stuttgart": "STU", "UnionBerlin": "UNB", "Union Berlin": "UNB",
    "Hoffenheim": "HOF", "Augsburg": "AUG", "Mainz": "MAI",
    "Bochum": "BOC", "Monchengladbach": "BMG", "Werder": "BRE",
    "Heidenheim": "HEI", "Darmstadt": "DAR", "Koln": "KOE",
    "PSG": "PSG", "Marseille": "MAR", "Lyon": "LYO", "Monaco": "MON",
    "Lille": "LIL", "Nice": "NIC", "Lens": "LEN", "Rennes": "REN",
    "Strasbourg": "STR", "Montpellier": "MTP", "Nantes": "NAN",
    "Toulouse": "TOU", "Reims": "REI", "Brest": "BRE",
    "LAFC": "LAFC", "LAGalaxy": "LAG", "LA Galaxy": "LAG",
    "Atlanta United": "ATL", "NYCFC": "NYC", "Inter Miami": "MIA",
    "Portland Timbers": "POR", "Seattle Sounders": "SEA", "Nashville SC": "NSH",
}


def fetch_massey_predictions(date_str: str, sport: str = "nba") -> dict:
    """
    Fetch game predictions from Massey Ratings.
    Massey publishes three rating systems per sport with predicted scores.
    Returns first available prediction set.
    """
    sport_urls = {
        "nba": "https://masseyratings.com/nba/games",
        "nhl": "https://masseyratings.com/nhl/games",
        "mlb": "https://masseyratings.com/mlb/games",
        "nfl": "https://masseyratings.com/nfl/games",
        "epl": "https://masseyratings.com/epl/games",
        "la_liga": "https://masseyratings.com/spa1/games",
        "serie_a": "https://masseyratings.com/ita1/games",
        "bundesliga": "https://masseyratings.com/ger1/games",
        "ligue_1": "https://masseyratings.com/fra1/games",
        "mls": "https://masseyratings.com/mls/games",
    }
    url = sport_urls.get(sport.lower())
    if not url:
        return {}

    predictions = {}
    today_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    today_display = f"{int(date_str[4:6])}/{int(date_str[6:8])}"

    try:
        html = _fetch_html(url)

        # Massey's game pages use pre-formatted text or simple HTML tables.
        # Look for lines with date, teams, and scores.
        # Format varies but typically: date away_team score - home_team score
        # or tabular format.

        # Try to find JSON data embedded in page (some Massey pages use JS)
        json_match = re.search(r'var\s+games\s*=\s*(\[.*?\]);', html, re.DOTALL)
        if json_match:
            try:
                games_data = json.loads(json_match.group(1))
                for game in games_data:
                    if today_iso not in str(game.get("date", "")):
                        continue
                    away = game.get("away", {})
                    home = game.get("home", {})
                    away_name = away.get("name", "")
                    home_name = home.get("name", "")
                    away_score = away.get("score")
                    home_score = home.get("score")
                    if away_score is None or home_score is None:
                        continue
                    away_abbr = MASSEY_TEAM_MAP.get(away_name, away_name[:3].upper())
                    home_abbr = MASSEY_TEAM_MAP.get(home_name, home_name[:3].upper())
                    key = f"{away_abbr}@{home_abbr}"
                    predictions[key] = {
                        "away_abbr": away_abbr, "home_abbr": home_abbr,
                        "away_score": float(away_score), "home_score": float(home_score),
                        "margin": round(float(home_score) - float(away_score), 1),
                    }
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback: parse HTML table rows
        if not predictions:
            # Look for <pre> blocks (Massey often uses preformatted text)
            pre_blocks = re.findall(r'<pre[^>]*>(.*?)</pre>', html, re.DOTALL)
            text_to_parse = "\n".join(pre_blocks) if pre_blocks else html

            # Also try parsing <tr> rows
            trs = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
            for tr in trs:
                text = re.sub(r'<[^>]+>', ' ', tr).strip()
                # Skip if doesn't contain today's date
                if today_display not in text and today_iso not in text:
                    continue

                # Look for pattern: TeamA <score> TeamB <score>
                # or: TeamA @ TeamB  predicted_score - predicted_score
                parts = text.split()
                teams_found = []
                scores_found = []

                for p in parts:
                    # Score: number that looks like a predicted score
                    try:
                        val = float(p)
                        if _is_valid_score(val, sport):
                            scores_found.append(val)
                    except ValueError:
                        # Check if it's a team name
                        clean = p.strip("@()")
                        if clean in MASSEY_TEAM_MAP:
                            teams_found.append(MASSEY_TEAM_MAP[clean])
                        elif len(clean) >= 3 and clean[0].isupper():
                            # Could be a team name
                            mapped = MASSEY_TEAM_MAP.get(clean)
                            if mapped:
                                teams_found.append(mapped)

                if len(teams_found) >= 2 and len(scores_found) >= 2:
                    away_abbr = teams_found[0]
                    home_abbr = teams_found[1]
                    away_score = scores_found[0]
                    home_score = scores_found[1]
                    key = f"{away_abbr}@{home_abbr}"
                    predictions[key] = {
                        "away_abbr": away_abbr, "home_abbr": home_abbr,
                        "away_score": away_score, "home_score": home_score,
                        "margin": round(home_score - away_score, 1),
                    }

        # Also try: fetch the ratings page and compute predictions from ratings
        if not predictions:
            predictions = _massey_from_ratings(date_str, sport)

        print(f"  Massey: found {len(predictions)} game predictions for {sport.upper()}")

    except Exception as e:
        print(f"  Massey fetch error ({sport}): {e}", file=sys.stderr)

    return predictions


def _massey_from_ratings(date_str: str, sport: str) -> dict:
    """Fallback: fetch Massey power ratings and derive game predictions.
    Requires knowing today's matchups (passed from ESPN schedule)."""
    ratings_urls = {
        "nba": "https://masseyratings.com/nba/ratings",
        "nhl": "https://masseyratings.com/nhl/ratings",
        "mlb": "https://masseyratings.com/mlb/ratings",
        "nfl": "https://masseyratings.com/nfl/ratings",
    }
    url = ratings_urls.get(sport.lower())
    if not url:
        return {}

    try:
        html = _fetch_html(url)
        # Parse rating values — Massey tables have team name and numeric rating
        ratings = {}
        trs = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        for tr in trs:
            cells = [re.sub(r'<[^>]+>', '', c).strip()
                     for c in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)]
            if len(cells) < 2:
                continue
            # Find team name and rating value
            team_name = None
            rating_val = None
            for cell in cells:
                if cell in MASSEY_TEAM_MAP and not team_name:
                    team_name = MASSEY_TEAM_MAP[cell]
                elif not team_name:
                    mapped = MASSEY_TEAM_MAP.get(cell)
                    if mapped:
                        team_name = mapped
                if rating_val is None:
                    try:
                        v = float(cell)
                        if -50 < v < 50:  # Reasonable rating range
                            rating_val = v
                    except ValueError:
                        pass
            if team_name and rating_val is not None:
                ratings[team_name] = rating_val

        # We can't build game predictions without matchup info here,
        # but we store ratings for use by the ensemble builder.
        # Return empty — the main scan will try to match these with schedule data.
        return {}

    except Exception as e:
        print(f"  Massey ratings fetch error ({sport}): {e}", file=sys.stderr)
        return {}


def _is_valid_score(val: float, sport: str) -> bool:
    """Check if a number could be a predicted game score for this sport."""
    ranges = {
        "nba": (70, 160), "nhl": (0.5, 8), "mlb": (0.5, 15), "nfl": (10, 55),
        "epl": (0.3, 5), "la_liga": (0.3, 5), "serie_a": (0.3, 5),
        "bundesliga": (0.3, 5), "ligue_1": (0.3, 5), "mls": (0.3, 5), "ucl": (0.3, 5),
    }
    lo, hi = ranges.get(sport.lower(), (0, 200))
    return lo <= val <= hi


# ══════════════════════════════════════════════════════
# 2. ODDSSHARK COMPUTER PICKS
# ══════════════════════════════════════════════════════

ODDSSHARK_TEAM_MAP = {
    # NBA
    "Hawks": "ATL", "Celtics": "BOS", "Nets": "BKN", "Hornets": "CHA",
    "Bulls": "CHI", "Cavaliers": "CLE", "Mavericks": "DAL", "Nuggets": "DEN",
    "Pistons": "DET", "Warriors": "GS", "Rockets": "HOU", "Pacers": "IND",
    "Clippers": "LAC", "Lakers": "LAL", "Grizzlies": "MEM", "Heat": "MIA",
    "Bucks": "MIL", "Timberwolves": "MIN", "Pelicans": "NO", "Knicks": "NY",
    "Thunder": "OKC", "Magic": "ORL", "76ers": "PHI", "Suns": "PHX",
    "Trail Blazers": "POR", "Kings": "SAC", "Spurs": "SA", "Raptors": "TOR",
    "Jazz": "UTA", "Wizards": "WSH",
    # NHL
    "Ducks": "ANA", "Coyotes": "ARI", "Bruins": "BOS", "Sabres": "BUF",
    "Flames": "CGY", "Hurricanes": "CAR", "Blackhawks": "CHI",
    "Avalanche": "COL", "Blue Jackets": "CBJ", "Stars": "DAL",
    "Red Wings": "DET", "Oilers": "EDM", "Panthers": "FLA",
    "Kings": "LAK", "Wild": "MIN", "Canadiens": "MTL", "Predators": "NSH",
    "Devils": "NJ", "Islanders": "NYI", "Rangers": "NYR", "Senators": "OTT",
    "Flyers": "PHI", "Penguins": "PIT", "Sharks": "SJ", "Kraken": "SEA",
    "Blues": "STL", "Lightning": "TB", "Maple Leafs": "TOR",
    "Canucks": "VAN", "Golden Knights": "VGK", "Capitals": "WSH", "Jets": "WPG",
    # MLB
    "Diamondbacks": "ARI", "Braves": "ATL", "Orioles": "BAL", "Red Sox": "BOS",
    "Cubs": "CHC", "White Sox": "CWS", "Reds": "CIN", "Guardians": "CLE",
    "Rockies": "COL", "Tigers": "DET", "Astros": "HOU", "Royals": "KC",
    "Angels": "LAA", "Dodgers": "LAD", "Marlins": "MIA", "Brewers": "MIL",
    "Twins": "MIN", "Yankees": "NYY", "Mets": "NYM", "Athletics": "OAK",
    "Phillies": "PHI", "Pirates": "PIT", "Padres": "SD", "Giants": "SF",
    "Mariners": "SEA", "Cardinals": "STL", "Rays": "TB", "Rangers": "TEX",
    "Blue Jays": "TOR", "Nationals": "WSH",
    # NFL (same as NHL for some, plus NFL-specific)
    "Bills": "BUF", "Dolphins": "MIA", "Patriots": "NE",
    "Ravens": "BAL", "Bengals": "CIN", "Browns": "CLE", "Steelers": "PIT",
    "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX", "Titans": "TEN",
    "Broncos": "DEN", "Chiefs": "KC", "Raiders": "LV", "Chargers": "LAC",
    "Cowboys": "DAL", "Eagles": "PHI", "Commanders": "WSH", "49ers": "SF",
    "Bears": "CHI", "Lions": "DET", "Packers": "GB", "Vikings": "MIN",
    "Falcons": "ATL", "Saints": "NO", "Buccaneers": "TB",
    "Cardinals": "ARI", "Rams": "LAR", "Seahawks": "SEA",
}


def fetch_oddsshark_predictions(date_str: str, sport: str = "nba") -> dict:
    """
    Fetch computer-generated score predictions from OddsShark.
    OddsShark publishes predicted scores based on last 100 games played.

    HTML structure (confirmed 2026-04-06):
    - Page splits by "Predicted Score" into per-game sections
    - Each section has <span class="highlighted-text team-shortname">ABBR</span>
      and <span class="highlighted-text">SCORE</span> pairs
    - Matchup URLs in href like /nba/new-york-atlanta-odds-... give away-home order
    - Games without predictions yet show "-" for scores
    """
    sport_urls = {
        "nba": "https://www.oddsshark.com/nba/computer-picks",
        "nhl": "https://www.oddsshark.com/nhl/computer-picks",
        "mlb": "https://www.oddsshark.com/mlb/computer-picks",
        "nfl": "https://www.oddsshark.com/nfl/computer-picks",
        "epl": "https://www.oddsshark.com/soccer/premier-league/computer-picks",
        "la_liga": "https://www.oddsshark.com/soccer/la-liga/computer-picks",
        "serie_a": "https://www.oddsshark.com/soccer/serie-a/computer-picks",
        "bundesliga": "https://www.oddsshark.com/soccer/bundesliga/computer-picks",
        "ucl": "https://www.oddsshark.com/soccer/champions-league/computer-picks",
    }
    url = sport_urls.get(sport.lower())
    if not url:
        return {}

    predictions = {}

    try:
        html = _fetch_html(url)

        # Split page by "Predicted Score" — each section is one game
        sections = html.split("Predicted Score")

        for section in sections[1:]:  # Skip preamble before first game
            # Limit search to first 3000 chars of each section (one game)
            chunk = section[:3000]

            # Extract team abbreviations (class includes "team-shortname")
            teams = re.findall(r'team-shortname[^>]*>([^<]+)', chunk)

            # Extract ALL highlighted-text values (includes both team abbrs and scores)
            all_highlighted = re.findall(r'highlighted-text[^>]*>([^<]+)', chunk)

            # Filter scores: must be numeric AND in valid range for the sport
            # This excludes spread values (e.g. -2.5, 1.5) that appear for
            # games where OddsShark hasn't generated score predictions yet
            scores = []
            for val in all_highlighted:
                val = val.strip()
                try:
                    num = float(val)
                    if _is_valid_score(num, sport):
                        scores.append(num)
                except ValueError:
                    continue

            if len(teams) < 2 or len(scores) < 2:
                continue  # Game doesn't have real predictions yet

            # Determine away/home order from matchup URL
            matchup_urls = re.findall(r'href="(/[^"]*odds[^"]*)"?', chunk)

            # OddsShark lists teams in page order: first team, second team
            team1_abbr = _resolve_oddsshark_abbr(teams[0].strip(), sport)
            team2_abbr = _resolve_oddsshark_abbr(teams[1].strip(), sport)

            if not team1_abbr or not team2_abbr:
                continue

            # Default: assume page order is away, home
            away_abbr, home_abbr = team1_abbr, team2_abbr
            away_score, home_score = scores[0], scores[1]

            if matchup_urls:
                url_path = matchup_urls[0].lower()
                t1_pos = _team_in_url(team1_abbr, url_path, sport)
                t2_pos = _team_in_url(team2_abbr, url_path, sport)
                if t1_pos is not None and t2_pos is not None:
                    if t1_pos < t2_pos:
                        away_abbr, home_abbr = team1_abbr, team2_abbr
                        away_score, home_score = scores[0], scores[1]
                    else:
                        away_abbr, home_abbr = team2_abbr, team1_abbr
                        away_score, home_score = scores[1], scores[0]

            key = f"{away_abbr}@{home_abbr}"
            predictions[key] = {
                "away_abbr": away_abbr, "home_abbr": home_abbr,
                "away_score": away_score, "home_score": home_score,
                "margin": round(home_score - away_score, 1),
            }

        print(f"  OddsShark: found {len(predictions)} game predictions for {sport.upper()}")

    except Exception as e:
        print(f"  OddsShark fetch error ({sport}): {e}", file=sys.stderr)

    return predictions


# OddsShark abbreviation -> ESPN abbreviation normalization
_ODDSSHARK_ABBR_NORMALIZE = {
    "SAN": "SA", "NOP": "NO", "NYK": "NY", "GSW": "GS",
    "CHR": "CHA", "BRK": "BKN", "PHO": "PHX",
    "MON": "MTL", "WAS": "WSH", "NAS": "NSH", "CLB": "CBJ",
    "CAL": "CGY", "WIN": "WPG",
    "CHW": "CWS",
}

# Sport-specific "LA" resolution (Kings in NHL, Dodgers in MLB, etc.)
_LA_BY_SPORT = {
    "nhl": "LAK",
    "mlb": "LAD",
    "nba": "LAL",  # Default to Lakers; Clippers use "LAC"
    "nfl": "LAR",  # Rams; Chargers use "LAC"
}


def _resolve_oddsshark_abbr(abbr: str, sport: str) -> str:
    """Resolve an OddsShark team abbreviation to our ESPN standard."""
    abbr = abbr.strip().upper()
    # Handle "LA" specially — depends on sport
    if abbr == "LA":
        return _LA_BY_SPORT.get(sport.lower(), "LAK")
    normalized = _ODDSSHARK_ABBR_NORMALIZE.get(abbr, abbr)
    # Check if it's already a known abbreviation
    if normalized in ODDSSHARK_TEAM_MAP.values():
        return normalized
    if abbr in ODDSSHARK_TEAM_MAP:
        return ODDSSHARK_TEAM_MAP[abbr]
    # Fallback: 2-4 uppercase letters = treat as abbreviation
    if 2 <= len(abbr) <= 4 and abbr.isalpha():
        return normalized
    return ""


# Map ESPN abbreviations to URL-friendly city names for OddsShark URL matching
_ABBR_TO_CITY = {
    "ATL": "atlanta", "BOS": "boston", "BKN": "brooklyn", "CHA": "charlotte",
    "CHI": "chicago", "CLE": "cleveland", "DAL": "dallas", "DEN": "denver",
    "DET": "detroit", "GS": "golden-state", "HOU": "houston", "IND": "indiana",
    "LAC": "los-angeles-clippers", "LAL": "los-angeles-lakers", "MEM": "memphis",
    "MIA": "miami", "MIL": "milwaukee", "MIN": "minnesota", "NO": "new-orleans",
    "NY": "new-york", "OKC": "oklahoma-city", "ORL": "orlando", "PHI": "philadelphia",
    "PHX": "phoenix", "POR": "portland", "SAC": "sacramento", "SA": "san-antonio",
    "TOR": "toronto", "UTA": "utah", "WSH": "washington",
    "ANA": "anaheim", "ARI": "arizona", "BUF": "buffalo", "CGY": "calgary",
    "CAR": "carolina", "COL": "colorado", "CBJ": "columbus",
    "EDM": "edmonton", "FLA": "florida", "LAK": "los-angeles",
    "MTL": "montreal", "NSH": "nashville", "NJ": "new-jersey",
    "NYI": "new-york-islanders", "NYR": "new-york-rangers", "OTT": "ottawa",
    "PIT": "pittsburgh", "SJ": "san-jose", "SEA": "seattle",
    "STL": "st-louis", "TB": "tampa-bay", "VAN": "vancouver",
    "VGK": "vegas", "WPG": "winnipeg",
    "BAL": "baltimore", "CWS": "chicago-white-sox", "CHC": "chicago-cubs",
    "CIN": "cincinnati", "KC": "kansas-city", "LAA": "los-angeles-angels",
    "LAD": "los-angeles-dodgers", "NYM": "new-york-mets", "NYY": "new-york-yankees",
    "OAK": "oakland", "SD": "san-diego", "SF": "san-francisco",
    "TEX": "texas",
}


def _team_in_url(abbr: str, url_path: str, sport: str):
    """Find position of a team in an OddsShark matchup URL. Returns index or None."""
    city = _ABBR_TO_CITY.get(abbr, "").lower()
    if city:
        idx = url_path.find(city)
        if idx >= 0:
            return idx
    # Fallback: try abbreviation itself lowercase
    idx = url_path.find(abbr.lower())
    if idx >= 0:
        return idx
    return None


def _resolve_team(name: str, sport: str) -> str:
    """Resolve a team name/nickname to ESPN abbreviation."""
    if not name:
        return ""
    name = name.strip()
    if name in ODDSSHARK_TEAM_MAP:
        return ODDSSHARK_TEAM_MAP[name]
    if name in MASSEY_TEAM_MAP:
        return MASSEY_TEAM_MAP[name]
    last = name.split()[-1] if name.split() else name
    if last in ODDSSHARK_TEAM_MAP:
        return ODDSSHARK_TEAM_MAP[last]
    if len(name) <= 4 and name.isupper():
        return name
    return ""


# ══════════════════════════════════════════════════════
# 3. CLUB ELO (Soccer only — free CSV API)
# ══════════════════════════════════════════════════════

# Club Elo team names → ESPN abbreviations
CLUB_ELO_MAP = {
    # EPL
    "Liverpool": "LIV", "Arsenal": "ARS", "Man City": "MCI",
    "Man United": "MUN", "Chelsea": "CHE", "Tottenham": "TOT",
    "Newcastle": "NEW", "Brighton": "BHA", "Aston Villa": "AVL",
    "West Ham": "WHU", "Bournemouth": "BOU", "Fulham": "FUL",
    "Crystal Palace": "CRY", "Brentford": "BRE", "Nottm Forest": "NFO",
    "Wolves": "WOL", "Everton": "EVE", "Leicester": "LEI",
    "Ipswich": "IPS", "Southampton": "SOU", "Burnley": "BUR",
    "Sheffield Utd": "SHU", "Luton": "LUT",
    # La Liga
    "Barcelona": "BAR", "Real Madrid": "RMA", "Atletico": "ATM",
    "Sevilla": "SEV", "Villarreal": "VIL", "Real Sociedad": "RSO",
    "Real Betis": "BET", "Ath Bilbao": "ATH", "Athletic": "ATH",
    "Valencia": "VAL", "Girona": "GIR", "Osasuna": "OSA",
    "Celta Vigo": "CEL", "Getafe": "GET", "Mallorca": "MAL",
    "Alaves": "ALA", "Las Palmas": "LPA", "Cadiz": "CAD",
    # Serie A
    "Juventus": "JUV", "Inter": "INT", "Milan": "MIL",
    "Napoli": "NAP", "Roma": "ROM", "Lazio": "LAZ",
    "Atalanta": "ATA", "Fiorentina": "FIO", "Bologna": "BOL",
    "Torino": "TOR", "Monza": "MON", "Genoa": "GEN",
    "Cagliari": "CAG", "Lecce": "LEC", "Empoli": "EMP",
    "Sassuolo": "SAS", "Verona": "VER", "Frosinone": "FRO",
    "Salernitana": "SAL", "Udinese": "UDI",
    # Bundesliga
    "Bayern": "BAY", "Dortmund": "DOR", "Leverkusen": "LEV",
    "Leipzig": "RBL", "Frankfurt": "FRA", "Wolfsburg": "WOB",
    "Freiburg": "FRE", "Stuttgart": "STU", "Union Berlin": "UNB",
    "Hoffenheim": "HOF", "Augsburg": "AUG", "Mainz": "MAI",
    "Bochum": "BOC", "Gladbach": "BMG", "Werder": "BRE",
    "Heidenheim": "HEI", "Darmstadt": "DAR", "Koeln": "KOE",
    # Ligue 1
    "PSG": "PSG", "Marseille": "MAR", "Lyon": "LYO",
    "Monaco": "MON", "Lille": "LIL", "Nice": "NIC",
    "Lens": "LEN", "Rennes": "REN", "Strasbourg": "STR",
    "Montpellier": "MTP", "Nantes": "NAN", "Toulouse": "TOU",
    "Reims": "REI", "Brest": "BRE",
}


def fetch_clubelo_ratings(date_str: str) -> dict:
    """
    Fetch Elo ratings from Club Elo's free CSV API.
    Returns dict keyed by team abbreviation with Elo rating.
    """
    iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    url = f"http://api.clubelo.com/{iso}"
    ratings = {}

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            csv_data = resp.read().decode("utf-8", errors="ignore")

        for line in csv_data.strip().split("\n"):
            parts = line.split(",")
            if len(parts) < 4:
                continue
            # Format: Rank,Club,Country,Level,Elo,...
            club = parts[1].strip()
            try:
                elo = float(parts[4].strip()) if len(parts) > 4 else float(parts[3].strip())
            except (ValueError, IndexError):
                continue

            abbr = CLUB_ELO_MAP.get(club)
            if abbr:
                ratings[abbr] = elo

        print(f"  Club Elo: loaded {len(ratings)} team ratings")

    except Exception as e:
        print(f"  Club Elo fetch error: {e}", file=sys.stderr)

    return ratings


def clubelo_to_predictions(ratings: dict, matchups: list, sport: str) -> dict:
    """
    Convert Club Elo ratings + today's matchups into score predictions.

    matchups: list of (away_abbr, home_abbr) tuples from ESPN schedule.
    Uses Elo → win probability → margin → score split.
    """
    predictions = {}
    ha = HOME_ADVANTAGE.get(sport.lower(), 0.35)

    for away_abbr, home_abbr in matchups:
        away_elo = ratings.get(away_abbr)
        home_elo = ratings.get(home_abbr)
        if away_elo is None or home_elo is None:
            continue

        # Elo → expected score (logistic model)
        # Add home advantage in Elo points (~65 Elo ≈ 0.35 goals)
        elo_diff = home_elo - away_elo + 65  # ~65 Elo = standard home advantage
        expected_home = 1.0 / (1.0 + 10 ** (-elo_diff / 400))

        # Convert win probability to margin (goals)
        # For soccer: margin ≈ (win_prob - 0.5) * 2.8 (empirical scaling)
        margin = (expected_home - 0.5) * 2.8

        away_score, home_score = _margin_to_scores(round(margin, 2), sport)

        key = f"{away_abbr}@{home_abbr}"
        predictions[key] = {
            "away_abbr": away_abbr, "home_abbr": home_abbr,
            "away_score": away_score, "home_score": home_score,
            "margin": round(margin, 2),
        }

    return predictions


# ══════════════════════════════════════════════════════
# 4. FOREBET (Soccer only — scrape)
# ══════════════════════════════════════════════════════

FOREBET_TEAM_MAP = {
    # Uses similar names to Club Elo map — merge at runtime
    **CLUB_ELO_MAP,
    **MASSEY_TEAM_MAP,
}


def fetch_forebet_predictions(date_str: str, sport: str = "epl") -> dict:
    """
    Fetch predicted scores from Forebet for soccer leagues.
    Forebet provides 1-3 (home-draw-away) predictions with exact score forecasts.
    """
    sport_urls = {
        "epl": "https://www.forebet.com/en/football-predictions/predictions-1x2/england-premier-league",
        "la_liga": "https://www.forebet.com/en/football-predictions/predictions-1x2/spain-la-liga",
        "serie_a": "https://www.forebet.com/en/football-predictions/predictions-1x2/italy-serie-a",
        "bundesliga": "https://www.forebet.com/en/football-predictions/predictions-1x2/germany-bundesliga",
        "ligue_1": "https://www.forebet.com/en/football-predictions/predictions-1x2/france-ligue-1",
        "mls": "https://www.forebet.com/en/football-predictions/predictions-1x2/usa-major-league-soccer",
        "ucl": "https://www.forebet.com/en/football-predictions/predictions-1x2/champions-league",
    }
    url = sport_urls.get(sport.lower())
    if not url:
        return {}

    predictions = {}

    try:
        html = _fetch_html(url, timeout=25)

        # Forebet uses divs with class "rcnt" for each match
        # Score prediction appears in elements like <span class="foremark">2 - 1</span>
        # Teams in <span class="homeTeam"> and <span class="awayTeam"> or similar

        # Look for match containers
        match_blocks = re.findall(
            r'<div[^>]*class="[^"]*rcnt[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
            html, re.DOTALL
        )
        if not match_blocks:
            # Try broader pattern
            match_blocks = re.findall(
                r'class="[^"]*contentMiddle[^"]*">(.*?)</(?:div|tr)',
                html, re.DOTALL
            )

        for block in match_blocks:
            # Extract team names
            home_match = re.search(r'homeTeam[^>]*>([^<]+)', block)
            away_match = re.search(r'awayTeam[^>]*>([^<]+)', block)
            if not home_match or not away_match:
                # Try: team names in <a> tags with team classes
                teams = re.findall(r'team[^>]*>([^<]+)<', block)
                if len(teams) >= 2:
                    home_name = teams[0].strip()
                    away_name = teams[1].strip()
                else:
                    continue
            else:
                home_name = home_match.group(1).strip()
                away_name = away_match.group(1).strip()

            # Extract predicted score
            score_match = re.search(r'(\d+)\s*-\s*(\d+)', block)
            if not score_match:
                continue

            home_score = float(score_match.group(1))
            away_score = float(score_match.group(2))

            home_abbr = FOREBET_TEAM_MAP.get(home_name, home_name[:3].upper())
            away_abbr = FOREBET_TEAM_MAP.get(away_name, away_name[:3].upper())

            key = f"{away_abbr}@{home_abbr}"
            predictions[key] = {
                "away_abbr": away_abbr, "home_abbr": home_abbr,
                "away_score": away_score, "home_score": home_score,
                "margin": round(home_score - away_score, 1),
            }

        print(f"  Forebet: found {len(predictions)} game predictions for {sport.upper()}")

    except Exception as e:
        print(f"  Forebet fetch error ({sport}): {e}", file=sys.stderr)

    return predictions


# ══════════════════════════════════════════════════════
# 5. SAGARIN RATINGS (NBA, NHL, NFL — power ratings)
# ══════════════════════════════════════════════════════

SAGARIN_TEAM_MAP = {
    # NBA
    "Atlanta": "ATL", "Boston": "BOS", "Brooklyn": "BKN", "Charlotte": "CHA",
    "Chicago": "CHI", "Cleveland": "CLE", "Dallas": "DAL", "Denver": "DEN",
    "Detroit": "DET", "GoldenSt": "GS", "Golden St": "GS", "Golden State": "GS",
    "Houston": "HOU", "Indiana": "IND", "LAClipper": "LAC", "LA Clippers": "LAC",
    "LALakers": "LAL", "LA Lakers": "LAL", "Memphis": "MEM", "Miami": "MIA",
    "Milwaukee": "MIL", "Minnesota": "MIN", "NewOrlean": "NO", "New Orleans": "NO",
    "NewYork": "NY", "New York": "NY", "OKCThunde": "OKC", "Okla City": "OKC",
    "Oklahoma City": "OKC", "Orlando": "ORL", "Phila": "PHI", "Philadelphia": "PHI",
    "Phoenix": "PHX", "Portland": "POR", "Sacramento": "SAC",
    "SanAntoni": "SA", "San Anton": "SA", "San Antonio": "SA",
    "Toronto": "TOR", "Utah": "UTA", "Washington": "WSH",
    # NHL
    "Anaheim": "ANA", "Arizona": "ARI", "Buffalo": "BUF", "Calgary": "CGY",
    "Carolina": "CAR", "Colorado": "COL", "Columbus": "CBJ",
    "Edmonton": "EDM", "Florida": "FLA", "LosAngele": "LAK", "Los Angeles": "LAK",
    "Montreal": "MTL", "Nashville": "NSH", "NewJersey": "NJ", "New Jersey": "NJ",
    "NYIsland": "NYI", "NY Island": "NYI", "NYRanger": "NYR", "NY Rangers": "NYR",
    "Ottawa": "OTT", "Phila": "PHI", "Pittsburgh": "PIT",
    "SanJose": "SJ", "San Jose": "SJ", "Seattle": "SEA",
    "St.Louis": "STL", "St. Louis": "STL", "TampaBay": "TB", "Tampa Bay": "TB",
    "Vancouver": "VAN", "Vegas": "VGK", "Washington": "WSH", "Winnipeg": "WPG",
    # NFL
    "Buffalo": "BUF", "Miami": "MIA", "NewEnglan": "NE", "New England": "NE",
    "NYJets": "NYJ", "NY Jets": "NYJ", "Baltimore": "BAL",
    "Cincinnati": "CIN", "Cleveland": "CLE", "Pittsburgh": "PIT",
    "Houston": "HOU", "Indianapolis": "IND", "Jacksonville": "JAX",
    "Tennessee": "TEN", "Denver": "DEN", "KansasCit": "KC", "Kansas City": "KC",
    "LasVegas": "LV", "Las Vegas": "LV", "LACharger": "LAC", "LA Chargers": "LAC",
    "Dallas": "DAL", "Philadelphia": "PHI", "Washington": "WSH",
    "SanFranci": "SF", "San Fran": "SF", "San Francisco": "SF",
    "Chicago": "CHI", "Detroit": "DET", "GreenBay": "GB", "Green Bay": "GB",
    "Minnesota": "MIN", "Atlanta": "ATL", "Carolina": "CAR",
    "NewOrlean": "NO", "New Orleans": "NO", "TampaBay": "TB", "Tampa Bay": "TB",
    "Arizona": "ARI", "LARams": "LAR", "LA Rams": "LAR", "Seattle": "SEA",
}


def fetch_sagarin_ratings(date_str: str, sport: str = "nba") -> dict:
    """
    Fetch Sagarin power ratings.
    Returns dict keyed by team abbreviation with rating value.
    Margin = home_rating - away_rating + home_advantage.
    """
    sport_pages = {
        "nba": "http://sagarin.com/sports/nbasend.htm",
        "nhl": "http://sagarin.com/sports/nhlsend.htm",
        "nfl": "http://sagarin.com/sports/nflsend.htm",
    }
    url = sport_pages.get(sport.lower())
    if not url:
        return {}

    ratings = {}

    try:
        html = _fetch_html(url, timeout=15)
        # Sagarin pages use <pre>/<font> formatted plain text.
        # Rating lines: "  1  Tampa Bay Lightning     =   4.81   48  28  ..."
        # Pattern: rank  team_name  =  rating  rest...
        # NBA ratings are ~80-100, NHL ~3-5, NFL ~50-100

        # Extract text content
        text = re.sub(r'<[^>]+>', '\n', html)

        # Rating ranges by sport (Sagarin uses different scales)
        rating_ranges = {
            "nba": (60, 130),
            "nhl": (2.0, 6.0),   # NHL uses goals-per-game scale ~3-5
            "nfl": (40, 110),
        }
        lo, hi = rating_ranges.get(sport.lower(), (0, 200))

        # Parse lines looking for: optional_rank  team_name  =  rating
        for line in text.split("\n"):
            line = line.strip()
            if not line or "=" not in line:
                continue

            # Pattern: digits(rank) team_name = rating digits...
            # The team name is everything between the rank and the =
            match = re.match(r'^\d*\s*(.*?)\s*=\s*(\d+\.?\d*)', line)
            if not match:
                continue

            team_name = match.group(1).strip()
            try:
                rating = float(match.group(2))
            except ValueError:
                continue

            if not (lo <= rating <= hi):
                continue

            # Try to resolve team name (exact, then partial)
            abbr = SAGARIN_TEAM_MAP.get(team_name)
            if not abbr:
                # Try matching known names within the team string
                for name, ab in SAGARIN_TEAM_MAP.items():
                    if name in team_name:
                        abbr = ab
                        break
            if not abbr:
                # Try matching just the first word (city name)
                first_word = team_name.split()[0] if team_name.split() else ""
                abbr = SAGARIN_TEAM_MAP.get(first_word)
            if abbr and abbr not in ratings:  # First match wins (avoid duplicates)
                ratings[abbr] = rating

        print(f"  Sagarin: loaded {len(ratings)} team ratings for {sport.upper()}")

    except Exception as e:
        print(f"  Sagarin fetch error ({sport}): {e}", file=sys.stderr)

    return ratings


def sagarin_to_predictions(ratings: dict, matchups: list, sport: str) -> dict:
    """
    Convert Sagarin ratings + today's matchups into score predictions.
    matchups: list of (away_abbr, home_abbr) tuples.
    """
    predictions = {}
    ha = HOME_ADVANTAGE.get(sport.lower(), 3.0)

    for away_abbr, home_abbr in matchups:
        away_rating = ratings.get(away_abbr)
        home_rating = ratings.get(home_abbr)
        if away_rating is None or home_rating is None:
            continue

        margin = (home_rating - away_rating) + ha
        away_score, home_score = _margin_to_scores(round(margin, 1), sport)

        key = f"{away_abbr}@{home_abbr}"
        predictions[key] = {
            "away_abbr": away_abbr, "home_abbr": home_abbr,
            "away_score": away_score, "home_score": home_score,
            "margin": round(margin, 1),
        }

    return predictions


# ══════════════════════════════════════════════════════
# 6. FANGRAPHS (MLB only — team projections)
# ══════════════════════════════════════════════════════

FANGRAPHS_TEAM_MAP = {
    "ARI": "ARI", "ATL": "ATL", "BAL": "BAL", "BOS": "BOS",
    "CHC": "CHC", "CHW": "CWS", "CIN": "CIN", "CLE": "CLE",
    "COL": "COL", "DET": "DET", "HOU": "HOU", "KCR": "KC",
    "LAA": "LAA", "LAD": "LAD", "MIA": "MIA", "MIL": "MIL",
    "MIN": "MIN", "NYM": "NYM", "NYY": "NYY", "OAK": "OAK",
    "PHI": "PHI", "PIT": "PIT", "SDP": "SD", "SEA": "SEA",
    "SFG": "SF", "STL": "STL", "TBR": "TB", "TEX": "TEX",
    "TOR": "TOR", "WSN": "WSH",
    # Full names
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Detroit Tigers": "DET",
    "Houston Astros": "HOU", "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Oakland Athletics": "OAK",
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD", "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB", "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH",
}


def fetch_fangraphs_projections(date_str: str) -> dict:
    """
    Fetch FanGraphs team strength projections for MLB.
    Returns dict keyed by team abbreviation with projected runs per game
    (offensive and defensive).
    """
    # FanGraphs Depth Charts standings/projections
    url = "https://www.fangraphs.com/depthcharts.aspx?position=Standings"
    projections = {}

    try:
        html = _fetch_html(url, timeout=20)

        # FanGraphs tables have team names and projected W-L, R/G, RA/G
        trs = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)

        for tr in trs:
            cells = [re.sub(r'<[^>]+>', '', c).strip()
                     for c in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)]
            if len(cells) < 5:
                continue

            # Find team name
            team_abbr = None
            rpg = None  # runs per game
            rapg = None  # runs allowed per game

            for cell in cells:
                if cell in FANGRAPHS_TEAM_MAP:
                    team_abbr = FANGRAPHS_TEAM_MAP[cell]
                elif not team_abbr:
                    mapped = FANGRAPHS_TEAM_MAP.get(cell)
                    if mapped:
                        team_abbr = mapped

            # Look for numeric values that could be R/G and RA/G
            nums = []
            for cell in cells:
                try:
                    v = float(cell)
                    if 2.0 <= v <= 7.0:  # Reasonable R/G range
                        nums.append(v)
                except ValueError:
                    pass

            if team_abbr and len(nums) >= 2:
                projections[team_abbr] = {
                    "rpg": nums[0],   # runs per game
                    "rapg": nums[1],  # runs allowed per game
                }

        print(f"  FanGraphs: loaded {len(projections)} team projections")

    except Exception as e:
        print(f"  FanGraphs fetch error: {e}", file=sys.stderr)

    return projections


def fangraphs_to_predictions(projections: dict, matchups: list) -> dict:
    """
    Convert FanGraphs team projections + today's matchups to score predictions.
    Away team scores: avg of away_team_rpg and home_team_rapg
    Home team scores: avg of home_team_rpg and away_team_rapg (+ small HFA)
    """
    predictions = {}
    ha = HOME_ADVANTAGE.get("mlb", 0.3)

    for away_abbr, home_abbr in matchups:
        away_proj = projections.get(away_abbr)
        home_proj = projections.get(home_abbr)
        if not away_proj or not home_proj:
            continue

        # Matchup-adjusted runs
        away_score = round((away_proj["rpg"] + home_proj["rapg"]) / 2, 1)
        home_score = round((home_proj["rpg"] + away_proj["rapg"]) / 2 + ha, 1)

        key = f"{away_abbr}@{home_abbr}"
        predictions[key] = {
            "away_abbr": away_abbr, "home_abbr": home_abbr,
            "away_score": away_score, "home_score": home_score,
            "margin": round(home_score - away_score, 1),
        }

    return predictions


# ══════════════════════════════════════════════════════
# 7. ACCUSCORE (Simulation-based — all sports)
# ══════════════════════════════════════════════════════

def fetch_accuscore_predictions(date_str: str, sport: str = "nba") -> dict:
    """
    Fetch simulation-based predictions from Accuscore.
    10,000+ simulations per game with projected scores.
    """
    sport_urls = {
        "nba": "https://www.accuscore.com/nba-basketball/nba/picks-and-predictions",
        "nhl": "https://www.accuscore.com/nhl-hockey/nhl/picks-and-predictions",
        "mlb": "https://www.accuscore.com/mlb-baseball/mlb/picks-and-predictions",
        "nfl": "https://www.accuscore.com/nfl-football/nfl/picks-and-predictions",
        "epl": "https://www.accuscore.com/soccer/english-premier-league/picks-and-predictions",
        "la_liga": "https://www.accuscore.com/soccer/spanish-la-liga/picks-and-predictions",
        "serie_a": "https://www.accuscore.com/soccer/italian-serie-a/picks-and-predictions",
        "bundesliga": "https://www.accuscore.com/soccer/german-bundesliga/picks-and-predictions",
    }
    url = sport_urls.get(sport.lower())
    if not url:
        return {}

    predictions = {}

    try:
        html = _fetch_html(url, timeout=20)

        # Accuscore shows predicted scores in match cards
        # Look for score patterns near team names

        # Try JSON-LD or embedded data
        json_blocks = re.findall(r'<script[^>]*type="application/(?:ld\+)?json"[^>]*>(.*?)</script>', html, re.DOTALL)
        for jb in json_blocks:
            try:
                data = json.loads(jb)
                if isinstance(data, list):
                    for item in data:
                        pred = _parse_accuscore_item(item, sport)
                        if pred:
                            predictions.update(pred)
                elif isinstance(data, dict):
                    pred = _parse_accuscore_item(data, sport)
                    if pred:
                        predictions.update(pred)
            except json.JSONDecodeError:
                continue

        # Fallback: parse HTML
        if not predictions:
            # Look for match containers with team names and scores
            # Pattern: team_name ... predicted_score ... team_name ... predicted_score
            match_divs = re.findall(
                r'class="[^"]*(?:match|game|prediction|pick)[^"]*"[^>]*>(.*?)</(?:div|section)',
                html, re.DOTALL
            )
            for div in match_divs:
                text = re.sub(r'<[^>]+>', ' ', div).strip()
                teams = []
                scores = []

                for word in text.split():
                    clean = word.strip("(),-")
                    if clean in ODDSSHARK_TEAM_MAP:
                        teams.append(ODDSSHARK_TEAM_MAP[clean])
                    elif clean in MASSEY_TEAM_MAP:
                        teams.append(MASSEY_TEAM_MAP[clean])
                    try:
                        v = float(word)
                        if _is_valid_score(v, sport):
                            scores.append(v)
                    except ValueError:
                        pass

                if len(teams) >= 2 and len(scores) >= 2:
                    key = f"{teams[0]}@{teams[1]}"
                    predictions[key] = {
                        "away_abbr": teams[0], "home_abbr": teams[1],
                        "away_score": scores[0], "home_score": scores[1],
                        "margin": round(scores[1] - scores[0], 1),
                    }

        print(f"  Accuscore: found {len(predictions)} game predictions for {sport.upper()}")

    except Exception as e:
        print(f"  Accuscore fetch error ({sport}): {e}", file=sys.stderr)

    return predictions


def _parse_accuscore_item(item: dict, sport: str) -> dict:
    """Parse an Accuscore JSON item into predictions."""
    if not isinstance(item, dict):
        return {}

    predictions = {}
    # Look for game/event structures
    for key in ["homeTeam", "home", "awayTeam", "away"]:
        if key in item:
            break
    else:
        return {}

    home_name = item.get("homeTeam", item.get("home", {
    })).get("name", "") if isinstance(item.get("homeTeam", item.get("home")), dict) else ""
    away_name = item.get("awayTeam", item.get("away", {
    })).get("name", "") if isinstance(item.get("awayTeam", item.get("away")), dict) else ""
    home_score = item.get("homeScore", item.get("predictedHomeScore"))
    away_score = item.get("awayScore", item.get("predictedAwayScore"))

    if not home_name or not away_name or home_score is None or away_score is None:
        return {}

    home_abbr = _resolve_team(home_name, sport)
    away_abbr = _resolve_team(away_name, sport)
    if not home_abbr or not away_abbr:
        return {}

    pk = f"{away_abbr}@{home_abbr}"
    predictions[pk] = {
        "away_abbr": away_abbr, "home_abbr": home_abbr,
        "away_score": float(away_score), "home_score": float(home_score),
        "margin": round(float(home_score) - float(away_score), 1),
    }
    return predictions


# ══════════════════════════════════════════════════════
# 8. ACTION NETWORK (Team score O/U → implied scores)
# ══════════════════════════════════════════════════════

# Action Network team IDs → ESPN abbreviations (populated on first fetch)
_ACTION_NETWORK_TEAM_CACHE = {}


def fetch_actionnetwork_predictions(date_str: str, sport: str = "nba") -> dict:
    """
    Fetch implied team scores from Action Network's scoreboard API.
    Uses team-specific over/under lines (core_bet_type_6_team_score)
    as implied projected scores. These are market-derived, not model-based,
    but represent the market's best estimate of each team's score.
    """
    sport_slugs = {
        "nba": "nba", "nhl": "nhl", "mlb": "mlb", "nfl": "nfl",
    }
    slug = sport_slugs.get(sport.lower())
    if not slug:
        return {}

    predictions = {}

    try:
        api_url = f"https://api.actionnetwork.com/web/v2/scoreboard/{slug}"
        hdrs = {
            **BROWSER_HEADERS,
            "Accept": "application/json, text/plain, */*",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Origin": "https://www.actionnetwork.com",
            "Referer": "https://www.actionnetwork.com/",
        }
        req = urllib.request.Request(api_url, headers=hdrs)
        with _opener.open(req, timeout=20) as resp:
            raw = resp.read()
            enc = resp.headers.get("Content-Encoding", "")
            if enc == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                import zlib
                raw = zlib.decompress(raw)
            elif enc == "br":
                try:
                    import brotli
                    raw = brotli.decompress(raw)
                except ImportError:
                    pass
            data = json.loads(raw.decode("utf-8", errors="ignore"))

        games = data.get("games", [])

        for game in games:
            if not isinstance(game, dict):
                continue

            # Skip games that are already final
            status = game.get("status", "")
            if status in ("final", "completed", "closed"):
                continue

            home_id = game.get("home_team_id")
            away_id = game.get("away_team_id")
            teams_data = game.get("teams", [])

            # Build team lookup — teams is a list of team objects, not a dict
            team_lookup = {}
            if isinstance(teams_data, list):
                for t in teams_data:
                    if isinstance(t, dict) and "id" in t:
                        team_lookup[t["id"]] = t
            elif isinstance(teams_data, dict):
                # Fallback if API changes to dict format
                team_lookup = {int(k) if k.isdigit() else k: v
                               for k, v in teams_data.items() if isinstance(v, dict)}

            # Resolve team abbreviations
            home_abbr = ""
            away_abbr = ""
            home_team = team_lookup.get(home_id, {})
            away_team = team_lookup.get(away_id, {})
            home_abbr = home_team.get("abbr", home_team.get("short_name", ""))
            away_abbr = away_team.get("abbr", away_team.get("short_name", ""))

            if not home_abbr or not away_abbr:
                continue

            # Normalize abbreviations
            home_abbr = _normalize_an_abbr(home_abbr, sport)
            away_abbr = _normalize_an_abbr(away_abbr, sport)

            # Find team score O/U lines from any sportsbook
            # These are in markets -> {book_id} -> event -> core_bet_type_6_team_score
            markets = game.get("markets", {})
            home_score = None
            away_score = None

            for book_id, book_data in markets.items():
                if not isinstance(book_data, dict):
                    continue
                event = book_data.get("event", {})
                if not isinstance(event, dict):
                    continue
                team_scores = event.get("core_bet_type_6_team_score", [])
                if not isinstance(team_scores, list):
                    continue

                for line in team_scores:
                    if not isinstance(line, dict):
                        continue
                    team_id = line.get("team_id")
                    value = line.get("value")
                    side = line.get("side", "")
                    if value is None or side != "over":
                        continue
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        continue

                    if team_id == home_id and home_score is None:
                        home_score = value
                    elif team_id == away_id and away_score is None:
                        away_score = value

                if home_score is not None and away_score is not None:
                    break  # Got both from this book

            if home_score is None or away_score is None:
                continue

            key = f"{away_abbr}@{home_abbr}"
            predictions[key] = {
                "away_abbr": away_abbr, "home_abbr": home_abbr,
                "away_score": away_score, "home_score": home_score,
                "margin": round(home_score - away_score, 1),
            }

        print(f"  ActionNetwork: found {len(predictions)} implied scores for {sport.upper()}")

    except Exception as e:
        print(f"  ActionNetwork fetch error ({sport}): {e}", file=sys.stderr)

    return predictions


# Action Network abbreviation normalization
_AN_ABBR_MAP = {
    # NBA
    "GS": "GS", "GSW": "GS", "SA": "SA", "SAS": "SA", "NO": "NO", "NOP": "NO",
    "NY": "NY", "NYK": "NY", "PHX": "PHX", "PHO": "PHX", "BKN": "BKN", "BRK": "BKN",
    "CHA": "CHA", "CHO": "CHA",
    # NHL
    "WSH": "WSH", "WAS": "WSH", "MTL": "MTL", "MON": "MTL",
    "NSH": "NSH", "NAS": "NSH", "CBJ": "CBJ", "CLB": "CBJ",
    "LAK": "LAK", "LA": "LAK", "CGY": "CGY", "CAL": "CGY",
    "WPG": "WPG", "WIN": "WPG", "VGK": "VGK",
    "UTA": "UTA", "ANA": "ANA", "NJ": "NJ", "NJD": "NJ",
    # MLB
    "CWS": "CWS", "CHW": "CWS", "KC": "KC", "KCR": "KC",
    "SD": "SD", "SDP": "SD", "SF": "SF", "SFG": "SF",
    "TB": "TB", "TBR": "TB",
}


def _normalize_an_abbr(abbr: str, sport: str) -> str:
    """Normalize an Action Network team abbreviation to ESPN standard."""
    abbr = abbr.strip().upper()
    # Handle "LA" specially
    if abbr == "LA":
        return _LA_BY_SPORT.get(sport.lower(), "LAK")
    return _AN_ABBR_MAP.get(abbr, abbr)


# ══════════════════════════════════════════════════════
# MAIN: Fetch all sources for a sport
# ══════════════════════════════════════════════════════

def fetch_all_sources(date_str: str, sport: str, matchups: list = None) -> dict:
    """
    Fetch predictions from all available sources for a given sport.

    Returns dict keyed by source name, each value is a predictions dict
    in the standard format: {"AWAY@HOME": {away_abbr, home_abbr, away_score, home_score, margin}}

    matchups: list of (away_abbr, home_abbr) tuples from ESPN schedule.
    Required for rating-based sources (Sagarin, Club Elo, FanGraphs).
    """
    matchups = matchups or []
    sources = {}

    # 1. Massey Ratings (all sports)
    try:
        massey = fetch_massey_predictions(date_str, sport)
        if massey:
            sources["massey"] = massey
    except Exception as e:
        print(f"  Massey error: {e}", file=sys.stderr)

    # 2. OddsShark (all sports)
    try:
        oddsshark = fetch_oddsshark_predictions(date_str, sport)
        if oddsshark:
            sources["oddsshark"] = oddsshark
    except Exception as e:
        print(f"  OddsShark error: {e}", file=sys.stderr)

    # 3. Club Elo (soccer only)
    is_soccer = sport.lower() in ("epl", "la_liga", "serie_a", "bundesliga", "ligue_1", "mls", "ucl")
    if is_soccer and matchups:
        try:
            elo_ratings = fetch_clubelo_ratings(date_str)
            if elo_ratings:
                clubelo = clubelo_to_predictions(elo_ratings, matchups, sport)
                if clubelo:
                    sources["clubelo"] = clubelo
        except Exception as e:
            print(f"  Club Elo error: {e}", file=sys.stderr)

    # 4. Forebet (soccer only)
    if is_soccer:
        try:
            forebet = fetch_forebet_predictions(date_str, sport)
            if forebet:
                sources["forebet"] = forebet
        except Exception as e:
            print(f"  Forebet error: {e}", file=sys.stderr)

    # 5. Sagarin (NBA, NHL, NFL)
    if sport.lower() in ("nba", "nhl", "nfl") and matchups:
        try:
            sag_ratings = fetch_sagarin_ratings(date_str, sport)
            if sag_ratings:
                sagarin = sagarin_to_predictions(sag_ratings, matchups, sport)
                if sagarin:
                    sources["sagarin"] = sagarin
        except Exception as e:
            print(f"  Sagarin error: {e}", file=sys.stderr)

    # 6. FanGraphs (MLB only)
    if sport.lower() == "mlb" and matchups:
        try:
            fg_proj = fetch_fangraphs_projections(date_str)
            if fg_proj:
                fangraphs = fangraphs_to_predictions(fg_proj, matchups)
                if fangraphs:
                    sources["fangraphs"] = fangraphs
        except Exception as e:
            print(f"  FanGraphs error: {e}", file=sys.stderr)

    # 7. Accuscore (all sports — may be Cloudflare-blocked)
    try:
        accuscore = fetch_accuscore_predictions(date_str, sport)
        if accuscore:
            sources["accuscore"] = accuscore
    except Exception as e:
        print(f"  Accuscore error: {e}", file=sys.stderr)

    # 8. Action Network (NBA, NHL, MLB, NFL — market-implied team scores)
    if sport.lower() in ("nba", "nhl", "mlb", "nfl"):
        try:
            an = fetch_actionnetwork_predictions(date_str, sport)
            if an:
                sources["actionnetwork"] = an
        except Exception as e:
            print(f"  ActionNetwork error: {e}", file=sys.stderr)

    print(f"  Total additional sources for {sport.upper()}: {len(sources)} "
          f"({', '.join(f'{k}({len(v)})' for k, v in sources.items())})")

    return sources
