import aiohttp
import time
import hmac
import hashlib
import json
import base64
from typing import Dict
from .base_executor import BaseOrderExecutor

class OKXOrderExecutor(BaseOrderExecutor):
    """OKX V5 Order Executor"""
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str):
        super().__init__(api_key, api_secret, passphrase)
        self.base_url = "https://www.okx.com"
        
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """
        OKX Signature: Base64(HMAC-SHA256(timestamp + method + requestPath + body))
        """
        message = f"{timestamp}{method}{request_path}{body}"
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode('utf-8')
        
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """Place market order on OKX"""
        try:
            # POST /api/v5/trade/order
            # instId: BTC-USDT (OKX uses dash, works with our standard)
            # side: buy/sell
            # ordType: market
            # sz: quantity (Note: for spot, sz is usually base currency amount?)
            # OKX 'sz' logic depends on tdMode/instType. For Spot, sz is in base ccy.
            
            endpoint = "/api/v5/trade/order"
            method = "POST"
            timestamp = str(time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()))
            # OKX prefers ISO8601 or unix epoch. Let's use ISO.
            # Actually Docs say ISO 8601 format e.g. 2020-12-08T09:08:57.715Z
            
            payload = {
                "instId": symbol,
                "tdMode": "cash", # Spot
                "side": side.lower(),
                "ordType": "market",
                "sz": str(quantity)
            }
            body_str = json.dumps(payload)
            
            signature = self._generate_signature(timestamp, method, endpoint, body_str)
            
            headers = {
                "OK-ACCESS-KEY": self.api_key,
                "OK-ACCESS-SIGN": signature,
                "OK-ACCESS-TIMESTAMP": timestamp,
                "OK-ACCESS-PASSPHRASE": self.passphrase,
                "Content-Type": "application/json"
            }
            
            session = await self.get_session()
            async with session.post(
                f"{self.base_url}{endpoint}",
                data=body_str,
                headers=headers
            ) as response:
                result = await response.json()
                
                if result.get("code") == "0":
                    data = result["data"][0]
                    print(f"✅ OKX {side} order executed: {quantity} {symbol}")
                    return {
                        "success": True,
                        "order_id": data["ordId"],
                        "status": "FILLED",
                        "executed_quantity": quantity
                    }
                else:
                    print(f"❌ OKX order failed: {result.get('msg')}")
                    return {"success": False, "error": result.get("msg")}
                    
        except Exception as e:
            print(f"❌ OKX order exception: {e}")
            return {"success": False, "error": str(e)}

    async def get_balance(self, asset: str) -> float:
        """Get trading balance"""
        try:
            # GET /api/v5/account/balance?ccy=BTC
            endpoint = f"/api/v5/account/balance?ccy={asset.upper()}"
            method = "GET"
            timestamp = str(time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()))
            
            signature = self._generate_signature(timestamp, method, endpoint)
            
            headers = {
                "OK-ACCESS-KEY": self.api_key,
                "OK-ACCESS-SIGN": signature,
                "OK-ACCESS-TIMESTAMP": timestamp,
                "OK-ACCESS-PASSPHRASE": self.passphrase
            }
            
            session = await self.get_session()
            async with session.get(
                f"{self.base_url}{endpoint}",
                headers=headers
            ) as response:
                result = await response.json()
                
                if result.get("code") == "0":
                    details = result["data"][0]["details"]
                    if details:
                        return float(details[0]["cashBal"]) # Cash balance
                    return 0.0
                else:
                    return 0.0
        except Exception as e:
            return 0.0
            
    async def get_order_status(self, order_id: str) -> Dict:
        return {}
