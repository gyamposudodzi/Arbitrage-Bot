import asyncio
import time
import json
from typing import Dict, Optional, List
from models.data_models import ArbitrageOpportunity, FundingOpportunity

# Import the order executors
from .binance_executor import BinanceOrderExecutor
from .kucoin_executor import KuCoinOrderExecutor
from .coinbase_executor import CoinbaseOrderExecutor
from .kraken_executor import KrakenOrderExecutor
from .bybit_executor import BybitOrderExecutor
from .okx_executor import OKXOrderExecutor
from .gateio_executor import GateIOOrderExecutor

class ExecutionManager:
    def __init__(self, bot):
        self.bot = bot
        self.trade_history = []
        self.is_live = False
        self.max_trade_size = 100  # $100 max per trade to start
        self.daily_loss_limit = 50  # $50 max daily loss
        self.total_pnl = 0.0
        
        # Initialize order executors
        self.executors = {}
        self._setup_executors()
        
    def _setup_executors(self):
        """Setup order executors for each enabled exchange"""
        print("🔄 Setting up execution layer...")
        for exchange_name, config in self.bot.config["exchanges"].items():
            if config["enabled"] and config.get("api_key"):
                try:
                    executor = None
                    if exchange_name == "binance":
                        executor = BinanceOrderExecutor(
                            config["api_key"], config["api_secret"]
                        )
                    elif exchange_name == "kucoin":
                        executor = KuCoinOrderExecutor(
                            config["api_key"], config["api_secret"], config.get("api_passphrase", "")
                        )
                    elif exchange_name == "coinbase":
                        executor = CoinbaseOrderExecutor(
                            config["api_key"], config["api_secret"]
                        )
                    elif exchange_name == "kraken":
                        executor = KrakenOrderExecutor(
                            config["api_key"], config["api_secret"]
                        )
                    elif exchange_name == "bybit":
                        executor = BybitOrderExecutor(
                            config["api_key"], config["api_secret"]
                        )
                    elif exchange_name == "okx":
                        executor = OKXOrderExecutor(
                            config["api_key"], config["api_secret"], config.get("api_passphrase", "")
                        )
                    elif exchange_name == "gateio":
                        executor = GateIOOrderExecutor(
                            config["api_key"], config["api_secret"]
                        )
                    
                    if executor:
                        self.executors[exchange_name] = executor
                        print(f"   ✅ {exchange_name.capitalize()} executor ready")
                    else:
                        print(f"   ⚠️  No executor for {exchange_name}")
                        
                except Exception as e:
                    print(f"   ❌ Failed to setup {exchange_name} executor: {e}")
        
    async def execute_trade(self, opportunity: ArbitrageOpportunity, manual_approval: bool = True) -> bool:
        """Execute a live arbitrage trade with REAL orders"""
        
        if not self.is_live:
            print("❌ Live trading disabled.")
            return False
            
        print(f"🚀 EXECUTING REAL LIVE TRADE: {opportunity.pair}")
        
        # 1. Get Executors
        buy_exec = self.executors.get(opportunity.buy_exchange)
        sell_exec = self.executors.get(opportunity.sell_exchange)
        
        if not buy_exec or not sell_exec:
            print("❌ Missing executors for this pair")
            return False

        # 2. Execute (Simple sequential for now)
        # Ideally we'd use gather, but let's be safe first
        
        try:
            quantity = self.max_trade_size / opportunity.buy_price
            
            # Buy
            print(f"📥 Buying on {opportunity.buy_exchange}...")
            buy_res = await buy_exec.place_market_order(
                self.bot.exchanges[opportunity.buy_exchange].normalize_pair(opportunity.pair),
                'buy',
                quantity
            )
            
            if not buy_res.get('success'):
                print(f"❌ Buy Failed: {buy_res.get('error')}")
                return False
                
            # Sell
            print(f"📤 Selling on {opportunity.sell_exchange}...")
            sell_res = await sell_exec.place_market_order(
                self.bot.exchanges[opportunity.sell_exchange].normalize_pair(opportunity.pair),
                'sell',
                quantity
            )
            
            if sell_res.get('success'):
                profit = self.max_trade_size * opportunity.actual_profit_percentage / 100
                self.total_pnl += profit
                print(f"✅ TRADE COMPLETE! Profit: ${profit:.4f}")
                
                # Record
                self.trade_history.append({
                    'timestamp': time.time(),
                    'pair': opportunity.pair,
                    'profit': profit,
                    'buy_id': buy_res.get('order_id'),
                    'sell_id': sell_res.get('order_id')
                })
                return True
            else:
                print(f"❌ Sell Failed: {sell_res.get('error')}")
                print("⚠️  CRITICAL: Open Position!")
                return False
                
        except Exception as e:
            print(f"❌ Execution Exception: {e}")
            return False

    async def execute_funding_trade(self, opportunity: FundingOpportunity, manual_approval: bool = True) -> bool:
        """
        Execute a Funding Rate Arbitrage trade (Delta Neutral).
        Strategy: Buy Spot + Short Futures (Perpetual).
        """
        if not self.is_live:
            print("❌ Live trading disabled.")
            return False
            
        # Currently only supporting Binance for Funding Arb
        if opportunity.exchange != "binance":
            print(f"❌ Funding execution only supported for Binance (got {opportunity.exchange})")
            return False
            
        executor = self.executors.get("binance")
        if not executor:
            print("❌ Binance executor not available")
            return False
            
        print(f"🚀 EXECUTING FUNDING ARB: {opportunity.pair}")
        print(f"   Rate: {opportunity.funding_rate*100:.4f}% | APY: {opportunity.annualized_rate:.2f}%")
        
        try:
            # 1. Calculate Quantity
            # We split capital: $50 Spot, $50 Futures Margin (approx)
            # Actually, for delta neutral, we need 1:1 exposure size.
            # Example: Buy $100 BTC, Short $100 BTC Futures (1x leverage).
            
            trade_size = self.max_trade_size 
            quantity = trade_size / opportunity.mark_price
            
            # 2. Execute Spot BUY
            print(f"📥 Buying {quantity:.4f} {opportunity.pair} Spot...")
            spot_res = await executor.place_market_order(
                opportunity.pair, 'buy', quantity
            )
            
            if not spot_res.get('success'):
                print(f"❌ Spot Buy Failed: {spot_res.get('error')}")
                return False
                
            executed_qty = spot_res.get('executed_quantity', quantity)
            print(f"   ✅ Spot Bought. Now Shorting Futures...")
            
            # 3. Execute Futures SHORT (Hedge)
            # Use same quantity to be delta neutral
            futures_res = await executor.place_futures_order(
                opportunity.pair, 'sell', executed_qty
            )
            
            if futures_res.get('success'):
                print(f"   ✅ Futures Shorted. DELTA NEUTRAL POSITIONS OPEN! 🛡️")
                
                # Record
                self.trade_history.append({
                    'timestamp': time.time(),
                    'type': 'FUNDING_ARB',
                    'pair': opportunity.pair,
                    'spot_id': spot_res.get('order_id'),
                    'futures_id': futures_res.get('order_id'),
                    'qty': executed_qty,
                    'apy': opportunity.annualized_rate
                })
                return True
            else:
                print(f"❌ Futures Short Failed: {futures_res.get('error')}")
                print("⚠️  CRITICAL: SPOT BOUGHT BUT HEDGE FAILED. SELLING SPOT NOW...")
                
                # Rollback: Sell Spot
                rollback_res = await executor.place_market_order(
                    opportunity.pair, 'sell', executed_qty
                )
                if rollback_res.get('success'):
                    print("   ✅ Rollback successful. Position closed.")
                else:
                    print("   ❌ ROLLBACK FAILED. YOU HAVE EXPOSED SPOT POSITION!")
                return False
                
        except Exception as e:
            print(f"❌ Funding Execution Exception: {e}")
            return False

    async def cleanup(self):
        """Clean up order executor sessions"""
        print("Closing execution layer sessions...")
        for name, executor in self.executors.items():
            try:
                await executor.close_session()
                print(f"   ✅ Closed {name} session")
            except Exception as e:
                print(f"   ❌ Error closing {name}: {e}")
