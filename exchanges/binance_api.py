import aiohttp
import asyncio
import json
from typing import Dict, List, Callable, Awaitable
from .base_exchange import BaseExchangeAPI
from .streaming_interface import StreamingExchangeInterface

class BinanceAPI(BaseExchangeAPI, StreamingExchangeInterface):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "binance"
        self.base_url = "https://api.binance.com/api/v3"
        self.ws = None
        self.running = False
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTCUSDT
        return pair.replace("-", "")
    
    async def get_all_tickers(self) -> Dict[str, float]:
        """Fetch all prices for Triangular Arbitrage"""
        prices = {}
        session = await self.get_session()
        try:
            async with session.get(f"{self.base_url}/ticker/bookTicker") as response:
                if response.status == 200:
                    data = await response.json()
                    # Return formatted pairs (e.g. "BTC-USDT") if possible, or raw
                    # For simplicity, we'll try to guess the format or just return raw symbols
                    # But Triangular Engine expects "BTC-USDT" format to split.
                    # Binance symbols are "BTCUSDT". We need to insert the hyphen.
                    # This is valid for standard pairs.
                    for item in data:
                        symbol = item['symbol']
                        # Simple heuristic for common quotes
                        quote_found = False
                        for quote in ['USDT', 'BTC', 'ETH', 'BNB', 'FDUSD', 'USDC']:
                            if symbol.endswith(quote):
                                base = symbol[:-len(quote)]
                                prices[f"{base}-{quote}"] = float(item['bidPrice'])
                                quote_found = True
                                break
                        if not quote_found:
                            prices[symbol] = float(item['bidPrice'])
        except Exception as e:
            print(f"Binance fetch error: {e}")
        return prices

    async def get_order_book(self, pair: str, limit: int = 20) -> Dict[str, List[List[str]]]:
        """
        Fetch order book depth.
        Returns: {'bids': [['price', 'qty'], ...], 'asks': [['price', 'qty'], ...]}
        """
        session = await self.get_session()
        symbol = self.normalize_pair(pair)
        try:
            async with session.get(f"{self.base_url}/depth", params={'symbol': symbol, 'limit': limit}) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Binance depth error {response.status} for {pair}")
                    return {}
        except Exception as e:
            print(f"Binance depth exception: {e}")
            return {}



    async def get_funding_rates(self) -> List[Dict]:
        """
        Fetch real-time funding rates from Binance Futures.
        """
        session = await self.get_session()
        try:
            # Note: Different base URL for Futures
            async with session.get("https://fapi.binance.com/fapi/v1/premiumIndex") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Binance funding error: {response.status}")
                    return []
        except Exception as e:
            print(f"Binance funding exception: {e}")
            return []

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

    async def start_stream(self, pairs: List[str], callback: Callable[[str, float, str], Awaitable[None]]):
        """Streaming implementation for Binance"""
        self.running = True
        session = await self.get_session()
        
        # Binance Combined Streams: stream?streams=<symbol>@bookTicker/<symbol>@bookTicker
        # Normalize pairs for Binance (lowercase, no hyphens)
        normalized_map = {self.normalize_pair(p).lower(): p for p in pairs}
        streams = "/".join([f"{k}@bookTicker" for k in normalized_map.keys()])
        ws_url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        
        print(f"🔌 Connecting to Binance WebSocket for {len(pairs)} pairs...")
        
        try:
            async with session.ws_connect(ws_url) as ws:
                self.ws = ws
                async for msg in ws:
                    if not self.running:
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        payload = json.loads(msg.data)
                        
                        # Handle potential errors or subscription components
                        if 'data' in payload:
                            data = payload['data']
                            symbol = data['s'].lower() # Binance symbols are upper, but let's be safe
                            
                            # 'b' is best bid price
                            # 'a' is best ask price
                            # Currently mapping to 'bid' to match get_prices behavior
                            price = float(data['b'])
                            
                            # Find original pair name
                            original_pair = normalized_map.get(symbol)
                            if not original_pair:
                                # Try uppercase if lowercase fail
                                original_pair = normalized_map.get(symbol.lower())
                            
                            if original_pair:
                                await callback(original_pair, price, self.name)
                                
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"❌ Binance WS Error: {ws.exception()}")
                        break
        except Exception as e:
            print(f"❌ Binance Connection Failed: {e}")
            self.running = False

    async def stop_stream(self):
        self.running = False
        if self.ws:
            await self.ws.close()
