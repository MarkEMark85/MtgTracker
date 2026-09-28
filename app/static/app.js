"use strict";

// ---------- helpers ----------

const $app = document.getElementById("app");
const GAME_KEY = "mtg.currentGame";
const TABLE_KEY = "mtg.lastTable";   // who sat where last time, so New game can keep the names
const H2H_KEY = "mtg.h2hDecks";      // decks picked in Head-to-head -> Decks
const MAX_H2H_DECKS = 3;
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

function load(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch (_) { return null; }
}
function store(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* storage blocked */ }
}
function saveGame() { store(GAME_KEY, state.game); }
function clearGame() {
  state.game = null;
  try { localStorage.removeItem(GAME_KEY); } catch (_) { /* storage blocked */ }
}

const ordinal = (n) => n + (["th", "st", "nd", "rd"][(n % 100 - 20) % 10] || ["th", "st", "nd", "rd"][n % 100] || "th");

// Look up the display label for a win con / archetype code.
function labelOf(list, code) {
  if (!code) return "";
  if (code === "UNKNOWN") return "Not recorded";
  const hit = state.meta[list].find((x) => x.code === code);
  return hit ? hit.label : code;
}

// ---------- state & routing ----------

const state = {
  view: "home",
  game: loadCurrentGame(),
  setup: null,
  meta: { win_cons: [], archetypes: [] },
  players: [],
  decks: [],
  statsTab: "players",
  statsView: "results",  // Players/Decks tabs: "results" or "combat" columns
  h2hMode: "players",
  h2hDecks: load(H2H_KEY) || [],
  deckOpen: null,  // deck id expanded in the Decks stats tab
  editLife: null,  // player index whose life total is being typed in
};
let lastTap = {};  // for spotting a double-tap on a life total

function loadCurrentGame() {
  const g = load(GAME_KEY);
  if (g) { g.dmg = g.dmg || {}; g.turnDmg = g.turnDmg || {}; }  // games started before damage tracking
  return g;
}

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

const blankRow = (player = "") => ({ player, deck: "", commander: "", archetype: "" });

function newSetup() {
  // Keep who's playing (plus table size and life), but every game starts with blank decks.
  const prev = state.setup || load(TABLE_KEY);
  const names = prev ? (prev.names || prev.rows.map((r) => r.player)) : [];
  return {
    count: prev ? prev.count : 4,
    life: prev ? prev.life : 40,
    rows: Array.from({ length: 8 }, (_, i) => blankRow(names[i] || "")),
  };
}

function archetypeOptions(cur) {
  return `<option value="">Archetype (optional)</option>` + state.meta.archetypes.map((a) =>
    `<option value="${a.code}" ${a.code === cur ? "selected" : ""}>${esc(a.label)}</option>`).join("");
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
          <select data-row="${i}" data-field="archetype">${archetypeOptions(r.archetype)}</select>
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
    <div class="row between">
      <p class="muted small">Enter players in seat order. Seat 1 goes first.</p>
      <button class="chip" data-action="clear-names">Clear names</button>
    </div>
    <datalist id="dl-players">${state.players.map((p) => `<option value="${esc(p.name)}">`).join("")}</datalist>
    <div class="stack">${rows}</div>
    <div class="stack gap-top">
      <button class="btn" data-action="rotate">Rotate seats <span class="sub">Everyone moves down one seat; the last seat goes first</span></button>
      <button class="btn primary big" data-action="start">Start game</button>
    </div>`;
}

function startGame() {
  const s = state.setup;
  const rows = s.rows.slice(0, s.count).map((r) => ({
    player: r.player.trim(), deck: r.deck.trim(), commander: r.commander.trim(), archetype: r.archetype || "",
  }));
  if (rows.some((r) => !r.player || !r.deck)) return toast("Every seat needs a player and a deck.");
  const names = rows.map((r) => r.player.toLowerCase());
  if (new Set(names).size !== names.length) return toast("Each player can only sit once.");

  store(TABLE_KEY, { count: s.count, life: s.life, names: rows.map((r) => r.player) });
  state.game = {
    life0: s.life,
    round: 1,
    active: 0,
    outCount: 0,
    openCmd: null,
    startedAt: new Date().toISOString(),
    events: [],
    dmg: {},      // dmg[target][source] = life lost to that source (commander damage is in players[].cmd)
    turnDmg: {},  // damage dealt this turn, so a "+" tap can undo a mis-tap instead of counting as lifegain
    players: rows.map((r, i) => ({ ...r, seat: i + 1, life: s.life, cmd: {}, poison: 0, out: null, outRound: null, outBy: null })),
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
    const outBy = p.out ? `
      <div class="outby">
        <span class="muted small">Out by</span>
        ${g.players.map((o, j) => j === i ? "" :
          `<button class="chip sm ${p.outBy === j ? "on" : ""}" data-action="out-by" data-p="${i}" data-by="${j}">${esc(o.player)}</button>`).join("")}
        <button class="chip sm ${p.outBy == null ? "on" : ""}" data-action="out-by" data-p="${i}" data-by="">&mdash;</button>
      </div>` : "";

    return `
      <div class="${classes}" style="--seat:${SEAT_COLORS[i]}">
        <div class="pcard-head" data-action="set-active" data-p="${i}">
          <span class="pname">${esc(p.player)}</span>
          <span class="pdeck">${esc(p.deck)}</span>
        </div>
        <div class="life-row">
          ${state.editLife === i
            // While typing a new total the -/+ buttons are hidden so the box gets the whole row.
            ? `<input class="life life-input" type="number" inputmode="numeric" data-life-edit="${i}" value="${p.life}" aria-label="Life total">`
            : `<button class="life-btn" data-action="life" data-p="${i}" data-delta="-1" aria-label="Lose 1 life">&minus;</button>
               <div class="life" data-action="life-tap" data-p="${i}" title="Double-tap to edit">${p.life}</div>
               <button class="life-btn" data-action="life" data-p="${i}" data-delta="1" aria-label="Gain 1 life">+</button>`}
        </div>
        <div class="pcard-tools">
          <button class="chip" data-action="life" data-p="${i}" data-delta="-5">&minus;5</button>
          <button class="chip" data-action="halve" data-p="${i}" aria-label="Lose half your life, rounded up">&frac12;</button>
          <button class="chip ${g.openCmd === i ? "on" : ""}" data-action="toggle-cmd" data-p="${i}">Cmdr ${cmdTotal ? cmdTotal : ""}</button>
          <button class="chip" data-action="life" data-p="${i}" data-delta="5">+5</button>
        </div>
        ${cmdRows}
        <button class="chip wide ${p.out ? "on" : ""}" data-action="eliminate" data-p="${i}">
          ${p.out ? `Out on round ${p.outRound} &middot; undo` : "Eliminated"}
        </button>
        ${outBy}
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

// Life loss is credited to the player whose turn it is. Loss on your own turn (paying life,
// fetches, your own spells) is self-inflicted and not credited to anyone.
function changeLife(i, delta) {
  const g = state.game;
  const src = g.active;
  g.players[i].life += delta;
  if (src === i) return;
  const bySource = (g.dmg[i] = g.dmg[i] || {});
  if (delta < 0) {
    bySource[src] = (bySource[src] || 0) - delta;
    g.turnDmg[i] = (g.turnDmg[i] || 0) - delta;
  } else {
    // A "+" first takes back damage dealt this turn (a mis-tap); anything beyond that is lifegain.
    const undo = Math.min(delta, g.turnDmg[i] || 0);
    bySource[src] = (bySource[src] || 0) - undo;
    g.turnDmg[i] = (g.turnDmg[i] || 0) - undo;
  }
}

// Set a life total directly (typed in after a double-tap). Goes through changeLife so a drop
// is still credited as damage to the active player.
function commitLifeEdit(el) {
  const i = +el.dataset.lifeEdit;
  if (state.editLife !== i) return;  // already handled (Enter and blur both land here)
  state.editLife = null;
  const v = parseInt(el.value, 10);
  if (Number.isFinite(v) && v !== state.game.players[i].life) {
    changeLife(i, v - state.game.players[i].life);
    saveGame();
  }
  render();
}

function setActive(i) {
  state.game.active = i;
  state.game.turnDmg = {};
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
  setActive(i);
}

function toggleEliminated(i) {
  const g = state.game;
  const p = g.players[i];
  if (p.out) {
    p.out = null;
    p.outRound = null;
    p.outBy = null;
    g.events = g.events.filter((e) => !(e.player === p.player && e.event === "eliminated"));
  } else {
    g.outCount += 1;
    p.out = g.outCount;
    p.outRound = g.round;
    p.outBy = guessKiller(i);
    g.events.push({ round: g.round, player: p.player, event: "eliminated" });
    if (g.active === i) nextTurn();
  }
  if (aliveCount() === 1) toast("One player left. Tap End game to record the result.");
}

// Best guess at who knocked player i out: lethal commander damage, else whoever's turn it is.
function guessKiller(i) {
  const g = state.game;
  const p = g.players[i];
  const cmd = Object.keys(p.cmd).find((j) => p.cmd[j] >= 21);
  if (cmd != null) return +cmd;
  return g.active !== i ? g.active : null;
}

// Total damage dealt and taken per player (life loss + commander damage).
function damageRows() {
  const g = state.game;
  const rows = [];
  g.players.forEach((target, t) => {
    Object.entries(g.dmg[t] || {}).forEach(([s, amount]) => {
      if (amount > 0) rows.push({ source: g.players[+s].player, target: target.player, amount, commander: false });
    });
    Object.entries(target.cmd).forEach(([s, amount]) => {
      if (amount > 0) rows.push({ source: g.players[+s].player, target: target.player, amount, commander: true });
    });
  });
  return rows;
}

// ---------- end game ----------

function prefillPlaces() {
  // Last eliminated = best non-winning place. Anyone still alive gets the top places in seat order,
  // or all share 1st in a draw.
  const g = state.game;
  const n = g.players.length;
  const alive = g.players.filter((p) => !p.out);
  const out = g.players.filter((p) => p.out).sort((a, b) => b.out - a.out);
  [...alive, ...out].forEach((p, idx) => {
    if (p.place == null) p.place = g.is_draw && !p.out ? 1 : Math.min(idx + 1, n);
  });
  if (g.turns == null) g.turns = g.round;
}

function viewEnd() {
  const g = state.game;
  prefillPlaces();
  const n = g.players.length;
  const winCons = `<option value="">&mdash;</option>` + state.meta.win_cons.map((w) =>
    `<option value="${w.code}" ${w.code === g.win_con ? "selected" : ""}>${esc(w.label)}</option>`).join("");
  const dmg = damageRows();
  const dealt = (name) => dmg.filter((d) => d.source === name).reduce((sum, d) => sum + d.amount, 0);
  const taken = (name) => dmg.filter((d) => d.target === name).reduce((sum, d) => sum + d.amount, 0);

  return `
    ${topbar("Result", "live")}
    <section class="card">
      <div class="row between">
        <h2>Finish order</h2>
        <div class="seg">
          <button class="${g.is_draw ? "" : "on"}" data-action="draw" data-on="0">Win</button>
          <button class="${g.is_draw ? "on" : ""}" data-action="draw" data-on="1">Draw</button>
        </div>
      </div>
      ${g.is_draw ? `<p class="muted small">Players tied at the end all take 1st. No one gets a win.</p>` : ""}
      ${g.players.map((p, i) => `
        <div class="place-row" style="--seat:${SEAT_COLORS[i]}">
          <div class="row between">
            <div><b>${esc(p.player)}</b><div class="muted small">${esc(p.deck)}</div></div>
            <select data-place="${i}">
              ${Array.from({ length: n }, (_, k) => k + 1).map((k) =>
                `<option value="${k}" ${p.place === k ? "selected" : ""}>${ordinal(k)}</option>`).join("")}
            </select>
          </div>
          <div class="row between outby-row">
            <span class="muted small">Knocked out by</span>
            <select data-outby="${i}">
              <option value="">&mdash;</option>
              ${g.players.map((o, j) => j === i ? "" :
                `<option value="${j}" ${p.outBy === j ? "selected" : ""}>${esc(o.player)}</option>`).join("")}
            </select>
          </div>
        </div>`).join("")}
    </section>
    ${dmg.length ? `
    <section class="card">
      <h2>Damage</h2>
      <p class="muted small">Life lost is credited to whoever's turn it was, so this is an estimate.</p>
      ${g.players.map((p) => `<div class="row between dmg-row"><b>${esc(p.player)}</b>
        <span class="muted small">dealt <b>${dealt(p.player)}</b> &middot; took <b>${taken(p.player)}</b></span></div>`).join("")}
    </section>` : ""}
    <section class="card">
      <div class="row between">
        <label for="turns">Turns (rounds)</label>
        <input id="turns" type="number" inputmode="numeric" min="1" value="${g.turns ?? ""}" class="num">
      </div>
      <label for="win_con">${g.is_draw ? "How did it end?" : "How did they win?"}</label>
      <select id="win_con">${winCons}</select>
      <label for="winning_play">Winning play</label>
      <input id="winning_play" placeholder="e.g. Craterhoof, Thassa's Oracle" value="${esc(g.winning_play || "")}" autocomplete="off">
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
  document.querySelectorAll("[data-outby]").forEach((el) => {
    g.players[+el.dataset.outby].outBy = el.value === "" ? null : +el.value;
  });
  const t = parseInt(document.getElementById("turns").value, 10);
  g.turns = Number.isFinite(t) && t > 0 ? t : null;
  g.win_con = document.getElementById("win_con").value || null;
  g.winning_play = document.getElementById("winning_play").value.trim() || null;
  g.notes = document.getElementById("notes").value.trim() || null;
  saveGame();
}

async function submitGame(btn) {
  readEndForm();
  const g = state.game;
  const firsts = g.players.filter((p) => p.place === 1).length;
  if (g.is_draw && firsts < 2) return toast("A draw needs at least two players tied for 1st.");
  if (!g.is_draw && firsts !== 1) return toast("Pick exactly one 1st place.");

  const payload = {
    played_at: g.startedAt,
    turns: g.turns,
    win_con: g.win_con,
    winning_play: g.winning_play,
    notes: g.notes,
    is_draw: !!g.is_draw,
    participants: g.players.map((p) => ({
      player: p.player, deck: p.deck, commander: p.commander || null, archetype: p.archetype || null,
      seat: p.seat, finish_place: p.place, eliminated_turn: p.outRound,
      eliminated_by: p.place !== 1 && p.outBy != null ? g.players[p.outBy].player : null,
    })),
    turn_events: g.events,
    damage: damageRows(),
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
  const tabs = [["players", "Players"], ["decks", "Decks"], ["seats", "Seats"], ["matchups", "Head-to-head"],
    ["nemesis", "Nemesis"], ["wincons", "Win cons"]];
  return `
    ${topbar("Stats", "home")}
    <div id="summary" class="tiles"></div>
    <div class="tabs">
      ${tabs.map(([k, label]) => `<button class="${state.statsTab === k ? "on" : ""}" data-action="stats-tab" data-tab="${k}">${label}</button>`).join("")}
    </div>
    <div id="stats-body" class="card"><p class="muted">Loading...</p></div>`;
}

// cols: [{label, key | fmt, num, raw}]. opts.rowAttrs(r) adds attributes to a row; opts.after(r) adds html after it.
function table(cols, rows, opts = {}) {
  if (!rows.length) return `<p class="muted">No games yet. Play one!</p>`;
  return `<div class="table-wrap"><table>
    <thead><tr>${cols.map((c) => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr ${opts.rowAttrs ? opts.rowAttrs(r) : ""}>${cols.map((c) => {
      const v = c.fmt ? c.fmt(r) : r[c.key];
      return `<td class="${c.num ? "num" : ""}">${c.raw ? v : esc(v ?? "–")}</td>`;
    }).join("")}</tr>${opts.after ? opts.after(r) : ""}`).join("")}</tbody>
  </table></div>`;
}

const pct = (key) => ({ label: "Win %", key, num: true, raw: true, fmt: (r) => bar(r[key]) });
function bar(v) {
  const n = v ?? 0;
  return `<span class="pct"><span class="pct-fill" style="width:${Math.min(100, n)}%"></span><span>${n.toFixed(1)}</span></span>`;
}
// Win % minus the chance-level rate for the table sizes played (25% in a 4-player pod).
const vsPar = { label: "&plusmn;Par", num: true, raw: true, fmt: (r) =>
  `<span class="${r.vs_par > 0 ? "pos" : r.vs_par < 0 ? "neg" : "muted"}">${r.vs_par > 0 ? "+" : ""}${r.vs_par.toFixed(1)}</span>` };
const last10 = { label: "Last 10", num: true, fmt: (r) => `${r.last10.wins}/${r.last10.games}` };
const nameCount = (x) => x ? `${esc(x.name)} <span class="muted">&times;${x.count}</span>` : "–";
// Knockout and damage columns, shared by the Players and Decks tabs' Combat view.
const combatCols = [
  { label: "KOs", key: "kos", num: true },
  { label: "Out 1st", num: true, fmt: (r) => `${r.first_out} (${r.first_out_rate.toFixed(0)}%)` },
  { label: "Dealt", key: "avg_dmg", num: true },
  { label: "Taken", key: "avg_taken", num: true },
  { label: "Hits most", raw: true, fmt: (r) => nameCount(r.most_targeted) },
];

function viewSwitch() {
  return `<div class="seg h2h-switch">
    ${[["results", "Results"], ["combat", "Combat"]].map(([k, label]) =>
      `<button class="${state.statsView === k ? "on" : ""}" data-action="stats-view" data-mode="${k}">${label}</button>`).join("")}
  </div>
  ${state.statsView === "combat"
    ? `<p class="muted small">Dealt and Taken are per game, only count games where damage was tracked, and credit damage to whoever's turn it was.</p>`
    : parNote()}`;
}

async function loadStats() {
  const body = document.getElementById("stats-body");
  try {
    const summary = await api("/stats/summary");
    document.getElementById("summary").innerHTML = `
      <div class="tile"><b>${summary.games}</b><span>games${summary.draws ? ` &middot; ${summary.draws} drawn` : ""}</span></div>
      <div class="tile"><b>${summary.avg_turns ?? "–"}</b><span>avg turns</span></div>`;

    let html;
    switch (state.statsTab) {
      case "players":
        html = viewSwitch() + table([
          { label: "Player", key: "player" }, { label: "G", key: "games", num: true },
          ...(state.statsView === "combat" ? combatCols : [
            { label: "W", key: "wins", num: true }, pct("win_rate"), vsPar, last10,
            { label: "Avg place", key: "avg_finish", num: true }, { label: "Win turn", key: "avg_win_turn", num: true },
          ]),
        ], await api("/stats/players"));
        break;
      case "decks":
        html = await decksTab();
        break;
      case "seats":
        html = `<p class="muted small">Does going first matter at your table?</p>` + table([
          { label: "Seat", fmt: (r) => ordinal(r.seat) }, { label: "G", key: "games", num: true },
          { label: "W", key: "wins", num: true }, pct("win_rate"), vsPar,
        ], await api("/stats/seats"));
        break;
      case "matchups":
        html = await matchupsTab();
        break;
      case "nemesis":
        html = `<p class="muted small">Who knocks each player out most often.</p>` + table([
          { label: "Player", key: "player" }, { label: "G", key: "games", num: true },
          { label: "Nemesis", raw: true, fmt: (r) => nameCount(r.nemesis) },
        ], await api("/stats/nemesis"));
        break;
      case "wincons":
        html = table([
          { label: "Win con", fmt: (r) => labelOf("win_cons", r.win_con) }, { label: "Games", key: "games", num: true },
          { label: "Share", num: true, raw: true, fmt: (r) => bar(summary.games ? (100 * r.games) / summary.games : 0) },
        ], summary.win_cons);
        break;
    }
    body.innerHTML = html;
  } catch (err) {
    body.innerHTML = `<p class="danger">Couldn't load stats: ${esc(err.message)}</p>`;
  }
}

function parNote() {
  return `<p class="muted small">&plusmn;Par compares win % to pure chance for the table sizes played (25% in a 4-player pod).</p>`;
}

async function decksTab() {
  const [rows, detail] = await Promise.all([
    api("/stats/decks"),
    state.deckOpen != null ? api("/stats/decks/" + state.deckOpen).catch(() => null) : null,
  ]);
  const cols = [
    { label: "Deck", raw: true, fmt: (r) => `${esc(r.deck)}<div class="muted small">${esc(r.owner)}${
      r.archetype ? " &middot; " + esc(labelOf("archetypes", r.archetype)) : ""}</div>` },
    { label: "G", key: "games", num: true },
    ...(state.statsView === "combat" ? combatCols : [
      { label: "W", key: "wins", num: true }, pct("win_rate"), vsPar, last10,
      { label: "Win turn", key: "avg_win_turn", num: true },
    ]),
  ];
  return viewSwitch() + `<p class="muted small">Tap a deck for how it wins, its seats and recent results.</p>` + table(cols, rows, {
    rowAttrs: (r) => `class="clickable ${r.id === state.deckOpen ? "open" : ""}" data-action="deck-detail" data-id="${r.id}"`,
    after: (r) => r.id === state.deckOpen && detail ? `<tr class="detail"><td colspan="${cols.length}">${deckDetail(detail)}</td></tr>` : "",
  });
}

function deckDetail(d) {
  const wins = d.win_cons.length
    ? d.win_cons.map((w) => `<span class="tag">${esc(labelOf("win_cons", w.win_con))} <b>${w.games}</b></span>`).join("")
    : `<span class="muted small">No wins yet.</span>`;
  const seats = d.seats.map((s) => `<span class="tag">${ordinal(s.seat)} seat <b>${s.wins}/${s.games}</b></span>`).join("");
  const recent = d.recent.map((r) =>
    `<span class="result ${r.result}" title="${ordinal(r.finish_place)} of ${r.players}">${r.result}</span>`).join("");
  return `
    <div class="detail-block"><div class="muted small">How it wins</div>${wins}</div>
    <div class="detail-block"><div class="muted small">By seat (wins/games)</div>${seats}</div>
    <div class="detail-block"><div class="muted small">Last ${d.recent.length}, newest first</div>${recent}</div>`;
}

async function matchupsTab() {
  const decks = state.h2hMode === "decks";
  const head = `
    <div class="seg h2h-switch">
      ${[["players", "Players"], ["decks", "Decks"]].map(([k, label]) =>
        `<button class="${state.h2hMode === k ? "on" : ""}" data-action="h2h-mode" data-mode="${k}">${label}</button>`).join("")}
    </div>
    <p class="muted small">"Ahead" = finished in a better place than the other ${decks ? "deck" : "player"}.</p>`;
  const wins = { label: "Wins", num: true, fmt: (r) => `${r.a_wins}–${r.b_wins}` };
  const ahead = { label: "Ahead", num: true, fmt: (r) => `${r.a_ahead}–${r.b_ahead}` };
  const games = { label: "G", key: "games", num: true };

  if (!decks) {
    return head + table([
      { label: "Pair", raw: true, fmt: (r) => `${esc(r.player_a)} <span class="muted">vs</span> ${esc(r.player_b)}` },
      games, wins, ahead,
    ], await api("/stats/matchups"));
  }

  if (!state.decks.length) await refreshLists();
  const chosen = state.h2hDecks.map((id) => state.decks.find((d) => d.id === id)).filter(Boolean);
  const available = state.decks.filter((d) => !state.h2hDecks.includes(d.id));
  const picker = `
    <select data-h2h-add ${chosen.length >= MAX_H2H_DECKS ? "disabled" : ""}>
      <option value="">${chosen.length >= MAX_H2H_DECKS ? `Up to ${MAX_H2H_DECKS} decks` : "Add a deck…"}</option>
      ${available.map((d) => `<option value="${d.id}">${esc(d.name)} — ${esc(d.owner)}</option>`).join("")}
    </select>
    <div class="chips">${chosen.map((d) =>
      `<button class="chip sm" data-action="h2h-remove" data-id="${d.id}">${esc(d.name)} &times;</button>`).join("")}</div>`;
  if (!chosen.length) return head + picker + `<p class="muted">Pick up to ${MAX_H2H_DECKS} decks to see how each has done against every deck it has faced.</p>`;

  const rows = await api("/stats/deck-matchups?" + chosen.map((d) => "deck=" + d.id).join("&"));
  return head + picker + chosen.map((d) => `
    <h3 class="h2h-heading">${esc(d.name)} <span class="muted small">${esc(d.owner)}</span></h3>
    ${table([
      { label: "Opponent", raw: true, fmt: (r) => `${esc(r.deck_b)}<div class="muted small">${esc(r.owner_b)}</div>` },
      games, wins, ahead,
    ], rows.filter((r) => r.deck_a_id === d.id))}`).join("");
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
          <b>${esc(new Date(g.played_at).toLocaleDateString())}${g.is_draw ? ` <span class="tag">Draw</span>` : ""}</b>
          <span class="muted small">${g.turns ? g.turns + " rounds" : ""}${g.win_con ? " &middot; " + esc(labelOf("win_cons", g.win_con)) : ""}</span>
        </div>
        ${g.winning_play ? `<div class="small">Winning play: <b>${esc(g.winning_play)}</b></div>` : ""}
        <ol class="finish">
          ${g.participants.map((p) => `<li class="${p.finish_place === 1 && !g.is_draw ? "winner" : ""}">
            <span>${ordinal(p.finish_place)}</span> <b>${esc(p.player)}</b> <span class="muted">${esc(p.deck)} &middot; seat ${p.seat}${
              p.eliminated_by ? " &middot; out by " + esc(p.eliminated_by) : ""}</span></li>`).join("")}
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
    case "rotate": {
      // Seat 1 -> 2, 2 -> 3, ..., last -> 1. Each player's deck moves with them.
      const rows = state.setup.rows.slice(0, state.setup.count);
      rows.unshift(rows.pop());
      state.setup.rows.splice(0, rows.length, ...rows);
      return render();
    }
    case "clear-names":
      state.setup.rows = state.setup.rows.map(() => blankRow());
      return render();
    case "start": return startGame();
    case "life": changeLife(i, +d.delta); break;
    case "halve": {
      // Lose half your life, rounded up (e.g. 19 -> lose 10, leaving 9). Nothing to halve at 0 or below.
      const life = g.players[i].life;
      if (life <= 0) return;
      changeLife(i, -Math.ceil(life / 2));
      break;
    }
    case "life-tap": {
      const now = Date.now();
      const double = lastTap.p === i && now - lastTap.t < 400;
      lastTap = double ? {} : { p: i, t: now };
      if (!double) return;
      state.editLife = i;
      render();
      const input = document.querySelector(`[data-life-edit="${i}"]`);
      input.focus();
      input.select();
      return;
    }
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
    case "set-active": if (!g.players[i].out && g.active !== i) setActive(i); break;
    case "eliminate": toggleEliminated(i); break;
    case "out-by": g.players[i].outBy = d.by === "" ? null : +d.by; break;
    case "round": g.round = Math.max(1, g.round + +d.delta); break;
    case "next-turn": nextTurn(); break;
    case "abandon":
      if (!confirm("Discard this game? It won't be saved.")) return;
      clearGame();
      return go("home");
    case "draw":
      readEndForm();
      g.is_draw = d.on === "1";
      g.players.forEach((p) => { p.place = null; });
      saveGame();
      return render();
    case "save-game": return submitGame(el);
    case "stats-tab":
      state.statsTab = d.tab;
      return render();
    case "stats-view":
      state.statsView = d.mode;
      return loadStats();
    case "h2h-mode":
      state.h2hMode = d.mode;
      return loadStats();
    case "h2h-remove":
      state.h2hDecks = state.h2hDecks.filter((id) => id !== +d.id);
      store(H2H_KEY, state.h2hDecks);
      return loadStats();
    case "deck-detail":
      state.deckOpen = state.deckOpen === +d.id ? null : +d.id;
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

// Editing a life total: Enter or tapping away saves, Escape cancels.
$app.addEventListener("keydown", (e) => {
  if (!e.target.matches("[data-life-edit]")) return;
  if (e.key === "Enter") commitLifeEdit(e.target);
  if (e.key === "Escape") { state.editLife = null; render(); }
});
$app.addEventListener("focusout", (e) => {
  if (e.target.matches("[data-life-edit]")) commitLifeEdit(e.target);
});

$app.addEventListener("change", (e) => {
  const el = e.target;
  if (el.matches("[data-h2h-add]") && el.value) {
    state.h2hDecks = [...state.h2hDecks, +el.value].slice(0, MAX_H2H_DECKS);
    store(H2H_KEY, state.h2hDecks);
    loadStats();
  }
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
  if (el.dataset.field === "deck") {
    // Picking a saved deck fills in its commander and archetype.
    const match = state.decks.find((d) =>
      d.owner.toLowerCase() === row.player.trim().toLowerCase() && d.name.toLowerCase() === el.value.trim().toLowerCase());
    const fields = el.parentElement;
    if (match && match.commander && !row.commander) {
      row.commander = match.commander;
      fields.querySelector('[data-field="commander"]').value = match.commander;
    }
    if (match && match.archetype && !row.archetype) {
      row.archetype = match.archetype;
      fields.querySelector('[data-field="archetype"]').value = match.archetype;
    }
  }
});

async function refreshLists() {
  try {
    [state.players, state.decks] = await Promise.all([api("/players"), api("/decks")]);
    if (state.view === "setup") {
      document.getElementById("dl-players").innerHTML =
        state.players.map((p) => `<option value="${esc(p.name)}">`).join("");
      // Seats that already have a name (kept from last game) need their deck suggestions too.
      state.setup.rows.slice(0, state.setup.count).forEach((r, i) => {
        const decks = state.decks.filter((d) => d.owner.toLowerCase() === r.player.trim().toLowerCase());
        const list = document.getElementById("dl-decks-" + i);
        if (list) list.innerHTML = decks.map((d) => `<option value="${esc(d.name)}">`).join("");
      });
    }
  } catch (_) { /* offline: autocomplete just stays empty */ }
}

// ---------- boot ----------

api("/meta").then((m) => { state.meta = m; if (state.view === "setup") render(); }).catch(() => {});
render();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
