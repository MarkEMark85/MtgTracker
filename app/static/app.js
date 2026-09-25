"use strict";

// ---------- helpers ----------

const $app = document.getElementById("app");
const GAME_KEY = "mtg.currentGame";
const SEAT_COLORS = ["#e0b64a", "#4a90e2", "#d9534f", "#5cb85c", "#9b6bd6", "#e67e22", "#1abc9c", "#c0c0c0"];

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

async function api(path, opts = {}) {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const data = await res.json();
      msg = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg.replace(/^Value error, /, "")).join("; ")
        : data.detail || msg;
    } catch (_) { /* not JSON */ }
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

let toastTimer;
function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3000);
}

function loadGame() {
  try { return JSON.parse(localStorage.getItem(GAME_KEY)); } catch (_) { return null; }
}
function saveGame() {
  try { localStorage.setItem(GAME_KEY, JSON.stringify(state.game)); } catch (_) { /* storage blocked */ }
}
function clearGame() {
  state.game = null;
  try { localStorage.removeItem(GAME_KEY); } catch (_) { /* storage blocked */ }
}

const ordinal = (n) => n + (["th", "st", "nd", "rd"][(n % 100 - 20) % 10] || ["th", "st", "nd", "rd"][n % 100] || "th");

// ---------- state & routing ----------

const state = {
  view: "home",
  game: loadGame(),
  setup: null,
  meta: { win_cons: [], win_details: [] },
  players: [],
  decks: [],
  statsTab: "players",
  h2hMode: "players",
};

function go(view) {
  state.view = view;
  render();
  window.scrollTo(0, 0);
}

function render() {
  const views = { home: viewHome, setup: viewSetup, live: viewLive, end: viewEnd, stats: viewStats, history: viewHistory };
  $app.innerHTML = views[state.view]();
  if (state.view === "stats") loadStats();
  if (state.view === "history") loadHistory();
}

// ---------- home ----------

function viewHome() {
  const g = state.game;
  return `
    <header class="hero">
      <div class="logo">&#9670;</div>
      <h1>MTG Tracker</h1>
      <p class="muted">Track your games. Learn from the numbers.</p>
    </header>
    <div class="stack">
      ${g ? `<button class="btn primary big" data-action="resume">
                Resume game <span class="sub">Round ${g.round} &middot; ${g.players.map((p) => esc(p.player)).join(", ")}</span>
             </button>` : ""}
      <button class="btn ${g ? "" : "primary"} big" data-action="new-game">New game</button>
      <button class="btn big" data-action="go" data-view="stats">Stats</button>
      <button class="btn big" data-action="go" data-view="history">Game history</button>
    </div>`;
}

// ---------- setup ----------

function newSetup() {
  const prev = state.setup;
  return {
    count: prev ? prev.count : 4,
    life: prev ? prev.life : 40,
    // Remember table size and life total, but always start with blank names.
    rows: Array.from({ length: 8 }, () => ({ player: "", deck: "", commander: "" })),
  };
}

function viewSetup() {
  const s = state.setup;
  const rows = s.rows.slice(0, s.count).map((r, i) => {
    const decks = state.decks.filter((d) => d.owner.toLowerCase() === r.player.trim().toLowerCase());
    return `
      <div class="seat-row" style="--seat:${SEAT_COLORS[i]}">
        <div class="seat-num">${i + 1}</div>
        <div class="seat-fields">
          <input list="dl-players" placeholder="Player" value="${esc(r.player)}" data-row="${i}" data-field="player" autocomplete="off">
          <input list="dl-decks-${i}" placeholder="Deck" value="${esc(r.deck)}" data-row="${i}" data-field="deck" autocomplete="off">
          <datalist id="dl-decks-${i}">${decks.map((d) => `<option value="${esc(d.name)}">`).join("")}</datalist>
          <input placeholder="Commander (optional)" value="${esc(r.commander)}" data-row="${i}" data-field="commander" autocomplete="off">
        </div>
      </div>`;
  }).join("");

  return `
    ${topbar("New game", "home")}
    <section class="card">
      <div class="row between">
        <label>Players</label>
        <div class="stepper">
          <button class="btn icon" data-action="count" data-delta="-1" aria-label="Fewer players">&minus;</button>
          <span>${s.count}</span>
          <button class="btn icon" data-action="count" data-delta="1" aria-label="More players">+</button>
        </div>
      </div>
      <div class="row between">
        <label>Starting life</label>
        <div class="seg">
          ${[20, 30, 40].map((l) => `<button class="${s.life === l ? "on" : ""}" data-action="life0" data-life="${l}">${l}</button>`).join("")}
        </div>
      </div>
    </section>
    <p class="muted small">Enter players in seat order. Seat 1 goes first.</p>
    <datalist id="dl-players">${state.players.map((p) => `<option value="${esc(p.name)}">`).join("")}</datalist>
    <div class="stack">${rows}</div>
    <div class="stack gap-top">
      <button class="btn" data-action="shuffle">Shuffle seats</button>
      <button class="btn primary big" data-action="start">Start game</button>
    </div>`;
}

function startGame() {
  const s = state.setup;
  const rows = s.rows.slice(0, s.count).map((r) => ({
    player: r.player.trim(), deck: r.deck.trim(), commander: r.commander.trim(),
  }));
  if (rows.some((r) => !r.player || !r.deck)) return toast("Every seat needs a player and a deck.");
  const names = rows.map((r) => r.player.toLowerCase());
  if (new Set(names).size !== names.length) return toast("Each player can only sit once.");

  state.game = {
    life0: s.life,
    round: 1,
    active: 0,
    outCount: 0,
    openCmd: null,
    startedAt: new Date().toISOString(),
    events: [],
    players: rows.map((r, i) => ({ ...r, seat: i + 1, life: s.life, cmd: {}, poison: 0, out: null, outRound: null })),
  };
  saveGame();
  go("live");
}

// ---------- live game ----------

function viewLive() {
  const g = state.game;
  const cards = g.players.map((p, i) => {
    const cmdTotal = Math.max(0, ...Object.values(p.cmd));
    const lethal = p.life <= 0 || cmdTotal >= 21 || p.poison >= 10;
    const classes = ["pcard", i === g.active ? "active" : "", g.openCmd === i ? "wide" : "", p.out ? "out" : "", lethal && !p.out ? "lethal" : ""].join(" ");
    const cmdRows = g.openCmd === i ? `
      <div class="cmd">
        <div class="cmd-title">Commander damage taken</div>
        ${g.players.map((o, j) => j === i ? "" : `
          <div class="cmd-row">
            <span class="dot" style="background:${SEAT_COLORS[j]}"></span>
            <span class="cmd-name">${esc(o.player)}</span>
            <button class="btn icon sm" data-action="cmd" data-p="${i}" data-from="${j}" data-delta="-1">&minus;</button>
            <b class="${(p.cmd[j] || 0) >= 21 ? "danger" : ""}">${p.cmd[j] || 0}</b>
            <button class="btn icon sm" data-action="cmd" data-p="${i}" data-from="${j}" data-delta="1">+</button>
          </div>`).join("")}
        <div class="cmd-row">
          <span class="dot poison"></span>
          <span class="cmd-name">Poison</span>
          <button class="btn icon sm" data-action="poison" data-p="${i}" data-delta="-1">&minus;</button>
          <b class="${p.poison >= 10 ? "danger" : ""}">${p.poison}</b>
          <button class="btn icon sm" data-action="poison" data-p="${i}" data-delta="1">+</button>
        </div>
      </div>` : "";

    return `
      <div class="${classes}" style="--seat:${SEAT_COLORS[i]}">
        <div class="pcard-head" data-action="set-active" data-p="${i}">
          <span class="pname">${esc(p.player)}</span>
          <span class="pdeck">${esc(p.deck)}</span>
        </div>
        <div class="life-row">
          <button class="life-btn" data-action="life" data-p="${i}" data-delta="-1" aria-label="Lose 1 life">&minus;</button>
          <div class="life">${p.life}</div>
          <button class="life-btn" data-action="life" data-p="${i}" data-delta="1" aria-label="Gain 1 life">+</button>
        </div>
        <div class="pcard-tools">
          <button class="chip" data-action="life" data-p="${i}" data-delta="-5">&minus;5</button>
          <button class="chip ${g.openCmd === i ? "on" : ""}" data-action="toggle-cmd" data-p="${i}">Cmdr ${cmdTotal ? cmdTotal : ""}</button>
          <button class="chip" data-action="life" data-p="${i}" data-delta="5">+5</button>
        </div>
        ${cmdRows}
        <button class="chip wide ${p.out ? "on" : ""}" data-action="eliminate" data-p="${i}">
          ${p.out ? `Out on round ${p.outRound} &middot; undo` : "Eliminated"}
        </button>
      </div>`;
  }).join("");

  return `
    ${topbar("Game", "home")}
    <section class="round-bar">
      <button class="btn icon" data-action="round" data-delta="-1" aria-label="Previous round">&minus;</button>
      <div class="round"><span class="muted small">Round</span><b>${g.round}</b></div>
      <button class="btn icon" data-action="round" data-delta="1" aria-label="Next round">+</button>
    </section>
    <div class="grid ${g.players.length > 2 ? "two" : ""}">${cards}</div>
    <div class="stack gap-top sticky-bottom">
      <div class="row">
        <button class="btn primary grow" data-action="next-turn">Next turn &rarr; <span class="sub">${esc(g.players[g.active].player)} is up</span></button>
      </div>
      <div class="row">
        <button class="btn grow" data-action="go" data-view="end">End game</button>
        <button class="btn danger-outline" data-action="abandon">Discard</button>
      </div>
    </div>`;
}

function aliveCount() {
  return state.game.players.filter((p) => !p.out).length;
}

function nextTurn() {
  const g = state.game;
  if (aliveCount() === 0) return;
  let i = g.active;
  do {
    i = (i + 1) % g.players.length;
    if (i === 0) g.round += 1;
  } while (g.players[i].out);
  g.active = i;
}

function toggleEliminated(i) {
  const g = state.game;
  const p = g.players[i];
  if (p.out) {
    p.out = null;
    p.outRound = null;
    g.events = g.events.filter((e) => !(e.player === p.player && e.event === "eliminated"));
  } else {
    g.outCount += 1;
    p.out = g.outCount;
    p.outRound = g.round;
    g.events.push({ round: g.round, player: p.player, event: "eliminated" });
    if (g.active === i) nextTurn();
  }
  if (aliveCount() === 1) toast("One player left. Tap End game to record the result.");
}

// ---------- end game ----------

function prefillPlaces() {
  // Last eliminated = best non-winning place. Anyone still alive gets the top places in seat order.
  const g = state.game;
  const n = g.players.length;
  const alive = g.players.filter((p) => !p.out);
  const out = g.players.filter((p) => p.out).sort((a, b) => b.out - a.out);
  [...alive, ...out].forEach((p, idx) => { if (p.place == null) p.place = Math.min(idx + 1, n); });
  if (g.turns == null) g.turns = g.round;
}

function viewEnd() {
  const g = state.game;
  prefillPlaces();
  const n = g.players.length;
  const opts = (list, cur) => `<option value="">&mdash;</option>` +
    list.map((v) => `<option ${v === cur ? "selected" : ""}>${esc(v)}</option>`).join("");

  return `
    ${topbar("Result", "live")}
    <section class="card">
      <h2>Finish order</h2>
      ${g.players.map((p, i) => `
        <div class="row between place-row" style="--seat:${SEAT_COLORS[i]}">
          <div><b>${esc(p.player)}</b><div class="muted small">${esc(p.deck)}</div></div>
          <select data-place="${i}">
            ${Array.from({ length: n }, (_, k) => k + 1).map((k) =>
              `<option value="${k}" ${p.place === k ? "selected" : ""}>${ordinal(k)}</option>`).join("")}
          </select>
        </div>`).join("")}
    </section>
    <section class="card">
      <div class="row between">
        <label for="turns">Turns (rounds)</label>
        <input id="turns" type="number" inputmode="numeric" min="1" value="${g.turns ?? ""}" class="num">
      </div>
      <label for="win_con">How did they win?</label>
      <select id="win_con">${opts(state.meta.win_cons, g.win_con)}</select>
      <label for="win_details">Details</label>
      <select id="win_details">${opts(state.meta.win_details, g.win_details)}</select>
      <label for="notes">Notes</label>
      <textarea id="notes" rows="3" placeholder="Key plays, mistakes, what to try next time...">${esc(g.notes || "")}</textarea>
    </section>
    <div class="stack">
      <button class="btn primary big" data-action="save-game">Save game</button>
    </div>`;
}

function readEndForm() {
  const g = state.game;
  document.querySelectorAll("[data-place]").forEach((el) => { g.players[+el.dataset.place].place = +el.value; });
  const t = parseInt(document.getElementById("turns").value, 10);
  g.turns = Number.isFinite(t) && t > 0 ? t : null;
  g.win_con = document.getElementById("win_con").value || null;
  g.win_details = document.getElementById("win_details").value || null;
  g.notes = document.getElementById("notes").value.trim() || null;
  saveGame();
}

async function submitGame(btn) {
  readEndForm();
  const g = state.game;
  const winners = g.players.filter((p) => p.place === 1).length;
  if (winners !== 1) return toast("Pick exactly one 1st place.");

  const payload = {
    played_at: g.startedAt,
    turns: g.turns,
    win_con: g.win_con,
    win_details: g.win_details,
    notes: g.notes,
    participants: g.players.map((p) => ({
      player: p.player, deck: p.deck, commander: p.commander || null,
      seat: p.seat, finish_place: p.place, eliminated_turn: p.outRound,
    })),
    turn_events: g.events,
  };
  btn.disabled = true;
  try {
    await api("/games", { method: "POST", body: payload });
    clearGame();
    toast("Game saved.");
    go("stats");
  } catch (err) {
    btn.disabled = false;
    toast(err instanceof TypeError
      ? "Can't reach the server. Your game is still on this phone, so try again."
      : "Couldn't save: " + err.message);
  }
}

// ---------- stats ----------

function viewStats() {
  const tabs = [["players", "Players"], ["decks", "Decks"], ["seats", "Seats"], ["matchups", "Head-to-head"], ["wincons", "Win cons"]];
  return `
    ${topbar("Stats", "home")}
    <div id="summary" class="tiles"></div>
    <div class="tabs">
      ${tabs.map(([k, label]) => `<button class="${state.statsTab === k ? "on" : ""}" data-action="stats-tab" data-tab="${k}">${label}</button>`).join("")}
    </div>
    <div id="stats-body" class="card"><p class="muted">Loading...</p></div>`;
}

function table(cols, rows) {
  if (!rows.length) return `<p class="muted">No games yet. Play one!</p>`;
  return `<div class="table-wrap"><table>
    <thead><tr>${cols.map((c) => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${cols.map((c) => {
      const v = c.fmt ? c.fmt(r) : r[c.key];
      return `<td class="${c.num ? "num" : ""}">${c.raw ? v : esc(v ?? "–")}</td>`;
    }).join("")}</tr>`).join("")}</tbody>
  </table></div>`;
}

const pct = (key) => ({ label: "Win %", key, num: true, raw: true, fmt: (r) => bar(r[key]) });
function bar(v) {
  const n = v ?? 0;
  return `<span class="pct"><span class="pct-fill" style="width:${Math.min(100, n)}%"></span><span>${n.toFixed(1)}</span></span>`;
}

async function loadStats() {
  const body = document.getElementById("stats-body");
  try {
    const summary = await api("/stats/summary");
    document.getElementById("summary").innerHTML = `
      <div class="tile"><b>${summary.games}</b><span>games</span></div>
      <div class="tile"><b>${summary.avg_turns ?? "–"}</b><span>avg turns</span></div>`;

    let html;
    switch (state.statsTab) {
      case "players":
        html = table([
          { label: "Player", key: "player" }, { label: "G", key: "games", num: true },
          { label: "W", key: "wins", num: true }, pct("win_rate"),
          { label: "Avg place", key: "avg_finish", num: true }, { label: "Win turn", key: "avg_win_turn", num: true },
        ], await api("/stats/players"));
        break;
      case "decks":
        html = table([
          { label: "Deck", raw: true, fmt: (r) => `${esc(r.deck)}<div class="muted small">${esc(r.owner)}${r.commander ? " &middot; " + esc(r.commander) : ""}</div>` },
          { label: "G", key: "games", num: true }, { label: "W", key: "wins", num: true }, pct("win_rate"),
          { label: "Win turn", key: "avg_win_turn", num: true },
        ], await api("/stats/decks"));
        break;
      case "seats":
        html = `<p class="muted small">Does going first matter at your table?</p>` + table([
          { label: "Seat", fmt: (r) => ordinal(r.seat) }, { label: "G", key: "games", num: true },
          { label: "W", key: "wins", num: true }, pct("win_rate"),
        ], await api("/stats/seats"));
        break;
      case "matchups": {
        const decks = state.h2hMode === "decks";
        const deckCell = (deck, owner) => `${esc(deck)}<div class="muted small">${esc(owner)}</div>`;
        const pair = decks
          ? { label: "Pair", raw: true, fmt: (r) => `<div class="h2h-pair">${deckCell(r.deck_a, r.owner_a)}<span class="muted">vs</span>${deckCell(r.deck_b, r.owner_b)}</div>` }
          : { label: "Pair", raw: true, fmt: (r) => `${esc(r.player_a)} <span class="muted">vs</span> ${esc(r.player_b)}` };
        html = `
          <div class="seg h2h-switch">
            ${[["players", "Players"], ["decks", "Decks"]].map(([k, label]) =>
              `<button class="${state.h2hMode === k ? "on" : ""}" data-action="h2h-mode" data-mode="${k}">${label}</button>`).join("")}
          </div>
          <p class="muted small">"Ahead" = finished in a better place than the other ${decks ? "deck" : "player"}.</p>` + table([
          pair,
          { label: "G", key: "games", num: true },
          { label: "Wins", num: true, fmt: (r) => `${r.a_wins}–${r.b_wins}` },
          { label: "Ahead", num: true, fmt: (r) => `${r.a_ahead}–${r.b_ahead}` },
        ], await api(decks ? "/stats/deck-matchups" : "/stats/matchups"));
        break;
      }
      case "wincons":
        html = table([
          { label: "Win con", key: "win_con" }, { label: "Games", key: "games", num: true },
          { label: "Share", num: true, raw: true, fmt: (r) => bar(summary.games ? (100 * r.games) / summary.games : 0) },
        ], summary.win_cons);
        break;
    }
    body.innerHTML = html;
  } catch (err) {
    body.innerHTML = `<p class="danger">Couldn't load stats: ${esc(err.message)}</p>`;
  }
}

// ---------- history ----------

function viewHistory() {
  return `${topbar("Game history", "home")}<div id="history" class="stack"><p class="muted">Loading...</p></div>`;
}

async function loadHistory() {
  const el = document.getElementById("history");
  try {
    const games = await api("/games?limit=100");
    if (!games.length) { el.innerHTML = `<p class="muted">No games yet.</p>`; return; }
    el.innerHTML = games.map((g) => `
      <article class="card game">
        <div class="row between">
          <b>${esc(new Date(g.played_at).toLocaleDateString())}</b>
          <span class="muted small">${g.turns ? g.turns + " rounds" : ""}${g.win_con ? " &middot; " + esc(g.win_con) : ""}${g.win_details ? " / " + esc(g.win_details) : ""}</span>
        </div>
        <ol class="finish">
          ${g.participants.map((p) => `<li class="${p.finish_place === 1 ? "winner" : ""}">
            <span>${ordinal(p.finish_place)}</span> <b>${esc(p.player)}</b> <span class="muted">${esc(p.deck)} &middot; seat ${p.seat}</span></li>`).join("")}
        </ol>
        ${g.notes ? `<p class="notes">${esc(g.notes)}</p>` : ""}
        <button class="chip danger-outline" data-action="delete-game" data-id="${g.id}">Delete</button>
      </article>`).join("");
  } catch (err) {
    el.innerHTML = `<p class="danger">Couldn't load games: ${esc(err.message)}</p>`;
  }
}

// ---------- shared UI ----------

function topbar(title, back) {
  return `<nav class="topbar">
    <button class="btn icon ghost" data-action="go" data-view="${back}" aria-label="Back">&larr;</button>
    <h1>${title}</h1><span class="spacer"></span>
  </nav>`;
}

// ---------- events ----------

$app.addEventListener("click", async (e) => {
  const el = e.target.closest("[data-action]");
  if (!el) return;
  const d = el.dataset;
  const g = state.game;
  const i = d.p != null ? +d.p : null;

  switch (d.action) {
    case "go":
      if (state.view === "end" && d.view === "live") readEndForm();
      return go(d.view);
    case "resume": return go("live");
    case "new-game":
      if (g && !confirm("You have a game in progress. Discard it and start a new one?")) return;
      clearGame();
      state.setup = newSetup();
      refreshLists();
      return go("setup");
    case "count":
      state.setup.count = Math.min(8, Math.max(2, state.setup.count + +d.delta));
      return render();
    case "life0":
      state.setup.life = +d.life;
      return render();
    case "shuffle": {
      const rows = state.setup.rows.slice(0, state.setup.count);
      for (let k = rows.length - 1; k > 0; k--) {
        const j = Math.floor(Math.random() * (k + 1));
        [rows[k], rows[j]] = [rows[j], rows[k]];
      }
      state.setup.rows.splice(0, rows.length, ...rows);
      return render();
    }
    case "start": return startGame();
    case "life": g.players[i].life += +d.delta; break;
    case "cmd": {
      const p = g.players[i];
      const cur = p.cmd[d.from] || 0;
      const next = Math.max(0, cur + +d.delta);
      p.cmd[d.from] = next;
      p.life -= next - cur; // commander damage is also life loss
      break;
    }
    case "poison": g.players[i].poison = Math.max(0, g.players[i].poison + +d.delta); break;
    case "toggle-cmd": g.openCmd = g.openCmd === i ? null : i; break;
    case "set-active": if (!g.players[i].out) g.active = i; break;
    case "eliminate": toggleEliminated(i); break;
    case "round": g.round = Math.max(1, g.round + +d.delta); break;
    case "next-turn": nextTurn(); break;
    case "abandon":
      if (!confirm("Discard this game? It won't be saved.")) return;
      clearGame();
      return go("home");
    case "save-game": return submitGame(el);
    case "stats-tab":
      state.statsTab = d.tab;
      return render();
    case "h2h-mode":
      state.h2hMode = d.mode;
      return loadStats();
    case "delete-game":
      if (!confirm("Delete this game permanently?")) return;
      try { await api("/games/" + d.id, { method: "DELETE" }); toast("Game deleted."); loadHistory(); }
      catch (err) { toast("Couldn't delete: " + err.message); }
      return;
    default: return;
  }
  // Live-game actions fall through to here.
  // If the result screen was visited already, recompute its defaults from the new game state.
  if (d.action === "eliminate") g.players.forEach((p) => { p.place = null; });
  if (d.action === "round" || d.action === "next-turn") g.turns = null;
  saveGame();
  render();
});

$app.addEventListener("input", (e) => {
  const el = e.target;
  if (state.view !== "setup" || el.dataset.row == null) return;
  const row = state.setup.rows[+el.dataset.row];
  row[el.dataset.field] = el.value;

  if (el.dataset.field === "player") {
    // Refresh this seat's deck suggestions for the chosen player.
    const decks = state.decks.filter((d) => d.owner.toLowerCase() === el.value.trim().toLowerCase());
    document.getElementById("dl-decks-" + el.dataset.row).innerHTML =
      decks.map((d) => `<option value="${esc(d.name)}">`).join("");
  }
  if (el.dataset.field === "deck" && !row.commander) {
    const match = state.decks.find((d) =>
      d.owner.toLowerCase() === row.player.trim().toLowerCase() && d.name.toLowerCase() === el.value.trim().toLowerCase());
    if (match && match.commander) {
      row.commander = match.commander;
      el.parentElement.querySelector('[data-field="commander"]').value = match.commander;
    }
  }
});

async function refreshLists() {
  try {
    [state.players, state.decks] = await Promise.all([api("/players"), api("/decks")]);
    if (state.view === "setup") {
      document.getElementById("dl-players").innerHTML =
        state.players.map((p) => `<option value="${esc(p.name)}">`).join("");
    }
  } catch (_) { /* offline: autocomplete just stays empty */ }
}

// ---------- boot ----------

api("/meta").then((m) => { state.meta = m; }).catch(() => {});
render();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
