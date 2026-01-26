import aiohttp
import time
import hmac
import hashlib
from typing import Dict
from .base_executor import BaseOrderExecutor

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
    
    async def place_futures_order(self, symbol: str, side: str, quantity: float, leverage: int = 1) -> Dict:
        """
        Place a Futures order on Binance (USD-M).
        """
        try:
            self.futures_url = "https://fapi.binance.com/fapi/v1"
            timestamp = int(time.time() * 1000)
            
            # 1. Set Leverage first (optional, but good practice)
            # We assume isolated margin for safety usually, but API defaults to Cross often.
            # For this MVP we just place the order.
            
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': 'MARKET',
                'quantity': quantity,
                'timestamp': timestamp
            }
            
            # Futures signature is same generation logic
            params['signature'] = self._generate_signature(params)
            
            session = await self.get_session()
            async with session.post(
                f"{self.futures_url}/order",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    print(f"✅ Binance Futures {side} executed: {quantity} {symbol}")
                    return {
                        'success': True,
                        'order_id': data.get('orderId'),
                        'status': data.get('status'),
                        'executed_quantity': float(data.get('executedQty', 0))
                    }
                else:
                    print(f"❌ Binance Futures order failed: {data}")
                    return {
                        'success': False,
                        'error': data.get('msg', 'Unknown error')
                    }
                    
        except Exception as e:
            print(f"❌ Binance Futures error: {e}")
            return {'success': False, 'error': str(e)}

    async def place_limit_order(self, symbol: str, side: str, price: float, quantity: float, time_in_force: str = "GTC") -> Dict:
        """
        Place a Limit Order (Maker).
        time_in_force: GTC (Good Till Cancel), IOC (Immediate or Cancel), FOK (Fill or Kill)
        """
        try:
            timestamp = int(time.time() * 1000)
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': 'LIMIT',
                'timeInForce': time_in_force,
                'quantity': quantity,
                'price': price,
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
                    print(f"✅ Binance Limit {side} placed: {quantity} @ {price}")
                    return {
                        'success': True,
                        'order_id': data.get('orderId'),
                        'status': data.get('status'),
                        'executed_quantity': float(data.get('executedQty', 0))
                    }
                else:
                    print(f"❌ Binance Limit order failed: {data}")
                    return {
                        'success': False,
                        'error': data.get('msg', 'Unknown error')
                    }
        except Exception as e:
            print(f"❌ Binance Limit Exception: {e}")
            return {'success': False, 'error': str(e)}

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
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an open order on Binance"""
        try:
            timestamp = int(time.time() * 1000)
            params = {
                'symbol': symbol,
                'orderId': order_id,
                'timestamp': timestamp
            }
            params['signature'] = self._generate_signature(params)
            
            session = await self.get_session()
            async with session.delete(
                f"{self.base_url}/order",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    print(f"✅ Binance order {order_id} CANCELED.")
                    return True
                else:
                    print(f"❌ Failed to cancel order: {data}")
                    return False
        except Exception as e:
            print(f"❌ Cancel exception: {e}")
            return False
    
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

    async def get_withdrawal_info(self, asset: str) -> Dict:
        """
        Get withdrawal fee and min amount for an asset.
        Returns: {'fee': float, 'min_withdraw': float, 'network': str}
        """
        try:
            # Endpoint: /sapi/v1/capital/config/getall
            # This is a signed endpoint
            sapi_url = "https://api.binance.com/sapi/v1"
            timestamp = int(time.time() * 1000)
            params = {'timestamp': timestamp}
            params['signature'] = self._generate_signature(params)
            
            session = await self.get_session()
            async with session.get(
                f"{sapi_url}/capital/config/getall",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Data is list of all coins
                    for coin_info in data:
                        if coin_info['coin'] == asset.upper():
                            # Find best network (usually one with lowest fee or specific one)
                            # For Arb, we usually use the cheapest or the one matching the destination.
                            # For simplicity, let's take the first non-congested one or just the first.
                            
                            networks = coin_info.get('networkList', [])
                            if networks:
                                # Simple heuristic: Pick lowest fee
                                best_net = min(networks, key=lambda x: float(x.get('withdrawFee', 999)))
                                return {
                                    'fee': float(best_net.get('withdrawFee', 0)),
                                    'min_withdraw': float(best_net.get('withdrawMin', 0)),
                                    'network': best_net.get('network')
                                }
                    return {}
                else:
                    return {}
        except Exception as e:
            print(f"❌ Binance withdrawal info error: {e}")
            return {}

    async def withdraw(self, asset: str, amount: float, address: str, network: str = None) -> bool:
        """
        Withdraw funds from Binance.
        Requires SAPI (Spot API) permissions and IP Whitelist on API Key.
        """
        try:
            # POST /sapi/v1/capital/withdraw/apply
            sapi_url = "https://api.binance.com/sapi/v1"
            timestamp = int(time.time() * 1000)
            
            params = {
                'coin': asset.upper(),
                'address': address,
                'amount': amount,
                'timestamp': timestamp
            }
            if network:
                params['network'] = network
                
            params['signature'] = self._generate_signature(params)
            
            session = await self.get_session()
            async with session.post(
                f"{sapi_url}/capital/withdraw/apply",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    print(f"✅ Binance Withdrawal Submitted: {amount} {asset} -> {address}")
                    # Returns {'id': 'withdraw_id'}
                    return True
                else:
                    print(f"❌ Withdrawal Failed: {data}")
                    return False
                    
        except Exception as e:
            print(f"❌ Withdrawal Exception: {e}")
            return False