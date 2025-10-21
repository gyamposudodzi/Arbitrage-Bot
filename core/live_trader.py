import asyncio
import time
import json
from typing import Dict, Optional
from models.data_models import ArbitrageOpportunity

# Import the order executors
from order_execution.binance_order import BinanceOrderExecutor
from order_execution.kucoin_order import KuCoinOrderExecutor
# Add other executors as you implement them:
# from order_execution.bybit_order import BybitOrderExecutor
# from order_execution.okx_order import OKXOrderExecutor
# from order_execution.gateio_order import GateIOOrderExecutor

class LiveTrader:
    def __init__(self, bot):
        self.bot = bot
        self.trade_history = []
        self.is_live = False
        self.max_trade_size = 100  # $100 max per trade to start
        self.daily_loss_limit = 50  # $50 max daily loss
        self.total_pnl = 0.0
        
        # Initialize order executors
        self.order_executors = {}
        self._setup_order_executors()
        
    def _setup_order_executors(self):
        """Setup order executors for each enabled exchange"""
        print("🔄 Setting up order executors...")
        for exchange_name, config in self.bot.config["exchanges"].items():
            if config["enabled"] and config.get("api_key"):
                try:
                    if exchange_name == "binance":
                        self.order_executors[exchange_name] = BinanceOrderExecutor(
                            config["api_key"], config["api_secret"]
                        )
                        print(f"   ✅ Binance order executor ready")
                    elif exchange_name == "kucoin":
                        self.order_executors[exchange_name] = KuCoinOrderExecutor(
                            config["api_key"], config["api_secret"], config.get("api_passphrase", "")
                        )
                        print(f"   ✅ KuCoin order executor ready")
                    # Add other exchanges as you implement them
                    # elif exchange_name == "bybit":
                    #     self.order_executors[exchange_name] = BybitOrderExecutor(
                    #         config["api_key"], config["api_secret"]
                    #     )
                    # elif exchange_name == "okx":
                    #     self.order_executors[exchange_name] = OKXOrderExecutor(
                    #         config["api_key"], config["api_secret"], config.get("api_passphrase", "")
                    #     )
                    # elif exchange_name == "gateio":
                    #     self.order_executors[exchange_name] = GateIOOrderExecutor(
                    #         config["api_key"], config["api_secret"]
                    #     )
                    else:
                        print(f"   ⚠️  Order executor not implemented for {exchange_name}")
                        
                except Exception as e:
                    print(f"   ❌ Failed to setup {exchange_name} order executor: {e}")
        
    async def execute_live_trade(self, opportunity: ArbitrageOpportunity, manual_approval: bool = True):
        """Execute a live arbitrage trade with REAL orders"""
        
        if not self.is_live:
            print("❌ Live trading disabled. Enable in config.")
            return False
        
        # Safety checks
        if not await self.safety_checks(opportunity):
            return False
        
        # Manual approval for first trades
        if manual_approval:
            print(f"\n🎯 LIVE TRADE OPPORTUNITY:")
            print(f"   {opportunity.pair}: {opportunity.buy_exchange} → {opportunity.sell_exchange}")
            print(f"   Net Profit: {opportunity.actual_profit_percentage:.4f}%")
            print(f"   Trade Amount: ${self.max_trade_size}")
            print(f"   Estimated Profit: ${(self.max_trade_size * opportunity.actual_profit_percentage / 100):.4f}")
            
            approve = input("Execute this REAL trade? (y/N): ").strip().lower()
            if approve != 'y':
                print("❌ Trade cancelled by user")
                return False
        
        print(f"🚀 EXECUTING REAL LIVE TRADE...")
        
        try:
            # 1. Check REAL balances using order executors
            buy_balance = await self.check_balance(opportunity.buy_exchange, 'USDT')
            if buy_balance < self.max_trade_size:
                print(f"❌ Insufficient REAL balance on {opportunity.buy_exchange}: ${buy_balance:.2f}")
                return False
            
            # 2. Execute REAL BUY order using order executor
            print(f"📥 Placing REAL BUY order on {opportunity.buy_exchange}...")
            buy_quantity = self.max_trade_size / opportunity.buy_price
            buy_result = await self.place_real_order(
                opportunity.buy_exchange, 
                opportunity.pair, 
                'buy', 
                buy_quantity
            )
            
            if not buy_result.get('success'):
                print(f"❌ REAL BUY order failed: {buy_result.get('error')}")
                return False
            
            # 3. Execute REAL SELL order using order executor
            print(f"📤 Placing REAL SELL order on {opportunity.sell_exchange}...")
            sell_result = await self.place_real_order(
                opportunity.sell_exchange,
                opportunity.pair,
                'sell', 
                buy_quantity  # Use same quantity from buy
            )
            
            if sell_result.get('success'):
                profit = self.max_trade_size * opportunity.actual_profit_percentage / 100
                self.total_pnl += profit
                
                trade_record = {
                    'timestamp': time.time(),
                    'pair': opportunity.pair,
                    'buy_exchange': opportunity.buy_exchange,
                    'sell_exchange': opportunity.sell_exchange,
                    'amount': self.max_trade_size,
                    'quantity': buy_quantity,
                    'estimated_profit': profit,
                    'actual_profit_percentage': opportunity.actual_profit_percentage,
                    'buy_order_id': buy_result.get('order_id'),
                    'sell_order_id': sell_result.get('order_id'),
                    'status': 'COMPLETED'
                }
                
                self.trade_history.append(trade_record)
                print(f"✅ REAL LIVE TRADE COMPLETED! Estimated profit: ${profit:.4f}")
                return True
            else:
                print(f"❌ REAL SELL order failed: {sell_result.get('error')}")
                # TODO: Implement emergency position close
                print("⚠️  WARNING: You may have an open position that needs manual closing!")
                return False
                
        except Exception as e:
            print(f"❌ REAL Trade execution error: {e}")
            return False
    
    async def place_real_order(self, exchange_name: str, pair: str, side: str, quantity: float) -> Dict:
        """Place REAL order using the order executor"""
        if exchange_name not in self.order_executors:
            return {
                'success': False, 
                'error': f'No order executor available for {exchange_name}. Please implement it in order_execution/ folder.'
            }
        
        executor = self.order_executors[exchange_name]
        
        # Convert pair to exchange-specific format using the existing API
        exchange_api = self.bot.exchanges[exchange_name]
        symbol = exchange_api.normalize_pair(pair)
        
        print(f"   🔄 Executing {side.upper()} {quantity:.6f} {symbol} on {exchange_name}")
        return await executor.place_market_order(symbol, side, quantity)
    
    async def check_balance(self, exchange_name: str, asset: str) -> float:
        """Check REAL balance using order executor"""
        if exchange_name not in self.order_executors:
            print(f"   ⚠️  No order executor for {exchange_name}, using simulated balance")
            return 1000.0  # Fallback to simulated balance
        
        executor = self.order_executors[exchange_name]
        balance = await executor.get_balance(asset)
        print(f"   💰 REAL Balance on {exchange_name}: ${balance:.2f} {asset}")
        return balance
    
    async def safety_checks(self, opportunity: ArbitrageOpportunity) -> bool:
        """Perform safety checks before trading"""
        
        # Minimum profit threshold
        if opportunity.actual_profit_percentage < 0.2:
            print("❌ Profit too low for live trading")
            return False
        
        # Check if order executors are available for both exchanges
        if opportunity.buy_exchange not in self.order_executors:
            print(f"❌ No order executor available for {opportunity.buy_exchange}")
            return False
            
        if opportunity.sell_exchange not in self.order_executors:
            print(f"❌ No order executor available for {opportunity.sell_exchange}")
            return False
        
        # Exchange connectivity check
        if not await self.exchange_health_check(opportunity.buy_exchange):
            return False
        if not await self.exchange_health_check(opportunity.sell_exchange):
            return False
            
        # Daily loss limit check
        if self.total_pnl < -self.daily_loss_limit:
            print("❌ Daily loss limit reached")
            return False
        
        return True
    
    async def exchange_health_check(self, exchange_name: str) -> bool:
        """Check if exchange is healthy"""
        try:
            exchange = self.bot.exchanges[exchange_name]
            prices = await exchange.get_prices(['BTC-USDT'])  # Test with one pair
            return len(prices) > 0
        except Exception as e:
            print(f"❌ Health check failed for {exchange_name}: {e}")
            return False
    
    async def cleanup(self):
        """Clean up order executor sessions"""
        print("Closing order executor sessions...")
        for exchange_name, executor in self.order_executors.items():
            try:
                await executor.close_session()
                print(f"✅ Closed {exchange_name} order executor session")
            except Exception as e:
                print(f"❌ Error closing {exchange_name} order executor: {e}")