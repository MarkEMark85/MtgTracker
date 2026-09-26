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
        "player": "Mark", "deck": "Atraxa, Praetors' Voice", "commander": None, "archetype": None,
        "seat": 1, "finish_place": 1, "eliminated_turn": None, "eliminated_by": None,
    }
    assert first["is_draw"] is False

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


def deck_id(client, owner, name):
    return next(d["id"] for d in client.get("/api/decks", params={"owner": owner}).json() if d["name"] == name)


def test_deck_matchup_filter_lists_every_opponent_of_chosen_deck(client):
    client.post("/api/games", json=game(TABLE, "Brett"))
    client.post("/api/games", json=game([("Chris", "Krenko"), ("Brett", "Omnath")], "Chris"))

    omnath = deck_id(client, "Brett", "Omnath")
    rows = client.get("/api/stats/deck-matchups", params={"deck": omnath}).json()
    assert {r["deck_a"] for r in rows} == {"Omnath"}                       # chosen deck always on the a side
    assert {r["deck_b"] for r in rows} == {"Atraxa, Praetors' Voice", "Krenko"}
    krenko = by(rows, "deck_b", "Krenko")
    assert (krenko["games"], krenko["a_wins"], krenko["b_wins"]) == (2, 1, 1)

    atraxa = deck_id(client, "Mark", "Atraxa, Praetors' Voice")
    both = client.get("/api/stats/deck-matchups", params={"deck": [omnath, atraxa]}).json()
    assert {r["deck_a_id"] for r in both} == {omnath, atraxa}
    assert all(r["deck_a_id"] != r["deck_b_id"] for r in both)

    too_many = client.get("/api/stats/deck-matchups", params={"deck": [1, 2, 3, 4]})
    assert too_many.status_code == 422


def test_win_con_labels_and_archetypes_in_meta(client):
    meta = client.get("/api/meta").json()
    assert {"code": "POISON", "label": "Poison / infect"} in meta["win_cons"]
    assert "VOLTRON" in {a["code"] for a in meta["archetypes"]}

    payload = game(TABLE, "Mark", win_con="COMBO", winning_play="Thassa's Oracle")
    payload["participants"][0]["archetype"] = "COMBO"
    client.post("/api/games", json=payload)
    g = client.get("/api/games").json()[0]
    assert (g["win_con"], g["winning_play"]) == ("COMBO", "Thassa's Oracle")
    assert by(client.get("/api/decks").json(), "owner", "Mark")["archetype"] == "COMBO"

    bad = game(TABLE, "Mark", win_con="MAGIC")
    assert client.post("/api/games", json=bad).status_code == 422
    bad = game(TABLE, "Mark")
    bad["participants"][0]["archetype"] = "TRIBAL-ISH"
    assert client.post("/api/games", json=bad).status_code == 422


def test_draw_counts_for_no_one(client):
    draw = game(TABLE, "Mark", is_draw=True)
    draw["participants"][1]["finish_place"] = 1  # Mark and Chris tied, Brett out first
    draw["participants"][2]["finish_place"] = 3
    assert client.post("/api/games", json=draw).status_code == 201
    client.post("/api/games", json=game(TABLE, "Brett"))

    players = client.get("/api/stats/players").json()
    assert by(players, "player", "Mark")["wins"] == 0
    assert by(players, "player", "Brett")["wins"] == 1
    assert client.get("/api/stats/summary").json()["draws"] == 1
    pair = next(p for p in client.get("/api/stats/matchups").json() if {p["player_a"], p["player_b"]} == {"Mark", "Chris"})
    assert (pair["a_wins"], pair["b_wins"]) == (0, 0)
    assert client.get("/api/games").json()[1]["is_draw"] is True


@pytest.mark.parametrize("is_draw, firsts, message", [
    (True, 1, "a draw needs at least two"),
    (False, 2, "exactly one player"),
])
def test_draw_validation(client, is_draw, firsts, message):
    payload = game(TABLE, "Mark", is_draw=is_draw)
    for p in payload["participants"][:firsts]:
        p["finish_place"] = 1
    r = client.post("/api/games", json=payload)
    assert r.status_code == 422 and message in r.text


def test_win_rate_vs_par_uses_table_size(client):
    client.post("/api/games", json=game(TABLE + [("Dana", "Sliver")], "Mark"))  # 4 players: par 25
    client.post("/api/games", json=game(TABLE, "Chris"))                        # 3 players: par 33.3
    mark = by(client.get("/api/stats/players").json(), "player", "Mark")
    assert (mark["win_rate"], mark["par"], mark["vs_par"]) == (50.0, 29.2, 20.8)
    assert mark["last10"] == {"wins": 1, "games": 2}
    dana = by(client.get("/api/stats/players").json(), "player", "Dana")
    assert (dana["par"], dana["vs_par"]) == (25.0, -25.0)
    seat1 = by(client.get("/api/stats/seats").json(), "seat", 1)
    assert seat1["par"] == 29.2


def test_knocked_out_by_and_nemesis(client):
    first = game(TABLE, "Mark")
    first["participants"][1]["eliminated_by"] = "mark"   # case-insensitive
    first["participants"][2]["eliminated_by"] = "Mark"
    client.post("/api/games", json=first)
    second = game(TABLE, "Chris")
    second["participants"][0]["eliminated_by"] = "Chris"
    client.post("/api/games", json=second)

    ko = {r["player"]: r for r in client.get("/api/stats/knockouts").json()}
    assert ko["Mark"]["kos"] == 2 and ko["Chris"]["kos"] == 1
    assert ko["Brett"]["nemesis"] == {"name": "Mark", "count": 1}
    assert ko["Mark"]["nemesis"] == {"name": "Chris", "count": 1}
    assert ko["Brett"]["first_out"] == 2 and ko["Brett"]["first_out_rate"] == 100.0
    history = client.get("/api/games").json()
    assert by(history[1]["participants"], "player", "Brett")["eliminated_by"] == "Mark"

    for name, message in (("Brett", "knock themselves out"), ("Zed", "not at the table")):
        bad = game(TABLE, "Mark")
        bad["participants"][2]["eliminated_by"] = name
        r = client.post("/api/games", json=bad)
        assert r.status_code == 422 and message in r.text


def test_damage_dealt(client):
    first = game(TABLE, "Mark", damage=[
        {"source": "Mark", "target": "Chris", "amount": 30},
        {"source": "Mark", "target": "Chris", "amount": 10},          # merged with the row above
        {"source": "Mark", "target": "Brett", "amount": 21, "commander": True},
        {"source": "Chris", "target": "Mark", "amount": 12},
    ])
    gid = client.post("/api/games", json=first).json()["id"]
    client.post("/api/games", json=game(TABLE, "Chris"))  # untracked game: ignored in damage averages

    players = client.get("/api/stats/players").json()
    assert by(players, "player", "Mark")["avg_dmg"] == 61.0
    assert by(players, "player", "Brett")["avg_dmg"] == 0.0
    assert by(client.get("/api/stats/decks").json(), "owner", "Chris")["avg_dmg"] == 12.0

    ko = {r["player"]: r for r in client.get("/api/stats/knockouts").json()}
    assert ko["Mark"]["most_targeted"] == {"name": "Chris", "count": 40}
    assert (ko["Chris"]["avg_taken"], ko["Brett"]["avg_taken"]) == (40.0, 21.0)
    assert ko["Brett"]["most_targeted"] is None

    for bad_row in ({"source": "Mark", "target": "Mark", "amount": 3},
                    {"source": "Mark", "target": "Zed", "amount": 3},
                    {"source": "Mark", "target": "Chris", "amount": 0}):
        assert client.post("/api/games", json=game(TABLE, "Mark", damage=[bad_row])).status_code == 422

    client.delete(f"/api/games/{gid}")
    assert by(client.get("/api/stats/players").json(), "player", "Mark")["avg_dmg"] is None


def test_deck_detail(client):
    client.post("/api/games", json=game(TABLE, "Mark", win_con="POISON"))
    client.post("/api/games", json=game([("Chris", "Krenko"), ("Mark", "Atraxa, Praetors' Voice")], "Mark", win_con="COMBAT"))
    client.post("/api/games", json=game(TABLE, "Chris"))

    atraxa = deck_id(client, "Mark", "Atraxa, Praetors' Voice")
    detail = client.get(f"/api/stats/decks/{atraxa}").json()
    assert detail["owner"] == "Mark"
    assert {w["win_con"]: w["games"] for w in detail["win_cons"]} == {"POISON": 1, "COMBAT": 1}
    assert {s["seat"]: (s["games"], s["wins"]) for s in detail["seats"]} == {1: (2, 1), 2: (1, 1)}
    assert [r["result"] for r in detail["recent"]] == ["L", "W", "W"]
    assert client.get("/api/stats/decks/999").status_code == 404
    assert "id" in client.get("/api/stats/decks").json()[0]


OLD_SCHEMA = """
CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE);
CREATE TABLE decks (id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE, owner_id INTEGER NOT NULL,
                    commander TEXT, colors TEXT, UNIQUE (name, owner_id));
CREATE TABLE games (id INTEGER PRIMARY KEY, played_at TEXT NOT NULL, turns INTEGER, win_con TEXT,
                    win_details TEXT, notes TEXT);
CREATE TABLE game_players (game_id INTEGER NOT NULL, player_id INTEGER NOT NULL, deck_id INTEGER NOT NULL,
                           seat INTEGER NOT NULL, finish_place INTEGER NOT NULL, eliminated_turn INTEGER,
                           PRIMARY KEY (game_id, player_id), UNIQUE (game_id, seat));
CREATE TABLE turn_events (id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL, round INTEGER NOT NULL,
                          player_id INTEGER, event TEXT NOT NULL);
INSERT INTO players VALUES (1, 'Mark'), (2, 'Chris');
INSERT INTO decks VALUES (1, 'Sigarda', 1, NULL, NULL), (2, 'Krenko', 2, NULL, NULL);
INSERT INTO games VALUES (1, '2026-09-01T20:00:00', 7, 'COMMANDER', 'VOLTRON', NULL);
INSERT INTO game_players VALUES (1, 1, 1, 1, 1, NULL), (1, 2, 2, 2, 2, 6);
"""


def test_old_database_is_migrated(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    with db.connect(path) as conn:
        conn.executescript(OLD_SCHEMA)
    monkeypatch.setenv("MTG_DB", str(path))
    with TestClient(app) as c:
        decks = {d["name"]: d["archetype"] for d in c.get("/api/decks").json()}
        assert decks == {"Sigarda": "VOLTRON", "Krenko": None}
        assert c.get("/api/games").json()[0]["is_draw"] is False
        assert by(c.get("/api/stats/players").json(), "player", "Mark")["wins"] == 1
        assert c.post("/api/games", json=game([("Mark", "Sigarda"), ("Chris", "Krenko")], "Chris")).status_code == 201
    db.init_db(path)  # running again is a no-op
