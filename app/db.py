"""SQLite data layer. Every query is parameterized; stats are computed at read time."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

APP_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = APP_DIR / "schema.sql"
DEFAULT_DB_PATH = APP_DIR.parent / "data" / "mtg_tracker.db"

# How the game ended: the final blow. (code stored in games.win_con, label shown in the app)
WIN_CONS = [
    ("COMBAT", "Combat damage"),
    ("COMMANDER", "Commander damage"),
    ("BURN", "Burn / direct damage"),
    ("DRAIN", "Drain / life loss"),
    ("POISON", "Poison / infect"),
    ("MILL", "Mill / decking"),
    ("COMBO", "Combo (infinite)"),
    ("ALT", "Alt-win card"),
    ("CONCEDE", "Concede"),
]
# What kind of deck it is. Set once per deck (decks.archetype).
ARCHETYPES = [
    ("AGGRO", "Aggro"),
    ("VOLTRON", "Voltron"),
    ("GO_WIDE", "Go-wide / tokens"),
    ("ARISTOCRATS", "Aristocrats"),
    ("COMBO", "Combo"),
    ("CONTROL", "Control"),
    ("STAX", "Stax"),
    ("SPELLSLINGER", "Spellslinger"),
    ("RAMP", "Ramp / big mana"),
    ("MIDRANGE", "Midrange / value"),
    ("GROUP_SLUG", "Group slug"),
]
WIN_CON_CODES = {c for c, _ in WIN_CONS}
ARCHETYPE_CODES = {c for c, _ in ARCHETYPES}

# Columns added after the first release: (table, column, definition).
_MIGRATIONS = [
    ("decks", "archetype", "TEXT"),
    ("games", "is_draw", "INTEGER NOT NULL DEFAULT 0"),
    ("games", "winning_play", "TEXT"),
    ("game_players", "eliminated_by", "INTEGER REFERENCES players(id)"),
]
# Old games.win_details values that describe a deck style become the winning deck's archetype.
_LEGACY_ARCHETYPES = {"OVERRUN": "GO_WIDE", "ARISTOCRATS": "ARISTOCRATS", "VOLTRON": "VOLTRON", "INFINITE": "COMBO"}


def db_path() -> Path:
    return Path(os.environ.get("MTG_DB", DEFAULT_DB_PATH))


@contextmanager
def connect(path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, roll back on error."""
    path = Path(path or db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Optional[Path] = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring a database created by an older version up to the current schema."""
    for table, column, definition in _MIGRATIONS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column in existing:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        if (table, column) == ("decks", "archetype"):
            for old, archetype in _LEGACY_ARCHETYPES.items():
                conn.execute("""
                    UPDATE decks SET archetype = ?
                    WHERE archetype IS NULL AND id IN (
                        SELECT gp.deck_id FROM game_players gp JOIN games g ON g.id = gp.game_id
                        WHERE g.win_details = ? AND gp.finish_place = 1)
                """, (archetype, old))


def _rows(cursor: sqlite3.Cursor) -> List[Dict]:
    return [dict(r) for r in cursor.fetchall()]


def _marks(values: Iterable) -> str:
    return ",".join("?" * len(list(values)))


# ---------- players & decks ----------

def get_or_create_player(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM players WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    return conn.execute("INSERT INTO players (name) VALUES (?)", (name,)).lastrowid


def get_or_create_deck(
    conn: sqlite3.Connection, owner_id: int, name: str,
    commander: Optional[str] = None, colors: Optional[str] = None, archetype: Optional[str] = None,
) -> int:
    row = conn.execute(
        "SELECT id FROM decks WHERE owner_id = ? AND name = ?", (owner_id, name)
    ).fetchone()
    if row:
        if commander or colors or archetype:
            conn.execute(
                """UPDATE decks SET commander = COALESCE(?, commander), colors = COALESCE(?, colors),
                                    archetype = COALESCE(?, archetype) WHERE id = ?""",
                (commander, colors, archetype, row["id"]),
            )
        return row["id"]
    return conn.execute(
        "INSERT INTO decks (name, owner_id, commander, colors, archetype) VALUES (?, ?, ?, ?, ?)",
        (name, owner_id, commander, colors, archetype),
    ).lastrowid


def list_players(conn: sqlite3.Connection) -> List[Dict]:
    return _rows(conn.execute("SELECT id, name FROM players ORDER BY name"))


def list_decks(conn: sqlite3.Connection, owner: Optional[str] = None) -> List[Dict]:
    sql = """
        SELECT d.id, d.name, d.commander, d.colors, d.archetype, p.name AS owner
        FROM decks d JOIN players p ON p.id = d.owner_id
    """
    params: tuple = ()
    if owner:
        sql += " WHERE p.name = ?"
        params = (owner,)
    return _rows(conn.execute(sql + " ORDER BY p.name, d.name", params))


# ---------- games ----------

def save_game(conn: sqlite3.Connection, game: Dict) -> int:
    """Save a finished game. `game` matches the GameIn model in main.py (already validated)."""
    played_at = game.get("played_at") or datetime.now().isoformat(timespec="seconds")
    game_id = conn.execute(
        "INSERT INTO games (played_at, turns, win_con, notes, is_draw, winning_play) VALUES (?, ?, ?, ?, ?, ?)",
        (played_at, game.get("turns"), game.get("win_con"), game.get("notes"),
         int(bool(game.get("is_draw"))), game.get("winning_play")),
    ).lastrowid

    ids_by_name = {p["player"].casefold(): get_or_create_player(conn, p["player"]) for p in game["participants"]}
    pid = lambda name: ids_by_name.get((name or "").casefold())  # noqa: E731

    for p in game["participants"]:
        player_id = pid(p["player"])
        deck_id = get_or_create_deck(
            conn, player_id, p["deck"], p.get("commander"), p.get("colors"), p.get("archetype"))
        conn.execute(
            """INSERT INTO game_players
                   (game_id, player_id, deck_id, seat, finish_place, eliminated_turn, eliminated_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (game_id, player_id, deck_id, p["seat"], p["finish_place"], p.get("eliminated_turn"),
             pid(p.get("eliminated_by"))),
        )

    for e in game.get("turn_events") or []:
        conn.execute(
            "INSERT INTO turn_events (game_id, round, player_id, event) VALUES (?, ?, ?, ?)",
            (game_id, e["round"], pid(e.get("player")), e["event"]),
        )

    totals: Dict[tuple, int] = {}
    for d in game.get("damage") or []:
        key = (pid(d["source"]), pid(d["target"]), int(bool(d.get("commander"))))
        totals[key] = totals.get(key, 0) + d["amount"]
    conn.executemany(
        "INSERT INTO damage (game_id, source_id, target_id, commander, amount) VALUES (?, ?, ?, ?, ?)",
        [(game_id, *key, amount) for key, amount in totals.items()],
    )
    return game_id


def list_games(conn: sqlite3.Connection, limit: int = 50) -> List[Dict]:
    games = _rows(conn.execute(
        """SELECT id, played_at, turns, win_con, win_details, notes, is_draw, winning_play
           FROM games ORDER BY played_at DESC, id DESC LIMIT ?""",
        (limit,),
    ))
    if not games:
        return games
    ids = [g["id"] for g in games]
    participants = _rows(conn.execute(
        f"""SELECT gp.game_id, p.name AS player, d.name AS deck, d.commander, d.archetype,
                   gp.seat, gp.finish_place, gp.eliminated_turn, kb.name AS eliminated_by
            FROM game_players gp
            JOIN players p ON p.id = gp.player_id
            JOIN decks d ON d.id = gp.deck_id
            LEFT JOIN players kb ON kb.id = gp.eliminated_by
            WHERE gp.game_id IN ({_marks(ids)})
            ORDER BY gp.finish_place, gp.seat""",
        ids,
    ))
    by_game: Dict[int, List[Dict]] = {i: [] for i in ids}
    for row in participants:
        by_game[row.pop("game_id")].append(row)
    for g in games:
        g["is_draw"] = bool(g["is_draw"])
        g["participants"] = by_game[g["id"]]
    return games


def delete_game(conn: sqlite3.Connection, game_id: int) -> bool:
    return conn.execute("DELETE FROM games WHERE id = ?", (game_id,)).rowcount > 0


# ---------- stats ----------
# Shared SQL fragments. They expect `gp` (game_players), `g` (games) and, for par, `s` (_SIZES).

_WON = "(gp.finish_place = 1 AND g.is_draw = 0)"  # a shared 1st in a draw is not a win
_WIN_RATE = f"ROUND(100.0 * SUM({_WON}) / COUNT(*), 1)"
_AVG_WIN_TURN = f"ROUND(AVG(CASE WHEN {_WON} THEN g.turns END), 1)"
_SIZES = "JOIN (SELECT game_id, COUNT(*) AS n FROM game_players GROUP BY game_id) s ON s.game_id = gp.game_id"
# Par = the win rate you'd expect by pure chance at the table sizes you actually played (1 in n).
_PAR = "ROUND(100.0 * AVG(1.0 / s.n), 1)"
# Damage is only averaged over games where damage was tracked, so older games don't drag it down.
_DEALT = "(SELECT COALESCE(SUM(dm.amount), 0) FROM damage dm WHERE dm.game_id = gp.game_id AND dm.source_id = gp.player_id)"
_TAKEN = "(SELECT COALESCE(SUM(dm.amount), 0) FROM damage dm WHERE dm.game_id = gp.game_id AND dm.target_id = gp.player_id)"
_TRACKED = "EXISTS (SELECT 1 FROM damage dt WHERE dt.game_id = gp.game_id)"
_AVG_DEALT = f"ROUND(AVG(CASE WHEN {_TRACKED} THEN {_DEALT} END), 1)"
_AVG_TAKEN = f"ROUND(AVG(CASE WHEN {_TRACKED} THEN {_TAKEN} END), 1)"


def _with_par(rows: List[Dict]) -> List[Dict]:
    for r in rows:
        r["vs_par"] = round(r["win_rate"] - r["par"], 1)
    return rows


def _recent(conn: sqlite3.Connection, key: str, n: int = 10) -> Dict[int, Dict]:
    """Wins in each player's/deck's last `n` games. key is 'player_id' or 'deck_id'."""
    rows = conn.execute(f"""
        SELECT id, SUM(won) AS wins, COUNT(*) AS games FROM (
            SELECT gp.{key} AS id, {_WON} AS won,
                   ROW_NUMBER() OVER (PARTITION BY gp.{key} ORDER BY g.played_at DESC, g.id DESC) AS rn
            FROM game_players gp JOIN games g ON g.id = gp.game_id
        ) WHERE rn <= ? GROUP BY id
    """, (n,))
    return {r["id"]: {"wins": r["wins"], "games": r["games"]} for r in rows}


def player_stats(conn: sqlite3.Connection) -> List[Dict]:
    rows = _rows(conn.execute(f"""
        SELECT p.id, p.name AS player,
               COUNT(*) AS games,
               SUM({_WON}) AS wins,
               {_WIN_RATE} AS win_rate,
               {_PAR} AS par,
               ROUND(AVG(gp.finish_place), 2) AS avg_finish,
               {_AVG_WIN_TURN} AS avg_win_turn,
               {_AVG_DEALT} AS avg_dmg
        FROM game_players gp
        JOIN players p ON p.id = gp.player_id
        JOIN games g ON g.id = gp.game_id
        {_SIZES}
        GROUP BY p.id
        ORDER BY win_rate DESC, games DESC, p.name
    """))
    recent = _recent(conn, "player_id")
    for r in rows:
        r["last10"] = recent[r.pop("id")]
    return _with_par(rows)


def deck_stats(conn: sqlite3.Connection, owner: Optional[str] = None) -> List[Dict]:
    where, params = ("WHERE p.name = ?", (owner,)) if owner else ("", ())
    rows = _rows(conn.execute(f"""
        SELECT d.id, d.name AS deck, d.commander, d.archetype, p.name AS owner,
               COUNT(*) AS games,
               SUM({_WON}) AS wins,
               {_WIN_RATE} AS win_rate,
               {_PAR} AS par,
               ROUND(AVG(gp.finish_place), 2) AS avg_finish,
               {_AVG_WIN_TURN} AS avg_win_turn,
               {_AVG_DEALT} AS avg_dmg
        FROM game_players gp
        JOIN decks d ON d.id = gp.deck_id
        JOIN players p ON p.id = d.owner_id
        JOIN games g ON g.id = gp.game_id
        {_SIZES}
        {where}
        GROUP BY d.id
        ORDER BY win_rate DESC, games DESC, d.name
    """, params))
    recent = _recent(conn, "deck_id")
    for r in rows:
        r["last10"] = recent[r["id"]]
    return _with_par(rows)


def deck_detail(conn: sqlite3.Connection, deck_id: int) -> Optional[Dict]:
    """How one deck wins, how it does from each seat, and its last 10 results."""
    deck = conn.execute("""
        SELECT d.id, d.name AS deck, d.commander, d.archetype, p.name AS owner
        FROM decks d JOIN players p ON p.id = d.owner_id WHERE d.id = ?
    """, (deck_id,)).fetchone()
    if not deck:
        return None
    detail = dict(deck)
    detail["win_cons"] = _rows(conn.execute(f"""
        SELECT COALESCE(g.win_con, 'UNKNOWN') AS win_con, COUNT(*) AS games
        FROM game_players gp JOIN games g ON g.id = gp.game_id
        WHERE gp.deck_id = ? AND {_WON}
        GROUP BY 1 ORDER BY games DESC
    """, (deck_id,)))
    detail["seats"] = _with_par(_rows(conn.execute(f"""
        SELECT gp.seat, COUNT(*) AS games, SUM({_WON}) AS wins, {_WIN_RATE} AS win_rate, {_PAR} AS par
        FROM game_players gp JOIN games g ON g.id = gp.game_id {_SIZES}
        WHERE gp.deck_id = ?
        GROUP BY gp.seat ORDER BY gp.seat
    """, (deck_id,))))
    detail["recent"] = _rows(conn.execute(f"""
        SELECT g.id AS game_id, g.played_at, gp.finish_place, s.n AS players,
               CASE WHEN {_WON} THEN 'W' WHEN g.is_draw = 1 AND gp.finish_place = 1 THEN 'D' ELSE 'L' END AS result
        FROM game_players gp JOIN games g ON g.id = gp.game_id {_SIZES}
        WHERE gp.deck_id = ?
        ORDER BY g.played_at DESC, g.id DESC LIMIT 10
    """, (deck_id,)))
    return detail


def seat_stats(conn: sqlite3.Connection) -> List[Dict]:
    return _with_par(_rows(conn.execute(f"""
        SELECT gp.seat, COUNT(*) AS games, SUM({_WON}) AS wins, {_WIN_RATE} AS win_rate, {_PAR} AS par
        FROM game_players gp
        JOIN games g ON g.id = gp.game_id
        {_SIZES}
        GROUP BY gp.seat
        ORDER BY gp.seat
    """)))


def matchup_stats(conn: sqlite3.Connection, player: Optional[str] = None) -> List[Dict]:
    """Head-to-head for every pair of players who have shared a table.

    `a_ahead` counts games where player_a finished in a better place than player_b.
    """
    where, params = ("WHERE pa.name = ? OR pb.name = ?", (player, player)) if player else ("", ())
    return _rows(conn.execute(f"""
        SELECT pa.name AS player_a, pb.name AS player_b,
               COUNT(*) AS games,
               SUM(ga.finish_place = 1 AND g.is_draw = 0) AS a_wins,
               SUM(gb.finish_place = 1 AND g.is_draw = 0) AS b_wins,
               SUM(ga.finish_place < gb.finish_place) AS a_ahead,
               SUM(gb.finish_place < ga.finish_place) AS b_ahead
        FROM game_players ga
        JOIN game_players gb ON gb.game_id = ga.game_id AND ga.player_id < gb.player_id
        JOIN games g ON g.id = ga.game_id
        JOIN players pa ON pa.id = ga.player_id
        JOIN players pb ON pb.id = gb.player_id
        {where}
        GROUP BY ga.player_id, gb.player_id
        ORDER BY games DESC, pa.name, pb.name
    """, params))


def deck_matchup_stats(conn: sqlite3.Connection, deck_ids: Optional[List[int]] = None) -> List[Dict]:
    """Head-to-head between decks (same columns as matchup_stats, plus deck ids).

    With `deck_ids`, returns every opponent each of those decks has faced, with the chosen
    deck always on the `a` side. Without, returns each pair of decks once.
    """
    if deck_ids:
        pair, where, params = "gb.deck_id != ga.deck_id", f"WHERE ga.deck_id IN ({_marks(deck_ids)})", deck_ids
    else:
        pair, where, params = "ga.deck_id < gb.deck_id", "", []
    return _rows(conn.execute(f"""
        SELECT ga.deck_id AS deck_a_id, da.name AS deck_a, pa.name AS owner_a,
               gb.deck_id AS deck_b_id, db.name AS deck_b, pb.name AS owner_b,
               COUNT(*) AS games,
               SUM(ga.finish_place = 1 AND g.is_draw = 0) AS a_wins,
               SUM(gb.finish_place = 1 AND g.is_draw = 0) AS b_wins,
               SUM(ga.finish_place < gb.finish_place) AS a_ahead,
               SUM(gb.finish_place < ga.finish_place) AS b_ahead
        FROM game_players ga
        JOIN game_players gb ON gb.game_id = ga.game_id AND {pair}
        JOIN games g ON g.id = ga.game_id
        JOIN decks da ON da.id = ga.deck_id
        JOIN decks db ON db.id = gb.deck_id
        JOIN players pa ON pa.id = da.owner_id
        JOIN players pb ON pb.id = db.owner_id
        {where}
        GROUP BY ga.deck_id, gb.deck_id
        ORDER BY games DESC, da.name, db.name
    """, params))


def knockout_stats(conn: sqlite3.Connection) -> List[Dict]:
    """Per player: knockouts dealt, how often they're out first, their nemesis, and damage."""
    rows = _rows(conn.execute(f"""
        SELECT p.id, p.name AS player,
               COUNT(*) AS games,
               (SELECT COUNT(*) FROM game_players k WHERE k.eliminated_by = p.id) AS kos,
               SUM(gp.finish_place = s.n) AS first_out,
               ROUND(100.0 * SUM(gp.finish_place = s.n) / COUNT(*), 1) AS first_out_rate,
               {_AVG_DEALT} AS avg_dealt,
               {_AVG_TAKEN} AS avg_taken
        FROM game_players gp
        JOIN players p ON p.id = gp.player_id
        JOIN games g ON g.id = gp.game_id
        {_SIZES}
        GROUP BY p.id
        ORDER BY kos DESC, first_out_rate, p.name
    """))
    nemesis = _top(conn.execute("""
        SELECT gp.player_id AS id, k.name, COUNT(*) AS n
        FROM game_players gp JOIN players k ON k.id = gp.eliminated_by
        GROUP BY gp.player_id, gp.eliminated_by
    """))
    targeted = _top(conn.execute("""
        SELECT dm.source_id AS id, t.name, SUM(dm.amount) AS n
        FROM damage dm JOIN players t ON t.id = dm.target_id
        GROUP BY dm.source_id, dm.target_id
    """))
    for r in rows:
        pid = r.pop("id")
        r["nemesis"] = nemesis.get(pid)
        r["most_targeted"] = targeted.get(pid)
    return rows


def _top(cursor: sqlite3.Cursor) -> Dict[int, Dict]:
    """From (id, name, n) rows, keep the highest n per id (ties go to the earlier name)."""
    best: Dict[int, Dict] = {}
    for r in cursor:
        cur = best.get(r["id"])
        if cur is None or (r["n"], cur["name"]) > (cur["count"], r["name"]):
            best[r["id"]] = {"name": r["name"], "count": r["n"]}
    return best


def summary_stats(conn: sqlite3.Connection) -> Dict:
    totals = dict(conn.execute(
        "SELECT COUNT(*) AS games, COALESCE(SUM(is_draw), 0) AS draws, ROUND(AVG(turns), 1) AS avg_turns FROM games"
    ).fetchone())
    totals["win_cons"] = _rows(conn.execute("""
        SELECT COALESCE(win_con, 'UNKNOWN') AS win_con, COUNT(*) AS games
        FROM games GROUP BY 1 ORDER BY games DESC
    """))
    return totals
