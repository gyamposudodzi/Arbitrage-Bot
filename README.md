# ⚡ Arbitrage Trading Bot

![Python](https://img.shields.io/badge/Python-3.12-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success)

A high-performance, multi-exchange **cryptocurrency arbitrage trading bot**. This advanced system includes **Smart Order Routing**, **Risk Management**, and support for multiple arbitrage strategies including Spot-Spot, Triangular, Funding Rates, and Spot-Future Basis.

---

## 🚀 Key Features

### 1. 🧠 Smart & Autonomous
*   **Smart Pair Retrieval (Auto-Discovery)**: Automatically fetches valid trading pairs from each exchange on startup. It filters your config against reality, preventing "Pair not found" errors.
*   **Smart Fund Awareness**: Checks your wallet balance before every trade.
    *   **Safety Gate**: Skips trades if funds < $10.
    *   **Dynamic Sizing**: Automatically resizes orders to fit your available balance (e.g., if you have $40 but config says $100, it trades $39.60).
*   **Smart Fee Management**: Calculates real-time withdrawal fees to ensure "Net Profit" is truly profitable.

### 2. 🛡️ Robust Execution Modes
*   **Normal Mode (Sequential)**: Buys on Exchange A, confirms success, then Sells on Exchange B. Safer but slower.
*   **HFT Mode (Parallel)**: Fires Buy (A) and Sell (B) orders **simultaneously** for zero-latency execution.
    *   **Atomic Rollback**: If one leg fails, the bot automatically reverses the other leg to prevent open exposure.
*   **Paper Trading**: Test strategies with simulated money (`$1000` starting balance).

### 3. 🌊 Real-Time Data
*   **Full WebSocket Support**: Subscribes to real-time ticker streams for all 7 supported exchanges.
*   **VWAP Liquidity Check**: Verifies order book depth (Volume Weighted Average Price) to ensure your trade size won't cause slippage.

---

## 📈 Arbitrage Strategies

The bot runs 4 distinct strategies concurrently:

### 1. standard Spot Arbitrage (Cross-Exchange)
*   **Logic**: Buy Low on Exchange A -> Sell High on Exchange B.
*   **Supported Exchanges**: All (Binance, Coinbase, Kraken, KuCoin, Bybit, OKX, GateIO).
*   **Requirement**: You must hold USDT on Exchange A and the Asset on Exchange B (for parallel execution).

### 2. 📐 Triangular Arbitrage
*   **Logic**: Trade within one exchange: `USDT` -> `BTC` -> `ETH` -> `USDT`.
*   **Supported Exchanges**: All.
*   **Status**: Fully implemented with Bellman-Ford path finding.

### 3. 🔮 Funding Rate Arbitrage (Delta-Neutral)
*   **Logic**: Exploits high positive funding rates on Perpetual Futures.
    *   **Action**: Buy Spot + Short Futures (1:1 hedge).
    *   **Profit**: Earn funding fees every 8 hours while being price-neutral.
*   **Supported Exchanges**: **Binance Only**.
*   **Limitation**: Requires Futures account enablement and API permissions.

### 4. 📉 Spot-Future Basis Arbitrage (Risk-Free Yield)
*   **Logic**: Exploits the price difference between Spot and **Dated (Delivery)** Futures.
    *   **Action**: Buy Spot + Short Dated Future (e.g. `BTC-JUN26`).
    *   **Profit**: Fixed spread locked in until expiry (No funding risk).
*   **Supported Exchanges**: **Binance Only**.

---

## ⚙️ Configuration

Edit `config.json` to control the bot:

```json
{
  "execution_mode": "normal",  // Options: "normal" or "hft"
  "order_type": "maker",       // Options: "maker" (Limit) or "taker" (Market)
  "trading_pairs": ["BTC-USDT", "ETH-USDT", ...],
  "exchanges": {
    "binance": { "enabled": true, "api_key": "...", "api_secret": "..." },
    ...
  },
  "live_trading": {
    "enabled": true,
    "max_trade_size": 100,
    "daily_loss_limit": 50
  },
  "rebalance": {
    "enabled": true,
    "min_balance": 200,      // Withdraw if balance > target
    "target_balance": 1000,
    "allowed_assets": ["USDT"],
    "deposit_addresses": {
      "binance": {"USDT": "TRC20_ADDRESS"},
      "kraken": {"USDT": "TRC20_ADDRESS"}
    }
  }
}
```

---

## ⚠️ Limitations & Roadmap

| Feature | Status | Supported Exchanges | Notes |
| :--- | :--- | :--- | :--- |
| **Spot Arbitrage** | ✅ Live | All 7 | Requires funds on both sides for HFT. |
| **Triangular Arb** | ✅ Live | All 7 | Profitability depends on low trading fees (BNB burn advised). |
| **Funding Arb** | ✅ Live | **Binance, Bybit, KuCoin, OKX** | Delta-Neutral Strategy. |
| **Basis Arb** | ✅ Live | **Binance Only** | Risk-Free Yield on Futures expiry. |
| **Rebalancer** | ✅ Live | All 7 | Auto-withdraws & deposits to maintain inventory. |


---

## 📦 Project Structure

```
├── main.py                   # Entry point
├── config.json               # Settings
├── core/
│   ├── arbitrage_bot.py      # Main Orchestrator
│   ├── arbitrage_engine.py   # Signal Detection
│   ├── basis_arb.py          # Spot-Future Basis Engine
│   ├── funding_arb.py        # Funding Rate Engine
│   ├── triangular_arb.py     # Triangular Engine
│   └── database_manager.py   # SQLite persistence
├── exchanges/                # API Wrappers (Unified Interface)
├── execution/                # Order Execution & Balance Mgmt
└── data/                     # Database storage
```

---

## 🛠 Installation

1.  **Clone**: `git clone https://github.com/gyamposudodzi/Arbitrage-Bot`
2.  **Install**: `pip install -r requirements.txt`
3.  **Config**: Rename `config.example.json` to `config.json` and add keys.
4.  **Run**: `python main.py`

---

## ⚠️ Disclaimer

This software is for **educational purposes**. High-Frequency Trading (HFT) involves significant risks including API rate limits, network latency, and execution slippage. Never trade money you cannot afford to lose. Use "Paper Trading" mode first!