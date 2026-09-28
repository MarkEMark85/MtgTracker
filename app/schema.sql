-- MTG Tracker schema. Stats (win rate, averages) are computed at query time, never stored.
-- Columns added after the first release are also listed in db._MIGRATIONS so older databases upgrade.

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
    archetype TEXT,
    UNIQUE (name, owner_id)
);

CREATE TABLE IF NOT EXISTS games (
    id           INTEGER PRIMARY KEY,
    played_at    TEXT NOT NULL,          -- ISO 8601 date/time
    turns        INTEGER,
    win_con      TEXT,
    win_details  TEXT,                   -- legacy, no longer written (moved to decks.archetype)
    notes        TEXT,
    is_draw      INTEGER NOT NULL DEFAULT 0,
    winning_play TEXT
);

-- One row per participant in a game.
CREATE TABLE IF NOT EXISTS game_players (
    game_id         INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id       INTEGER NOT NULL REFERENCES players(id),
    deck_id         INTEGER NOT NULL REFERENCES decks(id),
    seat            INTEGER NOT NULL,   -- 1 = went first
    finish_place    INTEGER NOT NULL,   -- 1 = winner (in a draw, everyone tied shares 1st)
    eliminated_turn INTEGER,
    eliminated_by   INTEGER REFERENCES players(id),
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

-- Damage dealt, one row per source -> target pair (and kind) per game.
CREATE TABLE IF NOT EXISTS damage (
    game_id   INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES players(id),
    target_id INTEGER NOT NULL REFERENCES players(id),
    amount    INTEGER NOT NULL,
    commander INTEGER NOT NULL DEFAULT 0,   -- 1 = commander damage
    PRIMARY KEY (game_id, source_id, target_id, commander)
);

CREATE INDEX IF NOT EXISTS idx_game_players_player ON game_players(player_id);
CREATE INDEX IF NOT EXISTS idx_game_players_deck ON game_players(deck_id);
