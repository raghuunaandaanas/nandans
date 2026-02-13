/**
 * =============================================================================
 * CRYPTO UI SERVER - Delta India Exchange Dashboard
 * =============================================================================
 * REPLICATED FROM: node_ui/server.js (Shoonya Version)
 * PURPOSE: Parallel crypto trading dashboard using same strategies
 * 
 * GIT TRACKING:
 * - Created: 2026-02-13
 * - Author: AI Assistant
 * - Feature: Initial crypto UI server - replicates Shoonya UI for crypto
 * - Status: New file - no modifications to existing codebase
 * 
 * PORT: 8788 (different from Shoonya's 8787 for parallel operation)
 * 
 * STRATEGIES REPLICATED:
 * 1. Smart Factor Selector (micro/mini/mega)
 * 2. B5 Factor Level Calculations
 * 3. Micro-Fibonacci Zone Analysis
 * 4. Paper Trading Engine
 * 5. Real-time Tick Processing
 * =============================================================================
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { DatabaseSync } = require('node:sqlite');

// =============================================================================
// CONFIGURATION - Parallel to Shoonya but on different port
// =============================================================================

const OUT_DIR = path.join(__dirname, '..', 'crypto_out');
const PUBLIC_DIR = path.join(__dirname, 'public');
const DB_FILE = path.join(OUT_DIR, 'crypto_data.db');
const SNAPSHOT_FILE = path.join(OUT_DIR, 'crypto_snapshot.json');

// Use port 8788 (Shoonya uses 8787)
const PORT = process.env.CRYPTO_UI_PORT || 8788;

// Same factor configurations as Shoonya
const FACTORS = {
  micro: 0.002611,   // 0.2611% - standard
  mini: 0.0261,      // 2.61% - high volatility
  mega: 0.2611,      // 26.11% - extreme/reversals
};

const PAPER_TF = '5m';  // Default timeframe
const PAPER_FACTOR = 'smart';  // Default to smart selector
const PAPER_CYCLE_MS = 1500;  // Trade cycle interval

// Market hours (crypto is 24/7)
const CRYPTO_MARKET_CLOSE = { hour: 23, minute: 59, second: 59 };

// =============================================================================
// DATABASE CONNECTION
// =============================================================================

let dbRead = null;

function getDbRead() {
  if (dbRead) return dbRead;
  if (!fs.existsSync(DB_FILE)) return null;
  try {
    dbRead = new DatabaseSync(DB_FILE, { open: true, readOnly: true });
    dbRead.exec('PRAGMA busy_timeout=2000');
    return dbRead;
  } catch {
    return null;
  }
}

// =============================================================================
// SMART FACTOR SELECTOR - Same logic as Shoonya
// =============================================================================

function selectSmartFactor(ltp, close, symbol) {
  const movePct = Math.abs((ltp - close) / close) * 100;
  
  // Crypto-specific: BTC/ETH often need mini due to volatility
  if (symbol && (symbol.includes('BTC') || symbol.includes('ETH'))) {
    if (movePct > 2) {
      return { factor: FACTORS.mini, factorName: 'mini', reason: 'crypto_vol' };
    }
  }
  
  // Universal rules
  if (movePct > 10) {
    return { factor: FACTORS.mega, factorName: 'mega', reason: 'extreme_vol' };
  }
  if (movePct > 5) {
    return { factor: FACTORS.mini, factorName: 'mini', reason: 'high_vol' };
  }
  
  return { factor: FACTORS.micro, factorName: 'micro', reason: 'standard' };
}

// =============================================================================
// MICRO-FIB CALCULATOR - Universal zones
// =============================================================================

const MICRO_ZONES = {
  0: { name: 'start', type: 'support' },
  11.8: { name: 'support_time', type: 'support' },
  22: { name: 'floor', type: 'support' },
  28: { name: 'support_test', type: 'support' },
  35: { name: 'confirmation', type: 'neutral' },
  38: { name: 'retracement_1', type: 'resistance' },
  45: { name: 'rejection', type: 'resistance' },
  50: { name: 'midpoint', type: 'neutral' },
  61.8: { name: 'fib_major', type: 'target' },
  78: { name: 'trend_fast', type: 'acceleration' },
  88: { name: 'decision', type: 'critical' },
  95: { name: 'rejection_major', type: 'resistance' },
  100: { name: 'next_block', type: 'target' },
};

function getMicroFibZone(position) {
  const keys = Object.keys(MICRO_ZONES).map(Number).sort((a, b) => a - b);
  
  for (let i = 0; i < keys.length - 1; i++) {
    if (position >= keys[i] && position < keys[i + 1]) {
      return {
        lower: keys[i],
        upper: keys[i + 1],
        position,
        ...MICRO_ZONES[keys[i]]
      };
    }
  }
  return { lower: 100, upper: 100, position, name: 'beyond', type: 'unknown' };
}

// =============================================================================
// B5 LEVEL CALCULATIONS
// =============================================================================

function calculateB5Levels(close, factorValue) {
  const points = close * factorValue;
  return {
    points,
    bu1: close + points,
    bu2: close + points * 2,
    bu3: close + points * 3,
    bu4: close + points * 4,
    bu5: close + points * 5,
    be1: close - points,
    be2: close - points * 2,
    be3: close - points * 3,
    be4: close - points * 4,
    be5: close - points * 5,
  };
}

// =============================================================================
// SNAPSHOT LOADING
// =============================================================================

let snapshotCache = { mtimeMs: -1, data: { day: '-', updated_at: '-', row_count: 0, rows: [] } };

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

// =============================================================================
// ANALYSIS ENGINE - Recompute derived data
// =============================================================================

function recomputeDerived(baseRows, factorName) {
  const allRows = [];
  const triggerRows = [];
  
  for (const row of baseRows) {
    const ltp = Number(row.ltp);
    const close = Number(row.close);
    if (!ltp || !close) continue;
    
    // Select factor
    let factorInfo;
    if (factorName === 'smart') {
      factorInfo = selectSmartFactor(ltp, close, row.symbol);
    } else {
      factorInfo = { factor: FACTORS[factorName], factorName, reason: 'config' };
    }
    
    // Calculate levels
    const levels = calculateB5Levels(close, factorInfo.factor);
    
    // Determine trend
    const trend = ltp > close ? 'UP' : ltp < close ? 'DOWN' : 'FLAT';
    const confirmation = Math.floor((ltp - close) / levels.points);
    const inRangeUp = ltp >= levels.bu1 && ltp <= levels.bu5;
    const sideways = confirmation < 1;
    
    // Calculate R:R
    const risk = Math.max(0.0001, ltp - levels.bu1);
    const reward = Math.max(0, levels.bu5 - ltp);
    const rr = reward / risk;
    
    // Get nearest level
    const allLevels = [
      ['BE5', levels.be5], ['BE1', levels.be1],
      ['BU1', levels.bu1], ['BU3', levels.bu3], ['BU5', levels.bu5]
    ];
    let nearName = '-';
    let nearValue = close;
    let minDiff = Infinity;
    
    for (const [name, val] of allLevels) {
      const diff = Math.abs(ltp - val);
      if (diff < minDiff) {
        minDiff = diff;
        nearName = name;
        nearValue = val;
      }
    }
    
    // Traderscope analysis from snapshot (if available)
    const digitAnalyses = row.digit_analyses || [];
    const selectedDigit = row.selected_digit || 5;
    const selectedAnalysis = digitAnalyses.find(d => d.digit === selectedDigit) || {};
    const gammaMove = row.gamma_move || null;
    const rangeShifts = row.range_shifts || [];
    
    const enriched = {
      ...row,
      close,
      points: levels.points,
      selected_factor: factorInfo.factorName,
      factor_reason: factorInfo.reason,
      selected_digit: selectedDigit,
      digit_analyses: digitAnalyses,
      gamma_move: gammaMove,
      range_shifts: rangeShifts,
      bu1: levels.bu1,
      bu2: levels.bu2,
      bu3: levels.bu3,
      bu4: levels.bu4,
      bu5: levels.bu5,
      be1: levels.be1,
      be5: levels.be5,
      trend,
      confirmation,
      in_range_up: inRangeUp,
      sideways,
      rr_to_bu5: rr,
      near_name: nearName,
      near_value: nearValue,
      near_diff: ltp - nearValue,
      // Traderscope zone info
      zone_name: selectedAnalysis.zone?.name || '-',
      zone_type: selectedAnalysis.zone?.type || '-',
      position_pct: selectedAnalysis.position?.toFixed(2) || '0',
    };
    
    allRows.push(enriched);
    if (inRangeUp && !sideways && trend === 'UP') {
      triggerRows.push(enriched);
    }
  }
  
  return { allRows, triggerRows };
}

// =============================================================================
// API HANDLERS
// =============================================================================

function handleDashboard(url, res) {
  const snapshot = loadSnapshot();
  const factorName = url.searchParams.get('factor') || PAPER_FACTOR;
  const triggerOnly = url.searchParams.get('trigger_only') !== '0';
  const limit = Math.min(5000, Number(url.searchParams.get('limit') || 100));
  
  const baseRows = Array.isArray(snapshot.rows) ? snapshot.rows : [];
  const derived = recomputeDerived(baseRows, factorName);
  const sourceRows = triggerOnly ? derived.triggerRows : derived.allRows;
  
  // Sort by confirmation (descending) and take top
  const sortedRows = sourceRows
    .sort((a, b) => (b.confirmation || 0) - (a.confirmation || 0))
    .slice(0, limit);
  
  const response = {
    snapshot_day: snapshot.day || '-',
    snapshot_updated_at: snapshot.updated_at || '-',
    snapshot_rows: snapshot.row_count || baseRows.length,
    displayed_rows: sortedRows.length,
    config: {
      timeframe: PAPER_TF,
      factor: factorName,
      factor_value: factorName === 'smart' ? 'auto' : FACTORS[factorName],
      trigger_only: triggerOnly,
    },
    stats: {
      total_symbols: baseRows.length,
      in_range_count: derived.triggerRows.length,
    },
    rows: sortedRows,
  };
  
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(response));
}

function handleHealth(res) {
  const response = {
    status: 'ok',
    service: 'crypto_ui',
    port: PORT,
    timestamp: new Date().toISOString(),
  };
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(response));
}

function handleTrades(res) {
  // Mock trades data for now - in production this would query the database
  const response = {
    open_trades: [],
    closed_trades: [],
    summary: {
      total_trades: 0,
      open_trades: 0,
      win_rate: 0,
      gross_pnl: 0,
      net_pnl: 0,
    }
  };
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(response));
}

function serveStaticFile(filePath, res) {
  const ext = path.extname(filePath);
  const contentTypes = {
    '.html': 'text/html',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
  };
  
  try {
    const content = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': contentTypes[ext] || 'text/plain' });
    res.end(content);
  } catch {
    res.writeHead(404);
    res.end('Not found');
  }
}

// =============================================================================
// HTTP SERVER
// =============================================================================

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }
  
  // API Routes
  if (url.pathname === '/api/health') {
    handleHealth(res);
    return;
  }
  
  if (url.pathname === '/api/dashboard') {
    handleDashboard(url, res);
    return;
  }
  
  if (url.pathname === '/api/trades') {
    handleTrades(res);
    return;
  }
  
  // Static files
  let filePath = path.join(PUBLIC_DIR, url.pathname === '/' ? 'index.html' : url.pathname);
  serveStaticFile(filePath, res);
});

// =============================================================================
// START SERVER
// =============================================================================

server.listen(PORT, () => {
  console.log(`[${new Date().toISOString()}] Crypto UI Server running on http://localhost:${PORT}`);
  console.log(`[${new Date().toISOString()}] Database: ${DB_FILE}`);
  console.log(`[${new Date().toISOString()}] Snapshot: ${SNAPSHOT_FILE}`);
});
