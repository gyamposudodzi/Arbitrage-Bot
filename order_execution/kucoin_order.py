import aiohttp
import base64
import hashlib
import hmac
import json
import time
from typing import Dict
from .base_order import BaseOrderExecutor

class KuCoinOrderExecutor(BaseOrderExecutor):
    """KuCoin order execution implementation"""
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str):
        super().__init__(api_key, api_secret, passphrase)
        self.base_url = "https://api.kucoin.com/api/v1"
    
    def _generate_kucoin_headers(self, method: str, endpoint: str, body: str = "") -> Dict:
        """Generate KuCoin authentication headers"""
        timestamp = str(int(time.time() * 1000))
        str_to_sign = timestamp + method + endpoint + body
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                str_to_sign.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        passphrase = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                self.passphrase.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return {
            "KC-API-KEY": self.api_key,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }
    
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """Place a market order on KuCoin"""
        try:
            endpoint = "/orders"
            body = {
                "clientOid": str(int(time.time() * 1000)),
                "side": side.lower(),
                "symbol": symbol,
                "type": "market",
                "size": quantity
            }
            
            headers = self._generate_kucoin_headers("POST", endpoint, json.dumps(body))
            
            session = await self.get_session()
            async with session.post(
                f"{self.base_url}{endpoint}",
                json=body,
                headers=headers
            ) as response:
                data = await response.json()
                
                if data.get('code') == '200000':
                    print(f"✅ KuCoin {side} order executed: {quantity} {symbol}")
                    return {
                        'success': True,
                        'order_id': data['data'].get('orderId'),
                        'status': 'filled'
                    }
                else:
                    print(f"❌ KuCoin order failed: {data}")
                    return {
                        'success': False,
                        'error': data.get('msg', 'Unknown error')
                    }
                    
        except Exception as e:
            print(f"❌ KuCoin order error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_balance(self, asset: str) -> float:
        """Get account balance from KuCoin"""
        try:
            endpoint = "/accounts"
            headers = self._generate_kucoin_headers("GET", endpoint)
            
            session = await self.get_session()
            async with session.get(
                f"{self.base_url}{endpoint}",
                headers=headers
            ) as response:
                data = await response.json()
                
                if data.get('code') == '200000':
                    accounts = data['data']
                    main_account = next(
                        (acc for acc in accounts if acc['type'] == 'trade' and acc['currency'] == asset.upper()),
                        None
                    )
                    return float(main_account['balance']) if main_account else 0.0
                else:
                    print(f"❌ KuCoin balance check failed: {data}")
                    return 0.0
                    
        except Exception as e:
            print(f"❌ KuCoin balance error: {e}")
            return 0.0
    
    async def get_order_status(self, order_id: str) -> Dict:
        """Check order status on KuCoin"""
        try:
            endpoint = f"/orders/{order_id}"
            headers = self._generate_kucoin_headers("GET", endpoint)
            
            session = await self.get_session()
            async with session.get(
                f"{self.base_url}{endpoint}",
                headers=headers
            ) as response:
                data = await response.json()
                return data
                
        except Exception as e:
            print(f"❌ KuCoin order status error: {e}")
            return {}