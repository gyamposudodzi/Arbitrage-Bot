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
            # Get all spot tickers
            url = f"{self.base_url}/v5/market/tickers?category=spot"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['retCode'] == 0:
                        # Build ticker dictionary with EXACT matching
                        all_tickers = {}
                        for item in data['result']['list']:
                            symbol = item['symbol']
                            bid_price = item.get('bid1Price')
                            if bid_price and bid_price.strip():
                                try:
                                    all_tickers[symbol] = float(bid_price)
                                except (ValueError, TypeError):
                                    continue
                        
                        # Debug: Show exact matches for our pairs
                        print(f"🔍 Bybit exact pair matching:")
                        
                        for pair in pairs:
                            exact_symbol = self.normalize_pair(pair)  # BTC-USDT → BTCUSDT
                            
                            if exact_symbol in all_tickers:
                                prices[pair] = all_tickers[exact_symbol]
                                #print(f"✅ Bybit {pair} → {exact_symbol}: ${prices[pair]:.4f}")
                            else:
                                # If exact match not found, skip this pair
                                #print(f"❌ Bybit {pair}: {exact_symbol} not found in available pairs")
                                continue
                                # DO NOT try to match with similar symbols - this causes wrong matches!
                    
                    else:
                        print(f"❌ Bybit API error: {data['retMsg']}")
                else:
                    print(f"❌ Bybit HTTP error {response.status}")
                    
        except Exception as e:
            print(f"❌ Bybit exception: {e}")
        
        return prices