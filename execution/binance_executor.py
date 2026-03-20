import aiohttp
import time
import hmac
import hashlib
import asyncio
from decimal import Decimal, ROUND_DOWN
from typing import Dict
from .base_executor import BaseOrderExecutor

class BinanceOrderExecutor(BaseOrderExecutor):
    """Binance order execution implementation"""
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.base_url = "https://api.binance.com/api/v3"
        self.symbol_rules = {}
    
    def _generate_signature(self, params: Dict) -> str:
        """Generate HMAC SHA256 signature for Binance"""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _get_symbol_rules(self, symbol: str) -> Dict:
        """Fetch and cache Binance trading rules for a symbol."""
        if symbol in self.symbol_rules:
            return self.symbol_rules[symbol]

        session = await self.get_session()
        try:
            async with session.get(f"{self.base_url}/exchangeInfo", params={"symbol": symbol}) as response:
                if response.status != 200:
                    return {}

                data = await response.json()
                symbols = data.get("symbols", [])
                if not symbols:
                    return {}

                info = symbols[0]
                filters = {item["filterType"]: item for item in info.get("filters", [])}
                rules = {
                    "base_asset_precision": int(info.get("baseAssetPrecision", 8)),
                    "quote_asset_precision": int(info.get("quoteAssetPrecision", 8)),
                    "lot_step_size": filters.get("LOT_SIZE", {}).get("stepSize"),
                    "lot_min_qty": filters.get("LOT_SIZE", {}).get("minQty"),
                    "market_step_size": filters.get("MARKET_LOT_SIZE", {}).get("stepSize"),
                    "market_min_qty": filters.get("MARKET_LOT_SIZE", {}).get("minQty"),
                    "min_notional": filters.get("MIN_NOTIONAL", {}).get("minNotional") or filters.get("NOTIONAL", {}).get("minNotional")
                }
                self.symbol_rules[symbol] = rules
                return rules
        except Exception:
            return {}

    @staticmethod
    def _round_to_step(value: float, step_size: str) -> float:
        if not step_size:
            return value

        step = Decimal(step_size)
        if step == 0:
            return value

        quantity = Decimal(str(value))
        rounded = (quantity / step).to_integral_value(rounding=ROUND_DOWN) * step
        return float(rounded)

    @staticmethod
    def _format_decimal(value: float, precision: int = 8) -> str:
        text = f"{value:.{precision}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text
    
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

    async def place_market_order(self, symbol: str, side: str, quantity: float = None, quote_order_qty: float = None) -> Dict:
        """Place a market order on Binance"""
        try:
            timestamp = int(time.time() * 1000)
            rules = await self._get_symbol_rules(symbol)
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': 'MARKET',
                'timestamp': timestamp
            }

            if quote_order_qty is not None and side.lower() == 'buy':
                precision = rules.get("quote_asset_precision", 8)
                params['quoteOrderQty'] = self._format_decimal(quote_order_qty, precision)
            else:
                if quantity is None:
                    raise ValueError("quantity is required when quote_order_qty is not used")
                step_size = rules.get("lot_step_size") or rules.get("market_step_size")
                adjusted_quantity = self._round_to_step(quantity, step_size)
                min_qty = rules.get("market_min_qty") or rules.get("lot_min_qty")
                if min_qty and adjusted_quantity < float(min_qty):
                    return {
                        'success': False,
                        'error': f"Quantity {adjusted_quantity} below minimum {min_qty} for {symbol}"
                    }
                base_precision = rules.get("base_asset_precision", 8)
                params['quantity'] = self._format_decimal(adjusted_quantity, base_precision)
            
            params['signature'] = self._generate_signature(params)
            
            session = await self.get_session()
            async with session.post(
                f"{self.base_url}/order",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    executed_amount = params.get('quantity', params.get('quoteOrderQty'))
                    fills = data.get('fills', [])
                    net_executed_quantity = float(data.get('executedQty', 0))
                    net_quote_quantity = float(data.get('cummulativeQuoteQty', 0))

                    if fills:
                        gross_base = sum(float(fill.get('qty', 0)) for fill in fills)
                        gross_quote = sum(float(fill.get('qty', 0)) * float(fill.get('price', 0)) for fill in fills)
                        base_commission = sum(
                            float(fill.get('commission', 0))
                            for fill in fills
                            if fill.get('commissionAsset', '').upper() == symbol.replace("USDT", "").replace("BTC", "")
                        )
                        quote_assets = {"USDT", "BTC", "ETH", "BNB", "FDUSD", "USDC"}
                        quote_asset = next((asset for asset in quote_assets if symbol.endswith(asset)), "")
                        quote_commission = sum(
                            float(fill.get('commission', 0))
                            for fill in fills
                            if fill.get('commissionAsset', '').upper() == quote_asset
                        )
                        if gross_base > 0:
                            net_executed_quantity = max(gross_base - base_commission, 0.0)
                        if gross_quote > 0:
                            net_quote_quantity = max(gross_quote - quote_commission, 0.0)

                    print(f"✅ Binance {side} order executed: {executed_amount} {symbol}")
                    return {
                        'success': True,
                        'order_id': data.get('orderId'),
                        'status': data.get('status'),
                        'executed_quantity': float(data.get('executedQty', 0)),
                        'net_executed_quantity': net_executed_quantity,
                        'cummulative_quote_qty': float(data.get('cummulativeQuoteQty', 0)),
                        'net_cummulative_quote_qty': net_quote_quantity,
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

    async def get_convert_quote(self, from_asset: str, to_asset: str, from_amount: float, wallet_type: str = "SPOT") -> Dict:
        """Request a Binance Convert quote."""
        try:
            sapi_url = "https://api.binance.com/sapi/v1"
            timestamp = int(time.time() * 1000)
            params = {
                'fromAsset': from_asset.upper(),
                'toAsset': to_asset.upper(),
                'fromAmount': self._format_decimal(from_amount, 8),
                'walletType': wallet_type,
                'validTime': '10s',
                'timestamp': timestamp
            }
            params['signature'] = self._generate_signature(params)

            session = await self.get_session()
            async with session.post(
                f"{sapi_url}/convert/getQuote",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                data = await response.json()
                if response.status == 200 and data.get('quoteId'):
                    return {'success': True, **data}
                return {'success': False, 'error': data.get('msg', data)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def accept_convert_quote(self, quote_id: str) -> Dict:
        """Accept a Binance Convert quote."""
        try:
            sapi_url = "https://api.binance.com/sapi/v1"
            timestamp = int(time.time() * 1000)
            params = {
                'quoteId': quote_id,
                'timestamp': timestamp
            }
            params['signature'] = self._generate_signature(params)

            session = await self.get_session()
            async with session.post(
                f"{sapi_url}/convert/acceptQuote",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                data = await response.json()
                if response.status == 200 and data.get('orderId'):
                    return {'success': True, **data}
                return {'success': False, 'error': data.get('msg', data)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def get_convert_order_status(self, order_id: str) -> Dict:
        """Fetch Binance Convert order status."""
        try:
            sapi_url = "https://api.binance.com/sapi/v1"
            timestamp = int(time.time() * 1000)
            params = {
                'orderId': order_id,
                'timestamp': timestamp
            }
            params['signature'] = self._generate_signature(params)

            session = await self.get_session()
            async with session.get(
                f"{sapi_url}/convert/orderStatus",
                params=params,
                headers={'X-MBX-APIKEY': self.api_key}
            ) as response:
                data = await response.json()
                if response.status == 200 and data.get('orderStatus'):
                    return {'success': True, **data}
                return {'success': False, 'error': data.get('msg', data)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def convert_asset(self, from_asset: str, to_asset: str, from_amount: float) -> Dict:
        """Try Binance Convert from one asset to another."""
        quote = await self.get_convert_quote(from_asset, to_asset, from_amount)
        if not quote.get('success'):
            return quote

        accepted = await self.accept_convert_quote(quote['quoteId'])
        if not accepted.get('success'):
            return accepted

        order_id = accepted.get('orderId')
        for _ in range(10):
            await asyncio.sleep(1)
            status = await self.get_convert_order_status(order_id)
            if not status.get('success'):
                return status

            if status.get('orderStatus') == 'SUCCESS':
                return {'success': True, **status}
            if status.get('orderStatus') == 'FAIL':
                return {'success': False, 'error': status}

        return {'success': False, 'error': 'Convert order status timed out'}

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
