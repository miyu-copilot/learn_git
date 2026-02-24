"""
USTA Tennis Player Scraper & Timeline Visualizer
-------------------------------------------------
Data source : https://www.tennisrecord.com/adult/profile.aspx?playername=<name>

Usage
-----
  python main.py                        # build dashboard for all 4 NJ players
  python main.py "Tie" "Zhao"           # single player (ntrp auto-detected)
  python main.py "Tony" "Liu" tony.html # single player, custom output file

Then open the HTML file in any browser.
"""

import sys
from usta_scraper import get_player_data, PlayerProfile
from timeline_visualizer import build_timeline, print_player_summary


# ---------------------------------------------------------------------------
# Pre-configured NJ players
# ---------------------------------------------------------------------------

NJ_PLAYERS = [
    {"first_name": "Tie",      "last_name": "Zhao",   "ntrp": 4.5},
    {"first_name": "Tony",     "last_name": "Liu",    "ntrp": 4.0},
    {"first_name": "Rui",      "last_name": "Qin",    "ntrp": 4.5},
    {"first_name": "Guoqiang", "last_name": "Zhang",  "ntrp": 5.0},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ntrp_for(first: str, last: str) -> float:
    for p in NJ_PLAYERS:
        if p["first_name"].lower() == first.lower() and p["last_name"].lower() == last.lower():
            return p["ntrp"]
    return 4.5


def run_single(first_name: str, last_name: str, output_html: str) -> None:
    ntrp   = _ntrp_for(first_name, last_name)
    player = get_player_data(first_name, last_name, ntrp)
    print_player_summary(player)
    build_timeline(player, output_html)
    print(f"\nOpen '{output_html}' in a browser to view the interactive timeline.")


def run_all(output_index: str = "usta_nj_dashboard.html") -> None:
    """Build individual timelines for every NJ player, then generate a dashboard index."""
    profiles      = []
    output_files  = []

    for p in NJ_PLAYERS:
        player = get_player_data(p["first_name"], p["last_name"], p["ntrp"])
        print_player_summary(player)
        fname = f"usta_{p['last_name']}_{p['first_name']}_timeline.html"
        build_timeline(player, fname)
        profiles.append(player)
        output_files.append((player.name, fname))

    _build_dashboard(profiles, output_files, output_index)
    print(f"\n[main] Dashboard → {output_index}")
    print("[main] Individual timelines:")
    for name, path in output_files:
        print(f"  • {name:30s} → {path}")


# ---------------------------------------------------------------------------
# Dashboard HTML index
# ---------------------------------------------------------------------------

def _build_dashboard(profiles: list[PlayerProfile],
                     file_pairs: list[tuple[str, str]],
                     output_path: str) -> None:
    cards = ""
    for player, (_, fpath) in zip(profiles, file_pairs):
        matches = player.matches
        total   = len(matches)
        wins    = sum(1 for m in matches if m.result == "W")
        losses  = total - wins
        pct     = f"{wins/total*100:.1f}%" if total else "N/A"
        wc      = "#27ae60" if total and wins / total >= 0.5 else "#e74c3c"

        team_rows = "".join(
            f"<li>{t.team_name} <em>[{t.season}]</em> "
            f"<strong style='color:#27ae60'>{t.wins}W</strong>–"
            f"<strong style='color:#e74c3c'>{t.losses}L</strong></li>"
            for t in player.teams
        )

        cards += f"""
        <div class="card">
          <h2><a href="{fpath}">{player.name}</a></h2>
          <div class="badges">
            <span class="badge ntrp">NTRP {player.ntrp_rating}</span>
            <span class="badge sect">{player.section}</span>
          </div>
          <div class="record" style="color:{wc}">
            {wins}W – {losses}L &nbsp;({pct})
          </div>
          <div class="sub">Teams ({len(player.teams)}) · {total} matches</div>
          <ul class="teams">{team_rows}</ul>
          <a class="btn" href="{fpath}">View Timeline →</a>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>USTA NJ Tennis – Player Dashboard</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Arial,sans-serif;background:#ecf0f1;padding:24px}}
h1{{text-align:center;color:#1a237e;font-size:1.8em;margin-bottom:6px}}
.subtitle{{text-align:center;color:#555;font-size:13px;margin-bottom:28px}}
.grid{{display:flex;flex-wrap:wrap;gap:20px;justify-content:center}}
.card{{background:#fff;border-radius:14px;box-shadow:0 3px 12px rgba(0,0,0,.1);
       padding:22px;width:330px;display:flex;flex-direction:column;gap:10px}}
.card h2{{font-size:1.15em;color:#1a237e}}
.card h2 a{{text-decoration:none;color:inherit}}
.card h2 a:hover{{text-decoration:underline}}
.badges{{display:flex;gap:6px;flex-wrap:wrap}}
.badge{{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700}}
.ntrp{{background:#e3f2fd;color:#0d47a1}}
.sect{{background:#fff3e0;color:#e65100}}
.record{{font-size:1.5em;font-weight:700}}
.sub{{font-size:11px;color:#888}}
.teams{{padding-left:16px;font-size:12px;color:#444;display:flex;flex-direction:column;gap:3px}}
.teams em{{color:#999;font-size:10px}}
.btn{{display:inline-block;background:#1a237e;color:#fff;padding:9px 18px;
      border-radius:7px;text-decoration:none;font-size:13px;font-weight:600;
      text-align:center;margin-top:auto}}
.btn:hover{{background:#283593}}
footer{{text-align:center;margin-top:40px;color:#aaa;font-size:11px}}
</style>
</head>
<body>
<h1>USTA Tennis — New Jersey Player Dashboard</h1>
<p class="subtitle">
  Section: Middle States (NJ) &nbsp;|&nbsp;
  Players: Tie Zhao · Tony Liu · Rui Qin · Guoqiang Zhang<br>
  Data source: <a href="https://www.tennisrecord.com" target="_blank">tennisrecord.com</a>
</p>
<div class="grid">{cards}</div>
<footer>
  Scraped from tennisrecord.com · Visualized with Plotly
</footer>
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
        fn     = args[0]
        ln     = args[1]
        output = args[2] if len(args) > 2 else f"usta_{ln}_{fn}_timeline.html"
        run_single(fn, ln, output)
    else:
        run_all("usta_nj_dashboard.html")
