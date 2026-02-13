const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { URL } = require('node:url');
const { DatabaseSync } = require('node:sqlite');

const PORT = Number(process.env.PORT || 8787);
const ROOT = path.resolve(__dirname, '..');
const PUBLIC_DIR = path.join(__dirname, 'public');
const OUT_DIR = path.join(ROOT, 'history_out');

const SNAPSHOT_FILE = path.join(OUT_DIR, 'ui_current_day.json');
const SYMBOL_CACHE_FILE = path.join(OUT_DIR, 'symbols_cache.json');
const DB_FILE = path.join(OUT_DIR, 'first_closes.db');
const TICKS_FILE = path.join(OUT_DIR, 'ticks.csv');
const PAPER_DB_FILE = path.join(OUT_DIR, 'paper_trades.db');

const FACTORS = {
  micro: 0.002611,
  mini: 0.0261,
  mega: 0.2611,
};

const TF_CLOSE_FIELD = {
  '1m': 'first_1m_close',
  '5m': 'first_5m_close',
  '15m': 'first_15m_close',
};

const PAPER_TF = ['1m', '5m', '15m'].includes(process.env.PAPER_TF) ? process.env.PAPER_TF : '5m';
const PAPER_FACTOR = ['micro', 'mini', 'mega'].includes(process.env.PAPER_FACTOR) ? process.env.PAPER_FACTOR : 'micro';
const PAPER_COOLDOWN_SEC = Number(process.env.PAPER_COOLDOWN_SEC || 30);

let snapshotCache = { mtimeMs: -1, data: { day: '-', updated_at: '-', row_count: 0, rows: [] } };
let symbolCache = { mtimeMs: -1, count: 0 };
let dbRead = null;
let paperDb = null;

const derivedCache = {
  snapshotMtimeMs: -1,
  byConfig: new Map(),
};

const paperState = {
  openTrades: new Map(),
  cooldownUntil: new Map(),
  lastSnapshotMtime: -1,
  peakEquity: 0,
  maxDrawdown: 0,
};

function json(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(body));
}

function toNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function normalize(s) {
  return String(s || '').toUpperCase();
}

function isoNow() {
  return new Date().toISOString();
}

function cfgKey(timeframe, factorName) {
  return `${timeframe}|${factorName}`;
}

function getDbRead() {
  if (dbRead) return dbRead;
  if (!fs.existsSync(DB_FILE)) return null;
  try {
    dbRead = new DatabaseSync(DB_FILE, { open: true, readOnly: true });
    dbRead.exec('PRAGMA busy_timeout=2000');
    return dbRead;
  } catch {
    dbRead = null;
    return null;
  }
}

function getPaperDb() {
  if (paperDb) return paperDb;
  paperDb = new DatabaseSync(PAPER_DB_FILE, { open: true, readOnly: false });
  paperDb.exec('PRAGMA journal_mode=WAL');
  paperDb.exec('PRAGMA synchronous=NORMAL');
  paperDb.exec(`
    CREATE TABLE IF NOT EXISTS paper_trades (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT NOT NULL,
      tsym TEXT,
      day TEXT NOT NULL,
      timeframe TEXT NOT NULL,
      factor TEXT NOT NULL,
      close_price REAL,
      points REAL,
      bu1 REAL,
      bu2 REAL,
      bu3 REAL,
      bu4 REAL,
      bu5 REAL,
      entry_ltp REAL NOT NULL,
      entry_ts TEXT NOT NULL,
      exit_ltp REAL,
      exit_ts TEXT,
      status TEXT NOT NULL,
      reason TEXT,
      last_ltp REAL,
      max_ltp REAL,
      min_ltp REAL,
      runup REAL,
      drawdown REAL,
      pnl REAL,
      pnl_pct REAL,
      updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_paper_status ON paper_trades(status);
    CREATE INDEX IF NOT EXISTS idx_paper_symbol ON paper_trades(symbol);
  `);
  return paperDb;
}

function loadSnapshot() {
  try {
    const st = fs.statSync(SNAPSHOT_FILE);
    if (st.mtimeMs !== snapshotCache.mtimeMs) {
      const txt = fs.readFileSync(SNAPSHOT_FILE, 'utf8');
      const data = JSON.parse(txt);
      snapshotCache = { mtimeMs: st.mtimeMs, data };
    }
  } catch {
    snapshotCache = { mtimeMs: -1, data: { day: '-', updated_at: '-', row_count: 0, rows: [] } };
  }
  return snapshotCache.data;
}

function loadSymbolCount() {
  try {
    const st = fs.statSync(SYMBOL_CACHE_FILE);
    if (st.mtimeMs !== symbolCache.mtimeMs) {
      const txt = fs.readFileSync(SYMBOL_CACHE_FILE, 'utf8');
      const data = JSON.parse(txt);
      symbolCache = {
        mtimeMs: st.mtimeMs,
        count: Object.keys(data.symbols || {}).length,
      };
    }
  } catch {
    symbolCache = { mtimeMs: -1, count: 0 };
  }
  return symbolCache.count;
}

function loadDbStats(day) {
  const out = {
    today_rows: 0,
    today_complete: 0,
    history_rows: 0,
    history_pending_symbols: 0,
  };

  if (!day || day === '-') return out;
  const db = getDbRead();
  if (!db) return out;

  try {
    out.today_rows = Number(db.prepare('SELECT COUNT(1) AS c FROM first_closes WHERE day = ?').get(day)?.c || 0);

    out.today_complete = Number(
      db
        .prepare(
          `SELECT COUNT(1) AS c
           FROM first_closes
           WHERE day = ?
             AND first_1m_close IS NOT NULL
             AND first_5m_close IS NOT NULL
             AND first_15m_close IS NOT NULL`
        )
        .get(day)?.c || 0
    );

    out.history_rows = Number(db.prepare('SELECT COUNT(1) AS c FROM first_closes WHERE day <> ?').get(day)?.c || 0);
    out.history_pending_symbols = Number(db.prepare('SELECT COUNT(1) AS c FROM history_state WHERE done = 0').get()?.c || 0);
  } catch {
    return out;
  }

  return out;
}

function ticksMeta() {
  try {
    const st = fs.statSync(TICKS_FILE);
    return {
      ticks_file_mb: Number((st.size / (1024 * 1024)).toFixed(1)),
      last_tick_write: new Date(st.mtimeMs).toISOString(),
    };
  } catch {
    return { ticks_file_mb: 0, last_tick_write: '-' };
  }
}

function recomputeDerivedForConfig(baseRows, timeframe, factorName) {
  const closeField = TF_CLOSE_FIELD[timeframe];
  const factorVal = FACTORS[factorName];

  const allRows = [];
  const triggerRows = [];

  for (const row of baseRows) {
    const ltp = toNum(row.ltp);
    const close = toNum(row[closeField]);
    if (ltp === null || close === null) continue;

    const points = close * factorVal;
    const bu1 = close + points;
    const bu2 = close + points * 2;
    const bu3 = close + points * 3;
    const bu4 = close + points * 4;
    const bu5 = close + points * 5;

    const levels = [bu1, bu2, bu3, bu4, bu5];
    let nearIdx = 0;
    let nearDiff = Math.abs(ltp - levels[0]);
    for (let i = 1; i < levels.length; i += 1) {
      const d = Math.abs(ltp - levels[i]);
      if (d < nearDiff) {
        nearDiff = d;
        nearIdx = i;
      }
    }
    const nearValue = levels[nearIdx];
    const nearPct = nearValue ? ((ltp - nearValue) / nearValue) * 100 : 0;

    const inRange = ltp >= bu1 && ltp <= bu5;
    const enriched = {
      ...row,
      close,
      points,
      bu1,
      bu2,
      bu3,
      bu4,
      bu5,
      near_level: nearIdx + 1,
      near_value: nearValue,
      near_diff: ltp - nearValue,
      near_pct: nearPct,
      in_range: inRange,
      above_bu1: ltp >= bu1,
      above_bu5: ltp > bu5,
    };

    allRows.push(enriched);
    if (inRange) triggerRows.push(enriched);
  }

  const cmp = (a, b) => {
    const sa = String(a.symbol || '');
    const sb = String(b.symbol || '');
    if (sa < sb) return -1;
    if (sa > sb) return 1;
    const ta = String(a.tsym || '');
    const tb = String(b.tsym || '');
    if (ta < tb) return -1;
    if (ta > tb) return 1;
    return 0;
  };

  allRows.sort(cmp);
  triggerRows.sort(cmp);

  return { allRows, triggerRows };
}

function ensureDerivedCache(snapshotMtimeMs, baseRows) {
  if (derivedCache.snapshotMtimeMs === snapshotMtimeMs) return;

  derivedCache.snapshotMtimeMs = snapshotMtimeMs;
  derivedCache.byConfig.clear();

  const tfs = ['1m', '5m', '15m'];
  const factors = ['micro', 'mini', 'mega'];

  for (const tf of tfs) {
    for (const f of factors) {
      derivedCache.byConfig.set(cfgKey(tf, f), recomputeDerivedForConfig(baseRows, tf, f));
    }
  }
}

function filterRows(rows, q, completeOnly, limit) {
  const query = normalize(q || '');
  const out = [];
  let scanned = 0;

  for (const r of rows) {
    scanned += 1;
    if (completeOnly && !r.fetch_done) continue;
    if (query) {
      const hit = normalize(r.symbol).includes(query) || normalize(r.tsym).includes(query);
      if (!hit) continue;
    }
    out.push(r);
    if (out.length >= limit) break;
  }

  return { rows: out, scanned };
}

function dashboardData(urlObj) {
  const snapshot = loadSnapshot();
  const totalSymbols = loadSymbolCount();

  const q = urlObj.searchParams.get('q') || '';
  const completeOnly = urlObj.searchParams.get('complete') === '1';
  const triggerOnly = urlObj.searchParams.get('trigger_only') !== '0';

  const timeframe = ['1m', '5m', '15m'].includes(urlObj.searchParams.get('tf'))
    ? urlObj.searchParams.get('tf')
    : '5m';
  const factorName = ['micro', 'mini', 'mega'].includes(urlObj.searchParams.get('factor'))
    ? urlObj.searchParams.get('factor')
    : 'micro';

  const limit = Math.max(1, Math.min(50000, Number(urlObj.searchParams.get('limit') || 5000)));

  const baseRows = Array.isArray(snapshot.rows) ? snapshot.rows : [];
  ensureDerivedCache(snapshotCache.mtimeMs, baseRows);

  const cacheItem = derivedCache.byConfig.get(cfgKey(timeframe, factorName)) || { allRows: [], triggerRows: [] };
  const sourceRows = triggerOnly ? cacheItem.triggerRows : cacheItem.allRows;

  const filtered = filterRows(sourceRows, q, completeOnly, limit);

  const dbStats = loadDbStats(snapshot.day);
  const tmeta = ticksMeta();

  return {
    snapshot_day: snapshot.day || '-',
    snapshot_updated_at: snapshot.updated_at || '-',
    snapshot_rows: Number(snapshot.row_count || baseRows.length || 0),
    displayed_rows: filtered.rows.length,
    scan_rows: filtered.scanned,
    trigger_in_range_seen: cacheItem.triggerRows.length,
    config: {
      timeframe,
      factor: factorName,
      factor_value: FACTORS[factorName],
      trigger_only: triggerOnly,
    },
    stats: {
      total_symbols: totalSymbols,
      today_rows: dbStats.today_rows,
      today_complete: dbStats.today_complete,
      today_pending: Math.max(0, totalSymbols - dbStats.today_complete),
      history_rows: dbStats.history_rows,
      history_pending_symbols: dbStats.history_pending_symbols,
      ticks_file_mb: tmeta.ticks_file_mb,
      last_tick_write: tmeta.last_tick_write,
    },
    rows: filtered.rows,
  };
}

function loadOpenTrades() {
  const db = getPaperDb();
  const cur = db.prepare('SELECT * FROM paper_trades WHERE status = ?').all('OPEN');
  for (const r of cur) paperState.openTrades.set(r.symbol, r);
}

function openTradeFromRow(row, day) {
  const db = getPaperDb();
  const now = isoNow();
  const stmt = db.prepare(`
    INSERT INTO paper_trades(
      symbol, tsym, day, timeframe, factor,
      close_price, points, bu1, bu2, bu3, bu4, bu5,
      entry_ltp, entry_ts, status, reason,
      last_ltp, max_ltp, min_ltp, runup, drawdown,
      pnl, pnl_pct, updated_at
    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  stmt.run(
    row.symbol,
    row.tsym || '',
    day,
    PAPER_TF,
    PAPER_FACTOR,
    row.close,
    row.points,
    row.bu1,
    row.bu2,
    row.bu3,
    row.bu4,
    row.bu5,
    row.ltp,
    now,
    'OPEN',
    '',
    row.ltp,
    row.ltp,
    row.ltp,
    0,
    0,
    0,
    0,
    now
  );

  const id = db.prepare('SELECT last_insert_rowid() AS id').get().id;
  const t = {
    id,
    symbol: row.symbol,
    tsym: row.tsym || '',
    day,
    timeframe: PAPER_TF,
    factor: PAPER_FACTOR,
    close_price: row.close,
    points: row.points,
    bu1: row.bu1,
    bu2: row.bu2,
    bu3: row.bu3,
    bu4: row.bu4,
    bu5: row.bu5,
    entry_ltp: row.ltp,
    entry_ts: now,
    exit_ltp: null,
    exit_ts: null,
    status: 'OPEN',
    reason: '',
    last_ltp: row.ltp,
    max_ltp: row.ltp,
    min_ltp: row.ltp,
    runup: 0,
    drawdown: 0,
    pnl: 0,
    pnl_pct: 0,
    updated_at: now,
  };
  paperState.openTrades.set(row.symbol, t);
}

function closeTrade(trade, ltp, reason) {
  const db = getPaperDb();
  const now = isoNow();
  const pnl = ltp - Number(trade.entry_ltp);
  const pnlPct = trade.entry_ltp ? (pnl / Number(trade.entry_ltp)) * 100 : 0;

  db.prepare(`
    UPDATE paper_trades
    SET exit_ltp=?, exit_ts=?, status='CLOSED', reason=?,
        last_ltp=?, max_ltp=?, min_ltp=?, runup=?, drawdown=?, pnl=?, pnl_pct=?, updated_at=?
    WHERE id=?
  `).run(
    ltp,
    now,
    reason,
    ltp,
    trade.max_ltp,
    trade.min_ltp,
    trade.runup,
    trade.drawdown,
    pnl,
    pnlPct,
    now,
    trade.id
  );

  paperState.openTrades.delete(trade.symbol);
  paperState.cooldownUntil.set(trade.symbol, Date.now() + PAPER_COOLDOWN_SEC * 1000);
}

function updateOpenTrade(trade, ltp) {
  trade.last_ltp = ltp;
  trade.max_ltp = Math.max(Number(trade.max_ltp), ltp);
  trade.min_ltp = Math.min(Number(trade.min_ltp), ltp);
  trade.runup = Math.max(Number(trade.runup), ltp - Number(trade.entry_ltp));
  trade.drawdown = Math.max(Number(trade.drawdown), Number(trade.entry_ltp) - ltp);
  trade.pnl = ltp - Number(trade.entry_ltp);
  trade.pnl_pct = trade.entry_ltp ? (trade.pnl / Number(trade.entry_ltp)) * 100 : 0;
  trade.updated_at = isoNow();

  const db = getPaperDb();
  db.prepare(`
    UPDATE paper_trades
    SET last_ltp=?, max_ltp=?, min_ltp=?, runup=?, drawdown=?, pnl=?, pnl_pct=?, updated_at=?
    WHERE id=?
  `).run(trade.last_ltp, trade.max_ltp, trade.min_ltp, trade.runup, trade.drawdown, trade.pnl, trade.pnl_pct, trade.updated_at, trade.id);
}

function runPaperCycle() {
  const snapshot = loadSnapshot();
  const baseRows = Array.isArray(snapshot.rows) ? snapshot.rows : [];
  if (!baseRows.length) return;

  ensureDerivedCache(snapshotCache.mtimeMs, baseRows);
  const item = derivedCache.byConfig.get(cfgKey(PAPER_TF, PAPER_FACTOR));
  if (!item) return;

  if (paperState.lastSnapshotMtime === snapshotCache.mtimeMs) return;
  paperState.lastSnapshotMtime = snapshotCache.mtimeMs;

  const rowMap = new Map();
  for (const r of item.allRows) rowMap.set(r.symbol, r);

  // Update open trades first.
  for (const t of Array.from(paperState.openTrades.values())) {
    const row = rowMap.get(t.symbol);
    if (!row) continue;
    const ltp = toNum(row.ltp);
    if (ltp === null) continue;

    updateOpenTrade(t, ltp);

    if (ltp >= Number(t.bu5)) {
      closeTrade(t, ltp, 'target_bu5');
    } else if (ltp < Number(t.bu1)) {
      closeTrade(t, ltp, 'sl_below_bu1');
    }
  }

  // New entries from in-range opportunities.
  const day = snapshot.day || '-';
  for (const r of item.triggerRows) {
    if (!r.fetch_done) continue;
    if (paperState.openTrades.has(r.symbol)) continue;
    const cool = paperState.cooldownUntil.get(r.symbol) || 0;
    if (Date.now() < cool) continue;
    if (toNum(r.ltp) === null) continue;

    openTradeFromRow(r, day);
  }
}

function paperSummary() {
  const db = getPaperDb();
  if (!db) {
    return {
      total_trades: 0,
      closed_trades: 0,
      open_trades: 0,
      wins: 0,
      losses: 0,
      win_rate: 0,
      realized_pnl: 0,
      open_pnl: 0,
      gross_pnl: 0,
      peak_equity: paperState.peakEquity,
      drawdown_now: 0,
      max_drawdown: paperState.maxDrawdown,
    };
  }

  const agg = db.prepare(`
    SELECT
      COUNT(1) AS total,
      SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END) AS closed,
      SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS open,
      SUM(CASE WHEN status='CLOSED' AND pnl > 0 THEN 1 ELSE 0 END) AS wins,
      SUM(CASE WHEN status='CLOSED' AND pnl <= 0 THEN 1 ELSE 0 END) AS losses,
      SUM(CASE WHEN status='CLOSED' THEN pnl ELSE 0 END) AS realized,
      SUM(CASE WHEN status='OPEN' THEN pnl ELSE 0 END) AS open_pnl
    FROM paper_trades
  `).get();

  const closed = Number(agg?.closed || 0);
  const wins = Number(agg?.wins || 0);
  const losses = Number(agg?.losses || 0);
  const realized = Number(agg?.realized || 0);
  const openPnl = Number(agg?.open_pnl || 0);
  const gross = realized + openPnl;

  if (gross > paperState.peakEquity) paperState.peakEquity = gross;
  const dd = paperState.peakEquity - gross;
  if (dd > paperState.maxDrawdown) paperState.maxDrawdown = dd;

  return {
    total_trades: Number(agg?.total || 0),
    closed_trades: closed,
    open_trades: Number(agg?.open || 0),
    wins,
    losses,
    win_rate: closed ? (wins / closed) * 100 : 0,
    realized_pnl: realized,
    open_pnl: openPnl,
    gross_pnl: gross,
    peak_equity: paperState.peakEquity,
    drawdown_now: dd,
    max_drawdown: paperState.maxDrawdown,
    strategy_tf: PAPER_TF,
    strategy_factor: PAPER_FACTOR,
  };
}

function tradesData(urlObj) {
  const limitOpen = Math.max(1, Math.min(5000, Number(urlObj.searchParams.get('open_limit') || 500)));
  const limitClosed = Math.max(1, Math.min(10000, Number(urlObj.searchParams.get('closed_limit') || 1000)));
  const q = normalize(urlObj.searchParams.get('q') || '');

  const db = getPaperDb();
  if (!db) return { summary: paperSummary(), open_trades: [], recent_closed: [] };

  let open = db.prepare('SELECT * FROM paper_trades WHERE status=? ORDER BY updated_at DESC LIMIT ?').all('OPEN', limitOpen);
  let closed = db.prepare('SELECT * FROM paper_trades WHERE status=? ORDER BY exit_ts DESC LIMIT ?').all('CLOSED', limitClosed);

  if (q) {
    open = open.filter((r) => normalize(r.symbol).includes(q) || normalize(r.tsym).includes(q));
    closed = closed.filter((r) => normalize(r.symbol).includes(q) || normalize(r.tsym).includes(q));
  }

  return {
    summary: paperSummary(),
    open_trades: open,
    recent_closed: closed,
    as_of: isoNow(),
  };
}

function contentType(file) {
  const ext = path.extname(file).toLowerCase();
  if (ext === '.html') return 'text/html; charset=utf-8';
  if (ext === '.js') return 'text/javascript; charset=utf-8';
  if (ext === '.css') return 'text/css; charset=utf-8';
  if (ext === '.json') return 'application/json; charset=utf-8';
  return 'text/plain; charset=utf-8';
}

function serveStatic(reqPath, res) {
  const clean = reqPath === '/' ? '/index.html' : reqPath;
  const file = path.join(PUBLIC_DIR, clean);
  if (!file.startsWith(PUBLIC_DIR)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  fs.readFile(file, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }
    res.writeHead(200, { 'Content-Type': contentType(file) });
    res.end(data);
  });
}

function initPaperEngine() {
  getPaperDb();
  loadOpenTrades();
  setInterval(runPaperCycle, 1000);
}

const server = http.createServer((req, res) => {
  const u = new URL(req.url, `http://${req.headers.host}`);

  if (u.pathname === '/api/health') return json(res, 200, { ok: true });
  if (u.pathname === '/api/dashboard') {
    try {
      return json(res, 200, dashboardData(u));
    } catch (e) {
      return json(res, 500, { error: String(e) });
    }
  }
  if (u.pathname === '/api/trades') {
    try {
      return json(res, 200, tradesData(u));
    } catch (e) {
      return json(res, 500, { error: String(e) });
    }
  }

  serveStatic(u.pathname, res);
});

initPaperEngine();

server.listen(PORT, () => {
  console.log(`Node UI running: http://127.0.0.1:${PORT}`);
  console.log(`Trade report: http://127.0.0.1:${PORT}/trades.html`);
});
