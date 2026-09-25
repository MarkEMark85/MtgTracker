-- MTG Tracker schema. Stats (win rate, averages) are computed at query time, never stored.

CREATE TABLE IF NOT EXISTS players (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS decks (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL COLLATE NOCASE,
    owner_id  INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    commander TEXT,
    colors    TEXT,
    UNIQUE (name, owner_id)
);

CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY,
    played_at   TEXT NOT NULL,          -- ISO 8601 date/time
    turns       INTEGER,
    win_con     TEXT,
    win_details TEXT,
    notes       TEXT
);

-- One row per participant in a game.
CREATE TABLE IF NOT EXISTS game_players (
    game_id         INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id       INTEGER NOT NULL REFERENCES players(id),
    deck_id         INTEGER NOT NULL REFERENCES decks(id),
    seat            INTEGER NOT NULL,   -- 1 = went first
    finish_place    INTEGER NOT NULL,   -- 1 = winner
    eliminated_turn INTEGER,
    PRIMARY KEY (game_id, player_id),
    UNIQUE (game_id, seat)
);

CREATE TABLE IF NOT EXISTS turn_events (
    id        INTEGER PRIMARY KEY,
    game_id   INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    round     INTEGER NOT NULL,
    player_id INTEGER REFERENCES players(id),
    event     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_game_players_player ON game_players(player_id);
CREATE INDEX IF NOT EXISTS idx_game_players_deck ON game_players(deck_id);
