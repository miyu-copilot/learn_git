"""
USTA Tennis Player Scraper — tennisrecord.com
=============================================
Scrapes player profile, team history, and match results from:
  https://www.tennisrecord.com/adult/profile.aspx?playername=<First Last>

Falls back to deterministic demo data when the site is unreachable.
"""

import re
import time
import random
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional
import urllib.parse


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    date: str            # "YYYY-MM-DD"
    partner: str         # doubles partner or "" for singles
    opponent: str        # opponent name(s)
    score: str           # e.g. "6-3, 6-2"
    result: str          # "W" or "L"
    match_type: str      # "Singles" or "Doubles"
    line: str            # court position, e.g. "S1", "D1"
    team: str
    league: str
    season: str


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


@dataclass
class PlayerProfile:
    name: str
    usta_id: str
    ntrp_rating: float
    section: str
    district: str
    state: str
    year_joined: int
    teams: list = field(default_factory=list)
    matches: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.tennisrecord.com/",
}

BASE_URL = "https://www.tennisrecord.com/adult/profile.aspx"


def _fetch_profile_html(player_name: str) -> Optional[str]:
    """GET the tennisrecord.com profile page and return raw HTML, or None on failure."""
    url = f"{BASE_URL}?playername={urllib.parse.quote(player_name)}"
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            print(f"[scraper] Fetched profile for '{player_name}' from tennisrecord.com")
            return resp.text
        else:
            print(f"[scraper] HTTP {resp.status_code} for '{player_name}' — using demo data.")
            return None
    except requests.exceptions.RequestException as exc:
        print(f"[scraper] Network error for '{player_name}': {exc} — using demo data.")
        return None


# ---------------------------------------------------------------------------
# HTML parsers for tennisrecord.com
# ---------------------------------------------------------------------------

def _parse_player_info(soup: BeautifulSoup) -> dict:
    """Extract header-level player info (NTRP, section, etc.)."""
    info = {
        "usta_id": "",
        "ntrp_rating": 0.0,
        "section": "",
        "district": "",
        "state": "",
        "year_joined": 0,
    }

    # The player info usually lives in a summary div or table near the top.
    # Common patterns on tennisrecord.com:
    for label_tag in soup.find_all(string=re.compile(r"NTRP|Rating|Section|District|USTA ID", re.I)):
        parent = label_tag.parent
        text = parent.get_text(" ", strip=True)

        if re.search(r"NTRP|Rating", text, re.I):
            m = re.search(r"(\d\.\d)", text)
            if m:
                info["ntrp_rating"] = float(m.group(1))

        if re.search(r"Section", text, re.I):
            m = re.search(r"Section[:\s]+([A-Za-z ]+)", text, re.I)
            if m:
                info["section"] = m.group(1).strip()

        if re.search(r"District", text, re.I):
            m = re.search(r"District[:\s]+([A-Za-z ]+)", text, re.I)
            if m:
                info["district"] = m.group(1).strip()

        if re.search(r"USTA ID", text, re.I):
            m = re.search(r"(\d{7,12})", text)
            if m:
                info["usta_id"] = m.group(1)

    # Fallback: scan all text blocks
    page_text = soup.get_text(" ", strip=True)
    if not info["ntrp_rating"]:
        m = re.search(r"NTRP[:\s]+(\d\.\d)", page_text, re.I)
        if m:
            info["ntrp_rating"] = float(m.group(1))
    if not info["section"]:
        m = re.search(r"Section[:\s]+([A-Za-z ]+?)(?:\s{2,}|$)", page_text, re.I)
        if m:
            info["section"] = m.group(1).strip()

    return info


def _parse_matches(soup: BeautifulSoup, player_name: str) -> list[MatchResult]:
    """
    Parse the match-result tables on tennisrecord.com.

    The page typically has one table (or one per season/team) with columns:
      Date | Partner | Opponent | Score | W/L | Line | Team | League/Season
    Column order can vary; we detect by header text.
    """
    matches = []

    tables = soup.find_all("table")
    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not headers:
            # Try first row as header
            first_row = table.find("tr")
            if first_row:
                headers = [td.get_text(strip=True).lower() for td in first_row.find_all(["th", "td"])]

        # Must have at least date + score columns to be a match table
        if not any("date" in h for h in headers):
            continue

        col = {
            "date":     _col_idx(headers, ["date"]),
            "partner":  _col_idx(headers, ["partner"]),
            "opponent": _col_idx(headers, ["opponent", "opponents"]),
            "score":    _col_idx(headers, ["score"]),
            "result":   _col_idx(headers, ["w/l", "result", "win"]),
            "line":     _col_idx(headers, ["line", "court", "pos"]),
            "team":     _col_idx(headers, ["team"]),
            "league":   _col_idx(headers, ["league", "division", "season"]),
            "season":   _col_idx(headers, ["season", "year"]),
        }

        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 3:
                continue

            def _get(key, default=""):
                idx = col.get(key, -1)
                if idx is None or idx < 0 or idx >= len(cells):
                    return default
                return cells[idx].strip()

            raw_date = _get("date")
            if not raw_date or not re.search(r"\d", raw_date):
                continue

            # Normalise date
            date_str = _normalise_date(raw_date)
            if not date_str:
                continue

            partner  = _get("partner")
            opponent = _get("opponent")
            score    = _get("score")
            result   = _get("result", "").upper()
            if result not in ("W", "L"):
                result = "W" if re.search(r"\bW\b|win", _get("result"), re.I) else "L"
            line     = _get("line")
            team     = _get("team")
            league   = _get("league") or _get("season")
            season   = _get("season") or league

            match_type = "Doubles" if partner else "Singles"

            matches.append(MatchResult(
                date=date_str,
                partner=partner,
                opponent=opponent,
                score=score,
                result=result,
                match_type=match_type,
                line=line,
                team=team,
                league=league,
                season=season,
            ))

    matches.sort(key=lambda m: m.date)
    return matches


def _col_idx(headers: list[str], keywords: list[str]) -> int:
    """Return the first header index that contains any keyword, or -1."""
    for i, h in enumerate(headers):
        for kw in keywords:
            if kw in h:
                return i
    return -1


def _normalise_date(raw: str) -> Optional[str]:
    """Try several date formats and return YYYY-MM-DD or None."""
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y",
                "%d-%b-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Try partial: "Sep 12, 2023"
    m = re.search(r"(\w+ \d{1,2},? \d{4})", raw)
    if m:
        for fmt in ("%B %d %Y", "%b %d %Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(m.group(1).replace(",", ""), fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def _derive_teams_from_matches(matches: list[MatchResult], ntrp: float) -> list[Team]:
    """Build Team objects from the match list (group by team name + season)."""
    seen: dict[str, Team] = {}
    for m in matches:
        key = f"{m.team}|{m.season}"
        if key not in seen:
            # Infer NTRP from league/division text
            inferred_ntrp = _infer_ntrp(m.league or m.season) or ntrp
            seen[key] = Team(
                team_name=m.team or "Unknown Team",
                league=m.league,
                division=m.league,
                season=m.season,
                captain="",
                ntrp_level=inferred_ntrp,
            )
        t = seen[key]
        if m.result == "W":
            t.wins += 1
        else:
            t.losses += 1
    return sorted(seen.values(), key=lambda t: t.season)


def _infer_ntrp(text: str) -> Optional[float]:
    m = re.search(r"(\d\.\d)", text or "")
    if m:
        return float(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Live scraping entry point
# ---------------------------------------------------------------------------

def scrape_player(player_name: str) -> Optional[PlayerProfile]:
    """
    Attempt to scrape tennisrecord.com for player_name ("First Last").
    Returns a PlayerProfile on success, None on failure.
    """
    html = _fetch_profile_html(player_name)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")

    # Check if we got a meaningful player page (not a "no results" page)
    page_text = soup.get_text(" ", strip=True)
    if re.search(r"no results|no player found|not found", page_text, re.I):
        print(f"[scraper] No results for '{player_name}' on tennisrecord.com.")
        return None

    info    = _parse_player_info(soup)
    matches = _parse_matches(soup, player_name)

    if not matches:
        print(f"[scraper] Parsed 0 matches for '{player_name}' — page structure may have changed.")
        return None

    ntrp  = info["ntrp_rating"] or 4.0
    teams = _derive_teams_from_matches(matches, ntrp)

    print(f"[scraper] Parsed {len(matches)} matches across {len(teams)} teams for '{player_name}'.")

    # Normalise name to "Last, First"
    parts = player_name.strip().split()
    norm_name = f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) > 1 else player_name

    return PlayerProfile(
        name=norm_name,
        usta_id=info["usta_id"] or f"P{random.randint(10_000_000, 99_999_999)}",
        ntrp_rating=ntrp,
        section=info["section"] or "Middle States",
        district=info["district"] or "New Jersey District",
        state="New Jersey",
        year_joined=info["year_joined"] or _earliest_year(matches),
        teams=teams,
        matches=matches,
    )


def _earliest_year(matches: list[MatchResult]) -> int:
    if not matches:
        return 2020
    try:
        return int(min(m.date for m in matches)[:4])
    except Exception:
        return 2020


# ---------------------------------------------------------------------------
# Demo / fallback data  (deterministic per player name)
# ---------------------------------------------------------------------------

_NJ_TEAMS = {
    4.0: [
        ("Princeton Tennis Center 4.0M",   "USTA Middle States Adult 18+", "4.0 Men's"),
        ("Mercer County 4.0 Men",           "USTA Middle States Adult 40+", "4.0 Men's"),
        ("Bergen Racquet Club 4.0",         "USTA Middle States Adult 18+", "4.0 Men's"),
        ("Essex County TC 4.0M",            "USTA Middle States Adult 18+", "4.0 Men's"),
    ],
    4.5: [
        ("Morris County TC 4.5M",           "USTA Middle States Adult 18+", "4.5 Men's"),
        ("Bridgewater Racquet Club 4.5",    "USTA Middle States Adult 40+", "4.5 Men's"),
        ("Short Hills Club 4.5M",           "USTA Middle States Adult 18+", "4.5 Men's"),
        ("Montclair TC 4.5M",               "USTA Middle States Adult 18+", "4.5 Men's"),
        ("NJ State Champions 4.5",          "USTA Middle States Sectionals","4.5 Men's"),
    ],
    5.0: [
        ("Livingston TC 5.0M",              "USTA Middle States Adult 18+", "5.0 Men's"),
        ("Princeton Univ TC 5.0",           "USTA Middle States Adult 18+", "5.0 Men's"),
        ("Union County TC 5.0M",            "USTA Middle States Adult 40+", "5.0 Men's"),
        ("NJ Elite 5.0",                    "USTA Middle States Sectionals","5.0 Men's"),
    ],
}

_NJ_OPPONENTS = [
    "Wang, Peter", "Li, Michael", "Singh, Arjun", "Kim, James",
    "Thompson, Eric", "Martinez, Diego", "Okonkwo, Chidi", "Yamamoto, Ken",
    "Fischer, Hans", "Rao, Srinivas", "Park, David", "Chen, Wei",
    "Murphy, Sean", "Kowalski, Adam", "Nguyen, Brian", "Patel, Raj",
]

_NJ_PARTNERS = [
    "Zhang, Wei", "Liu, Yang", "Wang, Hao", "Chen, Long",
    "Kim, Jason", "Park, Kevin", "Rodriguez, Carlos", "Patel, Raj",
]

_SEASONS = [
    ("2022 Spring", "2022-03-15", "2022-06-30"),
    ("2022 Fall",   "2022-09-01", "2022-11-30"),
    ("2023 Spring", "2023-03-15", "2023-07-15"),
    ("2023 Fall",   "2023-09-01", "2023-12-01"),
    ("2024 Spring", "2024-03-15", "2024-07-15"),
    ("2024 Fall",   "2024-09-01", "2024-12-01"),
]


def generate_demo_player(first_name: str, last_name: str, ntrp: float = 4.5) -> PlayerProfile:
    """Return a realistic-looking demo PlayerProfile (used when live scraping fails)."""
    rng = random.Random(hash(f"{first_name}{last_name}"))  # deterministic

    team_pool  = _NJ_TEAMS.get(ntrp, _NJ_TEAMS[4.5])
    team_defs  = rng.sample(team_pool, min(len(team_pool), 4))
    seasons    = _SEASONS[:len(team_defs)]

    teams: list[Team]       = []
    matches: list[MatchResult] = []

    lines_s = ["S1", "S2", "S3"]
    lines_d = ["D1", "D2", "D3"]

    for team_def, (season_name, start_str, end_str) in zip(team_defs, seasons):
        team_name, league, division = team_def
        start_dt = datetime.strptime(start_str, "%Y-%m-%d")
        end_dt   = datetime.strptime(end_str,   "%Y-%m-%d")
        span     = (end_dt - start_dt).days
        n_matches = rng.randint(8, 14)

        season_idx = seasons.index((season_name, start_str, end_str))
        w = l = 0

        for i in range(n_matches):
            match_dt = start_dt + timedelta(
                days=int(i * span / n_matches) + rng.randint(-2, 2)
            )
            match_dt = min(match_dt, end_dt)

            win_prob = 0.42 + season_idx * 0.06 + rng.uniform(-0.05, 0.05)
            win_prob = max(0.25, min(0.82, win_prob))
            result   = "W" if rng.random() < win_prob else "L"

            is_doubles  = rng.random() < 0.35
            match_type  = "Doubles" if is_doubles else "Singles"
            partner     = rng.choice(_NJ_PARTNERS) if is_doubles else ""
            opponent    = rng.choice(_NJ_OPPONENTS)
            if is_doubles:
                opponent += " / " + rng.choice(_NJ_OPPONENTS)
            line = rng.choice(lines_d if is_doubles else lines_s)

            if result == "W":
                w += 1
                score = rng.choice(["6-3, 6-2", "6-4, 6-3", "7-5, 6-4",
                                     "6-2, 6-3", "6-4, 7-5", "7-6, 6-3"])
            else:
                l += 1
                score = rng.choice(["3-6, 2-6", "4-6, 3-6",
                                     "6-4, 3-6, 4-6", "5-7, 4-6"])

            matches.append(MatchResult(
                date=match_dt.strftime("%Y-%m-%d"),
                partner=partner,
                opponent=opponent,
                score=score,
                result=result,
                match_type=match_type,
                line=line,
                team=team_name,
                league=league,
                season=season_name,
            ))

        teams.append(Team(
            team_name=team_name,
            league=league,
            division=division,
            season=season_name,
            captain=rng.choice(["Rodriguez, C.", "Kim, J.", "Patel, R.", "Chen, W."]),
            ntrp_level=ntrp,
            wins=w,
            losses=l,
        ))

    matches.sort(key=lambda m: m.date)

    return PlayerProfile(
        name=f"{last_name}, {first_name}",
        usta_id=f"P{rng.randint(10_000_000, 99_999_999)}",
        ntrp_rating=ntrp,
        section="Middle States",
        district="New Jersey District",
        state="New Jersey",
        year_joined=2022,
        teams=teams,
        matches=matches,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_player_data(
    first_name: str,
    last_name: str,
    ntrp: float = 4.5,
    force_demo: bool = False,
) -> PlayerProfile:
    """
    Return a PlayerProfile by scraping tennisrecord.com, falling back to demo data.
    """
    full_name = f"{first_name} {last_name}"
    print(f"\n[scraper] === {full_name} ===")

    if not force_demo:
        profile = scrape_player(full_name)
        if profile:
            return profile

    print(f"[scraper] Using demo data for {full_name}.")
    return generate_demo_player(first_name, last_name, ntrp)
