import aiohttp
from typing import Dict, List
from .base_exchange import BaseExchangeAPI

class GateIOAPI(BaseExchangeAPI):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "gateio"
        self.base_url = "https://api.gateio.ws/api/v4"
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTC_USDT (Gate.io uses underscores)
        return pair.replace("-", "_")
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            # Gate.io tickers endpoint
            async with session.get(f"{self.base_url}/spot/tickers") as response:
                if response.status == 200:
                    data = await response.json()
                    # Create lookup dictionary
                    tickers = {}
                    for item in data:
                        if item['lowest_ask']:  # Use lowest ask as approximate bid
                            try:
                                tickers[item['currency_pair']] = float(item['lowest_ask'])
                            except (ValueError, TypeError):
                                continue
                    
                    for pair in pairs:
                        normalized = self.normalize_pair(pair)
                        if normalized in tickers:
                            prices[pair] = tickers[normalized]
                else:
                    print(f"Gate.io API error: {response.status}")
        except Exception as e:
            print(f"Gate.io error: {e}")
        
        return prices