import aiohttp
from typing import Dict, List
from .base_exchange import BaseExchangeAPI

class CoinbaseAPI(BaseExchangeAPI):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "coinbase"
        self.base_url = "https://api.pro.coinbase.com"
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTC-USDT (Coinbase uses dashes)
        return pair.replace("-", "-")
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        for pair in pairs:
            try:
                normalized = self.normalize_pair(pair)
                async with session.get(f"{self.base_url}/products/{normalized}/ticker") as response:
                    if response.status == 200:
                        data = await response.json()
                        prices[pair] = float(data['bid'])
                    else:
                        print(f"Coinbase API error for {pair}: {response.status}")
            except Exception as e:
                print(f"Coinbase error for {pair}: {e}")
        
        return prices