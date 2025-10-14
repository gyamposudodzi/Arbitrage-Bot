from dataclasses import dataclass
from typing import Dict, List

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