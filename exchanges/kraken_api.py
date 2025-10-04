import aiohttp
from typing import Dict, List
from .base_exchange import BaseExchangeAPI

class KrakenAPI(BaseExchangeAPI):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "kraken"
        self.base_url = "https://api.kraken.com/0"
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to XBTUSDT (Kraken uses different symbols)
        mapping = {
            "BTC-USDT": "XBTUSDT",
            "ETH-USDT": "ETHUSDT",
            "ADA-USDT": "ADAUSDT"
        }
        return mapping.get(pair, pair.replace("-", ""))
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            pairs_param = ",".join([self.normalize_pair(pair) for pair in pairs])
            async with session.get(f"{self.base_url}/public/Ticker?pair={pairs_param}") as response:
                if response.status == 200:
                    data = await response.json()
                    for pair in pairs:
                        normalized = self.normalize_pair(pair)
                        if normalized in data['result']:
                            # Kraken returns array with [bid, ask, ...]
                            prices[pair] = float(data['result'][normalized]['b'][0])
                else:
                    print(f"Kraken API error: {response.status}")
        except Exception as e:
            print(f"Kraken error: {e}")
        
        return prices