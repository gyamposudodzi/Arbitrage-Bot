import aiohttp
from typing import Dict, List
from .base_exchange import BaseExchangeAPI

class OKXAPI(BaseExchangeAPI):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "okx"
        self.base_url = "https://www.okx.com/api/v5"
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTC-USDT (OKX uses dashes)
        return pair.replace("-", "-")
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            # OKX tickers endpoint
            async with session.get(f"{self.base_url}/market/tickers?instType=SPOT") as response:
                if response.status == 200:
                    data = await response.json()
                    if data['code'] == '0':  # OKX success code
                        # Create lookup dictionary
                        tickers = {}
                        for item in data['data']:
                            if item['bidPx']:  # Use bid price
                                try:
                                    tickers[item['instId']] = float(item['bidPx'])
                                except (ValueError, TypeError):
                                    continue
                        
                        for pair in pairs:
                            normalized = self.normalize_pair(pair)
                            if normalized in tickers:
                                prices[pair] = tickers[normalized]
                else:
                    print(f"OKX API error: {response.status}")
        except Exception as e:
            print(f"OKX error: {e}")
        
        return prices