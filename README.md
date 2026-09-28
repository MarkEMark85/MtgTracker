# MTG Tracker

A phone-friendly web app for tracking Commander / Magic: The Gathering games and learning from the stats.

- **Setup:** player names carry over to the next game, with decks cleared. Rotate seats moves everyone down one seat, and the last seat goes first.
- **Live game:** life totals, commander damage, poison, round counter and turn order, with players marked as they're knocked out and who knocked them out. Damage is credited to whoever's turn it is. An in-progress game is kept on the phone, so a refresh or closed tab won't lose it.
- **Results:** full finish order (or a draw), number of turns, the win con (final blow), the winning play, and notes.
- **Stats:** win rate by player, deck and seat, compared with par for the table size (25% in a 4-player pod). Also recent form (last 10), knockouts and damage per game (a Results | Combat switch on Players and Decks), each player's nemesis, player and deck head-to-head (pick up to 3 decks), and a per-deck breakdown of how it wins.
- **History:** every game, with a delete option for fixing mistakes.

Built with FastAPI + SQLite on the back end and plain HTML/JS on the front end (no build step).

## Run it

```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 on the PC.

Data is stored in `data/mtg_tracker.db`. To use a different file, set the `MTG_DB` environment variable.

## Use it on your phone (same Wi-Fi)

1. Find the PC's local IP address: run `ipconfig` and look for the IPv4 Address, e.g. `192.168.1.23`.
2. On the phone, open `http://192.168.1.23:8000`.
3. Add it to the home screen:
   - **iPhone:** Share → *Add to Home Screen*.
   - **Android:** ⋮ menu → *Add to Home screen*.
4. If the phone can't connect, allow Python through Windows Firewall on private networks.

The PC has to be running the server while you play. Offline caching and the full "Install app" prompt on Android need HTTPS, which you get automatically once the app is hosted (see below).

## Tests

```bash
pytest
```

## Hosting it later (sharing with your playgroup)

The app deploys unchanged to any host that runs Python, such as Render, Fly.io or PythonAnywhere. Start command:

`uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Keep `MTG_DB` on a persistent disk or volume so data survives redeploys. Before sharing the link, add a simple passcode.

## Project layout

```
app/
  main.py        API routes + request validation
  db.py          SQLite queries (parameterized) and stats
  schema.sql     tables
  static/        mobile front end, web app manifest, service worker, icons
  make_icons.py  regenerates the PNG icons
tests/           pytest suite
```
