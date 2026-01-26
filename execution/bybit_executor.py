import aiohttp
import time
import hmac
import hashlib
import json
from typing import Dict
from .base_executor import BaseOrderExecutor

class BybitOrderExecutor(BaseOrderExecutor):
    """Bybit V5 Order Executor"""
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.base_url = "https://api.bybit.com"
        
    def _generate_signature(self, params: str, timestamp: str, recv_window: str) -> str:
        """
        Bybit V5 Signature: HMAC-SHA256(timestamp + api_key + recv_window + params)
        """
        payload = f"{timestamp}{self.api_key}{recv_window}{params}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """Place market order on Bybit V5"""
        try:
            # Bybit V5: POST /v5/order/create
            # category: 'spot' or 'linear'
            endpoint = "/v5/order/create"
            timestamp = str(int(time.time() * 1000))
            recv_window = "5000"
            
            # Helper: Bybit usually BTCUSDT, but if robot passes BTC-USDT, remove dash
            clean_symbol = symbol.replace("-", "")
            
            payload = {
                "category": "spot",
                "symbol": clean_symbol,
                "side": side.capitalize(), # Buy/Sell
                "orderType": "Market",
                "qty": str(quantity)
            }
            body_str = json.dumps(payload)
            
            signature = self._generate_signature(body_str, timestamp, recv_window)
            
            headers = {
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-SIGN": signature,
                "X-BAPI-RECV-WINDOW": recv_window,
                "Content-Type": "application/json"
            }
            
            session = await self.get_session()
            async with session.post(
                f"{self.base_url}{endpoint}",
                data=body_str,
                headers=headers
            ) as response:
                result = await response.json()
                
                if result.get("retCode") == 0:
                    print(f"✅ Bybit {side} order executed: {quantity} {symbol}")
                    return {
                        "success": True,
                        "order_id": result["result"]["orderId"],
                        "status": "FILLED",
                        "executed_quantity": quantity
                    }
                else:
                    print(f"❌ Bybit order failed: {result.get('retMsg')}")
                    return {"success": False, "error": result.get("retMsg")}
                    
        except Exception as e:
            print(f"❌ Bybit order exception: {e}")
            return {"success": False, "error": str(e)}

    async def place_futures_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """
        Place a Perpetual Future Order (Linear).
        Used for Funding Rate Arbitrage (Shorting).
        """
        try:
            endpoint = "/v5/order/create"
            timestamp = str(int(time.time() * 1000))
            recv_window = "5000"
            clean_symbol = symbol.replace("-", "") # BTC-USDT -> BTCUSDT
            
            # Bybit V5 Linear payload
            payload = {
                "category": "linear",
                "symbol": clean_symbol,
                "side": side.capitalize(),
                "orderType": "Market",
                "qty": str(quantity),
                "positionIdx": 0, # 0 = One-Way Mode (Standard), 1/2 = Hedge Mode. Assuming 0.
            }
            body_str = json.dumps(payload)
            signature = self._generate_signature(body_str, timestamp, recv_window)
            
            headers = {
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-SIGN": signature,
                "X-BAPI-RECV-WINDOW": recv_window,
                "Content-Type": "application/json"
            }
            
            session = await self.get_session()
            async with session.post(f"{self.base_url}{endpoint}", data=body_str, headers=headers) as response:
                result = await response.json()
                if result.get("retCode") == 0:
                    print(f"✅ Bybit Futures {side} executed: {quantity} {symbol}")
                    return {
                        "success": True,
                        "order_id": result["result"]["orderId"],
                        "status": "FILLED",
                        "executed_quantity": quantity
                    }
                else:
                    return {"success": False, "error": result.get("retMsg")}
                    
        except Exception as e:
            print(f"❌ Bybit Futures exception: {e}")
            return {"success": False, "error": str(e)}

    async def get_balance(self, asset: str) -> float:
        """Get Unified/Spot wallet balance"""
        try:
            # GET /v5/account/wallet-balance?accountType=UNIFIED&coin=BTC
            # Or accountType=SPOT if legacy. Most bybit accounts are Unified now.
            # We'll try UNIFIED first.
            endpoint = "/v5/account/wallet-balance"
            timestamp = str(int(time.time() * 1000))
            recv_window = "5000"
            params = f"accountType=UNIFIED&coin={asset.upper()}"
            
            signature = self._generate_signature(params, timestamp, recv_window)
            
            headers = {
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-SIGN": signature,
                "X-BAPI-RECV-WINDOW": recv_window
            }
            
            session = await self.get_session()
            async with session.get(
                f"{self.base_url}{endpoint}?{params}",
                headers=headers
            ) as response:
                result = await response.json()
                
                if result.get("retCode") == 0:
                    list_data = result["result"]["list"]
                    if list_data:
                        # Find coin in the list
                        for coin in list_data[0]["coin"]:
                            if coin["coin"] == asset.upper():
                                return float(coin["walletBalance"])
                    return 0.0
                else:
                    # Fallback to SPOT just in case legacy
                    # ... omitted for brevity
                    print(f"❌ Bybit balance failed: {result.get('retMsg')}")
                    return 0.0
        except Exception as e:
            return 0.0
            
    async def get_order_status(self, order_id: str) -> Dict:
        return {}
