import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MTG_DB", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def game(order, winner, turns=8, **extra):
    """order: list of (player, deck) in seat order. winner: player name who finished 1st.
    Everyone else gets places 2..n in seat order."""
    places, nxt = {}, 2
    for name, _ in order:
        if name == winner:
            places[name] = 1
        else:
            places[name], nxt = nxt, nxt + 1
    return {
        "turns": turns,
        "win_con": "COMBAT",
        "participants": [
            {"player": p, "deck": d, "seat": i + 1, "finish_place": places[p]}
            for i, (p, d) in enumerate(order)
        ],
        **extra,
    }


TABLE = [("Mark", "Atraxa, Praetors' Voice"), ("Chris", "Krenko"), ("Brett", "Omnath")]


def by(rows, key, value):
    return next(r for r in rows if r[key] == value)


def test_save_game_creates_players_and_decks(client):
    r = client.post("/api/games", json=game(TABLE, "Chris"))
    assert r.status_code == 201

    players = {p["name"] for p in client.get("/api/players").json()}
    assert players == {"Mark", "Chris", "Brett"}
    decks = client.get("/api/decks", params={"owner": "Mark"}).json()
    assert [d["name"] for d in decks] == ["Atraxa, Praetors' Voice"]  # apostrophe + comma survive


def test_player_win_rate_counts_own_wins(client):
    client.post("/api/games", json=game(TABLE, "Mark", turns=6))
    client.post("/api/games", json=game(TABLE, "Chris", turns=10))
    client.post("/api/games", json=game(TABLE, "Chris", turns=8))

    stats = client.get("/api/stats/players").json()
    mark, chris, brett = (by(stats, "player", n) for n in ("Mark", "Chris", "Brett"))
    assert (mark["games"], mark["wins"], mark["win_rate"]) == (3, 1, 33.3)
    assert (chris["wins"], chris["win_rate"], chris["avg_win_turn"]) == (2, 66.7, 9.0)
    assert (brett["wins"], brett["win_rate"], brett["avg_win_turn"]) == (0, 0.0, None)
    assert stats[0]["player"] == "Chris"


def test_same_deck_name_different_owners_kept_separate(client):
    client.post("/api/games", json=game([("Mark", "Elves"), ("Chris", "Elves")], "Mark"))
    decks = client.get("/api/stats/decks").json()
    assert {(d["owner"], d["wins"]) for d in decks} == {("Mark", 1), ("Chris", 0)}


def test_player_names_are_case_insensitive(client):
    client.post("/api/games", json=game([("Mark", "Elves"), ("Chris", "Goblins")], "Mark"))
    client.post("/api/games", json=game([("mark", "elves"), ("Chris", "Goblins")], "mark"))
    stats = client.get("/api/stats/players").json()
    assert by(stats, "player", "Mark")["wins"] == 2
    assert len(client.get("/api/decks").json()) == 2


def test_seat_and_matchup_stats(client):
    client.post("/api/games", json=game(TABLE, "Mark"))   # seat 1 wins
    client.post("/api/games", json=game(TABLE, "Brett"))  # seat 3 wins

    seats = {s["seat"]: s for s in client.get("/api/stats/seats").json()}
    assert seats[1]["win_rate"] == 50.0 and seats[2]["win_rate"] == 0.0 and seats[3]["win_rate"] == 50.0

    pairs = client.get("/api/stats/matchups", params={"player": "Mark"}).json()
    mb = next(p for p in pairs if {p["player_a"], p["player_b"]} == {"Mark", "Brett"})
    assert mb["games"] == 2
    assert mb["a_wins"] + mb["b_wins"] == 2


def test_summary_and_history_and_delete(client):
    gid = client.post("/api/games", json=game(TABLE, "Mark", turns=6, notes="close one")).json()["id"]
    client.post("/api/games", json=game(TABLE, "Chris", turns=10))

    summary = client.get("/api/stats/summary").json()
    assert summary["games"] == 2 and summary["avg_turns"] == 8.0
    assert summary["win_cons"] == [{"win_con": "COMBAT", "games": 2}]

    history = client.get("/api/games").json()
    first = by(history, "id", gid)
    assert first["notes"] == "close one"
    assert first["participants"][0] == {
        "player": "Mark", "deck": "Atraxa, Praetors' Voice", "commander": None,
        "seat": 1, "finish_place": 1, "eliminated_turn": None,
    }

    assert client.delete(f"/api/games/{gid}").status_code == 204
    assert client.delete(f"/api/games/{gid}").status_code == 404
    assert client.get("/api/stats/summary").json()["games"] == 1
    assert by(client.get("/api/stats/players").json(), "player", "Mark")["games"] == 1


def test_turn_events_saved(client, tmp_path):
    payload = game(TABLE, "Mark", turn_events=[{"round": 4, "player": "Brett", "event": "eliminated"}])
    gid = client.post("/api/games", json=payload).json()["id"]
    with db.connect(tmp_path / "test.db") as conn:
        row = conn.execute(
            "SELECT e.round, p.name, e.event FROM turn_events e JOIN players p ON p.id = e.player_id WHERE game_id = ?",
            (gid,),
        ).fetchone()
    assert tuple(row) == (4, "Brett", "eliminated")


@pytest.mark.parametrize("mutate, message", [
    (lambda g: g["participants"][0].update(finish_place=2), "exactly one player"),
    (lambda g: g["participants"][1].update(finish_place=1), "exactly one player"),
    (lambda g: g["participants"][0].update(seat=2), "seats must be"),
    (lambda g: g["participants"][0].update(finish_place=9), "finish places"),
    (lambda g: g["participants"][1].update(player="mark"), "only appear once"),
    (lambda g: g["participants"][0].update(player="   "), "required"),
    (lambda g: g["participants"][0].update(deck=""), "required"),
    (lambda g: g.update(participants=g["participants"][:1]), "at least 2"),
])
def test_invalid_games_rejected(client, mutate, message):
    payload = game(TABLE, "Mark")
    mutate(payload)
    r = client.post("/api/games", json=payload)
    assert r.status_code == 422
    assert message in r.text
    assert client.get("/api/stats/summary").json()["games"] == 0


def test_front_end_served(client):
    assert "MTG Tracker" in client.get("/").text
    assert client.get("/static/manifest.json").json()["display"] == "standalone"
    assert client.get("/sw.js").headers["content-type"].startswith("application/javascript")


def test_deck_matchup_stats(client):
    client.post("/api/games", json=game([("Mark", "Elves"), ("Chris", "Elves")], "Mark"))
    client.post("/api/games", json=game([("Mark", "Elves"), ("Chris", "Elves")], "Chris"))
    client.post("/api/games", json=game([("Mark", "Elves"), ("Chris", "Krenko")], "Chris"))

    pairs = client.get("/api/stats/deck-matchups").json()
    assert len(pairs) == 2
    elves = next(p for p in pairs if p["deck_b"] == "Elves")
    assert {elves["owner_a"], elves["owner_b"]} == {"Mark", "Chris"}
    assert elves["games"] == 2 and elves["a_wins"] == 1 and elves["b_wins"] == 1
    assert elves["a_ahead"] + elves["b_ahead"] == 2

    krenko = next(p for p in pairs if "Krenko" in (p["deck_a"], p["deck_b"]))
    assert krenko["games"] == 1
