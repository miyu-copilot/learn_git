"""
USTA Tennis Player Timeline Visualizer
Creates an interactive HTML timeline of a player's match history and team affiliations.
"""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Optional
import os

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
    print("[visualizer] plotly not available – install with: pip install plotly")

from usta_scraper import PlayerProfile, MatchResult


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

WIN_COLOR   = "#2ecc71"   # green
LOSS_COLOR  = "#e74c3c"   # red
TEAM_COLORS = px.colors.qualitative.Set2 if HAS_PLOTLY else []

SINGLES_SHAPE = "circle"
DOUBLES_SHAPE = "diamond"

NTRP_COLOR_MAP = {
    3.0: "#95a5a6",
    3.5: "#3498db",
    4.0: "#9b59b6",
    4.5: "#e67e22",
    5.0: "#c0392b",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def _score_to_sets_won(score: str) -> tuple[int, int]:
    """Return (player_sets, opponent_sets) from a score string."""
    parts = score.split(", ")
    p, o = 0, 0
    for part in parts:
        sub = part.split("-")
        if len(sub) == 2:
            try:
                a, b = int(sub[0]), int(sub[1])
                if a > b:
                    p += 1
                else:
                    o += 1
            except ValueError:
                pass
    return p, o


def _win_rate_series(matches: list, window: int = 5) -> tuple[list, list]:
    """Compute rolling win rate (window matches)."""
    dates, rates = [], []
    results = [1 if m.result == "W" else 0 for m in matches]
    for i in range(len(results)):
        start = max(0, i - window + 1)
        win_rate = sum(results[start : i + 1]) / (i - start + 1)
        dates.append(_parse_date(matches[i].date))
        rates.append(round(win_rate * 100, 1))
    return dates, rates


# ---------------------------------------------------------------------------
# Main visualizer
# ---------------------------------------------------------------------------

def build_timeline(player: PlayerProfile, output_path: str = "usta_timeline.html") -> str:
    """
    Build an interactive Plotly HTML timeline and save to output_path.
    Returns the path to the saved file.
    """
    if not HAS_PLOTLY:
        raise RuntimeError("plotly is required: pip install plotly")

    matches: list[MatchResult] = player.matches
    if not matches:
        raise ValueError("No match data found for player.")

    # Sort by date
    matches = sorted(matches, key=lambda m: m.date)

    # Assign a color per team
    team_names = list(dict.fromkeys(m.team for m in matches))
    team_color_map = {
        name: TEAM_COLORS[i % len(TEAM_COLORS)]
        for i, name in enumerate(team_names)
    }

    # Build figure with 4 rows
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.42, 0.22, 0.20, 0.16],
        vertical_spacing=0.06,
        subplot_titles=[
            "Match Timeline (W/L · Singles ● Doubles ◆)",
            "Rolling Win Rate (5-match window)",
            "Team Affiliations",
            "Cumulative Wins & Losses",
        ],
    )

    # -----------------------------------------------------------------------
    # Row 1 – match scatter plot
    # -----------------------------------------------------------------------
    for team_name in team_names:
        team_matches = [m for m in matches if m.team == team_name]
        color = team_color_map[team_name]

        win_singles  = [m for m in team_matches if m.result == "W" and m.match_type == "Singles"]
        win_doubles  = [m for m in team_matches if m.result == "W" and m.match_type == "Doubles"]
        loss_singles = [m for m in team_matches if m.result == "L" and m.match_type == "Singles"]
        loss_doubles = [m for m in team_matches if m.result == "L" and m.match_type == "Doubles"]

        def _hover(m_list):
            return [
                f"<b>{m.result} – {m.match_type}</b><br>"
                f"Date: {m.date}<br>"
                f"Opponent: {m.opponent}<br>"
                f"Score: {m.score}<br>"
                f"Team: {m.team}<br>"
                f"League: {m.league}<br>"
                f"Round: {m.round_name}"
                for m in m_list
            ]

        # Win Singles
        if win_singles:
            fig.add_trace(go.Scatter(
                x=[_parse_date(m.date) for m in win_singles],
                y=[1] * len(win_singles),
                mode="markers",
                marker=dict(size=14, symbol="circle", color=WIN_COLOR,
                            line=dict(color=color, width=2)),
                name=f"{team_name} – W",
                text=_hover(win_singles),
                hovertemplate="%{text}<extra></extra>",
                legendgroup=team_name,
                showlegend=True,
            ), row=1, col=1)

        # Win Doubles
        if win_doubles:
            fig.add_trace(go.Scatter(
                x=[_parse_date(m.date) for m in win_doubles],
                y=[1] * len(win_doubles),
                mode="markers",
                marker=dict(size=14, symbol="diamond", color=WIN_COLOR,
                            line=dict(color=color, width=2)),
                name=f"{team_name} – W Dbl",
                text=_hover(win_doubles),
                hovertemplate="%{text}<extra></extra>",
                legendgroup=team_name,
                showlegend=False,
            ), row=1, col=1)

        # Loss Singles
        if loss_singles:
            fig.add_trace(go.Scatter(
                x=[_parse_date(m.date) for m in loss_singles],
                y=[0] * len(loss_singles),
                mode="markers",
                marker=dict(size=14, symbol="circle", color=LOSS_COLOR,
                            line=dict(color=color, width=2)),
                name=f"{team_name} – L",
                text=_hover(loss_singles),
                hovertemplate="%{text}<extra></extra>",
                legendgroup=team_name,
                showlegend=False,
            ), row=1, col=1)

        # Loss Doubles
        if loss_doubles:
            fig.add_trace(go.Scatter(
                x=[_parse_date(m.date) for m in loss_doubles],
                y=[0] * len(loss_doubles),
                mode="markers",
                marker=dict(size=14, symbol="diamond", color=LOSS_COLOR,
                            line=dict(color=color, width=2)),
                name=f"{team_name} – L Dbl",
                text=_hover(loss_doubles),
                hovertemplate="%{text}<extra></extra>",
                legendgroup=team_name,
                showlegend=False,
            ), row=1, col=1)

    # W / L axis labels
    fig.update_yaxes(
        tickvals=[0, 1],
        ticktext=["Loss", "Win"],
        row=1, col=1,
    )

    # Team separator lines (vertical dashed lines at team transitions)
    seen_teams = []
    for m in matches:
        if not seen_teams or seen_teams[-1] != m.team:
            seen_teams.append(m.team)
            if len(seen_teams) > 1:
                fig.add_vline(
                    x=_parse_date(m.date).timestamp() * 1000,
                    line_dash="dot",
                    line_color="gray",
                    line_width=1,
                    row=1, col=1,
                )

    # -----------------------------------------------------------------------
    # Row 2 – rolling win rate
    # -----------------------------------------------------------------------
    rate_dates, rate_vals = _win_rate_series(matches)
    fig.add_trace(go.Scatter(
        x=rate_dates,
        y=rate_vals,
        mode="lines+markers",
        line=dict(color="#3498db", width=2),
        marker=dict(size=5),
        name="Win Rate %",
        hovertemplate="Date: %{x|%Y-%m-%d}<br>Win Rate: %{y:.1f}%<extra></extra>",
        showlegend=True,
    ), row=2, col=1)

    # 50% reference line
    fig.add_hline(y=50, line_dash="dash", line_color="gray", line_width=1, row=2, col=1)

    fig.update_yaxes(title_text="Win %", range=[0, 105], row=2, col=1)

    # -----------------------------------------------------------------------
    # Row 3 – team affiliation gantt-style bars
    # -----------------------------------------------------------------------
    for i, team in enumerate(player.teams):
        team_matches = [m for m in matches if m.team == team.team_name]
        if not team_matches:
            continue
        start_dt = _parse_date(min(m.date for m in team_matches))
        end_dt   = _parse_date(max(m.date for m in team_matches))
        color    = team_color_map.get(team.team_name, "#7f8c8d")

        fig.add_trace(go.Scatter(
            x=[start_dt, end_dt],
            y=[i, i],
            mode="lines+markers+text",
            line=dict(color=color, width=10),
            marker=dict(size=6, color=color),
            text=[team.team_name, ""],
            textposition="top right",
            name=team.team_name,
            hovertemplate=(
                f"<b>{team.team_name}</b><br>"
                f"League: {team.league}<br>"
                f"Division: {team.division}<br>"
                f"Season: {team.season}<br>"
                f"Record: {team.wins}W – {team.losses}L<br>"
                f"NTRP: {team.ntrp_level}"
                "<extra></extra>"
            ),
            legendgroup=team.team_name,
            showlegend=False,
        ), row=3, col=1)

    fig.update_yaxes(
        showticklabels=False,
        row=3, col=1,
        title_text="Teams",
    )

    # -----------------------------------------------------------------------
    # Row 4 – cumulative wins and losses
    # -----------------------------------------------------------------------
    cum_wins   = []
    cum_losses = []
    w = l = 0
    dates_cum  = []
    for m in matches:
        if m.result == "W":
            w += 1
        else:
            l += 1
        cum_wins.append(w)
        cum_losses.append(l)
        dates_cum.append(_parse_date(m.date))

    fig.add_trace(go.Scatter(
        x=dates_cum, y=cum_wins,
        mode="lines",
        line=dict(color=WIN_COLOR, width=2),
        name="Cumul. Wins",
        fill="tozeroy",
        fillcolor="rgba(46,204,113,0.15)",
        hovertemplate="Date: %{x|%Y-%m-%d}<br>Total Wins: %{y}<extra></extra>",
    ), row=4, col=1)

    fig.add_trace(go.Scatter(
        x=dates_cum, y=cum_losses,
        mode="lines",
        line=dict(color=LOSS_COLOR, width=2),
        name="Cumul. Losses",
        fill="tozeroy",
        fillcolor="rgba(231,76,60,0.15)",
        hovertemplate="Date: %{x|%Y-%m-%d}<br>Total Losses: %{y}<extra></extra>",
    ), row=4, col=1)

    fig.update_yaxes(title_text="Count", row=4, col=1)

    # -----------------------------------------------------------------------
    # Overall layout
    # -----------------------------------------------------------------------
    total_matches = len(matches)
    total_wins    = sum(1 for m in matches if m.result == "W")
    total_losses  = total_matches - total_wins
    win_pct       = round(total_wins / total_matches * 100, 1) if total_matches else 0

    fig.update_layout(
        title=dict(
            text=(
                f"USTA Tennis Timeline — <b>{player.name}</b><br>"
                f"<sub>USTA ID: {player.usta_id} · NTRP: {player.ntrp_rating} · "
                f"WTN: {player.world_tennis_number} · "
                f"Section: {player.section} · "
                f"Record: {total_wins}W–{total_losses}L ({win_pct}%)</sub>"
            ),
            x=0.5,
            xanchor="center",
            font=dict(size=18),
        ),
        height=950,
        hovermode="closest",
        legend=dict(
            orientation="v",
            x=1.01,
            y=1,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#ccc",
            borderwidth=1,
            font=dict(size=10),
        ),
        plot_bgcolor="#fafafa",
        paper_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", size=12),
        margin=dict(l=60, r=220, t=120, b=60),
    )

    # Shared x-axis label
    fig.update_xaxes(title_text="Date", row=4, col=1)

    fig.write_html(output_path, include_plotlyjs="cdn", full_html=True)
    print(f"[visualizer] Saved interactive timeline to: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Stats summary (text / JSON)
# ---------------------------------------------------------------------------

def print_player_summary(player: PlayerProfile) -> None:
    """Print a concise text summary of the player's data."""
    matches = player.matches
    total   = len(matches)
    wins    = sum(1 for m in matches if m.result == "W")
    losses  = total - wins
    singles = [m for m in matches if m.match_type == "Singles"]
    doubles = [m for m in matches if m.match_type == "Doubles"]

    print("\n" + "=" * 60)
    print(f"  USTA PLAYER PROFILE — {player.name}")
    print("=" * 60)
    print(f"  USTA ID          : {player.usta_id}")
    print(f"  NTRP Rating      : {player.ntrp_rating}")
    print(f"  World Tennis #   : {player.world_tennis_number}")
    print(f"  Section          : {player.section}")
    print(f"  District         : {player.district}")
    print(f"  Member Since     : {player.year_joined}")
    print()
    print(f"  Overall Record   : {wins}W – {losses}L  ({wins/total*100:.1f}%)")
    print(f"  Singles          : {sum(1 for m in singles if m.result=='W')}W – "
          f"{sum(1 for m in singles if m.result=='L')}L")
    print(f"  Doubles          : {sum(1 for m in doubles if m.result=='W')}W – "
          f"{sum(1 for m in doubles if m.result=='L')}L")
    print()
    print(f"  Teams ({len(player.teams)}):")
    for t in player.teams:
        print(f"    • {t.team_name}  [{t.season}]  {t.wins}W–{t.losses}L  NTRP {t.ntrp_level}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    from usta_scraper import get_player_data
    import sys
    fn = sys.argv[1] if len(sys.argv) > 1 else "Alex"
    ln = sys.argv[2] if len(sys.argv) > 2 else "Johnson"
    out = sys.argv[3] if len(sys.argv) > 3 else "usta_timeline.html"

    player = get_player_data(fn, ln)
    print_player_summary(player)
    build_timeline(player, out)
