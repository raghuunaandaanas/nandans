# Smart Factor Selector

## Overview
The Smart Factor Selector automatically chooses the best B5 Factor (0.2611%, 2.61%, or 26.11%) based on:
- **Instrument type** (Index, Option, Future, Equity, MCX Commodity)
- **Price volatility** (how much price has moved from first close)

## Selection Logic

### MCX Commodities
- Always use **mini (2.61%)** for commodities
- Reason: MCX prices move differently than equities

### Indices (NIFTY, BANKNIFTY, FINNIFTY, SENSEX)
- Always use **micro (0.2611%)**
- Reason: Indices need fine-grained levels for scalping

### Options (NFO, BFO, or symbols ending with CE/PE)
- **mega (26.11%)** if price moved > 10% → Extreme volatility
- **mini (2.61%)** if price moved > 5% → High volatility  
- **micro (0.2611%)** otherwise → Standard

### Futures (symbols containing FUT)
- **mini (2.61%)** if price moved > 3%
- **micro (0.2611%)** otherwise

### Equities
- **mega (26.11%)** if price moved > 8% → Extreme volatility
- **mini (2.61%)** if price moved > 3% → High volatility
- **micro (0.2611%)** otherwise → Standard

## Usage

### Web UI
1. Select "🧠 Smart (Auto)" from the Factor dropdown
2. The Factor column will show which factor was selected for each symbol:
   - 🟢 **MICRO** (green) - 0.2611% - Standard scalping
   - 🟡 **MINI** (amber) - 2.61% - High volatility
   - 🔴 **MEGA** (red) - 26.11% - Extreme volatility

### API
```
GET /api/dashboard?factor=smart&limit=100
```

Response includes:
- `config.factor`: "smart"
- `config.factor_value`: "auto"
- Each row has:
  - `selected_factor`: "micro" | "mini" | "mega"
  - `factor_reason`: why this factor was chosen
  - `points`: calculated points based on selected factor

### Environment Variable
```bash
PAPER_FACTOR=smart  # Default
```

## Examples

| Symbol | LTP | First Close | Move % | Selected Factor | Reason |
|--------|-----|-------------|--------|-----------------|--------|
| MCX|GOLD | 78000 | 75000 | 4% | **mini** | mcx_commodity |
| NFO|NIFTY | 22450 | 22400 | 0.2% | **micro** | standard_option |
| BFO|SENSEX | 74000 | 73500 | 0.7% | **micro** | standard_option |
| NFO|BANKNIFTY | 48000 | 45000 | 6.7% | **mini** | high_volatility_option |
| BFO|Option | 1725 | 1290 | 33.7% | **mega** | extreme_volatility_option |

## Benefits

1. **No manual switching** - System automatically picks the right factor
2. **Adapts to volatility** - High volatility → Larger factors for bigger targets
3. **Per-symbol selection** - Each symbol can have a different factor based on its movement
4. **Optimized for scalping** - Small moves use micro, big moves use mini/mega

## Trade Management

As you mentioned, most trades don't hit BU5. They exit at BU3 or BU4. The smart selector helps by:
- Using **micro** for quick scalps (small targets)
- Using **mini/mega** for bigger moves (larger targets)
- Automatically adjusting as volatility changes

Each trade is still managed individually after entry - the factor just determines the initial level spacing.
