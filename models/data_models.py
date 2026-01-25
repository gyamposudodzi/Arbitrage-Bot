from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class ArbitrageOpportunity:
    pair: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread: float
    spread_percentage: float
    timestamp: float
    # NEW: Fee-aware fields
    buy_fee: float = 0.0
    sell_fee: float = 0.0
    net_spread_percentage: float = 0.0
    actual_profit_percentage: float = 0.0

@dataclass
class TriangularOpportunity:
    """
    Represents a triangular arbitrage opportunity on a single exchange.
    Path example: ['USDT', 'BTC', 'ETH', 'USDT']
    """
    exchange: str
    path: List[str]
    rates: List[float]  # Exchange rates for each step
    actions: List[str]  # 'BUY' or 'SELL' for each step
    initial_amount: float
    final_amount: float
    profit: float
    profit_percentage: float
    timestamp: float

@dataclass
class FundingOpportunity:
    """
    Represents a funding rate arbitrage opportunity (Long/Short Delta Neutral).
    """
    pair: str
    exchange: str
    funding_rate: float        # e.g., 0.0001 (0.01%)
    annualized_rate: float     # e.g. 10.95%
    next_funding_time: float   # Timestamp
    mark_price: float
    timestamp: float