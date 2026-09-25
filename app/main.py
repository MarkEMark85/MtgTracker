"""FastAPI app: JSON API under /api, mobile web front end served from /."""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from app import db

STATIC_DIR = Path(__file__).resolve().parent / "static"



@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="MTG Tracker", lifespan=lifespan)


# ---------- models ----------

def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


class PlayerIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("name is required")
        return v


class DeckIn(BaseModel):
    name: str
    owner: str
    commander: Optional[str] = None
    colors: Optional[str] = None

    @field_validator("name", "owner")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("required")
        return v

    @field_validator("commander", "colors")
    @classmethod
    def tidy(cls, v: Optional[str]) -> Optional[str]:
        return _clean(v)


class Participant(BaseModel):
    player: str
    deck: str
    commander: Optional[str] = None
    seat: int = Field(ge=1)
    finish_place: int = Field(ge=1)
    eliminated_turn: Optional[int] = Field(default=None, ge=1)

    @field_validator("player", "deck")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("required")
        return v

    @field_validator("commander")
    @classmethod
    def tidy(cls, v: Optional[str]) -> Optional[str]:
        return _clean(v)


class TurnEvent(BaseModel):
    round: int = Field(ge=1)
    player: Optional[str] = None
    event: str


class GameIn(BaseModel):
    played_at: Optional[str] = None
    turns: Optional[int] = Field(default=None, ge=1)
    win_con: Optional[str] = None
    win_details: Optional[str] = None
    notes: Optional[str] = None
    participants: List[Participant] = Field(min_length=2, max_length=8)
    turn_events: List[TurnEvent] = []

    @model_validator(mode="after")
    def check_table(self) -> "GameIn":
        n = len(self.participants)
        names = [p.player.casefold() for p in self.participants]
        if len(set(names)) != n:
            raise ValueError("each player can only appear once")
        if sorted(p.seat for p in self.participants) != list(range(1, n + 1)):
            raise ValueError(f"seats must be 1..{n}, each used once")
        places = [p.finish_place for p in self.participants]
        if any(pl > n for pl in places):
            raise ValueError(f"finish places must be between 1 and {n}")
        if places.count(1) != 1:
            raise ValueError("exactly one player must finish in 1st place")
        return self


# ---------- API ----------

@app.get("/api/meta")
def meta():
    return {"win_cons": db.WIN_CONS, "win_details": db.WIN_DETAILS}


@app.get("/api/players")
def get_players():
    with db.connect() as conn:
        return db.list_players(conn)


@app.post("/api/players", status_code=201)
def add_player(player: PlayerIn):
    with db.connect() as conn:
        return {"id": db.get_or_create_player(conn, player.name), "name": player.name}


@app.get("/api/decks")
def get_decks(owner: Optional[str] = None):
    with db.connect() as conn:
        return db.list_decks(conn, owner)


@app.post("/api/decks", status_code=201)
def add_deck(deck: DeckIn):
    with db.connect() as conn:
        owner_id = db.get_or_create_player(conn, deck.owner)
        deck_id = db.get_or_create_deck(conn, owner_id, deck.name, deck.commander, deck.colors)
        return {"id": deck_id, **deck.model_dump()}


@app.get("/api/games")
def get_games(limit: int = 50):
    with db.connect() as conn:
        return db.list_games(conn, limit)


@app.post("/api/games", status_code=201)
def add_game(game: GameIn):
    with db.connect() as conn:
        return {"id": db.save_game(conn, game.model_dump())}


@app.delete("/api/games/{game_id}", status_code=204)
def remove_game(game_id: int):
    with db.connect() as conn:
        if not db.delete_game(conn, game_id):
            raise HTTPException(404, "game not found")


@app.get("/api/stats/summary")
def stats_summary():
    with db.connect() as conn:
        return db.summary_stats(conn)


@app.get("/api/stats/players")
def stats_players():
    with db.connect() as conn:
        return db.player_stats(conn)


@app.get("/api/stats/decks")
def stats_decks(owner: Optional[str] = None):
    with db.connect() as conn:
        return db.deck_stats(conn, owner)


@app.get("/api/stats/seats")
def stats_seats():
    with db.connect() as conn:
        return db.seat_stats(conn)


@app.get("/api/stats/matchups")
def stats_matchups(player: Optional[str] = None):
    with db.connect() as conn:
        return db.matchup_stats(conn, player)


@app.get("/api/stats/deck-matchups")
def stats_deck_matchups():
    with db.connect() as conn:
        return db.deck_matchup_stats(conn)


# ---------- front end ----------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # Served from the root so the worker's scope covers the whole app.
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
