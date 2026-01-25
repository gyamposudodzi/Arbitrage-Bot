-- Trade History Table
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    strategy_type TEXT NOT NULL, -- 'STANDARD' or 'TRIANGULAR'
    pair TEXT,                   -- e.g. 'BTC-USDT' or 'USDT-BTC-ETH-USDT'
    buy_exchange TEXT,
    sell_exchange TEXT,
    buy_price REAL,
    sell_price REAL,
    spread REAL,
    spread_percentage REAL,
    net_profit REAL,
    status TEXT DEFAULT 'EXECUTED'
);

-- Performance Stats (Optional snapshot)
CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,
    total_trades INTEGER DEFAULT 0,
    total_profit REAL DEFAULT 0.0,
    win_rate REAL DEFAULT 0.0
);
