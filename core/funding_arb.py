import time
from typing import List, Dict
from models.data_models import FundingOpportunity

class FundingRateArbitrageEngine:
    def __init__(self, bot):
        self.bot = bot
        self.min_annual_rate = 10.0 # Minimum 10% APY to consider
        
    def find_opportunities(self, funding_data: List[Dict], exchange_name: str = "binance") -> List[FundingOpportunity]:
        """
        Analyze funding data and return profitable opportunities.
        """
        opportunities = []
        
        for item in funding_data:
            try:
                # API returns strings usually
                symbol = item['symbol']
                last_funding_rate = float(item['lastFundingRate'])
                mark_price = float(item['markPrice'])
                next_funding_time = int(item['nextFundingTime']) / 1000 # Convert ms to s
                
                # We are looking for POSITIVE funding rates.
                # Positive rate = Longs pay Shorts.
                # Strategy: Open SHORT in Futures, Buy SPOT.
                # We collect the fee.
                
                if last_funding_rate > 0:
                    # Calculate Annualized Rate
                    # Standard interval is 8 hours (3 times a day)
                    daily_rate = last_funding_rate * 3
                    annualized_rate = daily_rate * 365 * 100 # Percentage
                    
                    if annualized_rate >= self.min_annual_rate:
                        opp = FundingOpportunity(
                            pair=symbol,
                            exchange=exchange_name,
                            funding_rate=last_funding_rate,
                            annualized_rate=annualized_rate,
                            next_funding_time=next_funding_time,
                            mark_price=mark_price,
                            timestamp=time.time()
                        )
                        opportunities.append(opp)
                        
            except (KeyError, ValueError):
                continue
                
        # Sort by best APY
        opportunities.sort(key=lambda x: x.annualized_rate, reverse=True)
        
        return opportunities
