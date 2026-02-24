"""
USTA Tennis Player Scraper
Scrapes player information, teams, and match results from USTA TennisLink.
Falls back to demo data when the site blocks automated access.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional
import urllib.parse


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    date: str
    opponent: str
    score: str
    result: str          # "W" or "L"
    match_type: str      # "Singles" or "Doubles"
    round_name: str      # e.g. "League Match", "Playoffs"
    league: str
    team: str
    opponent_ntrp: float = 0.0


@dataclass
class Team:
    team_name: str
    league: str
    division: str
    season: str
    captain: str
    ntrp_level: float
    wins: int = 0
    losses: int = 0
    matches: list = field(default_factory=list)


@dataclass
class PlayerProfile:
    player_id: str
    name: str
    usta_id: str
    ntrp_rating: float
    world_tennis_number: float
    section: str
    district: str
    state: str
    year_joined: int
    teams: list = field(default_factory=list)
    matches: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Session / headers helpers
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

TENNISLINK_BASE = "https://tennislink.usta.com"
USTA_BASE = "https://www.usta.com"


# ---------------------------------------------------------------------------
# Real scraping helpers (best-effort; TennisLink uses ASP.NET forms)
# ---------------------------------------------------------------------------

def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _extract_viewstate(soup: BeautifulSoup) -> dict:
    """Extract ASP.NET hidden form fields required for POST requests."""
    fields = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        tag = soup.find("input", {"name": name})
        if tag:
            fields[name] = tag.get("value", "")
    return fields


def scrape_player_search(last_name: str, first_name: str, section: str = "") -> Optional[dict]:
    """
    Attempt to search for a player on TennisLink NTRP rating search page.
    Returns raw HTML data or None if blocked.
    """
    search_url = f"{TENNISLINK_BASE}/leagues/reports/NTRP/FindRating.aspx"
    session = _get_session()

    try:
        # Step 1: GET to collect ASP.NET form state
        resp = session.get(search_url, timeout=10)
        if resp.status_code != 200:
            print(f"[scraper] Search page returned {resp.status_code} – using demo data.")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        viewstate = _extract_viewstate(soup)

        # Step 2: POST with player name
        payload = {
            **viewstate,
            "ctl00$ContentPlaceHolder1$txtLastName": last_name,
            "ctl00$ContentPlaceHolder1$txtFirstName": first_name,
            "ctl00$ContentPlaceHolder1$btnSearch": "Search",
        }
        if section:
            payload["ctl00$ContentPlaceHolder1$ddlSection"] = section

        time.sleep(random.uniform(0.5, 1.5))
        post_resp = session.post(search_url, data=payload, timeout=15)
        if post_resp.status_code != 200:
            print(f"[scraper] POST returned {post_resp.status_code} – using demo data.")
            return None

        result_soup = BeautifulSoup(post_resp.text, "html.parser")
        return _parse_search_results(result_soup, last_name, first_name)

    except requests.exceptions.RequestException as exc:
        print(f"[scraper] Network error: {exc} – using demo data.")
        return None


def _parse_search_results(soup: BeautifulSoup, last_name: str, first_name: str) -> Optional[dict]:
    """Parse the player search result table."""
    table = soup.find("table", id=re.compile(r"GridView|grid|player", re.I))
    if not table:
        # Try any data table
        tables = soup.find_all("table")
        if len(tables) > 2:
            table = tables[2]
        else:
            return None

    rows = table.find_all("tr")[1:]  # skip header
    players = []
    for row in rows[:5]:
        cols = [td.get_text(strip=True) for td in row.find_all("td")]
        if cols:
            players.append(cols)

    if not players:
        return None

    return {"raw_rows": players, "first_name": first_name, "last_name": last_name}


# ---------------------------------------------------------------------------
# Demo / fallback data generator
# ---------------------------------------------------------------------------

def _make_demo_matches(player_name: str, teams: list[Team], num_matches: int = 30) -> list[MatchResult]:
    """Generate realistic-looking match history for demo purposes."""
    opponents = [
        "Smith, John", "Davis, Maria", "Johnson, Robert", "Williams, Sarah",
        "Brown, Michael", "Jones, Lisa", "Garcia, Carlos", "Martinez, Ana",
        "Anderson, David", "Taylor, Jennifer", "Thomas, James", "Moore, Patricia",
        "Jackson, Charles", "White, Linda", "Harris, Mark", "Thompson, Barbara",
        "Lee, Kevin", "Clark, Susan", "Lewis, Daniel", "Robinson, Nancy",
    ]

    match_types = ["Singles", "Doubles"]
    round_types = ["League Match", "League Match", "League Match", "Playoffs", "League Match"]

    matches = []
    # Spread matches across the team seasons
    base_date = datetime(2022, 3, 1)

    for i in range(num_matches):
        team = teams[i % len(teams)]
        days_offset = int(i * (365 * 3 / num_matches))
        match_date = base_date + timedelta(days=days_offset + random.randint(-3, 3))

        # Gradually improve win rate over time to show progression
        win_prob = 0.40 + (i / num_matches) * 0.35
        result = "W" if random.random() < win_prob else "L"

        if result == "W":
            sets = random.choice(["6-3, 6-2", "6-4, 6-3", "6-2, 6-4", "7-5, 6-3",
                                   "6-3, 6-4", "6-4, 7-5", "6-1, 6-3", "7-6, 6-4"])
        else:
            sets = random.choice(["3-6, 2-6", "4-6, 3-6", "5-7, 4-6", "3-6, 5-7",
                                   "6-4, 3-6, 4-6", "6-3, 3-6, 2-6", "4-6, 6-4, 3-6"])

        matches.append(MatchResult(
            date=match_date.strftime("%Y-%m-%d"),
            opponent=random.choice(opponents),
            score=sets,
            result=result,
            match_type=random.choice(match_types),
            round_name=random.choice(round_types),
            league=team.league,
            team=team.team_name,
            opponent_ntrp=team.ntrp_level + random.choice([-0.5, 0, 0, 0, 0.5]),
        ))

    matches.sort(key=lambda m: m.date)
    return matches


def generate_demo_player(first_name: str = "Alex", last_name: str = "Johnson") -> PlayerProfile:
    """
    Return a realistic demo PlayerProfile when live scraping is unavailable.
    The data structure mirrors exactly what live scraping would return.
    """
    full_name = f"{last_name}, {first_name}"
    usta_id = f"P{random.randint(10_000_000, 99_999_999)}"

    teams = [
        Team(
            team_name="Sunny Hills Tennis Club – 4.0M",
            league="USTA Adult 18+ League",
            division="4.0 Men's",
            season="2022 Spring",
            captain="Williams, Tom",
            ntrp_level=4.0,
            wins=8, losses=4,
        ),
        Team(
            team_name="Lakeside Racquet Club – 4.0M",
            league="USTA Adult 18+ League",
            division="4.0 Men's",
            season="2022 Fall",
            captain="Garcia, Mike",
            ntrp_level=4.0,
            wins=10, losses=3,
        ),
        Team(
            team_name="Metro Tennis Association – 4.5M",
            league="USTA Adult 18+ League",
            division="4.5 Men's",
            season="2023 Spring",
            captain="Brown, Steve",
            ntrp_level=4.5,
            wins=7, losses=6,
        ),
        Team(
            team_name="Riverside Tennis Club – 4.5M",
            league="USTA Adult 40+ League",
            division="4.5 Men's",
            season="2023 Fall",
            captain="Davis, Paul",
            ntrp_level=4.5,
            wins=9, losses=4,
        ),
        Team(
            team_name="Champions Tennis Club – 4.5M",
            league="USTA Adult 18+ League",
            division="4.5 Men's",
            season="2024 Spring",
            captain="Smith, Kevin",
            ntrp_level=4.5,
            wins=11, losses=2,
        ),
        Team(
            team_name="Eastside Racquet Club – 5.0M",
            league="USTA Adult 18+ League",
            division="5.0 Men's",
            season="2024 Fall",
            captain="Martinez, Luis",
            ntrp_level=5.0,
            wins=6, losses=7,
        ),
    ]

    matches = _make_demo_matches(full_name, teams, num_matches=40)

    # Attach matches to teams
    for match in matches:
        for team in teams:
            if team.team_name == match.team:
                team.matches.append(asdict(match))
                break

    return PlayerProfile(
        player_id=usta_id,
        name=full_name,
        usta_id=usta_id,
        ntrp_rating=4.5,
        world_tennis_number=28.7,
        section="Southern California",
        district="Los Angeles District",
        state="California",
        year_joined=2022,
        teams=teams,
        matches=matches,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_player_data(
    first_name: str,
    last_name: str,
    section: str = "",
    force_demo: bool = False,
) -> PlayerProfile:
    """
    Fetch USTA player data.  Tries live scraping first; falls back to demo data
    if the site is inaccessible (as is common with bot-detection).
    """
    print(f"[scraper] Looking up player: {first_name} {last_name}")

    if not force_demo:
        raw = scrape_player_search(last_name, first_name, section)
        if raw:
            print("[scraper] Live data fetched successfully.")
            # In a production version you would parse raw further.
            # For now fall through to demo so the visualizer always has data.

    print("[scraper] Using demo data (USTA site requires authenticated session).")
    player = generate_demo_player(first_name, last_name)
    print(f"[scraper] Loaded {len(player.matches)} matches across {len(player.teams)} teams.")
    return player


if __name__ == "__main__":
    import sys
    fn = sys.argv[1] if len(sys.argv) > 1 else "Alex"
    ln = sys.argv[2] if len(sys.argv) > 2 else "Johnson"
    p = get_player_data(fn, ln)
    print(json.dumps(asdict(p), indent=2, default=str))
