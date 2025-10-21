import aiohttp
import time
import hmac
import hashlib
from typing import Dict
from .base_order import BaseOrderExecutor

class BinanceOrderExecutor(BaseOrderExecutor):
    """Binance order execution implementation"""
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.base_url = "https://api.binance.com/api/v3"
    
    def _generate_signature(self, params: Dict) -> str:
        """Generate HMAC SHA256 signature for Binance"""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """Place a market order on Binance"""
        try:
            timestamp = int(time.time() * 1000)
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': 'MARKET',
                'quantity': quantity,
                'timestamp': timestamp
            }
            
            params['signature'] = self._generate_signature(params)
            
            session = await self.get_session()
            async with session.post(
                f"{self.base_url}/order",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    print(f"✅ Binance {side} order executed: {quantity} {symbol}")
                    return {
                        'success': True,
                        'order_id': data.get('orderId'),
                        'status': data.get('status'),
                        'executed_quantity': float(data.get('executedQty', 0)),
                        'fills': data.get('fills', [])
                    }
                else:
                    print(f"❌ Binance order failed: {data}")
                    return {
                        'success': False,
                        'error': data.get('msg', 'Unknown error')
                    }
                    
        except Exception as e:
            print(f"❌ Binance order error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_balance(self, asset: str) -> float:
        """Get account balance from Binance"""
        try:
            timestamp = int(time.time() * 1000)
            params = {'timestamp': timestamp}
            params['signature'] = self._generate_signature(params)
            
            session = await self.get_session()
            async with session.get(
                f"{self.base_url}/account",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    balances = data.get('balances', [])
                    asset_balance = next(
                        (float(b['free']) for b in balances if b['asset'] == asset.upper()), 
                        0.0
                    )
                    return asset_balance
                else:
                    print(f"❌ Binance balance check failed: {data}")
                    return 0.0
                    
        except Exception as e:
            print(f"❌ Binance balance error: {e}")
            return 0.0
    
    async def get_order_status(self, order_id: str) -> Dict:
        """Check order status on Binance"""
        try:
            timestamp = int(time.time() * 1000)
            params = {
                'orderId': order_id,
                'timestamp': timestamp
            }
            params['signature'] = self._generate_signature(params)
            
            session = await self.get_session()
            async with session.get(
                f"{self.base_url}/order",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                data = await response.json()
                return data
                
        except Exception as e:
            print(f"❌ Binance order status error: {e}")
            return {}