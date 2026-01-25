import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class BasisOpportunity:
    pair: str           # e.g. BTC-USDT
    future_symbol: str  # e.g. BTCUSD_250627
    spot_price: float
    future_price: float
    basis: float
    basis_percent: float
    days_to_expiry: int
    apr: float          # Annualized Percentage Rate
    timestamp: float

class BasisArbitrageEngine:
    def __init__(self, bot):
        self.bot = bot
        
    def _parse_expiry_date(self, symbol: str) -> Optional[datetime]:
        """
        Parse expiry from symbol like BTCUSD_250627 (YYMMDD)
        """
        try:
            # Split by underscore, take last part
            parts = symbol.split("_")
            if len(parts) < 2: return None
            
            date_str = parts[-1] # "250627"
            # Parse YYMMDD
            expiry = datetime.strptime(date_str, "%y%m%d")
            # Set to UTC
            expiry = expiry.replace(tzinfo=timezone.utc)
            return expiry
        except ValueError:
            return None

    def find_opportunities(self, delivery_data: List[Dict], spot_prices: Dict[str, float]) -> List[BasisOpportunity]:
        """
        Find profitable basis trades.
        delivery_data: from Binance dapi (COIN-M)
        spot_prices: from Binance Spot
        """
        opportunities = []
        now = datetime.now(timezone.utc)
        
        for item in delivery_data:
            # Symbol: BTCUSD_250627
            future_symbol = item['symbol']
            pair_base = item['pair'] # e.g. BTCUSD
            
            # Map BTCUSD -> BTC-USDT for Spot check
            # COIN-M is usually Quote=USD. Spot is usually Quote=USDT.
            # We assume BTC-USDT spot price is close enough to BTC-USD index for checking yield.
            # Ideally we check the Index Price but Spot is what we BUY.
            
            asset = pair_base.replace("USD", "") # BTC
            spot_pair = f"{asset}-USDT"
            
            if spot_pair not in spot_prices:
                continue
                
            spot_price = spot_prices[spot_pair]
            future_price = float(item.get('markPrice', 0)) # Use Mark Price for accuracy
            
            if spot_price <= 0 or future_price <= 0:
                continue
                
            # Calcs
            basis = future_price - spot_price
            basis_percent = (basis / spot_price) * 100
            
            # Expiry
            expiry = self._parse_expiry_date(future_symbol)
            if not expiry: continue
            
            delta = expiry - now
            days_to_expiry = delta.days
            
            if days_to_expiry <= 0: continue
            
            # Annualized Yield (APR)
            # APR = (Basis% / Days) * 365
            apr = (basis_percent / days_to_expiry) * 365
            
            if apr > 5.0: # Filter for decent yields (>5%)
                opportunities.append(BasisOpportunity(
                    pair=spot_pair,
                    future_symbol=future_symbol,
                    spot_price=spot_price,
                    future_price=future_price,
                    basis=basis,
                    basis_percent=basis_percent,
                    days_to_expiry=days_to_expiry,
                    apr=apr,
                    timestamp=time.time()
                ))
                
        # Sort by APR descending
        opportunities.sort(key=lambda x: x.apr, reverse=True)
        return opportunities
