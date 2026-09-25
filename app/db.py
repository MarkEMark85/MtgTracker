"""SQLite data layer. Every query is parameterized; stats are computed at read time."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, List, Optional

APP_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = APP_DIR / "schema.sql"
DEFAULT_DB_PATH = APP_DIR.parent / "data" / "mtg_tracker.db"

WIN_CONS = ["COMBAT", "COMMANDER", "BURN", "DRAIN", "MILL", "POISON", "COMBO", "ALT", "CONCEDE"]
WIN_DETAILS = ["OVERRUN", "ARISTOCRATS", "FIREBALL", "PAPER_CUTS", "INFINITE", "VOLTRON", "STANDARD"]


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


def _rows(cursor: sqlite3.Cursor) -> List[Dict]:
    return [dict(r) for r in cursor.fetchall()]


# ---------- players & decks ----------

def get_or_create_player(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM players WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    return conn.execute("INSERT INTO players (name) VALUES (?)", (name,)).lastrowid


def get_or_create_deck(
    conn: sqlite3.Connection, owner_id: int, name: str,
    commander: Optional[str] = None, colors: Optional[str] = None,
) -> int:
    row = conn.execute(
        "SELECT id FROM decks WHERE owner_id = ? AND name = ?", (owner_id, name)
    ).fetchone()
    if row:
        if commander or colors:
            conn.execute(
                "UPDATE decks SET commander = COALESCE(?, commander), colors = COALESCE(?, colors) WHERE id = ?",
                (commander, colors, row["id"]),
            )
        return row["id"]
    return conn.execute(
        "INSERT INTO decks (name, owner_id, commander, colors) VALUES (?, ?, ?, ?)",
        (name, owner_id, commander, colors),
    ).lastrowid


def list_players(conn: sqlite3.Connection) -> List[Dict]:
    return _rows(conn.execute("SELECT id, name FROM players ORDER BY name"))


def list_decks(conn: sqlite3.Connection, owner: Optional[str] = None) -> List[Dict]:
    sql = """
        SELECT d.id, d.name, d.commander, d.colors, p.name AS owner
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
        "INSERT INTO games (played_at, turns, win_con, win_details, notes) VALUES (?, ?, ?, ?, ?)",
        (played_at, game.get("turns"), game.get("win_con"), game.get("win_details"), game.get("notes")),
    ).lastrowid

    ids_by_name = {}
    for p in game["participants"]:
        player_id = get_or_create_player(conn, p["player"])
        ids_by_name[p["player"].casefold()] = player_id
        deck_id = get_or_create_deck(conn, player_id, p["deck"], p.get("commander"), p.get("colors"))
        conn.execute(
            """INSERT INTO game_players (game_id, player_id, deck_id, seat, finish_place, eliminated_turn)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (game_id, player_id, deck_id, p["seat"], p["finish_place"], p.get("eliminated_turn")),
        )

    for e in game.get("turn_events") or []:
        player_id = ids_by_name.get((e.get("player") or "").casefold())
        conn.execute(
            "INSERT INTO turn_events (game_id, round, player_id, event) VALUES (?, ?, ?, ?)",
            (game_id, e["round"], player_id, e["event"]),
        )
    return game_id


def list_games(conn: sqlite3.Connection, limit: int = 50) -> List[Dict]:
    games = _rows(conn.execute(
        "SELECT id, played_at, turns, win_con, win_details, notes FROM games ORDER BY played_at DESC, id DESC LIMIT ?",
        (limit,),
    ))
    if not games:
        return games
    ids = [g["id"] for g in games]
    marks = ",".join("?" * len(ids))
    participants = _rows(conn.execute(
        f"""SELECT gp.game_id, p.name AS player, d.name AS deck, d.commander,
                   gp.seat, gp.finish_place, gp.eliminated_turn
            FROM game_players gp
            JOIN players p ON p.id = gp.player_id
            JOIN decks d ON d.id = gp.deck_id
            WHERE gp.game_id IN ({marks})
            ORDER BY gp.finish_place, gp.seat""",
        ids,
    ))
    by_game: Dict[int, List[Dict]] = {i: [] for i in ids}
    for row in participants:
        by_game[row.pop("game_id")].append(row)
    for g in games:
        g["participants"] = by_game[g["id"]]
    return games


def delete_game(conn: sqlite3.Connection, game_id: int) -> bool:
    return conn.execute("DELETE FROM games WHERE id = ?", (game_id,)).rowcount > 0


# ---------- stats ----------

_WIN_RATE = "ROUND(100.0 * SUM(gp.finish_place = 1) / COUNT(*), 1)"
_AVG_WIN_TURN = "ROUND(AVG(CASE WHEN gp.finish_place = 1 THEN g.turns END), 1)"


def player_stats(conn: sqlite3.Connection) -> List[Dict]:
    return _rows(conn.execute(f"""
        SELECT p.name AS player,
               COUNT(*) AS games,
               SUM(gp.finish_place = 1) AS wins,
               {_WIN_RATE} AS win_rate,
               ROUND(AVG(gp.finish_place), 2) AS avg_finish,
               {_AVG_WIN_TURN} AS avg_win_turn
        FROM game_players gp
        JOIN players p ON p.id = gp.player_id
        JOIN games g ON g.id = gp.game_id
        GROUP BY p.id
        ORDER BY win_rate DESC, games DESC, p.name
    """))


def deck_stats(conn: sqlite3.Connection, owner: Optional[str] = None) -> List[Dict]:
    where, params = ("WHERE p.name = ?", (owner,)) if owner else ("", ())
    return _rows(conn.execute(f"""
        SELECT d.name AS deck, d.commander, p.name AS owner,
               COUNT(*) AS games,
               SUM(gp.finish_place = 1) AS wins,
               {_WIN_RATE} AS win_rate,
               ROUND(AVG(gp.finish_place), 2) AS avg_finish,
               {_AVG_WIN_TURN} AS avg_win_turn
        FROM game_players gp
        JOIN decks d ON d.id = gp.deck_id
        JOIN players p ON p.id = d.owner_id
        JOIN games g ON g.id = gp.game_id
        {where}
        GROUP BY d.id
        ORDER BY win_rate DESC, games DESC, d.name
    """, params))


def seat_stats(conn: sqlite3.Connection) -> List[Dict]:
    return _rows(conn.execute(f"""
        SELECT gp.seat, COUNT(*) AS games, SUM(gp.finish_place = 1) AS wins, {_WIN_RATE} AS win_rate
        FROM game_players gp
        GROUP BY gp.seat
        ORDER BY gp.seat
    """))


def matchup_stats(conn: sqlite3.Connection, player: Optional[str] = None) -> List[Dict]:
    """Head-to-head for every pair of players who have shared a table.

    `a_ahead` counts games where player_a finished in a better place than player_b.
    """
    where, params = ("WHERE pa.name = ? OR pb.name = ?", (player, player)) if player else ("", ())
    return _rows(conn.execute(f"""
        SELECT pa.name AS player_a, pb.name AS player_b,
               COUNT(*) AS games,
               SUM(ga.finish_place = 1) AS a_wins,
               SUM(gb.finish_place = 1) AS b_wins,
               SUM(ga.finish_place < gb.finish_place) AS a_ahead,
               SUM(gb.finish_place < ga.finish_place) AS b_ahead
        FROM game_players ga
        JOIN game_players gb ON gb.game_id = ga.game_id AND ga.player_id < gb.player_id
        JOIN players pa ON pa.id = ga.player_id
        JOIN players pb ON pb.id = gb.player_id
        {where}
        GROUP BY ga.player_id, gb.player_id
        ORDER BY games DESC, pa.name, pb.name
    """, params))


def deck_matchup_stats(conn: sqlite3.Connection) -> List[Dict]:
    """Head-to-head for every pair of decks that have shared a table (same columns as matchup_stats)."""
    return _rows(conn.execute("""
        SELECT da.name AS deck_a, pa.name AS owner_a, db.name AS deck_b, pb.name AS owner_b,
               COUNT(*) AS games,
               SUM(ga.finish_place = 1) AS a_wins,
               SUM(gb.finish_place = 1) AS b_wins,
               SUM(ga.finish_place < gb.finish_place) AS a_ahead,
               SUM(gb.finish_place < ga.finish_place) AS b_ahead
        FROM game_players ga
        JOIN game_players gb ON gb.game_id = ga.game_id AND ga.deck_id < gb.deck_id
        JOIN decks da ON da.id = ga.deck_id
        JOIN decks db ON db.id = gb.deck_id
        JOIN players pa ON pa.id = da.owner_id
        JOIN players pb ON pb.id = db.owner_id
        GROUP BY ga.deck_id, gb.deck_id
        ORDER BY games DESC, da.name, db.name
    """))


def summary_stats(conn: sqlite3.Connection) -> Dict:
    totals = dict(conn.execute(
        "SELECT COUNT(*) AS games, ROUND(AVG(turns), 1) AS avg_turns FROM games"
    ).fetchone())
    totals["win_cons"] = _rows(conn.execute("""
        SELECT COALESCE(win_con, 'UNKNOWN') AS win_con, COUNT(*) AS games
        FROM games GROUP BY 1 ORDER BY games DESC
    """))
    return totals
