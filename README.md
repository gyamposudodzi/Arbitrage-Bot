# ⚡ Arbitrage Trading Bot

![Python](https://img.shields.io/badge/Python-3.12-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![GitHub Repo Size](https://img.shields.io/github/repo-size/gyamposudodzi/Arbitrage-Bot)

A high-performance, multi-exchange **cryptocurrency arbitrage trading bot** designed to scan markets, detect profitable price discrepancies, and execute trades automatically. Supports **live and paper trading**, multiple exchanges, fee-aware calculations, and modular architecture.

---

## 🚀 Key Features

### 🔄 Multi-Exchange Support
Supports major exchanges through modular API wrappers:
- Binance  
- OKX  
- Bybit  
- Coinbase  
- Kraken  
- Gate.io  
- KuCoin  

Each exchange implements:
- Market data fetching    
- Order execution  
- Unified interface through `BaseExchange`

---

### ⚡ Real-Time Arbitrage Engine
Detects opportunities by:
- Fetching order book/price data  
- Calculating spreads  
- Determining profitability after fees and slippage  
- Executing trades automatically  

Core logic lives in:

```

core/arbitrage_engine.py
core/arbitrage_bot.py

```

---

### 💰 Fee & Profitability Handling
Uses a dedicated module to ensure accurate calculations:

```

core/fee_calculator.py

```

Handles:
- Exchange-specific fee structures  
- Profitability validation before execution  

---

### 📈 Live vs Paper Trading
Two trading modes:
```

core/live_trader.py(In development)      # Executes real trades
core/paper_trader.py     # Simulated trading for testing

```

Paper trading allows **risk-free strategy testing** before going live.

---

### 🧱 Modular Order Execution
Each exchange has its own order execution class, inheriting from a shared base:

```

order_execution/base_order.py
order_execution/binance_order.py
...

```

Benefits:
- Clean abstraction  
- Easy extension to new exchanges  
- Reliable error handling  

---

### 📦 Project Structure

```

├── main.py                   # Entry point for running the bot
├── config.json               # API keys and runtime settings
├── debug_prices.py           # Debugging tool for price feeds
├── core/                     # Core engine and trading logic
├── exchanges/                # Exchange API wrappers
├── order_execution/          # Order-building & execution logic
├── models/                   # Data models & type definitions
├── requirements.txt
├── README.md
└── LICENSE

````

---

## ⚙️ How It Works

### 1. Price Fetching
Each exchange exposes unified methods:

```python
Find_opportunities()
get_price()
````

### 2. Opportunity Detection

Calculates the spread:

```python
spread = (sell_price - buy_price) / buy_price * 100
```

Validates:

* Fees
* Minimum profit threshold
* Liquidity
* Trade amount

### 3. Execution Layer

`live_trader.py(in development)` or `paper_trader.py` handles:

* Coordinated buy/sell orders
* Order tracking
* Error handling
* Logging

---

## 🛠 Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/gyamposudodzi/Arbitrage-Bot
cd arbitrage-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API keys

Edit `config.json`:

```json
{
  "min_profit_percent": 0.2,
  "trade_amount": 50,
  "exchanges": {
    "binance": { "apiKey": "", "secret": "" },
    "okx": { "apiKey": "", "secret": "" },
    "kraken": { "apiKey": "", "secret": "" }
  }
}
```

### 4. Run the bot

```bash
python main.py
```

---

## 🎯 Project Goals

* Modular, extendable arbitrage framework
* Easy testing on multiple exchanges
* Reliable fee-aware spread evaluation
* Expandable into **Triangular Arbitrage**

---

## 🧪 Testing & Debugging

Verify exchange connections and price feeds:

```bash
python debug_prices.py
```

---

## ⚠️ Disclaimer

This project is for **educational and research purposes only**.
Cryptocurrency trading carries **significant financial risk**.
Use responsibly and at your own risk.

---

## 🤝 Contributing

Not taking one at the Moment. But I am very sure i will

---

## 📄 License

[MIT License](LICENSE)


```
