import aiohttp
from typing import Dict, List
from .base_exchange import BaseExchangeAPI

class KrakenAPI(BaseExchangeAPI):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "kraken"
        self.base_url = "https://api.kraken.com/0/public"
    
    def normalize_pair(self, pair: str) -> str:
        # Kraken uses different naming, e.g. BTC/USDT → XBTUSDT
        base, quote = pair.split("-")
        if base == "BTC":
            base = "XBT"
        if quote == "USDT":
            quote = "USDT"
        return f"{base}{quote}"

    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()

        for pair in pairs:
            try:
                normalized = self.normalize_pair(pair)
                url = f"{self.base_url}/Ticker?pair={normalized}"

                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Kraken returns dynamic keys
                        result = data.get("result", {})
                        if not result:
                            #print(f"{pair} not listed on Kraken.")
                            continue

                        first_key = next(iter(result))
                        ticker_info = result[first_key]
                        prices[pair] = float(ticker_info["b"][0])  # bid price
                    else:
                        print(f"Kraken API error for {pair}: {response.status}")

            except Exception as e:
                print(f"Kraken error for {pair}: {e}")

        return prices
