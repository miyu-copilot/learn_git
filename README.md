# USTA Tennis Player Scraper & Timeline Visualizer

Scrapes (or generates demo data for) USTA player profiles, team affiliations, and match
results, then renders an interactive HTML timeline powered by **Plotly**.

---

## Features

| Feature | Detail |
|---|---|
| Player profile | USTA ID, NTRP rating, World Tennis Number, section/district |
| Team history | Multiple teams across seasons with W-L records |
| Match timeline | Every match plotted by date – W (green) / L (red), Singles (●) / Doubles (◆) |
| Rolling win rate | 5-match sliding window win-% trend line |
| Team gantt | Visual band showing which team was active when |
| Cumulative chart | Running total of wins & losses over time |
| Dashboard index | One HTML page linking to all individual player timelines |

---

## Quick start

```bash
pip install -r requirements.txt

# All 4 NJ players (generates index + individual timelines)
python main.py

# Single player
python main.py "Tie"      "Zhao"
python main.py "Tony"     "Liu"
python main.py "Rui"      "Qin"
python main.py "Guoqiang" "Zhang"

# Custom output file
python main.py "Tie" "Zhao" tie_zhao_timeline.html
```

Open the generated `usta_nj_players_timeline.html` (dashboard) or any individual
`usta_<Name>_timeline.html` file in a web browser.

---

## Live scraping vs. demo mode

The scraper first attempts to contact **USTA TennisLink**
(`tennislink.usta.com`).  TennisLink uses ASP.NET session tokens and typically
returns `403` or blocks unauthenticated bots, so the tool gracefully falls back
to **realistic demo data** that mirrors the real data schema exactly.

To use real data you have two options:

1. **USTA Connect API** – email `worldtennisnumber@usta.com` to request
   OAuth 2.0 credentials, then replace the `generate_demo_player()` call in
   `usta_scraper.py` with API calls.
2. **Authenticated session replay** – capture the `__VIEWSTATE` tokens from a
   logged-in browser session and inject them into the POST payload in
   `scrape_player_search()`.

---

## NJ players pre-configured

| Player | NTRP | Section |
|---|---|---|
| Tie Zhao | 4.5 | Middle States (NJ) |
| Tony Liu | 4.0 | Middle States (NJ) |
| Rui Qin | 4.5 | Middle States (NJ) |
| Guoqiang Zhang | 5.0 | Middle States (NJ) |

---

## File structure

```
main.py               – Entry point; NJ player definitions & dashboard builder
usta_scraper.py       – TennisLink scraper + demo data generator
timeline_visualizer.py – Plotly 4-panel timeline builder
requirements.txt      – Python dependencies
```

---

## Requirements

- Python 3.10+
- `requests`, `beautifulsoup4`, `lxml` – for scraping
- `plotly[express]`, `numpy` – for visualization
