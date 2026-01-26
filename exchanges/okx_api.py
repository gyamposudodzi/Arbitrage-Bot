import aiohttp
import asyncio
import json
from typing import Dict, List, Callable, Awaitable
from .base_exchange import BaseExchangeAPI
from .streaming_interface import StreamingExchangeInterface

class OKXAPI(BaseExchangeAPI, StreamingExchangeInterface):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "okx"
        self.base_url = "https://www.okx.com/api/v5"
        self.ws = None
        self.running = False
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTC-USDT (OKX uses dashes)
        return pair.replace("-", "-")
    
    async def get_funding_rates(self) -> List[Dict]:
        """
        Fetch funding rates for configured pairs from OKX (SWAP).
        Uses batch async requests since there is no 'get all' endpoint.
        """
        session = await self.get_session()
        funding_data = []
        
        # 1. Identify pairs to check (from Config)
        # We need access to bot config... but valid pairs might be better.
        # Ideally this class should know its interesting pairs.
        # For now, we'll try to use a hardcoded list or if we can pass it in?
        # The interface signature is checking `self.config`? No, `BaseExchangeAPI` has `self.config`.
        # Taking a risk: assuming config has 'trading_pairs'
        
        target_pairs = self.config.get("trading_pairs", [])
        if not target_pairs:
             # Fallback
             target_pairs = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]

        tasks = []
        inst_ids = []

        for pair in target_pairs:
            # OKX Swap ID: BTC-USDT-SWAP
            inst_id = f"{pair}-SWAP"
            inst_ids.append(inst_id)
            url = f"{self.base_url}/public/funding-rate?instId={inst_id}"
            tasks.append(session.get(url))
            
        # 2. Fire requests parallel
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for inst_id, response in zip(inst_ids, responses):
            if isinstance(response, Exception):
                continue
                
            try:
                if response.status == 200:
                    data = await response.json()
                    if data['code'] == '0' and data['data']:
                        item = data['data'][0] # {"fundingRate": "...", "nextFundingTime": "..."}
                        
                        # Normalize back: BTC-USDT-SWAP -> BTC-USDT
                        symbol = inst_id.replace("-SWAP", "")
                        
                        funding_data.append({
                            "symbol": symbol,
                            "lastFundingRate": item['fundingRate'],
                            "markPrice": 0.0, # OKX funding endpoint doesn't give mark price, assume 0 or fetch separately
                            "nextFundingTime": item['nextFundingTime']
                        })
            except Exception:
                 pass
                 
        return funding_data

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

    async def start_stream(self, pairs: List[str], callback: Callable[[str, float, str], Awaitable[None]]):
        """Streaming implementation for OKX"""
        self.running = True
        session = await self.get_session()
        
        # Prepare args
        args = []
        ws_map = {}
        
        for pair in pairs:
            inst_id = self.normalize_pair(pair)
            args.append({"channel": "tickers", "instId": inst_id})
            ws_map[inst_id] = pair
            
        print(f"🔌 Connecting to OKX WebSocket for {len(args)} pairs...")
        ws_url = "wss://ws.okx.com:8443/ws/v5/public"
        
        try:
            async with session.ws_connect(ws_url) as ws:
                self.ws = ws
                
                # Subscribe
                subscribe_msg = {
                    "op": "subscribe",
                    "args": args
                }
                await ws.send_json(subscribe_msg)
                
                async for msg in ws:
                    if not self.running:
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        payload = json.loads(msg.data)
                        
                        # OKX data structure: { arg: {}, data: [{...}] }
                        if "data" in payload and payload["data"]:
                            for ticker in payload["data"]:
                                inst_id = ticker.get("instId")
                                bid_px = ticker.get("bidPx")
                                
                                if inst_id and bid_px:
                                    if inst_id in ws_map:
                                        original_pair = ws_map[inst_id]
                                        await callback(original_pair, float(bid_px), self.name)
                                        
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"❌ OKX WS Error: {ws.exception()}")
                        break
                        
        except Exception as e:
            print(f"❌ OKX Connection Failed: {e}")
            self.running = False

    async def stop_stream(self):
        self.running = False
        if self.ws:
            await self.ws.close()