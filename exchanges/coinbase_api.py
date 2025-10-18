import aiohttp
from typing import Dict, List
from .base_exchange import BaseExchangeAPI

class CoinbaseAPI(BaseExchangeAPI):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "coinbase"
        self.base_url = "https://api.exchange.coinbase.com"  # correct base
    
    def normalize_pair(self, pair: str) -> str:
        """
        Normalize trading pair format.
        Example: BTCUSDT -> BTC-USDT, BTC_USDT -> BTC-USDT, BTC/USD -> BTC-USD
        """
        return pair.replace("_", "-").replace("/", "-").upper()

    async def get_supported_pairs(self) -> set:
        """
        Fetch and return all supported product pairs from Coinbase Exchange.
        """
        session = await self.get_session()
        try:
            async with session.get(f"{self.base_url}/products") as response:
                if response.status == 200:
                    data = await response.json()
                    return {item["id"].upper() for item in data}
                else:
                    print(f"Error fetching supported pairs: {response.status}")
                    return set()
        except Exception as e:
            print(f"Error loading supported pairs: {e}")
            return set()

    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        """
        Fetch ticker prices for given pairs. 
        Automatically falls back from USDT -> USD if USDT pair not listed.
        """
        prices = {}
        session = await self.get_session()
        supported = await self.get_supported_pairs()  # load all pairs once
        
        for pair in pairs:
            try:
                normalized = self.normalize_pair(pair)
                # Fallback to USD if USDT version not found
                alt_pair = normalized.replace("-USDT", "-USD") if normalized.endswith("-USDT") else None

                target = (
                    normalized
                    if normalized in supported
                    else alt_pair if alt_pair and alt_pair in supported
                    else None
                )

                if not target:
                    print(f"{pair} not listed on Coinbase.")
                    continue

                async with session.get(f"{self.base_url}/products/{target}/ticker") as response:
                    if response.status == 200:
                        data = await response.json()
                        prices[pair] = float(data["price"])
                    else:
                        print(f"Coinbase API error for {pair}: {response.status}")

            except Exception as e:
                print(f"Coinbase error for {pair}: {e}")
        
        return prices
