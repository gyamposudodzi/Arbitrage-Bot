import aiohttp
import time
import hmac
import hashlib
import base64
import urllib.parse
from typing import Dict
from .base_executor import BaseOrderExecutor

class KrakenOrderExecutor(BaseOrderExecutor):
    """Kraken order execution implementation"""
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.base_url = "https://api.kraken.com"
    
    def _generate_signature(self, urlpath: str, data: Dict) -> str:
        """
        Kraken signature: HMAC-SHA512 of (URI path + SHA256(nonce + POST data)) 
        and base64 decoded secret API key.
        """
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()

        mac = hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512)
        sigdigest = base64.b64encode(mac.digest())
        return sigdigest.decode()
    
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """Place a market order on Kraken"""
        try:
            # Kraken symbols: XBTUSDT -> XBTUSDT (usually)
            # Normalization might be needed outside or here.
            # Kraken AddOrder: pair, type (buy/sell), ordertype (market), volume
            
            uri_path = "/0/private/AddOrder"
            nonce = int(time.time() * 1000)
            
            data = {
                "nonce": nonce,
                "ordertype": "market",
                "type": side.lower(),
                "volume": str(quantity),
                "pair": symbol
            }
            
            headers = {
                "API-Key": self.api_key,
                "API-Sign": self._generate_signature(uri_path, data)
            }
            
            session = await self.get_session()
            async with session.post(
                f"{self.base_url}{uri_path}",
                data=data,
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200 and not result.get('error'):
                    txid = result['result']['txid'][0] # List of txids
                    print(f"✅ Kraken {side} order executed: {quantity} {symbol}")
                    return {
                        'success': True,
                        'order_id': txid,
                        'status': 'FILLED', # Market assumed filled
                        'executed_quantity': quantity
                    }
                else:
                    error = result.get('error', ['Unknown error'])[0]
                    print(f"❌ Kraken order failed: {error}")
                    return {
                        'success': False,
                        'error': error
                    }
                    
        except Exception as e:
            print(f"❌ Kraken order error: {e}")
            return {'success': False, 'error': str(e)}

    async def get_balance(self, asset: str) -> float:
        """Get account balance"""
        try:
            # Kraken Balance: /0/private/Balance
            uri_path = "/0/private/Balance"
            nonce = int(time.time() * 1000)
            data = {"nonce": nonce}
            
            headers = {
                "API-Key": self.api_key,
                "API-Sign": self._generate_signature(uri_path, data)
            }
            
            session = await self.get_session()
            async with session.post(
                f"{self.base_url}{uri_path}",
                data=data,
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200 and not result.get('error'):
                    balances = result['result']
                    # Kraken asset naming: ZUSD, XXBT, etc. or standard
                    # Try exact match, then mapped match
                    
                    target = asset.upper()
                    if target == "BTC": target = "XXBT"
                    if target == "USD": target = "ZUSD"
                    # USDT is usually USDT
                    
                    if target in balances:
                        return float(balances[target])
                    elif asset.upper() in balances:
                        return float(balances[asset.upper()])
                    return 0.0
                else:
                    print(f"❌ Kraken balance failed: {result.get('error')}")
                    return 0.0
        except Exception as e:
            print(f"❌ Kraken balance exception: {e}")
            return 0.0

    async def get_order_status(self, order_id: str) -> Dict:
        # Check OpenOrders or QueryOrders
        return {}
