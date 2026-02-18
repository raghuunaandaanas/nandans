import json
import hmac
import hashlib
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys
import datetime as dt

with open('delta_cred.json') as f:
    cred = json.load(f)

api_key = cred['api_key']
api_secret = cred['api_secret']

base_url = "https://api.india.delta.exchange"
cache_data = None
cache_ts = 0
cache_ttl = 5

def create_signature(method, endpoint, timestamp):
    signature_data = method + timestamp + endpoint
    signature = hmac.new(
        api_secret.encode('utf-8'),
        signature_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

def get_headers(endpoint, method="GET"):
    timestamp = str(int(time.time()))
    signature = create_signature(method, endpoint, timestamp)
    return {
        'api-key': api_key,
        'timestamp': timestamp,
        'signature': signature,
        'Content-Type': 'application/json'
    }

def get_candle_close(symbol, resolution):
    """Get the last closed candle's close price for a given symbol and resolution"""
    try:
        now_utc = dt.datetime.now(dt.timezone.utc)
        now_ist = now_utc + dt.timedelta(hours=5, minutes=30)
        today_ist = now_ist.replace(hour=5, minute=30, second=0, microsecond=0)
        today_utc = today_ist - dt.timedelta(hours=5, minutes=30)
        start = int(today_utc.timestamp())
        end = start + 3600
        url = f"{base_url}/v2/history/candles"
        params = {'symbol': symbol, 'resolution': resolution, 'start': start, 'end': end}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            result = response.json()
            if result.get('success') and result.get('result'):
                candles = result['result']
                if candles:
                    return float(candles[-1].get('close', 0))
        return None
    except:
        return None

def calc_levels(base_price):
    """Calculate BU/BE levels based on the base price"""
    if not base_price or base_price == 0:
        return None
    if base_price < 1000:
        factor = 0.2611
    elif base_price < 10000:
        factor = 0.02611
    else:
        factor = 0.002611
    pts = base_price * factor
    return {
        'base': base_price, 'pts': pts,
        'be5': base_price - pts*5, 'be4': base_price - pts*4, 'be3': base_price - pts*3,
        'be2': base_price - pts*2, 'be1': base_price - pts*1,
        'bu1': base_price + pts*1, 'bu2': base_price + pts*2, 'bu3': base_price + pts*3,
        'bu4': base_price + pts*4, 'bu5': base_price + pts*5
    }

def get_option_chain_data():
    """Fetch option chain data for nearest expiry with BTC levels and option levels"""
    
    # Get BTC price (spot)
    btc_price = 67677
    resp = requests.get(base_url + "/v2/tickers", headers=get_headers("/v2/tickers"))
    if resp.status_code == 200 and resp.json().get('success'):
        for t in resp.json()['result']:
            if t.get('symbol') == 'BTCUSD':
                btc_price = float(t.get('mark_price', 0))
                break
    
    # Get BTC 1m, 5m, 15m closing prices
    btc_1m_close = get_candle_close('BTCUSD', '1m')
    btc_5m_close = get_candle_close('BTCUSD', '5m')
    btc_15m_close = get_candle_close('BTCUSD', '15m')
    
    # If candle close not available, use spot
    if not btc_1m_close: btc_1m_close = btc_price
    if not btc_5m_close: btc_5m_close = btc_price
    if not btc_15m_close: btc_15m_close = btc_price
    
    btc_levels_1m = calc_levels(btc_1m_close)
    btc_levels_5m = calc_levels(btc_5m_close)
    btc_levels_15m = calc_levels(btc_15m_close)
    
    # Get all products
    resp = requests.get(base_url + "/v2/products", headers=get_headers("/v2/products"))
    if resp.status_code != 200:
        return None
    
    products = resp.json()['result']
    
    # Get tickers
    ticker_map = {}
    resp = requests.get(base_url + "/v2/tickers", headers=get_headers("/v2/tickers"))
    if resp.status_code == 200 and resp.json().get('success'):
        for t in resp.json()['result']:
            pid = t.get('product_id') or t.get('contract_id')
            if pid:
                ticker_map[pid] = t
    
    # Find nearest expiry - 180226 (18 Feb 2026)
    calls = [p for p in products if p.get('symbol', '').startswith('C-BTC-') and '180226' in p.get('symbol', '')]
    puts = [p for p in products if p.get('symbol', '').startswith('P-BTC-') and '180226' in p.get('symbol', '')]
    
    if not calls or not puts:
        return None
    
    calls.sort(key=lambda x: float(x.get('strike_price', 0)))
    puts.sort(key=lambda x: float(x.get('strike_price', 0)))
    
    expiry = "18-Feb-2026 (Today)"
    
    # Determine ATM strike based on BTC 1m close
    atm_idx = 0
    for i, c in enumerate(calls):
        if float(c['strike_price']) >= btc_1m_close:
            atm_idx = i
            break
    
    # Show 6 strikes above and below ATM (12 total)
    start = max(0, atm_idx - 6)
    end = min(len(calls), atm_idx + 6)
    
    options = []
    for i in range(start, end):
        call = calls[i]
        put = puts[i] if i < len(puts) else None
        
        strike = float(call['strike_price'])
        
        # Get call data
        call_t = ticker_map.get(call['id'], {})
        c_bid = float(call_t.get('best_bid') or call_t.get('bid') or 0)
        c_ask = float(call_t.get('best_ask') or call_t.get('ask') or 0)
        c_ltp = float(call_t.get('last_price') or call_t.get('mark_price') or 0)
        if not c_ltp and c_bid and c_ask:
            c_ltp = (c_bid + c_ask) / 2
        if not c_ltp:
            c_ltp = c_bid or c_ask or 0
        if not c_bid and c_ltp: c_bid = c_ltp
        if not c_ask and c_ltp: c_ask = c_ltp
        
        # Get put data
        p_bid = p_ask = p_ltp = 0
        if put:
            put_t = ticker_map.get(put['id'], {})
            p_bid = float(put_t.get('best_bid') or put_t.get('bid') or 0)
            p_ask = float(put_t.get('best_ask') or put_t.get('ask') or 0)
            p_ltp = float(put_t.get('last_price') or put_t.get('mark_price') or 0)
            if not p_ltp and p_bid and p_ask:
                p_ltp = (p_bid + p_ask) / 2
            if not p_ltp:
                p_ltp = p_bid or p_ask or 0
            if not p_bid and p_ltp: p_bid = p_ltp
            if not p_ask and p_ltp: p_ask = p_ltp
        
        is_atm = abs(strike - btc_price) < btc_price * 0.015
        
        ce_levels_1m = calc_levels(c_ltp) if c_ltp else None
        pe_levels_1m = calc_levels(p_ltp) if p_ltp else None
        
        # Determine positions based on option LTP vs levels
        def get_level_position(ltp, levels):
            if not ltp or not levels or ltp == 0:
                return "NO DATA"
            if ltp >= levels['bu5']:
                return "ABOVE BU5"
            elif ltp >= levels['bu4']:
                return "BU4-BU5"
            elif ltp >= levels['bu3']:
                return "BU3-BU4"
            elif ltp >= levels['bu2']:
                return "BU2-BU3"
            elif ltp >= levels['bu1']:
                return "BU1-BU2"
            elif ltp >= levels['base']:
                return "BASE-BU1"
            elif ltp >= levels['be1']:
                return "BE1-BASE"
            elif ltp >= levels['be2']:
                return "BE2-BE1"
            elif ltp >= levels['be3']:
                return "BE3-BE2"
            elif ltp >= levels['be4']:
                return "BE4-BE3"
            elif ltp >= levels['be5']:
                return "BE5-BE4"
            else:
                return "BELOW BE5"
        
        ce_pos_1m = get_level_position(c_ltp, ce_levels_1m) if ce_levels_1m else "NO DATA"
        pe_pos_1m = get_level_position(p_ltp, pe_levels_1m) if pe_levels_1m else "NO DATA"
        
        options.append({
            'strike': int(strike),
            'call_bid': round(c_bid, 2),
            'call_ask': round(c_ask, 2),
            'call_ltp': round(c_ltp, 2),
            'put_bid': round(p_bid, 2),
            'put_ask': round(p_ask, 2),
            'put_ltp': round(p_ltp, 2),
            'is_atm': is_atm,
            # BTC levels info
            'btc_1m': round(btc_1m_close, 2),
            'btc_5m': round(btc_5m_close, 2),
            'btc_15m': round(btc_15m_close, 2),
            'btc_base_1m': round(btc_levels_1m['base'], 2) if btc_levels_1m else 0,
            'btc_be5_1m': round(btc_levels_1m['be5'], 2) if btc_levels_1m else 0,
            'btc_be4_1m': round(btc_levels_1m['be4'], 2) if btc_levels_1m else 0,
            'btc_be3_1m': round(btc_levels_1m['be3'], 2) if btc_levels_1m else 0,
            'btc_be2_1m': round(btc_levels_1m['be2'], 2) if btc_levels_1m else 0,
            'btc_be1_1m': round(btc_levels_1m['be1'], 2) if btc_levels_1m else 0,
            'btc_bu1_1m': round(btc_levels_1m['bu1'], 2) if btc_levels_1m else 0,
            'btc_bu2_1m': round(btc_levels_1m['bu2'], 2) if btc_levels_1m else 0,
            'btc_bu3_1m': round(btc_levels_1m['bu3'], 2) if btc_levels_1m else 0,
            'btc_bu4_1m': round(btc_levels_1m['bu4'], 2) if btc_levels_1m else 0,
            'btc_bu5_1m': round(btc_levels_1m['bu5'], 2) if btc_levels_1m else 0,
            'btc_base_5m': round(btc_levels_5m['base'], 2) if btc_levels_5m else 0,
            'btc_be5_5m': round(btc_levels_5m['be5'], 2) if btc_levels_5m else 0,
            'btc_be4_5m': round(btc_levels_5m['be4'], 2) if btc_levels_5m else 0,
            'btc_be3_5m': round(btc_levels_5m['be3'], 2) if btc_levels_5m else 0,
            'btc_be2_5m': round(btc_levels_5m['be2'], 2) if btc_levels_5m else 0,
            'btc_be1_5m': round(btc_levels_5m['be1'], 2) if btc_levels_5m else 0,
            'btc_bu1_5m': round(btc_levels_5m['bu1'], 2) if btc_levels_5m else 0,
            'btc_bu2_5m': round(btc_levels_5m['bu2'], 2) if btc_levels_5m else 0,
            'btc_bu3_5m': round(btc_levels_5m['bu3'], 2) if btc_levels_5m else 0,
            'btc_bu4_5m': round(btc_levels_5m['bu4'], 2) if btc_levels_5m else 0,
            'btc_bu5_5m': round(btc_levels_5m['bu5'], 2) if btc_levels_5m else 0,
            'btc_base_15m': round(btc_levels_15m['base'], 2) if btc_levels_15m else 0,
            'btc_be5_15m': round(btc_levels_15m['be5'], 2) if btc_levels_15m else 0,
            'btc_be4_15m': round(btc_levels_15m['be4'], 2) if btc_levels_15m else 0,
            'btc_be3_15m': round(btc_levels_15m['be3'], 2) if btc_levels_15m else 0,
            'btc_be2_15m': round(btc_levels_15m['be2'], 2) if btc_levels_15m else 0,
            'btc_be1_15m': round(btc_levels_15m['be1'], 2) if btc_levels_15m else 0,
            'btc_bu1_15m': round(btc_levels_15m['bu1'], 2) if btc_levels_15m else 0,
            'btc_bu2_15m': round(btc_levels_15m['bu2'], 2) if btc_levels_15m else 0,
            'btc_bu3_15m': round(btc_levels_15m['bu3'], 2) if btc_levels_15m else 0,
            'btc_bu4_15m': round(btc_levels_15m['bu4'], 2) if btc_levels_15m else 0,
            'btc_bu5_15m': round(btc_levels_15m['bu5'], 2) if btc_levels_15m else 0,
            # CE levels for 1m
            'ce_be5': round(ce_levels_1m['be5'], 2) if ce_levels_1m else 0,
            'ce_be4': round(ce_levels_1m['be4'], 2) if ce_levels_1m else 0,
            'ce_be3': round(ce_levels_1m['be3'], 2) if ce_levels_1m else 0,
            'ce_be2': round(ce_levels_1m['be2'], 2) if ce_levels_1m else 0,
            'ce_bu1': round(ce_levels_1m['bu1'], 2) if ce_levels_1m else 0,
            'ce_bu2': round(ce_levels_1m['bu2'], 2) if ce_levels_1m else 0,
            'ce_bu3': round(ce_levels_1m['bu3'], 2) if ce_levels_1m else 0,
            'ce_bu4': round(ce_levels_1m['bu4'], 2) if ce_levels_1m else 0,
            'ce_bu5': round(ce_levels_1m['bu5'], 2) if ce_levels_1m else 0,
            'ce_be1': round(ce_levels_1m['be1'], 2) if ce_levels_1m else 0,
            'ce_base': round(ce_levels_1m['base'], 2) if ce_levels_1m else 0,
            # CE positions
            'ce_pos_1m': ce_pos_1m,
            # PE levels for 1m
            'pe_be5': round(pe_levels_1m['be5'], 2) if pe_levels_1m else 0,
            'pe_be4': round(pe_levels_1m['be4'], 2) if pe_levels_1m else 0,
            'pe_be3': round(pe_levels_1m['be3'], 2) if pe_levels_1m else 0,
            'pe_be2': round(pe_levels_1m['be2'], 2) if pe_levels_1m else 0,
            'pe_bu1': round(pe_levels_1m['bu1'], 2) if pe_levels_1m else 0,
            'pe_bu2': round(pe_levels_1m['bu2'], 2) if pe_levels_1m else 0,
            'pe_bu3': round(pe_levels_1m['bu3'], 2) if pe_levels_1m else 0,
            'pe_bu4': round(pe_levels_1m['bu4'], 2) if pe_levels_1m else 0,
            'pe_bu5': round(pe_levels_1m['bu5'], 2) if pe_levels_1m else 0,
            'pe_be1': round(pe_levels_1m['be1'], 2) if pe_levels_1m else 0,
            'pe_base': round(pe_levels_1m['base'], 2) if pe_levels_1m else 0,
            # PE positions
            'pe_pos_1m': pe_pos_1m,
        })
    
    return {
        'btc_price': round(btc_price, 2),
        'btc_1m': round(btc_1m_close, 2),
        'btc_5m': round(btc_5m_close, 2),
        'btc_15m': round(btc_15m_close, 2),
        'expiry': expiry,
        'options': options
    }

# Use simple string replacement instead of format
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Delta BTC Options Chain - LIVE with Levels</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: radial-gradient(circle at top, #1b2440 0%, #0c111f 55%, #0b0f1a 100%);
            min-height: 100vh;
            color: #e6eefc;
            margin: 0;
            padding: 24px;
        }
        .container {
            max-width: 1280px;
            margin: 0 auto;
        }
        .header h1 {
            color: #79d2ff;
            font-size: 30px;
            text-align: center;
            margin-bottom: 6px;
        }
        .live-indicator {
            text-align: center;
            color: #2bff9a;
            font-size: 12px;
            margin-bottom: 18px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .info {
            display: flex;
            justify-content: center;
            gap: 14px;
            margin-bottom: 18px;
            flex-wrap: wrap;
        }
        .info-box {
            background: rgba(255,255,255,0.06);
            padding: 12px 18px;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 6px 18px rgba(0,0,0,0.35);
            text-align: center;
            min-width: 140px;
        }
        .info-box .label { color: #9fb0c8; font-size: 10px; letter-spacing: 0.4px; }
        .info-box .value { font-size: 20px; font-weight: 700; color: #79d2ff; }
        .info-box .value.expiry { color: #ff8b8b; }
        .info-box .value.update-time { color: #2bff9a; font-size: 13px; }
        .info-box .btc-info { color: #ffd47a; font-size: 15px; }
        
        .levels-info {
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-bottom: 18px;
            flex-wrap: wrap;
            background: rgba(255,215,0,0.08);
            padding: 10px 12px;
            border-radius: 10px;
            border: 1px solid rgba(255,215,0,0.18);
        }
        .levels-info .label { color: #ffd47a; font-size: 10px; }
        .levels-info .value { color: #f7f9ff; font-size: 13px; margin: 0 4px; }
        
        .slider-bar {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin: 10px 0 18px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 8px 12px;
        }
        .slider-bar label { color: #9fb0c8; font-size: 11px; }
        .slider-bar input[type="range"] { width: 240px; }
        .slider-value { color: #79d2ff; font-weight: 700; font-size: 12px; }
        
        table { 
            width: 100%; 
            border-collapse: collapse;
            background: rgba(255,255,255,0.04);
            border-radius: 12px;
            overflow: hidden;
            font-size: 11px;
            box-shadow: 0 10px 24px rgba(0,0,0,0.35);
        }
        th { 
            background: rgba(121,210,255,0.2);
            padding: 8px 6px;
            text-align: center;
            font-size: 10px;
            color: #9fe1ff;
            position: sticky;
            top: 0;
        }
        td { 
            padding: 8px 6px;
            text-align: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        tr:nth-child(even) { background: rgba(255,255,255,0.02); }
        tr:hover { background: rgba(121,210,255,0.12); }
        tr.atm { background: rgba(121,210,255,0.25); }
        tr.atm td { font-weight: bold; }
        tr.atm td.strike { 
            color: #fff;
            background: #ff6b6b;
            border-radius: 6px;
            padding: 5px 8px;
        }
        .strike { color: #ff7b7b; font-weight: 700; }
        .call { color: #2bff9a; font-weight: 600; }
        .put { color: #ff7b7b; font-weight: 600; }
        .levels { color: #ffd47a; font-size: 9px; }
        .level-active { background: rgba(255,212,122,0.18); border-radius: 6px; }
        .position { font-size: 9px; font-weight: 700; }
        .pos-bu { color: #ff6b6b; }
        .pos-be { color: #ff6b6b; }
        .pos-base { color: #2bff9a; }
        .ltp-cell { display: flex; flex-direction: column; align-items: center; gap: 4px; }
        .ltp-val { font-weight: 700; }
        .mini-slider {
            -webkit-appearance: none;
            width: 120px;
            height: 6px;
            border-radius: 999px;
            background: linear-gradient(90deg, #ff5c5c, #ffd47a, #2bff9a);
            outline: none;
            opacity: 0.95;
        }
        .mini-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #fff;
            border: 2px solid #79d2ff;
        }
        .mini-slider::-moz-range-thumb {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #fff;
            border: 2px solid #79d2ff;
        }
        .slider-labels { width: 120px; display: flex; justify-content: space-between; font-size: 9px; color: #9fb0c8; }
        
        .sub-header {
            background: rgba(255,255,255,0.1);
            font-weight: bold;
            color: #aaa;
        }
    </style>
</head>
<body>
    <div class="container">
    <div class="header">
        <h1>Delta BTC Options Chain - With Levels</h1>
        <div class="live-indicator">● LIVE - Auto-updating every 60 seconds</div>
    </div>
    
    <div class="info">
        <div class="info-box">
            <div class="label">BTC SPOT</div>
            <div class="value" id="btc-price">{BTC_PRICE}</div>
        </div>
        <div class="info-box">
            <div class="label">BTC 1m CLOSE</div>
            <div class="value btc-info" id="btc-1m">{BTC_1M}</div>
        </div>
        <div class="info-box">
            <div class="label">BTC 5m CLOSE</div>
            <div class="value btc-info" id="btc-5m">{BTC_5M}</div>
        </div>
        <div class="info-box">
            <div class="label">BTC 15m CLOSE</div>
            <div class="value btc-info" id="btc-15m">{BTC_15M}</div>
        </div>
        <div class="info-box">
            <div class="label">EXPIRY</div>
            <div class="value expiry" id="expiry">{EXPIRY}</div>
        </div>
        <div class="info-box">
            <div class="label">LAST UPDATE</div>
            <div class="value update-time" id="last-update">--:--:--</div>
        </div>
    </div>
    
    <div class="levels-info">
        <div class="label">BTC 1m Levels:</div>
        <div class="value">BE1: <span id="BTC_BE1">{BTC_BE1}</span></div>
        <div class="value">BU1: <span id="BTC_BU1">{BTC_BU1}</span></div>
        <div class="value">BU2: <span id="BTC_BU2">{BTC_BU2}</span></div>
        <div class="value">BU3: <span id="BTC_BU3">{BTC_BU3}</span></div>
        <div class="value">BU4: <span id="BTC_BU4">{BTC_BU4}</span></div>
        <div class="value">BU5: <span id="BTC_BU5">{BTC_BU5}</span></div>
    </div>

    <div class="slider-bar">
        <label>STRIKES AROUND ATM</label>
        <input id="range-slider" type="range" min="2" max="10" step="1" value="6">
        <span class="slider-value" id="range-value">6</span>
    </div>
    
    <table>
        <thead>
            <tr>
                <th colspan="6">CALLS (CE)</th>
                <th rowspan="2">STRIKE</th>
                <th colspan="6">PUTS (PE)</th>
            </tr>
            <tr>
                <th>LTP</th>
                <th>Pos(1m)</th>
                <th>BU1</th>
                <th>BU2</th>
                <th>BU3</th>
                <th>BE1</th>
                <th>LTP</th>
                <th>Pos(1m)</th>
                <th>BU1</th>
                <th>BU2</th>
                <th>BU3</th>
                <th>BE1</th>
            </tr>
        </thead>
        <tbody id="options-body">
            {ROWS}
        </tbody>
    </table>
    
    <script>
        function formatNumber(n) {
            if (n >= 100) return Math.round(n).toLocaleString();
            if (n >= 10) return n.toFixed(1);
            return n.toFixed(2);
        }
        
        function getPosClass(pos) {
            if (pos.includes('BU')) return 'pos-bu';
            if (pos.includes('BE')) return 'pos-be';
            if (pos === 'BASE-BU1' || pos === 'BE1-BASE') return 'pos-base';
            return '';
        }
        
        function getLevelMarks(ltp, bu1, bu2, bu3, be1) {
            return {
                bu1: ltp >= bu1 && ltp < bu2,
                bu2: ltp >= bu2 && ltp < bu3,
                bu3: ltp >= bu3,
                be1: ltp < bu1 && ltp >= be1
            };
        }
        
        function clamp(v, min, max) {
            return Math.min(Math.max(v, min), max);
        }
        
        function sliderBackground(min, max, bu1, bu2) {
            const range = max - min;
            if (!isFinite(range) || range <= 0) return '';
            const p1 = Math.max(0, Math.min(100, ((bu1 - min) / range) * 100));
            const p2 = Math.max(0, Math.min(100, ((bu2 - min) / range) * 100));
            return `background: linear-gradient(90deg, #ff5c5c 0%, #ff5c5c ${p1}%, #ffd47a ${p1}%, #ffd47a ${p2}%, #2bff9a ${p2}%, #2bff9a 100%)`;
        }
        
        function buildSlider(ltp, be1, bu1, bu2, bu3) {
            const min = Math.min(be1, bu3);
            const max = Math.max(be1, bu3);
            if (!isFinite(min) || !isFinite(max) || max <= min) {
                return `<div class="ltp-val">${formatNumber(ltp)}</div>`;
            }
            const v = clamp(ltp, min, max);
            const bg = sliderBackground(min, max, bu1, bu2);
            return `<div class="ltp-cell">
                <div class="ltp-val">${formatNumber(ltp)}</div>
                <input class="mini-slider" type="range" min="${min}" max="${max}" step="0.01" value="${v}" style="${bg}" disabled>
                <div class="slider-labels"><span>Low</span><span>High</span></div>
            </div>`;
        }
        
        function buildRow(opt) {
            const atmClass = opt.is_atm ? ' class="atm"' : '';
            const atmMarker = opt.is_atm ? ' ◉ ATM' : '';
            
            const cePosClass = getPosClass(opt.ce_pos_1m);
            const pePosClass = getPosClass(opt.pe_pos_1m);
            const ceMarks = getLevelMarks(opt.call_ltp, opt.ce_bu1, opt.ce_bu2, opt.ce_bu3, opt.ce_be1);
            const peMarks = getLevelMarks(opt.put_ltp, opt.pe_bu1, opt.pe_bu2, opt.pe_bu3, opt.pe_be1);
            
            return `<tr${atmClass}>
                <td class="call">${buildSlider(opt.call_ltp, opt.ce_be1, opt.ce_bu1, opt.ce_bu2, opt.ce_bu3)}</td>
                <td class="position ${cePosClass}">${opt.ce_pos_1m}</td>
                <td class="levels ${ceMarks.bu1 ? 'level-active' : ''}">${formatNumber(opt.ce_bu1)}</td>
                <td class="levels ${ceMarks.bu2 ? 'level-active' : ''}">${formatNumber(opt.ce_bu2)}</td>
                <td class="levels ${ceMarks.bu3 ? 'level-active' : ''}">${formatNumber(opt.ce_bu3)}</td>
                <td class="levels ${ceMarks.be1 ? 'level-active' : ''}">${formatNumber(opt.ce_be1)}</td>
                <td class="strike">${opt.strike.toLocaleString()}${atmMarker}</td>
                <td class="put">${buildSlider(opt.put_ltp, opt.pe_be1, opt.pe_bu1, opt.pe_bu2, opt.pe_bu3)}</td>
                <td class="position ${pePosClass}">${opt.pe_pos_1m}</td>
                <td class="levels ${peMarks.bu1 ? 'level-active' : ''}">${formatNumber(opt.pe_bu1)}</td>
                <td class="levels ${peMarks.bu2 ? 'level-active' : ''}">${formatNumber(opt.pe_bu2)}</td>
                <td class="levels ${peMarks.bu3 ? 'level-active' : ''}">${formatNumber(opt.pe_bu3)}</td>
                <td class="levels ${peMarks.be1 ? 'level-active' : ''}">${formatNumber(opt.pe_be1)}</td>
            </tr>`;
        }
        
        function renderRows(data) {
            if (!data || !data.options) return;
            const range = parseInt(document.getElementById('range-slider').value, 10);
            const options = data.options;
            let atmIndex = options.findIndex(o => o.is_atm);
            if (atmIndex < 0) atmIndex = Math.floor(options.length / 2);
            const start = Math.max(0, atmIndex - range);
            const end = Math.min(options.length, atmIndex + range + 1);
            const tbody = document.getElementById('options-body');
            tbody.innerHTML = options.slice(start, end).map(buildRow).join('');
        }
        
        let latestData = null;
        async function updateData() {
            try {
                const resp = await fetch('/api/data');
                if (!resp.ok) return;
                const data = await resp.json();
                latestData = data;
                
                // Update header info
                document.getElementById('btc-price').textContent = formatNumber(data.btc_price);
                document.getElementById('btc-1m').textContent = formatNumber(data.btc_1m);
                document.getElementById('btc-5m').textContent = formatNumber(data.btc_5m);
                document.getElementById('btc-15m').textContent = formatNumber(data.btc_15m);
                document.getElementById('expiry').textContent = data.expiry;
                
                // Update BTC levels info (from first option)
                if (data.options && data.options.length > 0) {
                    const opt = data.options[0];
                    document.getElementById('BTC_BE1').textContent = formatNumber(opt.btc_be1);
                    document.getElementById('BTC_BU1').textContent = formatNumber(opt.btc_bu1);
                    document.getElementById('BTC_BU2').textContent = formatNumber(opt.btc_bu2);
                    document.getElementById('BTC_BU3').textContent = formatNumber(opt.btc_bu3);
                    document.getElementById('BTC_BU4').textContent = formatNumber(opt.btc_bu4);
                    document.getElementById('BTC_BU5').textContent = formatNumber(opt.btc_bu5);
                }
                
                renderRows(data);
                
                // Update timestamp
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
            } catch(e) {
                console.error('Update error:', e);
            }
        }
        
        document.getElementById('range-slider').addEventListener('input', (e) => {
            document.getElementById('range-value').textContent = e.target.value;
            renderRows(latestData);
        });
        
        // Initial load
        updateData();
        
        // Live update every 60 seconds
        setInterval(updateData, 60000);
    </script>
    </div>
</body>
</html>
"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global cache_data, cache_ts
        if self.path == '/api/data':
            # Return JSON data for live updates
            now = time.time()
            if cache_data and now - cache_ts < cache_ttl:
                data = cache_data
            else:
                data = get_option_chain_data()
                if data is not None:
                    cache_data = data
                    cache_ts = now
            if data is None:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Failed to load data'}).encode())
                return
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            try:
                self.wfile.write(json.dumps(data).encode())
            except (BrokenPipeError, ConnectionAbortedError):
                return
            return
        
        # Serve index.html
        try:
            with open('index.html', 'rb') as f:
                html = f.read()
        except:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Error loading index.html")
            return
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        try:
            self.wfile.write(html)
        except (BrokenPipeError, ConnectionAbortedError):
            return
    
    def log_message(self, format, *args):
        pass

def run_server():
    server = HTTPServer(('127.0.0.1', 3000), Handler)
    print("="*60)
    print("  Delta BTC Options Chain UI - LIVE with Levels")
    print("="*60)
    print("\nServer running at: http://127.0.0.1:3000")
    print("Features:")
    print("- BTC 1m, 5m, 15m closing prices")
    print("- ATM strike based on BTC 1m close")
    print("- Option CE/PE closes for 1m, 5m, 15m")
    print("- BU1-BU5 and BE1 levels for both options")
    print("- Position tracking (where LTP is relative to levels)")
    print("\nPress Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.shutdown()

if __name__ == "__main__":
    try:
        run_server()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
