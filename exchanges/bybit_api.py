import aiohttp
from typing import Dict, List
from .base_exchange import BaseExchangeAPI

class BybitAPI(BaseExchangeAPI):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "bybit"
        self.base_url = "https://api.bybit.com"
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTCUSDT
        return pair.replace("-", "")
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            # Bybit spot tickers endpoint
            async with session.get(f"{self.base_url}/spot/v3/public/quote/ticker/24hr") as response:
                if response.status == 200:
                    data = await response.json()
                    if data['retCode'] == 0:  # Bybit success code
                        # Create lookup dictionary
                        tickers = {}
                        for item in data['result']['list']:
                            if item['bid1Price']:  # Use bid price
                                try:
                                    tickers[item['s']] = float(item['bid1Price'])
                                except (ValueError, TypeError):
                                    continue
                        
                        for pair in pairs:
                            normalized = self.normalize_pair(pair)
                            if normalized in tickers:
                                prices[pair] = tickers[normalized]
                else:
                    print(f"Bybit API error: {response.status}")
        except Exception as e:
            print(f"Bybit error: {e}")
        
        return prices