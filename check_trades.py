import sqlite3

db = sqlite3.connect('crypto_app/crypto_out/crypto_data.db')
db.row_factory = sqlite3.Row

# Count open trades
cursor = db.execute("SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'")
open_count = cursor.fetchone()[0]
print(f"Open trades: {open_count}")

# Total trades
cursor = db.execute("SELECT COUNT(*) FROM paper_trades")
total = cursor.fetchone()[0]
print(f"Total trades: {total}")

# Closed with PnL
cursor = db.execute("SELECT COUNT(*), SUM(pnl) FROM paper_trades WHERE status='CLOSED' AND pnl IS NOT NULL")
closed, pnl = cursor.fetchone()
print(f"Closed trades: {closed}")
print(f"Total PnL: {round(pnl or 0, 2)}")

# Recent 10 trades
print("\nRecent trades:")
cursor = db.execute("SELECT symbol, entry_price, status, pnl, sl_price, tp_price FROM paper_trades ORDER BY entry_time DESC LIMIT 10")
for row in cursor.fetchall():
    pnl_str = f"PnL: {row['pnl']:.2f}" if row['pnl'] else "OPEN"
    print(f"  {row['symbol']}: Entry {row['entry_price']:.2f} | SL {row['sl_price']:.2f} | TP {row['tp_price']:.2f} | {row['status']} | {pnl_str}")
