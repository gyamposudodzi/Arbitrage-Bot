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