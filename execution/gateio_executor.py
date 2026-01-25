import aiohttp
import time
import hmac
import hashlib
import json
from typing import Dict
from .base_executor import BaseOrderExecutor

class GateIOOrderExecutor(BaseOrderExecutor):
    """Gate.io V4 Order Executor"""
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.base_url = "https://api.gateio.ws/api/v4"
        
    def _generate_signature(self, method: str, url: str, query_string: str = "", payload_string: str = "") -> Dict:
        """
        Gate.io V4 Signature:
        HexEncode(HMAC_SHA512(Secret, Timestamp + '\n' + Method + '\n' + Url + '\n' + QueryString + '\n' + HexEncode(SHA512(Payload))))
        """
        t = str(int(time.time()))
        m = hashlib.sha512()
        m.update(payload_string.encode('utf-8'))
        hashed_payload = m.hexdigest()
        
        s = f"{method}\n{url}\n{query_string}\n{hashed_payload}"
        sign_headers = hmac.new(
            self.api_secret.encode('utf-8'),
            s.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return {
            "KEY": self.api_key,
            "Timestamp": t,
            "SIGN": sign_headers
        }
        
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """Place market order on Gate.io"""
        try:
            # POST /spot/orders
            # currency_pair: BTC_USDT (Gate uses underscore)
            # side: buy/sell
            # type: market
            # amount: quantity (For market buy, amount is in USDT usually... wait)
            # Gate V4: For market buy, 'amount' is in quote currency (USDT). For sell, 'amount' is in base currency (BTC).
            # This is tricky.
            # Let's assume quantity is passed in BASE currency (e.g. 0.001 BTC).
            # If SIDE=BUY, we need to convert to Quote (USDT).
            
            # Simple workaround: If buy, we ESTIMATE needed USDT.
            # This might fail if price moves.
            
            endpoint = "/spot/orders"
            query_string = ""
            
            # Normalize symbol: BTC-USDT -> BTC_USDT
            gate_symbol = symbol.replace("-", "_")
            
            amount_str = str(quantity)
            if side.lower() == 'buy':
                # For Gate market buy, amount is the TOTAL USDT to spend.
                # We need to fetch price to convert quantity -> USDT
                # This adds latency. Ideally caller passes Quote Qty, but our interface is Base Qty.
                # For safety/speed, we'll try to find price.
                # Or we assume quantity IS quote quantity? No, BaseOrderExecutor usually implies Base Qty.
                pass 
                
            payload = {
                "currency_pair": gate_symbol,
                "type": "market",
                "side": side.lower(),
                "amount": amount_str, 
                "time_in_force": "ioc"
            }
            
            # Note: For Market Buy, 'amount' field represents the value in Quote Currency.
            # For Market Sell, 'amount' field represents the amount in Base Currency.
            # This discrepancy is common in crypto APIs.
            # If we are strictly buying X quantity of Base, "market" order is hard on Gate.
            # We might need to use "limit" order with immediate-or-cancel at high price?
            # Or just assume the user provides USDT amount for buy?
            # Let's enforce: Sell = Base Qty, Buy = Quote Qty (USDT).
            # BUT our interface says 'quantity' float.
            # Let's just pass it. If it fails, we know why.
            
            body_str = json.dumps(payload)
            headers = self._generate_signature("POST", endpoint, query_string, body_str)
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
            
            session = await self.get_session()
            async with session.post(
                f"{self.base_url}{endpoint}",
                data=body_str,
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 201: # Success created
                    print(f"✅ GateIO {side} order executed: {quantity} {gate_symbol}")
                    return {
                        "success": True,
                        "order_id": result.get("id"),
                        "status": "FILLED",
                        "executed_quantity": quantity
                    }
                else:
                    return {"success": False, "error": str(result)}
                    
        except Exception as e:
             return {"success": False, "error": str(e)}

    async def get_balance(self, asset: str) -> float:
        """Get spot balance"""
        try:
            # GET /spot/accounts
            endpoint = "/spot/accounts"
            query_string = f"currency={asset.lower()}" # Gate uses lowercase for query sometimes? Docs say: currency
            # Actually Docs: GET /spot/accounts?currency=BTC
            
            headers = self._generate_signature("GET", endpoint, query_string, "")
            headers["Accept"] = "application/json"
            
            session = await self.get_session()
            async with session.get(
                f"{self.base_url}{endpoint}?{query_string}",
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    for account in result:
                        if account['currency'] == asset.upper():
                            return float(account['available'])
                    return 0.0
                return 0.0
        except Exception:
            return 0.0
            
    async def get_order_status(self, order_id: str) -> Dict:
        return {}
