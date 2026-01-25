import aiohttp
import asyncio
import json
from typing import Dict, List, Callable, Awaitable
from .base_exchange import BaseExchangeAPI
from .streaming_interface import StreamingExchangeInterface

class KrakenAPI(BaseExchangeAPI, StreamingExchangeInterface):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "kraken"
        self.base_url = "https://api.kraken.com/0/public"
        self.ws = None
        self.running = False
    
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
    async def start_stream(self, pairs: List[str], callback: Callable[[str, float, str], Awaitable[None]]):
        """Streaming implementation for Kraken"""
        self.running = True
        session = await self.get_session()
        
        # Map user pairs to Kraken WS pairs
        # Kraken WS often uses slash, e.g. "XBT/USD"
        ws_map = {} # "XBT/USDT" -> "BTC-USDT"
        ws_pairs = []
        
        for pair in pairs:
            # BTC-USDT -> XBT/USDT
            base, quote = pair.split("-")
            if base == "BTC": base = "XBT"
            if base == "DOGE": base = "XDG" # Kraken quirk
            
            # Try both /USD and /USDT if quote is USDT
            # But normally we just want what we asked for.
            # However, Kraken is weird. Let's just try exact mapping first.
            ws_pair = f"{base}/{quote}"
            ws_map[ws_pair] = pair
            ws_pairs.append(ws_pair)
            
        print(f"🔌 Connecting to Kraken WebSocket for {len(ws_pairs)} pairs...")
        ws_url = "wss://ws.kraken.com"
        
        try:
            async with session.ws_connect(ws_url) as ws:
                self.ws = ws
                
                # Subscribe
                subscribe_msg = {
                    "event": "subscribe",
                    "pair": ws_pairs,
                    "subscription": {"name": "ticker"}
                }
                await ws.send_json(subscribe_msg)
                
                async for msg in ws:
                    if not self.running:
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        
                        # Kraken sends Data as List: [channelID, {data}, channelName, pairName]
                        if isinstance(data, list):
                            if len(data) >= 4 and "ticker" in data[2]:
                                pair_name = data[3]
                                ticker_data = data[1]
                                
                                # 'b' is bid [price, volume, timestamp]
                                if "b" in ticker_data:
                                    bid_price = float(ticker_data["b"][0])
                                    
                                    if pair_name in ws_map:
                                        original_pair = ws_map[pair_name]
                                        await callback(original_pair, bid_price, self.name)
                                        
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"❌ Kraken WS Error: {ws.exception()}")
                        break
        except Exception as e:
            print(f"❌ Kraken Connection Failed: {e}")
            self.running = False

    async def stop_stream(self):
        self.running = False
        if self.ws:
            await self.ws.close()
