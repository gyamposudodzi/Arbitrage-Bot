import aiohttp
import asyncio
import json
import time
from typing import Dict, List, Callable, Awaitable
from .base_exchange import BaseExchangeAPI
from .streaming_interface import StreamingExchangeInterface

class GateIOAPI(BaseExchangeAPI, StreamingExchangeInterface):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "gateio"
        self.base_url = "https://api.gateio.ws/api/v4"
        self.ws = None
        self.running = False
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTC_USDT (Gate.io uses underscores)
        return pair.replace("-", "_")
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            # Gate.io tickers endpoint
            async with session.get(f"{self.base_url}/spot/tickers") as response:
                if response.status == 200:
                    data = await response.json()
                    # Create lookup dictionary
                    tickers = {}
                    for item in data:
                        if item['lowest_ask']:  # Use lowest ask as approximate bid
                            try:
                                tickers[item['currency_pair']] = float(item['lowest_ask'])
                            except (ValueError, TypeError):
                                continue
                    
                    for pair in pairs:
                        normalized = self.normalize_pair(pair)
                        if normalized in tickers:
                            prices[pair] = tickers[normalized]
                else:
                    print(f"Gate.io API error: {response.status}")
        except Exception as e:
            print(f"Gate.io error: {e}")
        
        return prices

    async def start_stream(self, pairs: List[str], callback: Callable[[str, float, str], Awaitable[None]]):
        """Streaming implementation for GateIO"""
        self.running = True
        session = await self.get_session()
        
        # Prepare params
        ws_pairs = []
        ws_map = {}
        
        for pair in pairs:
            # Gate uses BTC_USDT
            gate_pair = self.normalize_pair(pair)
            ws_pairs.append(gate_pair)
            ws_map[gate_pair] = pair
            
        print(f"🔌 Connecting to Gate.io WebSocket for {len(ws_pairs)} pairs...")
        ws_url = "wss://api.gateio.ws/ws/v4/"
        
        try:
            async with session.ws_connect(ws_url) as ws:
                self.ws = ws
                
                # Subscribe
                subscribe_msg = {
                    "time": int(time.time()),
                    "channel": "spot.tickers",
                    "event": "subscribe",
                    "payload": ws_pairs
                }
                await ws.send_json(subscribe_msg)
                
                async for msg in ws:
                    if not self.running:
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        payload = json.loads(msg.data)
                        
                        event = payload.get("event")
                        channel = payload.get("channel")
                        result = payload.get("result")
                        
                        if event == "update" and channel == "spot.tickers" and result:
                            # result is dict
                            currency_pair = result.get("currency_pair")
                            last_price = result.get("last")
                            
                            if currency_pair and last_price:
                                if currency_pair in ws_map:
                                    original_pair = ws_map[currency_pair]
                                    await callback(original_pair, float(last_price), self.name)
                                        
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"❌ GateIO WS Error: {ws.exception()}")
                        break
                        
        except Exception as e:
            print(f"❌ GateIO Connection Failed: {e}")
            self.running = False

    async def stop_stream(self):
        self.running = False
        if self.ws:
            await self.ws.close()