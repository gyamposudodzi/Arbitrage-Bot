import aiohttp
import time
import hmac
import hashlib
import json
import base64
from typing import Dict
from .base_executor import BaseOrderExecutor

class CoinbaseOrderExecutor(BaseOrderExecutor):
    """Coinbase Advanced Trade order execution implementation"""
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.base_url = "https://api.coinbase.com/api/v3/brokerage"
    
    def _generate_signature(self, method: str, request_path: str, body: str = "") -> Dict[str, str]:
        """Generate headers for Coinbase Advanced Trade"""
        timestamp = str(int(time.time()))
        message = timestamp + method + request_path + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }
    
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """
        Place a market order on Coinbase.
        Symbol: "BTC-USDT" -> "BTC-USDT" (Coinbase uses dashes, so simple pass-through usually works, 
        or normalize via API class if needed. Here we assume generic format or handle normalization).
        """
        try:
            # Coinbase Advanced Trade uses "product_id" e.g. "BTC-USD"
            # Helper: normalize "BTCUSDT" to "BTC-USDT" if needed, but usually 
            # the bot passes "BTC-USDT".
            # Note: Coinbase has BTC-USD, not BTC-USDT usually.
            product_id = symbol.replace("USDT", "USD") if "USDT" in symbol else symbol
            
            # Construct body
            # https://docs.cloud.coinbase.com/advanced-trade-api/reference/createorder
            client_order_id = str(int(time.time() * 1000000))
            
            order_config = {}
            if side.lower() == 'buy':
                 # For buy market orders, Coinbase often requires 'quote_size' (amount in USD)
                 # But we can try 'base_size' (amount in BTC) if allowed.
                 # Let's try base_size first.
                 order_config["market_market_ioc"] = {
                     "base_size": str(quantity)
                 }
            else:
                 order_config["market_market_ioc"] = {
                     "base_size": str(quantity)
                 }

            payload = {
                "client_order_id": client_order_id,
                "product_id": product_id,
                "side": side.upper(),
                "order_configuration": order_config
            }
            
            body_str = json.dumps(payload)
            request_path = "/api/v3/brokerage/orders"
            headers = self._generate_signature("POST", request_path, body_str)
            
            session = await self.get_session()
            async with session.post(
                f"https://api.coinbase.com{request_path}",
                data=body_str,
                headers=headers
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    if data.get("success"):
                        return {
                            "success": True,
                            "order_id": data.get("order_id"),
                            "status": "FILLED", # Market orders are usually immediate
                            "executed_quantity": quantity, # Approximate
                            "original_response": data
                        }
                    else:
                         return {
                            "success": False,
                            "error": str(data.get("error_response"))
                        }
                else:
                    return {"success": False, "error": f"HTTP {response.status}: {data}"}
                    
        except Exception as e:
            print(f"❌ Coinbase order error: {e}")
            return {'success': False, 'error': str(e)}

    async def get_balance(self, asset: str) -> float:
        """Get account balance"""
        try:
            request_path = "/api/v3/brokerage/accounts"
            headers = self._generate_signature("GET", request_path)
            
            session = await self.get_session()
            async with session.get(
                f"https://api.coinbase.com{request_path}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Data: {"accounts": [...]}
                    for account in data.get("accounts", []):
                        if account.get("currency") == asset.upper():
                            return float(account.get("available_balance", {}).get("value", 0.0))
                    return 0.0
                else:
                    print(f"❌ Coinbase balance error: {response.status}")
                    return 0.0
        except Exception as e:
            print(f"❌ Coinbase balance exception: {e}")
            return 0.0

    async def get_order_status(self, order_id: str) -> Dict:
        # Implementation omitted for brevity
        return {}
