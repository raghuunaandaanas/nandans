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
const EXPORT_DIR = path.join(OUT_DIR, 'exports');

// B5 Factor - 0.2611% (26.11% as the lowest point for stocks)
const FACTORS = {
  micro: 0.002611,   // 0.2611% - for intraday
  mini: 0.0261,      // 2.61% - for swing
  mega: 0.2611,      // 26.11% - for long term investment (yearly)
};

const TF_CLOSE_FIELD = {
  '1m': 'first_1m_close',
  '5m': 'first_5m_close',
  '15m': 'first_15m_close',
};

const PAPER_TF = ['1m', '5m', '15m'].includes(process.env.PAPER_TF) ? process.env.PAPER_TF : '5m';
const PAPER_FACTOR = ['micro', 'mini', 'mega', 'smart'].includes(process.env.PAPER_FACTOR) ? process.env.PAPER_FACTOR : 'smart'; // Default to smart selector
const PAPER_FACTOR_MCX = ['micro', 'mini', 'mega'].includes(process.env.PAPER_FACTOR_MCX) ? process.env.PAPER_FACTOR_MCX : 'mini'; // Use larger factor for commodities
const PAPER_COOLDOWN_SEC = Number(process.env.PAPER_COOLDOWN_SEC || 30);
const PAPER_CYCLE_MS = Math.max(500, Number(process.env.PAPER_CYCLE_MS || 1500));

const TRADE_MODE = ['paper', 'live'].includes(String(process.env.TRADE_MODE || 'paper').toLowerCase())
  ? String(process.env.TRADE_MODE || 'paper').toLowerCase()
  : 'paper';
const ENABLE_LIVE_TRADING = process.env.ENABLE_LIVE_TRADING === '1';
const TREND_ONLY = process.env.TREND_ONLY !== '0';
const MIN_CONFIRMATION = Math.max(1, Number(process.env.MIN_CONFIRMATION || 2));  // Lower to 2 for faster entries
const MIN_RR = Math.max(0.1, Number(process.env.MIN_RR || 0.5));  // Lower to 0.5 for options/commodities
const JACKPOT_ONLY = process.env.JACKPOT_ONLY === '1';  // Only jackpot if explicitly set
const JACKPOT_TOUCH_LOOKBACK_SEC = Math.max(60, Number(process.env.JACKPOT_TOUCH_LOOKBACK_SEC || 1800));
const JACKPOT_MIN_CONFIRMATION = Math.max(MIN_CONFIRMATION, Number(process.env.JACKPOT_MIN_CONFIRMATION || 3));
const JACKPOT_MIN_RR = Math.max(MIN_RR, Number(process.env.JACKPOT_MIN_RR || 2.2));
const MIN_VOLUME_ACCEL = Math.max(1, Number(process.env.MIN_VOLUME_ACCEL || 1.15));
const MIN_PROBABILITY_SCORE = Math.max(0, Math.min(100, Number(process.env.MIN_PROBABILITY_SCORE || 35)));  // Lower to 35 for commodities
const MAX_SPIKE_POINTS_MULT = Math.max(0.5, Number(process.env.MAX_SPIKE_POINTS_MULT || 2.5));

// Broker Limits Configuration
const BROKER_LIMITS = {
  max_orders_per_day: Number(process.env.MAX_ORDERS_PER_DAY || 2000),
  max_open_positions: Number(process.env.MAX_OPEN_POSITIONS || 100),
  max_margin_used_pct: Number(process.env.MAX_MARGIN_USED_PCT || 80),
};

// Market Close Times (IST)
const MARKET_CLOSE = {
  NSE: { hour: 15, minute: 28, second: 30 },
  BSE: { hour: 15, minute: 28, second: 30 },
  NFO: { hour: 15, minute: 28, second: 30 },
  BFO: { hour: 15, minute: 28, second: 30 },
  MCX: { hour: 23, minute: 30, second: 0 }, // MCX closes at 11:30 PM
};

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
  dailyStats: {
    ordersPlaced: 0,
    day: '',
  },
};

const signalState = {
  byConfig: new Map(),
};

// Voice Announcements State
const voiceState = {
  lastTopVolumeAnnounce: 0,
  lastTopGainersAnnounce: 0,
  lastLevelsPerformanceAnnounce: 0,
  lastNoTradesIntro: 0,
  announcementCooldownMs: 120000, // 2 minutes between announcements
};

function json(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(body));
}

function toNum(v) {
  if (v === null || v === undefined || v === '') return null;
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

function toMs(v) {
  const ms = Date.parse(String(v || ''));
  return Number.isFinite(ms) ? ms : null;
}

// Time helpers
function getISTTime() {
  const now = new Date();
  const istOffset = 5.5 * 60 * 60 * 1000; // IST is UTC+5:30
  return new Date(now.getTime() + istOffset);
}

function formatISTTime(date = new Date()) {
  return date.toLocaleTimeString('en-IN', { 
    timeZone: 'Asia/Kolkata',
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

function formatISTDateTime(date = new Date()) {
  return date.toLocaleString('en-IN', { 
    timeZone: 'Asia/Kolkata',
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

// Smart Factor Selector - automatically picks best factor based on price movement
function selectSmartFactor(ltp, close, exchange, tsym) {
  const ex = String(exchange || '').toUpperCase();
  const sym = String(tsym || '').toUpperCase();
  
  // MCX commodities always use mini factor (2.61%)
  if (ex === 'MCX') {
    return { factor: FACTORS.mini, factorName: 'mini', reason: 'mcx_commodity' };
  }
  
  // Calculate price movement percentage from close
  const movePct = Math.abs((ltp - close) / close) * 100;
  
  // Detect instrument type
  const isIndex = /^(NIFTY|BANKNIFTY|FINNIFTY|SENSEX)$/.test(sym);
  const isOption = ex === 'NFO' || ex === 'BFO' || /(CE|PE)$/.test(sym);
  const isFuture = /FUT/.test(sym);
  
  // For indices - always use micro (0.2611%)
  if (isIndex) {
    return { factor: FACTORS.micro, factorName: 'micro', reason: 'index' };
  }
  
  // For options - select based on moneyness and volatility
  if (isOption) {
    // If very volatile (> 10%), use mega for extreme targets
    if (movePct > 10) {
      return { factor: FACTORS.mega, factorName: 'mega', reason: 'extreme_volatility_option' };
    }
    // If price has moved > 5%, use mini for bigger targets
    if (movePct > 5) {
      return { factor: FACTORS.mini, factorName: 'mini', reason: 'high_volatility_option' };
    }
    // Default for options
    return { factor: FACTORS.micro, factorName: 'micro', reason: 'standard_option' };
  }
  
  // For futures
  if (isFuture) {
    if (movePct > 3) {
      return { factor: FACTORS.mini, factorName: 'mini', reason: 'volatile_future' };
    }
    return { factor: FACTORS.micro, factorName: 'micro', reason: 'standard_future' };
  }
  
  // For equities - select based on volatility
  if (movePct > 8) {
    return { factor: FACTORS.mega, factorName: 'mega', reason: 'extreme_volatility_equity' };
  }
  if (movePct > 3) {
    return { factor: FACTORS.mini, factorName: 'mini', reason: 'volatile_equity' };
  }
  
  // Default: micro for most stocks
  return { factor: FACTORS.micro, factorName: 'micro', reason: 'standard_equity' };
}

// Check if market should be closed for a symbol
function shouldAutoClose(exchange) {
  const ex = String(exchange || '').toUpperCase();
  const closeTime = MARKET_CLOSE[ex];
  if (!closeTime) return false;
  
  const now = new Date();
  const istNow = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
  
  const currentHour = istNow.getHours();
  const currentMinute = istNow.getMinutes();
  const currentSecond = istNow.getSeconds();
  
  const closeSeconds = closeTime.hour * 3600 + closeTime.minute * 60 + closeTime.second;
  const currentSeconds = currentHour * 3600 + currentMinute * 60 + currentSecond;
  
  return currentSeconds >= closeSeconds;
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

function migratePaperDb(db) {
  // Check if new columns exist, add them if not
  try {
    const cols = db.prepare("PRAGMA table_info(paper_trades)").all();
    const colNames = cols.map(c => c.name);
    
    // Add missing columns for new schema
    const migrations = [
      { col: 'exchange', sql: 'ALTER TABLE paper_trades ADD COLUMN exchange TEXT' },
      { col: 'instrument_type', sql: 'ALTER TABLE paper_trades ADD COLUMN instrument_type TEXT DEFAULT "EQUITY"' },
      { col: 'be1', sql: 'ALTER TABLE paper_trades ADD COLUMN be1 REAL' },
      { col: 'be2', sql: 'ALTER TABLE paper_trades ADD COLUMN be2 REAL' },
      { col: 'be3', sql: 'ALTER TABLE paper_trades ADD COLUMN be3 REAL' },
      { col: 'be4', sql: 'ALTER TABLE paper_trades ADD COLUMN be4 REAL' },
      { col: 'be5', sql: 'ALTER TABLE paper_trades ADD COLUMN be5 REAL' },
      { col: 'sl_price', sql: 'ALTER TABLE paper_trades ADD COLUMN sl_price REAL' },
      { col: 'tp_price', sql: 'ALTER TABLE paper_trades ADD COLUMN tp_price REAL' },
      { col: 'tsl_trigger', sql: 'ALTER TABLE paper_trades ADD COLUMN tsl_trigger REAL' },
      { col: 'tsl_active', sql: 'ALTER TABLE paper_trades ADD COLUMN tsl_active INTEGER DEFAULT 0' },
      { col: 'tsl_sl_price', sql: 'ALTER TABLE paper_trades ADD COLUMN tsl_sl_price REAL' },
      { col: 'max_profit_points', sql: 'ALTER TABLE paper_trades ADD COLUMN max_profit_points REAL DEFAULT 0' },
      { col: 'quantity', sql: 'ALTER TABLE paper_trades ADD COLUMN quantity INTEGER DEFAULT 1' },
      { col: 'brokerage', sql: 'ALTER TABLE paper_trades ADD COLUMN brokerage REAL DEFAULT 0' },
      { col: 'stt', sql: 'ALTER TABLE paper_trades ADD COLUMN stt REAL DEFAULT 0' },
      { col: 'exchange_charges', sql: 'ALTER TABLE paper_trades ADD COLUMN exchange_charges REAL DEFAULT 0' },
      { col: 'sebi_charges', sql: 'ALTER TABLE paper_trades ADD COLUMN sebi_charges REAL DEFAULT 0' },
      { col: 'stamp_duty', sql: 'ALTER TABLE paper_trades ADD COLUMN stamp_duty REAL DEFAULT 0' },
      { col: 'gst', sql: 'ALTER TABLE paper_trades ADD COLUMN gst REAL DEFAULT 0' },
      { col: 'total_charges', sql: 'ALTER TABLE paper_trades ADD COLUMN total_charges REAL DEFAULT 0' },
      { col: 'net_pnl', sql: 'ALTER TABLE paper_trades ADD COLUMN net_pnl REAL' },
    ];
    
    for (const mig of migrations) {
      if (!colNames.includes(mig.col)) {
        try {
          db.exec(mig.sql);
        } catch (e) {
          // Column might already exist
        }
      }
    }
  } catch (e) {
    // Table might not exist yet
  }
}

function getPaperDb() {
  if (paperDb) return paperDb;
  paperDb = new DatabaseSync(PAPER_DB_FILE, { open: true, readOnly: false });
  paperDb.exec('PRAGMA journal_mode=WAL');
  paperDb.exec('PRAGMA synchronous=NORMAL');
  
  // Enhanced paper_trades table with SL, TP, TSL
  paperDb.exec(`
    CREATE TABLE IF NOT EXISTS paper_trades (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT NOT NULL,
      tsym TEXT,
      exchange TEXT,
      day TEXT NOT NULL,
      timeframe TEXT NOT NULL,
      factor TEXT NOT NULL,
      instrument_type TEXT DEFAULT 'EQUITY',
      close_price REAL,
      points REAL,
      bu1 REAL,
      bu2 REAL,
      bu3 REAL,
      bu4 REAL,
      bu5 REAL,
      be1 REAL,
      be2 REAL,
      be3 REAL,
      be4 REAL,
      be5 REAL,
      entry_ltp REAL NOT NULL,
      entry_ts TEXT NOT NULL,
      exit_ltp REAL,
      exit_ts TEXT,
      sl_price REAL,
      tp_price REAL,
      tsl_trigger REAL,
      tsl_active INTEGER DEFAULT 0,
      tsl_sl_price REAL,
      max_profit_points REAL DEFAULT 0,
      status TEXT NOT NULL,
      reason TEXT,
      last_ltp REAL,
      max_ltp REAL,
      min_ltp REAL,
      runup REAL,
      drawdown REAL,
      pnl REAL,
      pnl_pct REAL,
      quantity INTEGER DEFAULT 1,
      brokerage REAL DEFAULT 0,
      stt REAL DEFAULT 0,
      exchange_charges REAL DEFAULT 0,
      sebi_charges REAL DEFAULT 0,
      stamp_duty REAL DEFAULT 0,
      gst REAL DEFAULT 0,
      total_charges REAL DEFAULT 0,
      net_pnl REAL,
      updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_paper_status ON paper_trades(status);
    CREATE INDEX IF NOT EXISTS idx_paper_symbol ON paper_trades(symbol);
    CREATE INDEX IF NOT EXISTS idx_paper_day ON paper_trades(day);
  `);
  
  // Run migrations for existing tables
  migratePaperDb(paperDb);
  
  // Broker limits tracking table
  paperDb.exec(`
    CREATE TABLE IF NOT EXISTS broker_limits (
      day TEXT PRIMARY KEY,
      orders_placed INTEGER DEFAULT 0,
      orders_rejected INTEGER DEFAULT 0,
      open_positions INTEGER DEFAULT 0,
      margin_used REAL DEFAULT 0,
      margin_available REAL DEFAULT 0,
      updated_at TEXT
    );
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

// Broker Limit Functions
function getBrokerLimitsStatus() {
  const db = getPaperDb();
  if (!db) return null;
  
  const today = new Date().toISOString().split('T')[0];
  
  // Get or create today's record
  let record = db.prepare('SELECT * FROM broker_limits WHERE day = ?').get(today);
  if (!record) {
    db.prepare('INSERT INTO broker_limits (day, orders_placed, open_positions, updated_at) VALUES (?, 0, 0, ?)')
      .run(today, isoNow());
    record = { orders_placed: 0, open_positions: 0, margin_used: 0 };
  }
  
  // Count actual open positions
  const openPos = db.prepare("SELECT COUNT(1) as c FROM paper_trades WHERE status = 'OPEN' AND day = ?").get(today);
  const openPositions = openPos?.c || 0;
  
  // Calculate margin used (simplified - in real scenario would be based on actual margin requirements)
  const marginResult = db.prepare("SELECT SUM(entry_ltp * quantity) as margin FROM paper_trades WHERE status = 'OPEN' AND day = ?").get(today);
  const marginUsed = marginResult?.margin || 0;
  
  // Update record
  db.prepare('UPDATE broker_limits SET open_positions = ?, margin_used = ?, updated_at = ? WHERE day = ?')
    .run(openPositions, marginUsed, isoNow(), today);
  
  const ordersPlaced = record.orders_placed || 0;
  const ordersRemaining = Math.max(0, BROKER_LIMITS.max_orders_per_day - ordersPlaced);
  const positionsRemaining = Math.max(0, BROKER_LIMITS.max_open_positions - openPositions);
  
  // Determine status color
  let statusColor = 'green';
  if (ordersRemaining < BROKER_LIMITS.max_orders_per_day * 0.2 || positionsRemaining < BROKER_LIMITS.max_open_positions * 0.2) {
    statusColor = 'red';
  } else if (ordersRemaining < BROKER_LIMITS.max_orders_per_day * 0.5 || positionsRemaining < BROKER_LIMITS.max_open_positions * 0.5) {
    statusColor = 'yellow';
  }
  
  return {
    orders_placed: ordersPlaced,
    orders_remaining: ordersRemaining,
    orders_limit: BROKER_LIMITS.max_orders_per_day,
    orders_pct_used: ((ordersPlaced / BROKER_LIMITS.max_orders_per_day) * 100).toFixed(1),
    open_positions: openPositions,
    positions_remaining: positionsRemaining,
    positions_limit: BROKER_LIMITS.max_open_positions,
    positions_pct_used: ((openPositions / BROKER_LIMITS.max_open_positions) * 100).toFixed(1),
    margin_used: marginUsed.toFixed(2),
    status_color: statusColor,
    safe_to_trade: statusColor === 'green',
    warning: statusColor === 'yellow',
    danger: statusColor === 'red',
    updated_at: formatISTDateTime(),
  };
}

function incrementOrderCount() {
  const db = getPaperDb();
  if (!db) return;
  
  const today = new Date().toISOString().split('T')[0];
  db.prepare('UPDATE broker_limits SET orders_placed = orders_placed + 1, updated_at = ? WHERE day = ?')
    .run(isoNow(), today);
}

// Calculate brokerage charges for realistic PnL
function calculateBrokerageCharges(entryPrice, exitPrice, quantity, exchange) {
  const turnover = (entryPrice + exitPrice) * quantity;
  const ex = String(exchange || '').toUpperCase();
  
  // Shoonya/Fyers like charges (approximate)
  const brokerage = Math.min(turnover * 0.0001, 20); // Max Rs 20 per order
  const stt = ex.includes('NSE') || ex.includes('BSE') ? turnover * 0.00025 : turnover * 0.0001; // 0.025% for equity
  const exchangeCharges = turnover * 0.0000325; // Exchange charges
  const sebiCharges = turnover * 0.000001; // SEBI charges
  const stampDuty = entryPrice * quantity * 0.00015; // Stamp duty on buy side
  const gst = (brokerage + exchangeCharges) * 0.18; // 18% GST on brokerage + exchange charges
  
  const totalCharges = brokerage + stt + exchangeCharges + sebiCharges + stampDuty + gst;
  
  return {
    brokerage: Number(brokerage.toFixed(2)),
    stt: Number(stt.toFixed(2)),
    exchange_charges: Number(exchangeCharges.toFixed(2)),
    sebi_charges: Number(sebiCharges.toFixed(2)),
    stamp_duty: Number(stampDuty.toFixed(2)),
    gst: Number(gst.toFixed(2)),
    total_charges: Number(totalCharges.toFixed(2)),
  };
}

function recomputeDerivedForConfig(baseRows, timeframe, factorName) {
  const closeField = TF_CLOSE_FIELD[timeframe];
  const factorVal = FACTORS[factorName];
  const factorValMCX = FACTORS[PAPER_FACTOR_MCX]; // Larger factor for commodities
  const key = cfgKey(timeframe, factorName);
  let cfgState = signalState.byConfig.get(key);
  if (!cfgState) {
    cfgState = new Map();
    signalState.byConfig.set(key, cfgState);
  }

  const allRows = [];
  const triggerRows = [];
  const seenSymbols = new Set();
  const nowMs = Date.now();

  for (const row of baseRows) {
    const ltp = toNum(row.ltp);
    const close = toNum(row[closeField]);
    if (ltp === null || close === null) continue;

    const symbol = String(row.symbol || '');
    if (!symbol) continue;
    seenSymbols.add(symbol);
    
    // Determine which factor to use
    const exchange = String(row.exchange || '').toUpperCase();
    let actualFactor, selectedFactorName, factorReason;
    
    if (factorName === 'smart') {
      // Smart selector: automatically pick best factor
      const smart = selectSmartFactor(ltp, close, exchange, row.tsym);
      actualFactor = smart.factor;
      selectedFactorName = smart.factorName;
      factorReason = smart.reason;
    } else {
      // Use configured factor
      const useMCXFactor = exchange === 'MCX';
      actualFactor = useMCXFactor ? factorValMCX : factorVal;
      selectedFactorName = useMCXFactor ? PAPER_FACTOR_MCX : factorName;
      factorReason = useMCXFactor ? 'mcx_auto' : 'config';
    }

    const volume = Math.max(0, Number(toNum(row.volume) || 0));
    const rowTsMs = toMs(row.updated_at) || nowMs;
    const prev = cfgState.get(symbol) || {
      prevLtp: null,
      prevVolume: null,
      prevVolDelta: 0,
      be5TouchTs: 0,
      be5MinLtp: null,
      be5TouchVolume: 0,
    };

    // B5 Factor calculations - use larger factor for commodities
    const points = close * actualFactor;
    const bu1 = close + points;
    const bu2 = close + points * 2;
    const bu3 = close + points * 3;
    const bu4 = close + points * 4;
    const bu5 = close + points * 5;

    const be1 = close - points;
    const be2 = close - points * 2;
    const be3 = close - points * 3;
    const be4 = close - points * 4;
    const be5 = close - points * 5;

    const levelPairs = [
      ['BU1', bu1],
      ['BU2', bu2],
      ['BU3', bu3],
      ['BU4', bu4],
      ['BU5', bu5],
      ['BE1', be1],
      ['BE2', be2],
      ['BE3', be3],
      ['BE4', be4],
      ['BE5', be5],
    ];

    let nearName = levelPairs[0][0];
    let nearValue = levelPairs[0][1];
    let nearDiff = Math.abs(ltp - nearValue);
    for (let i = 1; i < levelPairs.length; i += 1) {
      const cur = levelPairs[i][1];
      const d = Math.abs(ltp - cur);
      if (d < nearDiff) {
        nearDiff = d;
        nearName = levelPairs[i][0];
        nearValue = cur;
      }
    }

    const nearPct = nearValue ? ((ltp - nearValue) / nearValue) * 100 : 0;

    // Trading range: BU1-BU5 for longs (BE1-BE5 for shorts)
    const inRangeUp = ltp >= bu1 && ltp <= bu5;
    const inRangeDown = ltp <= be1 && ltp >= be5;
    const inRange = inRangeUp || inRangeDown;
    
    // Sideways: Between BE1 and BU1 (avoid this zone)
    const sideways = ltp > be1 && ltp < bu1;

    let trend = 'SIDEWAYS';
    if (ltp >= bu1) trend = 'UP';
    else if (ltp <= be1) trend = 'DOWN';

    const upBreakCount = [bu1, bu2, bu3, bu4, bu5].filter((v) => ltp >= v).length;
    const downBreakCount = [be1, be2, be3, be4, be5].filter((v) => ltp <= v).length;
    const confirmation = trend === 'UP' ? upBreakCount : trend === 'DOWN' ? downBreakCount : 0;

    const volDelta = prev.prevVolume === null ? 0 : Math.max(0, volume - Number(prev.prevVolume));
    const volumeAccel = prev.prevVolDelta > 0 ? volDelta / Number(prev.prevVolDelta) : (volDelta > 0 ? 1 : 0);
    const crossedBu1 = prev.prevLtp !== null && Number(prev.prevLtp) < bu1 && ltp >= bu1;
    const ltpJump = prev.prevLtp === null ? 0 : Math.abs(ltp - Number(prev.prevLtp));
    const spikeFlag = points > 0 ? ltpJump > (points * MAX_SPIKE_POINTS_MULT) : false;

    if (ltp <= be5) {
      prev.be5TouchTs = rowTsMs;
      prev.be5MinLtp = prev.be5MinLtp === null ? ltp : Math.min(Number(prev.be5MinLtp), ltp);
      prev.be5TouchVolume = volume;
    }

    const be5TouchAgeSec = prev.be5TouchTs ? Math.max(0, (rowTsMs - Number(prev.be5TouchTs)) / 1000) : null;
    const be5TouchedRecent = be5TouchAgeSec !== null && be5TouchAgeSec <= JACKPOT_TOUCH_LOOKBACK_SEC;

    if (!be5TouchedRecent) {
      prev.be5TouchTs = 0;
      prev.be5MinLtp = null;
      prev.be5TouchVolume = 0;
    }

    const risk = Math.max(0.0001, ltp - bu1);
    const reward = Math.max(0, bu5 - ltp);
    const rrToBu5 = reward / risk;

    const jackpotRetest = trend === 'UP' && nearName === 'BU1' && Math.abs(nearPct) <= 0.08;
    const jackpotBe5Reversal =
      be5TouchedRecent &&
      prev.be5MinLtp !== null &&
      Number(prev.be5MinLtp) <= be5 &&
      ltp >= bu1 &&
      (crossedBu1 || nearName === 'BU1') &&
      Number(confirmation) >= JACKPOT_MIN_CONFIRMATION &&
      rrToBu5 >= JACKPOT_MIN_RR &&
      volumeAccel >= MIN_VOLUME_ACCEL;

    const probabilityScore = Math.max(
      0,
      Math.min(
        100,
        Math.round(
          (Math.min(5, Math.max(0, Number(confirmation))) / 5) * 45 +
            (Math.min(5, Math.max(0, rrToBu5)) / 5) * 35 +
            (Math.min(3, Math.max(0, volumeAccel)) / 3) * 15 +
            (be5TouchedRecent ? 5 : 0)
        )
      )
    );

    const jackpotLong = jackpotBe5Reversal;
    const jackpotShort = trend === 'DOWN' && nearName === 'BE1' && Math.abs(nearPct) <= 0.08;

    // Traderscope data from backend
    const digitAnalyses = row.digit_analyses || [];
    const selectedDigit = row.selected_digit || 5;
    const selectedAnalysis = row.selected_analysis || {};
    const gammaMove = row.gamma_move || null;
    const rangeShifts = row.range_shifts || [];
    const traderscopeReady = row.traderscope_ready || false;

    const enriched = {
      ...row,
      close,
      points,
      selected_factor: selectedFactorName,
      factor_reason: factorReason,
      bu1,
      bu2,
      bu3,
      bu4,
      bu5,
      be1,
      be2,
      be3,
      be4,
      be5,
      near_name: nearName,
      near_value: nearValue,
      near_diff: ltp - nearValue,
      near_pct: nearPct,
      in_range_up: inRangeUp,
      in_range_down: inRangeDown,
      in_range: inRange,
      sideways,
      trend,
      confirmation,
      up_break_count: upBreakCount,
      down_break_count: downBreakCount,
      rr_to_bu5: rrToBu5,
      volume_delta: volDelta,
      volume_accel: volumeAccel,
      be5_touched_recent: be5TouchedRecent,
      be5_touch_age_sec: be5TouchedRecent ? be5TouchAgeSec : null,
      be5_low_ltp: prev.be5MinLtp,
      jackpot_long: jackpotLong,
      jackpot_retest: jackpotRetest,
      jackpot_be5_reversal: jackpotBe5Reversal,
      jackpot_short: jackpotShort,
      probability_score: probabilityScore,
      ltp_jump: ltpJump,
      spike_flag: spikeFlag,
      above_bu1: ltp >= bu1,
      below_be1: ltp <= be1,
      above_bu5: ltp > bu5,
      below_be5: ltp < be5,
      // Traderscope data
      digit_analyses: digitAnalyses,
      selected_digit: selectedDigit,
      selected_analysis: selectedAnalysis,
      gamma_move: gammaMove,
      range_shifts: rangeShifts,
      traderscope_ready: traderscopeReady,
      zone_name: selectedAnalysis.zone_name || '-',
      zone_type: selectedAnalysis.zone_type || '-',
      position_pct: selectedAnalysis.position?.toFixed(1) || '-',
      // IST Time
      ist_time: formatISTTime(),
      ist_datetime: formatISTDateTime(),
    };

    prev.prevLtp = ltp;
    prev.prevVolume = volume;
    prev.prevVolDelta = volDelta;
    cfgState.set(symbol, prev);

    allRows.push(enriched);
    // Only add to trigger rows if in BU1-BU5 range (trending up) - ignore sideways
    if (inRangeUp && !sideways) triggerRows.push(enriched);
  }

  for (const symbol of cfgState.keys()) {
    if (!seenSymbols.has(symbol)) cfgState.delete(symbol);
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

function getDerivedForConfig(snapshotMtimeMs, baseRows, timeframe, factorName) {
  if (derivedCache.snapshotMtimeMs !== snapshotMtimeMs) {
    derivedCache.snapshotMtimeMs = snapshotMtimeMs;
    derivedCache.byConfig.clear();
  }

  const key = cfgKey(timeframe, factorName);
  if (!derivedCache.byConfig.has(key)) {
    derivedCache.byConfig.set(key, recomputeDerivedForConfig(baseRows, timeframe, factorName));
  }
  return derivedCache.byConfig.get(key) || { allRows: [], triggerRows: [] };
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

function composeStatus(snapshot, tradeSummary) {
  const st = snapshot && typeof snapshot === 'object' ? snapshot.status || {} : {};
  return {
    login: st.login || {},
    websocket: st.websocket || {},
    history_store: st.history_store || {},
    analysis: st.analysis || {},
    today_first_close: st.today_first_close || {},
    past_data_download: st.past_data_download || {},
    storage: st.storage || {},
    trade: {
      ...tradeSummary,
      mode: TRADE_MODE,
      live_enabled: ENABLE_LIVE_TRADING,
      engine_state: TRADE_MODE === 'live' ? (ENABLE_LIVE_TRADING ? 'live_ready' : 'live_blocked') : 'paper',
    },
    broker_limits: getBrokerLimitsStatus(),
    market_time: {
      ist_time: formatISTTime(),
      ist_datetime: formatISTDateTime(),
      auto_close_nse_bse: shouldAutoClose('NSE'),
      auto_close_mcx: shouldAutoClose('MCX'),
    },
  };
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
  const factorName = ['micro', 'mini', 'mega', 'smart'].includes(urlObj.searchParams.get('factor'))
    ? urlObj.searchParams.get('factor')
    : 'smart';  // Default to smart selector

  const limit = Math.max(1, Math.min(50000, Number(urlObj.searchParams.get('limit') || 5000)));

  const baseRows = Array.isArray(snapshot.rows) ? snapshot.rows : [];
  const cacheItem = getDerivedForConfig(snapshotCache.mtimeMs, baseRows, timeframe, factorName);
  const sourceRows = triggerOnly ? cacheItem.triggerRows : cacheItem.allRows;

  const filtered = filterRows(sourceRows, q, completeOnly, limit);

  const dbStats = loadDbStats(snapshot.day);
  const tmeta = ticksMeta();
  const trade = paperSummary();

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
      factor_value: factorName === 'smart' ? 'auto' : FACTORS[factorName],
      trigger_only: triggerOnly,
      jackpot_only: JACKPOT_ONLY,
      jackpot_min_rr: JACKPOT_MIN_RR,
      jackpot_min_confirmation: JACKPOT_MIN_CONFIRMATION,
      jackpot_touch_lookback_sec: JACKPOT_TOUCH_LOOKBACK_SEC,
      min_probability_score: MIN_PROBABILITY_SCORE,
      max_spike_points_mult: MAX_SPIKE_POINTS_MULT,
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
    status: composeStatus(snapshot, trade),
    rows: filtered.rows,
  };
}

function tradeGuardLongRow(row, ltp) {
  const bu1 = toNum(row?.bu1);
  const bu5 = toNum(row?.bu5);

  if (ltp === null || bu1 === null || bu5 === null) {
    return { ok: false, reason: 'missing_levels' };
  }

  if (!(ltp >= bu1 && ltp <= bu5)) {
    return { ok: false, reason: 'outside_bu1_bu5' };
  }

  // Relaxed: Just need to be in range and trending up
  return { ok: true, reason: 'in_bu_range' };
}

function loadOpenTrades() {
  const db = getPaperDb();
  const cur = db.prepare('SELECT * FROM paper_trades WHERE status = ?').all('OPEN');
  for (const r of cur) {
    // Add defaults for new columns if not present
    const trade = {
      ...r,
      exchange: r.exchange || '',
      instrument_type: r.instrument_type || 'EQUITY',
      be1: r.be1 || (r.bu1 ? r.bu1 - (r.points || 0) : 0),
      be2: r.be2 || (r.bu1 ? r.bu1 - 2 * (r.points || 0) : 0),
      be3: r.be3 || (r.bu1 ? r.bu1 - 3 * (r.points || 0) : 0),
      be4: r.be4 || (r.bu1 ? r.bu1 - 4 * (r.points || 0) : 0),
      be5: r.be5 || (r.bu1 ? r.bu1 - 5 * (r.points || 0) : 0),
      sl_price: r.sl_price || (r.bu1 ? r.bu1 - (r.points || 0) : 0),
      tp_price: r.tp_price || r.bu5 || 0,
      tsl_trigger: r.tsl_trigger || r.bu3 || 0,
      tsl_active: r.tsl_active || 0,
      tsl_sl_price: r.tsl_sl_price || r.sl_price || 0,
      max_profit_points: r.max_profit_points || 0,
      quantity: r.quantity || 1,
      brokerage: r.brokerage || 0,
      stt: r.stt || 0,
      exchange_charges: r.exchange_charges || 0,
      sebi_charges: r.sebi_charges || 0,
      stamp_duty: r.stamp_duty || 0,
      gst: r.gst || 0,
      total_charges: r.total_charges || 0,
      net_pnl: r.net_pnl || r.pnl || 0,
    };
    paperState.openTrades.set(r.symbol, trade);
  }
}

function detectInstrumentType(exchange, tsym) {
  const ex = String(exchange || '').toUpperCase();
  const t = String(tsym || '').toUpperCase();
  if (ex === 'MCX') return 'COMMODITY';
  if (ex === 'NFO' || ex === 'BFO') {
    if (/(CE|PE)/.test(t) || /[CP]\d{2,6}$/.test(t)) return 'OPTION';
    if (/FUT/.test(t) || /\dF$/.test(t) || /\d{2}[A-Z]{3}\d{2}F/.test(t)) return 'FUTURE';
    return 'DERIVATIVE';
  }
  return 'EQUITY';
}

function openTradeFromRow(row, day, reason = 'trend_rr_entry') {
  const ltp = toNum(row?.ltp);
  const guard = tradeGuardLongRow(row, ltp);
  if (!guard.ok) return false;
  
  // Check broker limits
  const limits = getBrokerLimitsStatus();
  if (limits && !limits.safe_to_trade) {
    return false;
  }
  
  const db = getPaperDb();
  const now = isoNow();
  const instrumentType = detectInstrumentType(row.exchange, row.tsym);
  
  // Calculate SL, TP, TSL
  const slPrice = row.be1; // Stop Loss at BE1 (below BU1)
  const tpPrice = row.bu5; // Target at BU5
  const tslTrigger = row.bu3; // TSL activates at BU3
  
  // Determine quantity based on instrument type
  let quantity = 1;
  if (instrumentType === 'OPTION') quantity = 50; // Lot size for options
  else if (instrumentType === 'FUTURE') quantity = 1;
  else if (instrumentType === 'EQUITY') quantity = 1;
  
  try {
    const stmt = db.prepare(`
      INSERT INTO paper_trades(
        symbol, tsym, exchange, day, timeframe, factor, instrument_type,
        close_price, points, bu1, bu2, bu3, bu4, bu5, be1, be2, be3, be4, be5,
        entry_ltp, entry_ts, status, reason,
        sl_price, tp_price, tsl_trigger, tsl_active, tsl_sl_price,
        last_ltp, max_ltp, min_ltp, runup, drawdown,
        pnl, pnl_pct, quantity, updated_at
      ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    
    stmt.run(
      row.symbol,
      row.tsym || '',
      row.exchange || '',
      day,
      PAPER_TF,
      PAPER_FACTOR,
      instrumentType,
      row.close,
      row.points,
      row.bu1,
      row.bu2,
      row.bu3,
      row.bu4,
      row.bu5,
      row.be1,
      row.be2,
      row.be3,
      row.be4,
      row.be5,
      ltp,
      now,
      'OPEN',
      reason,
      slPrice,
      tpPrice,
      tslTrigger,
      0, // tsl_active
      slPrice, // initial tsl_sl_price = sl
      ltp,
      ltp,
      ltp,
      0,
      0,
      0,
      0,
      quantity,
      now
    );
  } catch (e) {
    // If columns don't exist, run migration and try simpler insert
    if (e.message && e.message.includes('no such column')) {
      migratePaperDb(db);
      // Fallback insert with just essential columns
      const stmt = db.prepare(`
        INSERT INTO paper_trades(
          symbol, tsym, exchange, day, timeframe, factor, instrument_type,
          close_price, points, bu1, bu2, bu3, bu4, bu5,
          entry_ltp, entry_ts, status, reason,
          last_ltp, max_ltp, min_ltp, runup, drawdown,
          pnl, pnl_pct, quantity, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);
      stmt.run(
        row.symbol, row.tsym || '', row.exchange || '', day, PAPER_TF, PAPER_FACTOR, instrumentType,
        row.close, row.points, row.bu1, row.bu2, row.bu3, row.bu4, row.bu5,
        ltp, now, 'OPEN', reason,
        ltp, ltp, ltp, 0, 0, 0, 0, quantity, now
      );
    } else {
      throw e;
    }
  }

  incrementOrderCount();
  
  const id = db.prepare('SELECT last_insert_rowid() AS id').get().id;
  const t = {
    id,
    symbol: row.symbol,
    tsym: row.tsym || '',
    exchange: row.exchange || '',
    day,
    timeframe: PAPER_TF,
    factor: PAPER_FACTOR,
    instrument_type: instrumentType,
    close_price: row.close,
    points: row.points,
    bu1: row.bu1,
    bu2: row.bu2,
    bu3: row.bu3,
    bu4: row.bu4,
    bu5: row.bu5,
    be1: row.be1,
    be2: row.be2,
    be3: row.be3,
    be4: row.be4,
    be5: row.be5,
    entry_ltp: ltp,
    entry_ts: now,
    exit_ltp: null,
    exit_ts: null,
    sl_price: slPrice,
    tp_price: tpPrice,
    tsl_trigger: tslTrigger,
    tsl_active: 0,
    tsl_sl_price: slPrice,
    max_profit_points: 0,
    status: 'OPEN',
    reason,
    last_ltp: ltp,
    max_ltp: ltp,
    min_ltp: ltp,
    runup: 0,
    drawdown: 0,
    pnl: 0,
    pnl_pct: 0,
    quantity,
    updated_at: now,
  };
  paperState.openTrades.set(row.symbol, t);
  return true;
}

function closeTrade(trade, ltp, reason) {
  const db = getPaperDb();
  const now = isoNow();
  
  // Calculate charges
  const charges = calculateBrokerageCharges(trade.entry_ltp, ltp, trade.quantity || 1, trade.exchange);
  
  const pnl = (ltp - Number(trade.entry_ltp)) * (trade.quantity || 1);
  const pnlPct = trade.entry_ltp ? ((ltp - Number(trade.entry_ltp)) / Number(trade.entry_ltp)) * 100 : 0;
  const netPnl = pnl - charges.total_charges;

  try {
    db.prepare(`
      UPDATE paper_trades
      SET exit_ltp=?, exit_ts=?, status='CLOSED', reason=?,
          last_ltp=?, max_ltp=?, min_ltp=?, runup=?, drawdown=?, pnl=?, pnl_pct=?,
          brokerage=?, stt=?, exchange_charges=?, sebi_charges=?, stamp_duty=?, gst=?,
          total_charges=?, net_pnl=?, updated_at=?
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
      charges.brokerage,
      charges.stt,
      charges.exchange_charges,
      charges.sebi_charges,
      charges.stamp_duty,
      charges.gst,
      charges.total_charges,
      netPnl,
      now,
      trade.id
    );
  } catch (e) {
    // If columns don't exist, try to add them and retry
    if (e.message && e.message.includes('no such column')) {
      migratePaperDb(db);
      try {
        db.prepare(`
          UPDATE paper_trades
          SET exit_ltp=?, exit_ts=?, status='CLOSED', reason=?,
              last_ltp=?, max_ltp=?, min_ltp=?, runup=?, drawdown=?, pnl=?, pnl_pct=?,
              brokerage=?, stt=?, exchange_charges=?, sebi_charges=?, stamp_duty=?, gst=?,
              total_charges=?, net_pnl=?, updated_at=?
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
          charges.brokerage,
          charges.stt,
          charges.exchange_charges,
          charges.sebi_charges,
          charges.stamp_duty,
          charges.gst,
          charges.total_charges,
          netPnl,
          now,
          trade.id
        );
      } catch (e2) {
        // Fallback: basic update
        db.prepare(`
          UPDATE paper_trades
          SET exit_ltp=?, exit_ts=?, status='CLOSED', reason=?,
              last_ltp=?, max_ltp=?, min_ltp=?, runup=?, drawdown=?, pnl=?, pnl_pct=?, updated_at=?
          WHERE id=?
        `).run(ltp, now, reason, ltp, trade.max_ltp, trade.min_ltp, trade.runup, trade.drawdown, pnl, pnlPct, now, trade.id);
      }
    }
  }

  paperState.openTrades.delete(trade.symbol);
  paperState.cooldownUntil.set(trade.symbol, Date.now() + PAPER_COOLDOWN_SEC * 1000);
}

function updateOpenTrade(trade, ltp) {
  trade.last_ltp = ltp;
  trade.max_ltp = Math.max(Number(trade.max_ltp), ltp);
  trade.min_ltp = Math.min(Number(trade.min_ltp), ltp);
  
  const currentRunup = ltp - Number(trade.entry_ltp);
  const currentDrawdown = Number(trade.entry_ltp) - ltp;
  trade.runup = Math.max(Number(trade.runup), currentRunup);
  trade.drawdown = Math.max(Number(trade.drawdown), currentDrawdown);
  
  // Calculate max profit points for TSL
  const points = Number(trade.points);
  const maxProfitPoints = Math.max(0, (trade.max_ltp - Number(trade.entry_ltp)));
  trade.max_profit_points = maxProfitPoints;
  
  // TSL Logic: When price reaches BU3, move SL to BE1 (breakeven)
  // When price reaches BU4, move SL to BU1
  // When price reaches BU5, move SL to BU2
  if (ltp >= Number(trade.tsl_trigger) && !trade.tsl_active) {
    trade.tsl_active = 1;
    trade.tsl_sl_price = trade.be1; // Move to breakeven
  }
  
  if (trade.tsl_active) {
    if (ltp >= Number(trade.bu4) && Number(trade.tsl_sl_price) < Number(trade.bu1)) {
      trade.tsl_sl_price = trade.bu1;
    }
    if (ltp >= Number(trade.bu5) && Number(trade.tsl_sl_price) < Number(trade.bu2)) {
      trade.tsl_sl_price = trade.bu2;
    }
  }
  
  // Calculate PnL with quantity
  const grossPnl = (ltp - Number(trade.entry_ltp)) * (trade.quantity || 1);
  trade.pnl = grossPnl;
  trade.pnl_pct = trade.entry_ltp ? ((ltp - Number(trade.entry_ltp)) / Number(trade.entry_ltp)) * 100 : 0;
  trade.updated_at = isoNow();

  const db = getPaperDb();
  try {
    db.prepare(`
      UPDATE paper_trades
      SET last_ltp=?, max_ltp=?, min_ltp=?, runup=?, drawdown=?, 
          tsl_active=?, tsl_sl_price=?, max_profit_points=?, pnl=?, pnl_pct=?, updated_at=?
      WHERE id=?
    `).run(trade.last_ltp, trade.max_ltp, trade.min_ltp, trade.runup, trade.drawdown, 
         trade.tsl_active, trade.tsl_sl_price, trade.max_profit_points, trade.pnl, trade.pnl_pct, trade.updated_at, trade.id);
  } catch (e) {
    // If columns don't exist, try to add them and retry
    if (e.message && e.message.includes('no such column')) {
      migratePaperDb(db);
      try {
        db.prepare(`
          UPDATE paper_trades
          SET last_ltp=?, max_ltp=?, min_ltp=?, runup=?, drawdown=?, 
              tsl_active=?, tsl_sl_price=?, max_profit_points=?, pnl=?, pnl_pct=?, updated_at=?
          WHERE id=?
        `).run(trade.last_ltp, trade.max_ltp, trade.min_ltp, trade.runup, trade.drawdown, 
             trade.tsl_active, trade.tsl_sl_price, trade.max_profit_points, trade.pnl, trade.pnl_pct, trade.updated_at, trade.id);
      } catch (e2) {
        // Fallback: update only essential columns
        db.prepare(`
          UPDATE paper_trades
          SET last_ltp=?, max_ltp=?, min_ltp=?, runup=?, drawdown=?, pnl=?, pnl_pct=?, updated_at=?
          WHERE id=?
        `).run(trade.last_ltp, trade.max_ltp, trade.min_ltp, trade.runup, trade.drawdown, trade.pnl, trade.pnl_pct, trade.updated_at, trade.id);
      }
    }
  }
}

function runPaperCycle() {
  const snapshot = loadSnapshot();
  const baseRows = Array.isArray(snapshot.rows) ? snapshot.rows : [];
  if (!baseRows.length) return;

  const item = getDerivedForConfig(snapshotCache.mtimeMs, baseRows, PAPER_TF, PAPER_FACTOR);
  if (!item) return;

  if (paperState.lastSnapshotMtime === snapshotCache.mtimeMs) return;
  paperState.lastSnapshotMtime = snapshotCache.mtimeMs;

  const rowMap = new Map();
  for (const r of item.allRows) rowMap.set(r.symbol, r);

  const day = snapshot.day || '-';
  
  // Check auto-close for all open trades first
  for (const t of Array.from(paperState.openTrades.values())) {
    const row = rowMap.get(t.symbol);
    if (!row) continue;
    const ltp = toNum(row.ltp);
    if (ltp === null) continue;

    updateOpenTrade(t, ltp);
    
    // Auto-close at market close time
    if (shouldAutoClose(t.exchange)) {
      closeTrade(t, ltp, 'market_close_auto');
      continue;
    }

    // Target hit - BU5
    if (ltp >= Number(t.bu5)) {
      closeTrade(t, ltp, 'target_bu5');
    }
    // Stop Loss - Below TSL if active, else below BU1
    else if (ltp < Number(t.tsl_active ? t.tsl_sl_price : t.bu1)) {
      closeTrade(t, ltp, t.tsl_active ? 'trailing_sl' : 'sl_below_bu1');
    }
    // Spike protection - close if sudden drop
    else if (row.spike_flag && ltp < Number(t.entry_ltp)) {
      closeTrade(t, ltp, 'spike_protection');
    }
  }

  // New entries from in-range opportunities (only BU1-BU5, no sideways)
  for (const r of item.triggerRows) {
    if (!r.fetch_done) continue;
    if (paperState.openTrades.has(r.symbol)) continue;
    const cool = paperState.cooldownUntil.get(r.symbol) || 0;
    if (Date.now() < cool) continue;

    const ltp = toNum(r.ltp);
    if (ltp === null) continue;

    // Only trade in BU1-BU5 range (trending up), avoid sideways
    if (!r.in_range_up) continue;
    if (r.sideways) continue; // Explicitly avoid sideways
    if (String(r.trend || '') !== 'UP') continue;
    if (Number(r.confirmation || 0) < MIN_CONFIRMATION) continue;

    const risk = Math.max(0.0001, ltp - Number(r.bu1));
    const reward = Math.max(0, Number(r.bu5) - ltp);
    const rr = reward / risk;
    if (rr < MIN_RR) continue;
    
    // MCX evening session: lower probability threshold since first closes are from morning
    const isMCX = String(r.exchange || '').toUpperCase() === 'MCX';
    const now = new Date();
    const istHour = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' })).getHours();
    const isMCXEvening = isMCX && istHour >= 17; // After 5 PM IST
    const minProb = isMCXEvening ? 25 : MIN_PROBABILITY_SCORE;
    
    if (Number(r.probability_score || 0) < minProb) continue;
    if (r.spike_flag) continue;

    if (JACKPOT_ONLY && !r.jackpot_be5_reversal) continue;

    const guard = tradeGuardLongRow(r, ltp);
    if (!guard.ok) continue;

    // Don't open new trades near market close
    if (shouldAutoClose(r.exchange)) continue;

    const reason = 'be5_reversal_guard_entry';
    openTradeFromRow(r, day, reason);
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
      net_pnl: 0,
      peak_equity: paperState.peakEquity,
      drawdown_now: 0,
      max_drawdown: paperState.maxDrawdown,
      strategy_tf: PAPER_TF,
      strategy_factor: PAPER_FACTOR,
      trade_mode: TRADE_MODE,
      live_enabled: ENABLE_LIVE_TRADING,
      engine_state: TRADE_MODE === 'live' ? (ENABLE_LIVE_TRADING ? 'live_ready' : 'live_blocked') : 'paper',
    };
  }

  const agg = db.prepare(`
    SELECT
      COUNT(1) AS total,
      SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END) AS closed,
      SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS open,
      SUM(CASE WHEN status='CLOSED' AND net_pnl > 0 THEN 1 ELSE 0 END) AS wins,
      SUM(CASE WHEN status='CLOSED' AND net_pnl <= 0 THEN 1 ELSE 0 END) AS losses,
      SUM(CASE WHEN status='CLOSED' THEN net_pnl ELSE 0 END) AS realized,
      SUM(CASE WHEN status='OPEN' THEN pnl ELSE 0 END) AS open_pnl,
      SUM(total_charges) AS total_charges
    FROM paper_trades
  `).get();

  const closed = Number(agg?.closed || 0);
  const wins = Number(agg?.wins || 0);
  const losses = Number(agg?.losses || 0);
  const realized = Number(agg?.realized || 0);
  const openPnl = Number(agg?.open_pnl || 0);
  const totalCharges = Number(agg?.total_charges || 0);
  const gross = realized + openPnl;
  const netPnl = gross - totalCharges;

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
    total_charges: totalCharges,
    net_pnl: netPnl,
    peak_equity: paperState.peakEquity,
    drawdown_now: dd,
    max_drawdown: paperState.maxDrawdown,
    strategy_tf: PAPER_TF,
    strategy_factor: PAPER_FACTOR,
    trade_mode: TRADE_MODE,
    live_enabled: ENABLE_LIVE_TRADING,
    engine_state: TRADE_MODE === 'live' ? (ENABLE_LIVE_TRADING ? 'live_ready' : 'live_blocked') : 'paper',
  };
}

function parseSymbolParts(symbol) {
  const s = String(symbol || '');
  const i = s.indexOf('|');
  if (i < 0) return { exchange: '', token: s };
  return { exchange: s.slice(0, i), token: s.slice(i + 1) };
}

function isTokenLike(v) {
  return /^\d+$/.test(String(v || '').trim());
}

function enrichTradeRows(rows, snapshotRows) {
  const snapMap = new Map();
  for (const r of snapshotRows || []) {
    if (r && r.symbol) snapMap.set(r.symbol, r);
  }

  return (rows || []).map((r) => {
    const snap = snapMap.get(r.symbol) || {};
    const parts = parseSymbolParts(r.symbol);
    const tsymRaw = String(r.tsym || snap.tsym || '').trim();
    const snapTsym = String(snap.tsym || '').trim();

    let display = tsymRaw;
    if (!display || isTokenLike(display)) {
      if (snapTsym && !isTokenLike(snapTsym)) display = snapTsym;
      else display = String(r.symbol || '');
    }

    return {
      ...r,
      exchange: parts.exchange || snap.exchange || r.exchange || '',
      token: parts.token || snap.token || r.token || '',
      tsym: tsymRaw,
      display_symbol: display,
      ltp: toNum(snap.ltp),
      volume: toNum(snap.volume),
      first_1m_close: toNum(snap.first_1m_close),
      first_5m_close: toNum(snap.first_5m_close),
      first_15m_close: toNum(snap.first_15m_close),
      ist_time: formatISTTime(),
    };
  });
}

function buildTradeAnalysis(openRows, closedRows, snapshotRows) {
  const topOpen = [...openRows].sort((a, b) => Number(b.pnl || 0) - Number(a.pnl || 0)).slice(0, 10);
  const topClosed = [...closedRows].sort((a, b) => Number(b.pnl || 0) - Number(a.pnl || 0)).slice(0, 10);
  const worstClosed = [...closedRows].sort((a, b) => Number(a.pnl || 0) - Number(b.pnl || 0)).slice(0, 10);

  const bySymbol = new Map();
  for (const r of closedRows) {
    const key = String(r.display_symbol || r.symbol || '');
    const prev = bySymbol.get(key) || {
      symbol: key,
      trades: 0,
      wins: 0,
      losses: 0,
      pnl: 0,
      avg_pnl: 0,
    };
    prev.trades += 1;
    const pnl = Number(r.net_pnl || r.pnl || 0);
    prev.pnl += pnl;
    if (pnl > 0) prev.wins += 1;
    else prev.losses += 1;
    prev.avg_pnl = prev.trades ? prev.pnl / prev.trades : 0;
    bySymbol.set(key, prev);
  }

  const symbolPerformance = Array.from(bySymbol.values())
    .sort((a, b) => b.pnl - a.pnl)
    .slice(0, 15)
    .map((r) => ({
      ...r,
      win_rate: r.trades ? (r.wins / r.trades) * 100 : 0,
    }));

  const volumeRows = [];
  for (const r of snapshotRows || []) {
    const vol = toNum(r.volume);
    if (vol === null || vol <= 0) continue;
    const tsymRaw = String(r.tsym || '').trim();
    const display = tsymRaw && !isTokenLike(tsymRaw) ? tsymRaw : String(r.symbol || '');
    volumeRows.push({
      symbol: r.symbol,
      display_symbol: display,
      volume: vol,
      ltp: toNum(r.ltp),
    });
  }

  let avgVol = 0;
  if (volumeRows.length) {
    avgVol = volumeRows.reduce((s, r) => s + Number(r.volume || 0), 0) / volumeRows.length;
  }

  const volumeLeaders = volumeRows
    .sort((a, b) => b.volume - a.volume)
    .slice(0, 20)
    .map((r) => ({
      ...r,
      volume_vs_avg: avgVol > 0 ? r.volume / avgVol : 0,
    }));
  
  // Top gainers
  const gainers = [];
  for (const r of snapshotRows || []) {
    const ltp = toNum(r.ltp);
    const close = toNum(r.first_5m_close || r.first_1m_close);
    if (ltp === null || close === null) continue;
    const change = ((ltp - close) / close) * 100;
    const tsymRaw = String(r.tsym || '').trim();
    const display = tsymRaw && !isTokenLike(tsymRaw) ? tsymRaw : String(r.symbol || '');
    const instType = detectInstrumentType(r.exchange, r.tsym);
    gainers.push({
      symbol: r.symbol,
      display_symbol: display,
      instrument_type: instType,
      ltp,
      close,
      change_pct: change,
    });
  }
  
  const topGainers = gainers
    .sort((a, b) => b.change_pct - a.change_pct)
    .slice(0, 5);
  
  const topLosers = gainers
    .sort((a, b) => a.change_pct - b.change_pct)
    .slice(0, 5);

  const topPerformer = topClosed.length ? topClosed[0] : (topOpen.length ? topOpen[0] : null);

  return {
    top_performer: topPerformer,
    top_open: topOpen,
    top_closed: topClosed,
    worst_closed: worstClosed,
    symbol_performance: symbolPerformance,
    volume_leaders: volumeLeaders,
    top_gainers: topGainers,
    top_losers: topLosers,
    average_volume: avgVol,
    analysis_time: formatISTDateTime(),
  };
}

function tradesData(urlObj) {
  const limitOpen = Math.max(1, Math.min(5000, Number(urlObj.searchParams.get('open_limit') || 500)));
  const limitClosed = Math.max(1, Math.min(10000, Number(urlObj.searchParams.get('closed_limit') || 1000)));
  const q = normalize(urlObj.searchParams.get('q') || '');

  const snapshot = loadSnapshot();
  const snapshotRows = Array.isArray(snapshot.rows) ? snapshot.rows : [];

  const db = getPaperDb();
  if (!db) {
    const summary0 = paperSummary();
    return {
      summary: summary0,
      status: composeStatus(snapshot, summary0),
      analysis: buildTradeAnalysis([], [], snapshotRows),
      open_trades: [],
      recent_closed: [],
      as_of: isoNow(),
      ist_time: formatISTTime(),
    };
  }

  let open = db.prepare('SELECT * FROM paper_trades WHERE status=? ORDER BY updated_at DESC LIMIT ?').all('OPEN', limitOpen);
  let closed = db.prepare('SELECT * FROM paper_trades WHERE status=? ORDER BY exit_ts DESC LIMIT ?').all('CLOSED', limitClosed);

  if (q) {
    open = open.filter((r) => normalize(r.symbol).includes(q) || normalize(r.tsym).includes(q));
    closed = closed.filter((r) => normalize(r.symbol).includes(q) || normalize(r.tsym).includes(q));
  }

  const openEnriched = enrichTradeRows(open, snapshotRows);
  const closedEnriched = enrichTradeRows(closed, snapshotRows);

  const summary = paperSummary();
  return {
    summary,
    status: composeStatus(snapshot, summary),
    analysis: buildTradeAnalysis(openEnriched, closedEnriched, snapshotRows),
    open_trades: openEnriched,
    recent_closed: closedEnriched,
    as_of: isoNow(),
    ist_time: formatISTTime(),
    ist_datetime: formatISTDateTime(),
  };
}

// Export trades to CSV
function exportTrades(format = 'csv') {
  const db = getPaperDb();
  if (!db) return null;
  
  if (!fs.existsSync(EXPORT_DIR)) {
    fs.mkdirSync(EXPORT_DIR, { recursive: true });
  }
  
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `trades_export_${timestamp}.${format}`;
  const filepath = path.join(EXPORT_DIR, filename);
  
  const trades = db.prepare(`
    SELECT * FROM paper_trades 
    ORDER BY entry_ts DESC
  `).all();
  
  if (format === 'csv') {
    const headers = [
      'ID', 'Symbol', 'TSym', 'Exchange', 'Day', 'Timeframe', 'Factor', 'Instrument Type',
      'Entry Price', 'Exit Price', 'SL Price', 'TP Price', 'TSL Active', 'TSL SL Price',
      'Quantity', 'Status', 'Reason', 'Entry Time', 'Exit Time',
      'PnL', 'PnL %', 'Brokerage', 'STT', 'Exchange Charges', 'SEBI', 'Stamp Duty', 'GST',
      'Total Charges', 'Net PnL', 'Max LTP', 'Min LTP', 'Runup', 'Drawdown', 'Updated At'
    ].join(',');
    
    const rows = trades.map(t => [
      t.id, t.symbol, t.tsym, t.exchange, t.day, t.timeframe, t.factor, t.instrument_type,
      t.entry_ltp, t.exit_ltp || '', t.sl_price, t.tp_price, t.tsl_active ? 'Yes' : 'No', t.tsl_sl_price || '',
      t.quantity, t.status, t.reason || '', t.entry_ts, t.exit_ts || '',
      t.pnl || 0, t.pnl_pct || 0, t.brokerage || 0, t.stt || 0, t.exchange_charges || 0, 
      t.sebi_charges || 0, t.stamp_duty || 0, t.gst || 0, t.total_charges || 0, t.net_pnl || 0,
      t.max_ltp, t.min_ltp, t.runup, t.drawdown, t.updated_at
    ].join(','));
    
    fs.writeFileSync(filepath, [headers, ...rows].join('\n'), 'utf8');
  } else if (format === 'json') {
    fs.writeFileSync(filepath, JSON.stringify(trades, null, 2), 'utf8');
  }
  
  return { filename, filepath, count: trades.length };
}

function contentType(file) {
  const ext = path.extname(file).toLowerCase();
  if (ext === '.html') return 'text/html; charset=utf-8';
  if (ext === '.js') return 'text/javascript; charset=utf-8';
  if (ext === '.css') return 'text/css; charset=utf-8';
  if (ext === '.json') return 'application/json; charset=utf-8';
  if (ext === '.csv') return 'text/csv; charset=utf-8';
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

// Serve export files
function serveExportFile(filename, res) {
  const filepath = path.join(EXPORT_DIR, filename);
  if (!filepath.startsWith(EXPORT_DIR)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }
  
  fs.readFile(filepath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }
    res.writeHead(200, { 
      'Content-Type': contentType(filepath),
      'Content-Disposition': `attachment; filename="${filename}"`
    });
    res.end(data);
  });
}

function initPaperEngine() {
  getPaperDb();
  loadOpenTrades();
  setInterval(runPaperCycle, PAPER_CYCLE_MS);
  
  // Auto export trades every hour
  setInterval(() => {
    exportTrades('csv');
  }, 3600000);
}

const server = http.createServer((req, res) => {
  const u = new URL(req.url, `http://${req.headers.host}`);

  if (u.pathname === '/api/health') return json(res, 200, { 
    ok: true, 
    trade_mode: TRADE_MODE, 
    live_enabled: ENABLE_LIVE_TRADING,
    ist_time: formatISTTime(),
    ist_datetime: formatISTDateTime(),
  });
  
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
  
  if (u.pathname === '/api/export') {
    try {
      const format = u.searchParams.get('format') || 'csv';
      const result = exportTrades(format);
      if (!result) {
        return json(res, 500, { error: 'Failed to export trades' });
      }
      return json(res, 200, { 
        success: true, 
        filename: result.filename, 
        count: result.count,
        download_url: `/exports/${result.filename}`,
        ist_time: formatISTTime(),
      });
    } catch (e) {
      return json(res, 500, { error: String(e) });
    }
  }
  
  if (u.pathname === '/api/broker-limits') {
    try {
      return json(res, 200, getBrokerLimitsStatus());
    } catch (e) {
      return json(res, 500, { error: String(e) });
    }
  }
  
  if (u.pathname.startsWith('/exports/')) {
    const filename = path.basename(u.pathname);
    return serveExportFile(filename, res);
  }

  serveStatic(u.pathname, res);
});

initPaperEngine();

server.listen(PORT, () => {
  console.log(`Node UI running: http://127.0.0.1:${PORT}`);
  console.log(`Trade report: http://127.0.0.1:${PORT}/trades.html`);
  console.log(`IST Time: ${formatISTDateTime()}`);
});
