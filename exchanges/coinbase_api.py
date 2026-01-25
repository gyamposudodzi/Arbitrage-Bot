import aiohttp
import asyncio
import json
from typing import Dict, List, Callable, Awaitable
from .base_exchange import BaseExchangeAPI
from .streaming_interface import StreamingExchangeInterface

class CoinbaseAPI(BaseExchangeAPI, StreamingExchangeInterface):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "coinbase"
        self.base_url = "https://api.exchange.coinbase.com"
        self.ws = None
        self.running = False
    
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

    async def get_trading_pairs(self) -> set:
        return await self.get_supported_pairs()

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
                    #print(f"{pair} not listed on Coinbase.")
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
    async def start_stream(self, pairs: List[str], callback: Callable[[str, float, str], Awaitable[None]]):
        """Streaming implementation for Coinbase"""
        self.running = True
        session = await self.get_session()
        
        # 1. Resolve pair mappings (USDT -> USD fallback)
        supported = await self.get_supported_pairs()
        product_ids = []
        # Mapping from Coinbase Product ID to User Pairs
        # e.g., 'BTC-USD': ['BTC-USDT'] (if user requested BTC-USDT but we use USD ver)
        id_map = {} 
        
        for pair in pairs:
            # Re-use logic from get_prices but simpler
            normalized = self.normalize_pair(pair)
            alt_pair = normalized.replace("-USDT", "-USD") if normalized.endswith("-USDT") else None
            
            target = None
            if normalized in supported:
                target = normalized
            elif alt_pair and alt_pair in supported:
                target = alt_pair
            
            if target:
                product_ids.append(target)
                if target not in id_map:
                    id_map[target] = []
                id_map[target].append(pair)
            else:
                print(f"⚠️ Coinbase WS: Pair {pair} not found")
        
        if not product_ids:
            print("❌ Coinbase WS: No valid pairs to stream")
            return

        ws_url = "wss://ws-feed.exchange.coinbase.com"
        print(f"🔌 Connecting to Coinbase WebSocket for {len(product_ids)} pairs...")
        
        try:
            async with session.ws_connect(ws_url) as ws:
                self.ws = ws
                
                # Subscribe
                subscribe_msg = {
                    "type": "subscribe",
                    "product_ids": product_ids,
                    "channels": ["ticker"]
                }
                await ws.send_json(subscribe_msg)
                
                async for msg in ws:
                    if not self.running:
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        
                        if data.get("type") == "ticker":
                            product_id = data.get("product_id")
                            price_str = data.get("price")
                            
                            if product_id and price_str:
                                price = float(price_str)
                                # Update all user pairs that map to this product logic
                                if product_id in id_map:
                                    for user_pair in id_map[product_id]:
                                        await callback(user_pair, price, self.name)
                                        
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"❌ Coinbase WS Error: {ws.exception()}")
                        break
        except Exception as e:
            print(f"❌ Coinbase Connection Failed: {e}")
            self.running = False

    async def stop_stream(self):
        self.running = False
        if self.ws:
            await self.ws.close()
