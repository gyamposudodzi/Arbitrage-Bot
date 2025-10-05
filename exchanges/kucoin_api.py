import aiohttp
from typing import Dict, List
from .base_exchange import BaseExchangeAPI

class KuCoinAPI(BaseExchangeAPI):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "kucoin"
        self.base_url = "https://api.kucoin.com/api/v1"
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTC-USDT (KuCoin uses dashes)
        return pair.replace("-", "-")
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            # KuCoin all tickers endpoint
            async with session.get(f"{self.base_url}/market/allTickers") as response:
                if response.status == 200:
                    data = await response.json()
                    if data['code'] == '200000':  # KuCoin success code
                        # FIXED: Filter out items with None prices
                        tickers = {}
                        for item in data['data']['ticker']:
                            if item['last'] is not None:  # 👈 KEY FIX
                                try:
                                    tickers[item['symbol']] = float(item['last'])
                                except (ValueError, TypeError):
                                    # Skip if price can't be converted to float
                                    continue
                        
                        for pair in pairs:
                            normalized = self.normalize_pair(pair)
                            if normalized in tickers:
                                prices[pair] = tickers[normalized]
                else:
                    print(f"KuCoin API error: {response.status}")
        except Exception as e:
            print(f"KuCoin error: {e}")
        
        return prices