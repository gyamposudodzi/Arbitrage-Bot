import aiohttp
import asyncio
import json
from typing import Dict, List, Callable, Awaitable
from .base_exchange import BaseExchangeAPI
from .streaming_interface import StreamingExchangeInterface

class BybitAPI(BaseExchangeAPI, StreamingExchangeInterface):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "bybit"
        self.base_url = "https://api.bybit.com"
        self.ws = None
        self.running = False
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTCUSDT
        return pair.replace("-", "")
    
    async def get_funding_rates(self) -> List[Dict]:
        """
        Fetch real-time funding rates from Bybit V5 Linear (USDT Perps).
        """
        session = await self.get_session()
        funding_data = []
        try:
            # Query Linear Tickers (USDT Perpetual)
            url = f"{self.base_url}/v5/market/tickers?category=linear"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['retCode'] == 0:
                        for item in data['result']['list']:
                            # Bybit returns: {"symbol": "BTCUSDT", "fundingRate": "0.0001", "nextFundingTime": "...", "markPrice": "..."}
                            # Map to Standard Format required by FundingEngine
                            funding_data.append({
                                "symbol": item['symbol'], # Matches normalized format BTCUSDT
                                "lastFundingRate": item['fundingRate'],
                                "markPrice": item['markPrice'],
                                "nextFundingTime": item['nextFundingTime']
                            })
                    else:
                        print(f"Bybit funding error: {data['retMsg']}")
        except Exception as e:
            print(f"Bybit funding exception: {e}")
            
        return funding_data

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
                        
                        for pair in pairs:
                            exact_symbol = self.normalize_pair(pair)  # BTC-USDT → BTCUSDT
                            
                            if exact_symbol in all_tickers:
                                prices[pair] = all_tickers[exact_symbol]
                            else:
                                continue
                    
                    else:
                        print(f"❌ Bybit API error: {data['retMsg']}")
                else:
                    print(f"❌ Bybit HTTP error {response.status}")
                    
        except Exception as e:
            print(f"❌ Bybit exception: {e}")
        
        return prices

    async def start_stream(self, pairs: List[str], callback: Callable[[str, float, str], Awaitable[None]]):
        """Streaming implementation for Bybit V5"""
        self.running = True
        session = await self.get_session()
        
        # Prepare topics
        # Bybit topic: tickers.<symbol>
        # e.g. tickers.BTCUSDT
        
        ws_map = {} # BTCUSDT -> BTC-USDT
        topics = []
        
        for pair in pairs:
            symbol = self.normalize_pair(pair)
            topic = f"tickers.{symbol}"
            topics.append(topic)
            ws_map[symbol] = pair
            
        print(f"🔌 Connecting to Bybit WebSocket for {len(topics)} pairs...")
        ws_url = "wss://stream.bybit.com/v5/public/spot"
        
        try:
            async with session.ws_connect(ws_url) as ws:
                self.ws = ws
                
                # Subscribe (Bybit allows max 10 topics per request, might need batching logic if thousands)
                # For small < 50 pairs, one req is usually fine.
                subscribe_msg = {
                    "op": "subscribe",
                    "args": topics
                }
                await ws.send_json(subscribe_msg)
                
                async for msg in ws:
                    if not self.running:
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        payload = json.loads(msg.data)
                        
                        # Handle Pong? Bybit sends auto-ping? We can ignore for now.
                        
                        topic = payload.get("topic")
                        data = payload.get("data")
                        
                        if topic and data and topic.startswith("tickers."):
                            symbol = data.get("symbol") # BTCUSDT
                            bid_price = data.get("bid1Price")
                            
                            if symbol and bid_price:
                                if symbol in ws_map:
                                    original_pair = ws_map[symbol]
                                    await callback(original_pair, float(bid_price), self.name)
                                        
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"❌ Bybit WS Error: {ws.exception()}")
                        break
                        
        except Exception as e:
            print(f"❌ Bybit Connection Failed: {e}")
            self.running = False

    async def stop_stream(self):
        self.running = False
        if self.ws:
            await self.ws.close()