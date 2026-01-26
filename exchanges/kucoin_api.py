import aiohttp
import asyncio
import json
import time
from typing import Dict, List, Callable, Awaitable
from .base_exchange import BaseExchangeAPI
from .streaming_interface import StreamingExchangeInterface

class KuCoinAPI(BaseExchangeAPI, StreamingExchangeInterface):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "kucoin"
        self.base_url = "https://api.kucoin.com/api/v1"
        self.ws = None
        self.running = False
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTC-USDT (KuCoin uses dashes)
        return pair.replace("-", "-")
    
    async def get_funding_rates(self) -> List[Dict]:
        """
        Fetch real-time funding rates from KuCoin Futures.
        """
        session = await self.get_session()
        funding_data = []
        try:
            # KuCoin Futures Endpoint (Different from Spot)
            url = "https://api-futures.kucoin.com/api/v1/contracts/active"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['code'] == '200000':
                        for item in data['data']:
                            # KuCoin Symbol: XBTUSDTM -> Need to map to BTC-USDT
                            symbol = item['symbol']
                            
                            # Simple Mapping Logic
                            # If starts with XBT, it's BTC. 
                            pair_name = symbol.replace("XBT", "BTC").replace("USDTM", "-USDT")
                            
                            # Only handle USDT-Margined
                            if "USDT" not in symbol: continue

                            funding_data.append({
                                "symbol": pair_name, # Normalized
                                "lastFundingRate": item.get('fundingFeeRate', 0),
                                "markPrice": item.get('markPrice', 0),
                                "nextFundingTime": item.get('nextFundingRateTime')
                            })
                    else:
                        print(f"KuCoin funding error: {data.get('msg')}")
        except Exception as e:
            print(f"KuCoin funding exception: {e}")
            
        return funding_data

    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            # KuCoin all tickers endpoint
            async with session.get(f"{self.base_url}/market/allTickers") as response:
                if response.status == 200:
                    data = await response.json()
                    if data['code'] == '200000':  # KuCoin success code
                        tickers = {}
                        for item in data['data']['ticker']:
                            if item['last'] is not None:
                                try:
                                    tickers[item['symbol']] = float(item['last'])
                                except (ValueError, TypeError):
                                    continue
                        
                        for pair in pairs:
                            normalized = self.normalize_pair(pair)
                            if normalized in tickers:
                                prices[pair] = tickers[normalized]
                else:
                    print(f"KuCoin API error: {response.status}")
        except Exception as e:
            print(f"KuCoin error: {e}")
        
        return prices

    async def start_stream(self, pairs: List[str], callback: Callable[[str, float, str], Awaitable[None]]):
        """Streaming implementation for KuCoin"""
        self.running = True
        session = await self.get_session()
        
        # 1. Get Token
        token = None
        endpoint = None
        
        try:
            async with session.post(f"{self.base_url}/bullet-public") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('code') == '200000':
                        token = data['data']['token']
                        endpoint = data['data']['instanceServers'][0]['endpoint']
        except Exception as e:
            print(f"❌ KuCoin Token Request Failed: {e}")
            self.running = False
            return
            
        if not token or not endpoint:
            print("❌ KuCoin WS Error: Could not get token")
            return

        # 2. Connect
        ws_url = f"{endpoint}?token={token}"
        formatted_pairs = [self.normalize_pair(p) for p in pairs]
        # KuCoin topics are comma separated strings
        topic_str = ",".join(formatted_pairs)
        
        print(f"🔌 Connecting to KuCoin WebSocket for {len(pairs)} pairs...")
        
        try:
            async with session.ws_connect(ws_url) as ws:
                self.ws = ws
                
                # Subscribe
                subscribe_msg = {
                    "id": int(time.time() * 1000),
                    "type": "subscribe",
                    "topic": f"/market/ticker:{topic_str}",
                    "privateChannel": False,
                    "response": True
                }
                await ws.send_json(subscribe_msg)
                
                # Ping interval handling (KuCoin requires ping every ~30s?)
                # We'll rely on aiohttp's auto-heartbeat or just standard read limits
                
                async for msg in ws:
                    if not self.running:
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        payload = json.loads(msg.data)
                        
                        if payload.get("type") == "message":
                            data = payload.get("data", {})
                            topic = payload.get("topic", "")
                            
                            # Topic: /market/ticker:BTC-USDT
                            pair = topic.split(":")[-1]
                            price_str = data.get("price")
                            
                            if price_str:
                                # KuCoin pairs match our normalized pairs, so just map back if needed
                                # Here we just pass the normalized pair name as 'pair'
                                # Ideally we map back to user input but for KuCoin it's usually 1:1
                                await callback(pair, float(price_str), self.name)
                                
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"❌ KuCoin WS Error: {ws.exception()}")
                        break
                        
        except Exception as e:
            print(f"❌ KuCoin Connection Failed: {e}")
            self.running = False

    async def stop_stream(self):
        self.running = False
        if self.ws:
            await self.ws.close()