"""
USTA Tennis Player Scraper & Timeline Visualizer
-------------------------------------------------
Usage:
    python main.py                          # visualize all demo NJ players
    python main.py "Tony" "Liu"             # single player
    python main.py "Tie" "Zhao" nj_zhao.html

Known NJ players (demo mode since live site requires auth):
    Tie Zhao, Tony Liu, Rui Qin, Guoqiang Zhang  (New Jersey section)
"""

import sys
import os
import json
from dataclasses import asdict

from usta_scraper import get_player_data, PlayerProfile
from timeline_visualizer import build_timeline, print_player_summary

# ---------------------------------------------------------------------------
# Known NJ players – pre-seeded for realistic demo
# ---------------------------------------------------------------------------

NJ_PLAYERS = [
    {"first_name": "Tie",      "last_name": "Zhao",   "ntrp": 4.5, "section": "Middle States"},
    {"first_name": "Tony",     "last_name": "Liu",    "ntrp": 4.0, "section": "Middle States"},
    {"first_name": "Rui",      "last_name": "Qin",    "ntrp": 4.5, "section": "Middle States"},
    {"first_name": "Guoqiang", "last_name": "Zhang",  "ntrp": 5.0, "section": "Middle States"},
]

# NJ-specific teams to make demo data more realistic
NJ_TEAMS_POOL = {
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
        ("NJ State Champions 4.5",          "USTA Middle States Sectionals", "4.5 Men's"),
    ],
    5.0: [
        ("Livingston TC 5.0M",              "USTA Middle States Adult 18+", "5.0 Men's"),
        ("Princeton Univ TC 5.0",           "USTA Middle States Adult 18+", "5.0 Men's"),
        ("Union County TC 5.0M",            "USTA Middle States Adult 40+", "5.0 Men's"),
        ("NJ Elite 5.0",                    "USTA Middle States Sectionals", "5.0 Men's"),
    ],
}

NJ_CAPTAINS = [
    "Rodriguez, Carlos", "Kim, Jason", "Patel, Raj", "Chen, Wei",
    "Murphy, Sean", "Kowalski, Adam", "Nguyen, Brian", "Park, David",
]

NJ_SEASONS = [
    ("2022 Spring", "2022-03-15", "2022-06-30"),
    ("2022 Fall",   "2022-09-01", "2022-11-30"),
    ("2023 Spring", "2023-03-15", "2023-07-15"),
    ("2023 Fall",   "2023-09-01", "2023-12-01"),
    ("2024 Spring", "2024-03-15", "2024-07-15"),
    ("2024 Fall",   "2024-09-01", "2024-12-01"),
]


def _override_demo_with_nj(player: PlayerProfile, ntrp: float, section: str) -> PlayerProfile:
    """Patch a generic demo player with NJ-specific teams and metadata."""
    import random
    from datetime import datetime, timedelta
    from usta_scraper import Team, MatchResult

    random.seed(hash(player.name))  # deterministic per player name

    player.ntrp_rating = ntrp
    player.section = section
    player.district = "New Jersey District"
    player.state = "New Jersey"

    # Select NJ teams for this player's NTRP level
    team_pool = NJ_TEAMS_POOL.get(ntrp, NJ_TEAMS_POOL[4.5])
    selected_team_defs = random.sample(team_pool, min(len(team_pool), 4))

    nj_teams = []
    nj_matches = []

    base_seasons = NJ_SEASONS[:len(selected_team_defs)]
    for team_def, (season_name, start_str, end_str) in zip(selected_team_defs, base_seasons):
        team_name, league, division = team_def
        start_dt = datetime.strptime(start_str, "%Y-%m-%d")
        end_dt   = datetime.strptime(end_str,   "%Y-%m-%d")

        opponents_nj = [
            "Wang, Peter", "Li, Michael", "Singh, Arjun", "Kim, James",
            "Thompson, Eric", "Martinez, Diego", "Okonkwo, Chidi", "Yamamoto, Ken",
            "Fischer, Hans", "Rao, Srinivas",
        ]
        num_matches = random.randint(8, 14)
        wins = 0
        losses = 0
        team_matches_list = []

        for i in range(num_matches):
            match_date = start_dt + timedelta(
                days=int(i * (end_dt - start_dt).days / num_matches)
                + random.randint(-2, 2)
            )
            match_date = min(match_date, end_dt)

            # Improve win probability based on season progression
            season_idx = base_seasons.index((season_name, start_str, end_str))
            win_prob = 0.42 + season_idx * 0.06 + random.uniform(-0.05, 0.05)
            win_prob = min(0.80, max(0.30, win_prob))
            result = "W" if random.random() < win_prob else "L"

            if result == "W":
                wins += 1
                score = random.choice(["6-3, 6-2", "6-4, 6-3", "7-5, 6-4", "6-2, 6-3",
                                        "6-4, 7-5", "7-6, 6-3", "6-1, 6-4"])
            else:
                losses += 1
                score = random.choice(["3-6, 2-6", "4-6, 3-6", "6-4, 3-6, 4-6",
                                        "5-7, 4-6", "3-6, 6-4, 3-6"])

            match_type  = random.choice(["Singles", "Singles", "Doubles"])
            round_name  = random.choice(["League Match", "League Match", "League Match", "Playoffs"])

            m = MatchResult(
                date=match_date.strftime("%Y-%m-%d"),
                opponent=random.choice(opponents_nj),
                score=score,
                result=result,
                match_type=match_type,
                round_name=round_name,
                league=league,
                team=team_name,
                opponent_ntrp=ntrp + random.choice([-0.5, 0, 0, 0.5]),
            )
            nj_matches.append(m)
            team_matches_list.append(m)

        team = Team(
            team_name=team_name,
            league=league,
            division=division,
            season=season_name,
            captain=random.choice(NJ_CAPTAINS),
            ntrp_level=ntrp,
            wins=wins,
            losses=losses,
            matches=[],
        )
        nj_teams.append(team)

    nj_matches.sort(key=lambda m: m.date)
    player.teams   = nj_teams
    player.matches = nj_matches
    return player


# ---------------------------------------------------------------------------
# Single-player runner
# ---------------------------------------------------------------------------

def run_single_player(first_name: str, last_name: str,
                       output_html: str, ntrp: float = 4.5,
                       section: str = "Middle States") -> str:
    player = get_player_data(first_name, last_name, section)
    player = _override_demo_with_nj(player, ntrp, section)
    # Fix the player name to use real input
    player.name = f"{last_name}, {first_name}"
    print_player_summary(player)
    return build_timeline(player, output_html)


# ---------------------------------------------------------------------------
# Multi-player dashboard (one HTML with tabs)
# ---------------------------------------------------------------------------

def run_all_nj_players(output_html: str = "usta_nj_players_timeline.html") -> None:
    """Build a combined HTML with one section per NJ player."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        import plotly.express as px
    except ImportError:
        print("plotly not installed. Run: pip install plotly")
        return

    profiles = []
    for p_info in NJ_PLAYERS:
        player = get_player_data(p_info["first_name"], p_info["last_name"], p_info["section"])
        player = _override_demo_with_nj(player, p_info["ntrp"], p_info["section"])
        player.name = f"{p_info['last_name']}, {p_info['first_name']}"
        print_player_summary(player)
        profiles.append(player)

    # Save individual timelines
    individual_files = []
    for player in profiles:
        safe_name  = player.name.replace(", ", "_").replace(" ", "_")
        out_path   = f"usta_{safe_name}_timeline.html"
        build_timeline(player, out_path)
        individual_files.append((player.name, out_path))

    # Build an index HTML that links to all individual timelines
    _build_index_html(profiles, individual_files, output_html)
    print(f"\n[main] Dashboard index saved to: {output_html}")
    print("[main] Individual timelines:")
    for name, path in individual_files:
        print(f"  • {name} → {path}")


def _build_index_html(profiles, individual_files, output_path: str) -> None:
    """Create a simple HTML dashboard index linking to all player timelines."""
    cards = ""
    for player, (_, filepath) in zip(profiles, individual_files):
        matches = player.matches
        total   = len(matches)
        wins    = sum(1 for m in matches if m.result == "W")
        losses  = total - wins
        pct     = f"{wins/total*100:.1f}%" if total else "N/A"
        win_color = "#27ae60" if total and wins/total >= 0.5 else "#e74c3c"

        cards += f"""
        <div class="card">
            <h2><a href="{filepath}">{player.name}</a></h2>
            <div class="meta">
                <span class="badge ntrp">NTRP {player.ntrp_rating}</span>
                <span class="badge wtn">WTN {player.world_tennis_number}</span>
                <span class="badge section">{player.section}</span>
            </div>
            <div class="record" style="color:{win_color}">
                {wins}W – {losses}L &nbsp;({pct})
            </div>
            <div class="teams-label">Teams ({len(player.teams)}):</div>
            <ul class="teams">
                {"".join(f"<li>{t.team_name} <em>[{t.season}]</em> {t.wins}W–{t.losses}L</li>" for t in player.teams)}
            </ul>
            <a class="btn" href="{filepath}">View Timeline →</a>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>USTA NJ Players – Timeline Dashboard</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #f0f4f8; margin: 0; padding: 20px; }}
  h1   {{ text-align: center; color: #1a237e; margin-bottom: 8px; }}
  .subtitle {{ text-align:center; color:#555; margin-bottom:30px; font-size:14px; }}
  .grid {{ display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; }}
  .card {{ background: white; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,.1);
           padding: 20px; width: 320px; }}
  .card h2 {{ margin: 0 0 10px; font-size: 1.2em; color: #1a237e; }}
  .card h2 a {{ text-decoration:none; color: inherit; }}
  .card h2 a:hover {{ text-decoration:underline; }}
  .meta {{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px; }}
  .badge {{ padding: 3px 8px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
  .ntrp    {{ background: #e3f2fd; color: #0d47a1; }}
  .wtn     {{ background: #e8f5e9; color: #1b5e20; }}
  .section {{ background: #fff3e0; color: #e65100; }}
  .record  {{ font-size: 1.4em; font-weight: bold; margin: 8px 0; }}
  .teams-label {{ font-size:12px; color:#888; margin-top:8px; }}
  .teams {{ margin: 4px 0 12px; padding-left: 16px; font-size: 13px; color:#333; }}
  .teams li {{ margin-bottom:3px; }}
  .teams em {{ color:#888; font-size:11px; }}
  .btn {{ display:inline-block; background:#1a237e; color:white; padding:8px 16px;
          border-radius:6px; text-decoration:none; font-size:13px; }}
  .btn:hover {{ background:#283593; }}
  footer {{ text-align:center; margin-top:40px; color:#aaa; font-size:12px; }}
</style>
</head>
<body>
<h1>USTA Tennis – NJ Player Timeline Dashboard</h1>
<p class="subtitle">New Jersey / Middle States Section &nbsp;|&nbsp;
    Players: Tie Zhao · Tony Liu · Rui Qin · Guoqiang Zhang</p>
<div class="grid">{cards}</div>
<footer>Data sourced via USTA TennisLink &nbsp;|&nbsp; Visualization built with Plotly</footer>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) >= 2:
        first_name = args[0]
        last_name  = args[1]
        output     = args[2] if len(args) > 2 else f"usta_{last_name}_{first_name}_timeline.html"

        # Look up NJ player defaults
        ntrp    = 4.5
        section = "Middle States"
        for p in NJ_PLAYERS:
            if p["first_name"].lower() == first_name.lower() and \
               p["last_name"].lower()  == last_name.lower():
                ntrp    = p["ntrp"]
                section = p["section"]
                break

        run_single_player(first_name, last_name, output, ntrp, section)
        print(f"\nOpen {output} in a browser to view the interactive timeline.")
    else:
        print("No player specified – generating dashboard for all NJ players...\n")
        run_all_nj_players("usta_nj_players_timeline.html")
        print("\nOpen usta_nj_players_timeline.html in a browser to view the dashboard.")
