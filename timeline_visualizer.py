"""
USTA Tennis Player Timeline Visualizer
Builds an interactive 4-panel Plotly HTML timeline from a PlayerProfile.
"""

from datetime import datetime
from dataclasses import asdict

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

from usta_scraper import PlayerProfile, MatchResult, Team


# ---------------------------------------------------------------------------
# Colour / style constants
# ---------------------------------------------------------------------------

WIN_COLOR   = "#27ae60"
LOSS_COLOR  = "#e74c3c"
_PALETTE    = px.colors.qualitative.Set2   # 8 distinct colours


def _team_palette(team_names: list[str]) -> dict[str, str]:
    return {name: _PALETTE[i % len(_PALETTE)] for i, name in enumerate(team_names)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dt(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def _rolling_win_rate(matches: list[MatchResult], window: int = 5):
    results = [1 if m.result == "W" else 0 for m in matches]
    dates, rates = [], []
    for i in range(len(results)):
        sl = results[max(0, i - window + 1): i + 1]
        dates.append(_dt(matches[i].date))
        rates.append(round(sum(sl) / len(sl) * 100, 1))
    return dates, rates


def _hover(m: MatchResult) -> str:
    partner_line = f"<br>Partner: {m.partner}" if m.partner else ""
    return (
        f"<b>{'✅ WIN' if m.result == 'W' else '❌ LOSS'} — {m.match_type} ({m.line})</b>"
        f"<br>Date: {m.date}"
        f"<br>Opponent: {m.opponent}"
        f"{partner_line}"
        f"<br>Score: {m.score}"
        f"<br>Team: {m.team}"
        f"<br>Season: {m.season}"
        f"<br>League: {m.league}"
    )


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------

def build_timeline(player: PlayerProfile, output_path: str = "usta_timeline.html") -> str:
    matches = sorted(player.matches, key=lambda m: m.date)
    if not matches:
        raise ValueError(f"No matches found for {player.name}.")

    team_names  = list(dict.fromkeys(m.team for m in matches))
    team_colors = _team_palette(team_names)

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.40, 0.22, 0.22, 0.16],
        vertical_spacing=0.055,
        subplot_titles=[
            "Match Timeline  (● Singles · ◆ Doubles · green = Win · red = Loss)",
            "Rolling Win Rate  (5-match window)",
            "Team Affiliations",
            "Cumulative Wins & Losses",
        ],
    )

    # ── Row 1: match scatter ────────────────────────────────────────────────
    for team_name in team_names:
        border = team_colors[team_name]
        for result, fill, y_pos in [("W", WIN_COLOR, 1), ("L", LOSS_COLOR, 0)]:
            for mtype, symbol in [("Singles", "circle"), ("Doubles", "diamond")]:
                subset = [m for m in matches
                          if m.team == team_name and m.result == result and m.match_type == mtype]
                if not subset:
                    continue
                fig.add_trace(go.Scatter(
                    x=[_dt(m.date) for m in subset],
                    y=[y_pos] * len(subset),
                    mode="markers",
                    marker=dict(
                        size=13,
                        symbol=symbol,
                        color=fill,
                        line=dict(color=border, width=2.5),
                    ),
                    name=team_name,
                    text=[_hover(m) for m in subset],
                    hovertemplate="%{text}<extra></extra>",
                    legendgroup=team_name,
                    showlegend=(result == "W" and mtype == "Singles"),
                ), row=1, col=1)

    fig.update_yaxes(
        tickvals=[0, 1], ticktext=["Loss", "Win"],
        range=[-0.4, 1.4], row=1, col=1,
    )

    # Team-change vertical guide lines
    prev_team = None
    for m in matches:
        if m.team != prev_team and prev_team is not None:
            fig.add_vline(
                x=_dt(m.date).timestamp() * 1000,
                line_dash="dot", line_color="#aaa", line_width=1,
                row=1, col=1,
            )
        prev_team = m.team

    # ── Row 2: rolling win rate ─────────────────────────────────────────────
    rate_dates, rate_vals = _rolling_win_rate(matches)
    fig.add_trace(go.Scatter(
        x=rate_dates, y=rate_vals,
        mode="lines+markers",
        line=dict(color="#2980b9", width=2.5),
        marker=dict(size=5),
        name="Win Rate %",
        hovertemplate="Date: %{x|%Y-%m-%d}<br>Win Rate: %{y:.1f}%<extra></extra>",
        showlegend=True,
    ), row=2, col=1)

    fig.add_hline(y=50, line_dash="dash", line_color="#aaa", line_width=1, row=2, col=1)
    fig.update_yaxes(title_text="Win %", range=[0, 105], row=2, col=1)

    # ── Row 3: team gantt bars ──────────────────────────────────────────────
    for i, team in enumerate(player.teams):
        tm = [m for m in matches if m.team == team.team_name]
        if not tm:
            continue
        s_dt = _dt(min(m.date for m in tm))
        e_dt = _dt(max(m.date for m in tm))
        color = team_colors.get(team.team_name, "#7f8c8d")

        fig.add_trace(go.Scatter(
            x=[s_dt, e_dt],
            y=[i, i],
            mode="lines+markers",
            line=dict(color=color, width=12),
            marker=dict(size=8, color=color),
            name=team.team_name,
            hovertemplate=(
                f"<b>{team.team_name}</b><br>"
                f"Season: {team.season}<br>"
                f"League: {team.league}<br>"
                f"Division: {team.division}<br>"
                f"Record: {team.wins}W – {team.losses}L<br>"
                f"NTRP: {team.ntrp_level}"
                "<extra></extra>"
            ),
            legendgroup=team.team_name,
            showlegend=False,
        ), row=3, col=1)

        # label on the right
        fig.add_annotation(
            x=e_dt, y=i,
            text=f"  {team.team_name}  {team.wins}W–{team.losses}L",
            showarrow=False,
            xanchor="left",
            font=dict(size=9, color=color),
            row=3, col=1,
        )

    fig.update_yaxes(showticklabels=False, title_text="Teams", row=3, col=1)

    # ── Row 4: cumulative W/L ───────────────────────────────────────────────
    cw = cl = 0
    cum_dates, cum_w, cum_l = [], [], []
    for m in matches:
        if m.result == "W":
            cw += 1
        else:
            cl += 1
        cum_dates.append(_dt(m.date))
        cum_w.append(cw)
        cum_l.append(cl)

    fig.add_trace(go.Scatter(
        x=cum_dates, y=cum_w, mode="lines",
        line=dict(color=WIN_COLOR, width=2),
        fill="tozeroy", fillcolor="rgba(39,174,96,0.15)",
        name="Cumul. Wins",
        hovertemplate="Date: %{x|%Y-%m-%d}<br>Total Wins: %{y}<extra></extra>",
    ), row=4, col=1)

    fig.add_trace(go.Scatter(
        x=cum_dates, y=cum_l, mode="lines",
        line=dict(color=LOSS_COLOR, width=2),
        fill="tozeroy", fillcolor="rgba(231,76,60,0.15)",
        name="Cumul. Losses",
        hovertemplate="Date: %{x|%Y-%m-%d}<br>Total Losses: %{y}<extra></extra>",
    ), row=4, col=1)

    fig.update_yaxes(title_text="Count", row=4, col=1)
    fig.update_xaxes(title_text="Date", row=4, col=1)

    # ── Global layout ───────────────────────────────────────────────────────
    total = len(matches)
    wins  = sum(1 for m in matches if m.result == "W")
    pct   = f"{wins / total * 100:.1f}%" if total else "N/A"

    fig.update_layout(
        title=dict(
            text=(
                f"USTA Tennis Timeline — <b>{player.name}</b><br>"
                f"<sub>USTA ID: {player.usta_id} · NTRP {player.ntrp_rating} · "
                f"WTN: {getattr(player, 'world_tennis_number', '—')} · "
                f"Section: {player.section} · "
                f"Record: {wins}W–{total - wins}L ({pct}) · "
                f"{len(player.teams)} teams · {total} matches</sub>"
            ),
            x=0.5, xanchor="center",
            font=dict(size=17),
        ),
        height=1000,
        hovermode="closest",
        legend=dict(
            orientation="v", x=1.01, y=1,
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="#ccc", borderwidth=1,
            font=dict(size=10),
        ),
        plot_bgcolor="#fafafa",
        paper_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", size=12),
        margin=dict(l=60, r=260, t=120, b=60),
    )

    fig.write_html(output_path, include_plotlyjs="cdn", full_html=True)
    print(f"[visualizer] Saved → {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Text summary
# ---------------------------------------------------------------------------

def print_player_summary(player: PlayerProfile) -> None:
    matches  = player.matches
    total    = len(matches)
    wins     = sum(1 for m in matches if m.result == "W")
    singles  = [m for m in matches if m.match_type == "Singles"]
    doubles  = [m for m in matches if m.match_type == "Doubles"]

    print("\n" + "=" * 62)
    print(f"  USTA PROFILE — {player.name}")
    print("=" * 62)
    print(f"  USTA ID      : {player.usta_id}")
    print(f"  NTRP Rating  : {player.ntrp_rating}")
    print(f"  Section      : {player.section} / {player.district}")
    print(f"  Member Since : {player.year_joined}")
    print()
    print(f"  Overall      : {wins}W – {total - wins}L  ({wins/total*100:.1f}%)" if total else "  No matches.")
    print(f"  Singles      : {sum(1 for m in singles if m.result=='W')}W – "
          f"{sum(1 for m in singles if m.result=='L')}L")
    print(f"  Doubles      : {sum(1 for m in doubles if m.result=='W')}W – "
          f"{sum(1 for m in doubles if m.result=='L')}L")
    print()
    print(f"  Teams ({len(player.teams)}):")
    for t in player.teams:
        print(f"    • {t.team_name}  [{t.season}]  {t.wins}W–{t.losses}L  NTRP {t.ntrp_level}")
    print("=" * 62 + "\n")
