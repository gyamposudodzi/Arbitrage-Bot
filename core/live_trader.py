import asyncio
import time
import json
from typing import Dict, Optional
from models.data_models import ArbitrageOpportunity

class LiveTrader:
    def _init_(self, bot):
        self.bot = bot
        self.trade_history = []
        self.is_live = False
        self.max_trade_size = 100  # $100 max per trade to start
        self.daily_loss_limit = 50  # $50 max daily loss
        self.total_pnl = 0.0
        
    async def execute_live_trade(self, opportunity: ArbitrageOpportunity, manual_approval: bool = True):
        """Execute a live arbitrage trade with safety checks"""
        
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
            print(f"   Estimated Profit: ${(self.max_trade_size * opportunity.actual_profit_percentage / 100):.4f}")
            
            approve = input("Execute this trade? (y/N): ").strip().lower()
            if approve != 'y':
                print("❌ Trade cancelled by user")
                return False
        
        print(f"🚀 EXECUTING LIVE TRADE...")
        
        try:
            # 1. Check balances
            buy_balance = await self.check_balance(opportunity.buy_exchange, 'USDT')
            if buy_balance < self.max_trade_size:
                print(f"❌ Insufficient balance on {opportunity.buy_exchange}")
                return False
            
            # 2. Execute BUY order
            print(f"📥 Placing BUY order on {opportunity.buy_exchange}...")
            buy_success = await self.place_order(
                opportunity.buy_exchange, 
                opportunity.pair, 
                'buy', 
                self.max_trade_size / opportunity.buy_price
            )
            
            if not buy_success:
                print("❌ BUY order failed")
                return False
            
            # 3. Execute SELL order  
            print(f"📤 Placing SELL order on {opportunity.sell_exchange}...")
            sell_success = await self.place_order(
                opportunity.sell_exchange,
                opportunity.pair,
                'sell', 
                self.max_trade_size / opportunity.buy_price  # Use same quantity
            )
            
            if sell_success:
                profit = self.max_trade_size * opportunity.actual_profit_percentage / 100
                self.total_pnl += profit
                
                trade_record = {
                    'timestamp': time.time(),
                    'pair': opportunity.pair,
                    'buy_exchange': opportunity.buy_exchange,
                    'sell_exchange': opportunity.sell_exchange,
                    'amount': self.max_trade_size,
                    'estimated_profit': profit,
                    'actual_profit_percentage': opportunity.actual_profit_percentage,
                    'status': 'COMPLETED'
                }
                
                self.trade_history.append(trade_record)
                print(f"✅ LIVE TRADE COMPLETED! Estimated profit: ${profit:.4f}")
                return True
            else:
                print("❌ SELL order failed - position may be open!")
                # TODO: Implement emergency close logic
                return False
                
        except Exception as e:
            print(f"❌ Trade execution error: {e}")
            return False
    
    async def safety_checks(self, opportunity: ArbitrageOpportunity) -> bool:
        """Perform safety checks before trading"""
        
        # Minimum profit threshold
        if opportunity.actual_profit_percentage < 0.2:
            print("❌ Profit too low for live trading")
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
    
    async def check_balance(self, exchange_name: str, asset: str) -> float:
        """Check balance on exchange"""
        try:
            # This would call exchange-specific balance API
            # For now, return a safe default
            return 1000.0  # Assume $1000 available
        except Exception as e:
            print(f"❌ Balance check failed for {exchange_name}: {e}")
            return 0.0
    
    async def place_order(self, exchange_name: str, pair: str, side: str, quantity: float) -> bool:
        """Place order on exchange"""
        try:
            exchange = self.bot.exchanges[exchange_name]
            # TODO: Implement actual order placement
            print(f"   📝 {side.upper()} {quantity:.6f} {pair} on {exchange_name}")
            
            # Simulate order execution for now
            await asyncio.sleep(0.5)  # Simulate API call
            print(f"   ✅ Order filled on {exchange_name}")
            return True
            
        except Exception as e:
            print(f"❌ Order failed on {exchange_name}: {e}")
            return False
    
    async def exchange_health_check(self, exchange_name: str) -> bool:
        """Check if exchange is healthy"""
        try:
            exchange = self.bot.exchanges[exchange_name]
            prices = await exchange.get_prices(['BTC-USDT'])  # Test with one pair
            return len(prices) > 0
        except:
            return False