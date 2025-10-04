import aiohttp
from typing import Dict, List
from .base_exchange import BaseExchangeAPI

class BinanceAPI(BaseExchangeAPI):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "binance"
        self.base_url = "https://api.binance.com/api/v3"
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTCUSDT
        return pair.replace("-", "")
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            async with session.get(f"{self.base_url}/ticker/bookTicker") as response:
                if response.status == 200:
                    data = await response.json()
                    # Convert to dict for easy lookup
                    price_dict = {item['symbol']: float(item['bidPrice']) for item in data}
                    
                    for pair in pairs:
                        normalized = self.normalize_pair(pair)
                        if normalized in price_dict:
                            prices[pair] = price_dict[normalized]
                else:
                    print(f"Binance API error: {response.status}")
        except Exception as e:
            print(f"Binance error: {e}")
        
        return prices