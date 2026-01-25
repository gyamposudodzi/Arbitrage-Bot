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
        self.balances = {} # Cache: {'binance': 1000.0, ...}
        self._setup_executors()
    
    async def refresh_balances(self):
        """Update cached USDT balances for all exchanges"""
        print("💰 Refreshing balances...")
        tasks = []
        names = []
        
        for name, executor in self.executors.items():
            names.append(name)
            tasks.append(executor.get_balance("USDT"))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for name, res in zip(names, results):
            if isinstance(res, Exception):
                print(f"   ⚠️ Could not fetch balance for {name}: {res}")
                self.balances[name] = 0.0
            else:
                self.balances[name] = float(res)
                print(f"   💵 {name.capitalize()}: ${self.balances[name]:.2f}")
        print("")

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
            
        # Check Execution Mode
        execution_mode = self.bot.config.get("execution_mode", "normal")
        if execution_mode == "hft":
            return await self.execute_parallel_trade(opportunity)
            
        print(f"🚀 EXECUTING REAL LIVE TRADE (Sequential): {opportunity.pair}")
        
        # 1. Get Executors
        buy_exec = self.executors.get(opportunity.buy_exchange)
        sell_exec = self.executors.get(opportunity.sell_exchange)
        
        if not buy_exec or not sell_exec:
            print("❌ Missing executors for this pair")
            return False

        # --- DYNAMIC SIZING & FUND CHECK ---
        buy_balance = self.balances.get(opportunity.buy_exchange, 0.0)
        
        # 1. Check Minimum Viability
        if buy_balance < 10.0: # Minimum $10 to trade
            print(f"❌ Insufficient funds on {opportunity.buy_exchange} (${buy_balance:.2f})")
            return False
            
        # 2. Dynamic Sizing
        # Use 99% of balance to leave dust for fees/variance, capped at max_trade_size
        safe_trade_amount = min(self.max_trade_size, buy_balance * 0.99)
        
        print(f"💰 Dynamic Sizing: Balance ${buy_balance:.2f} -> Trading ${safe_trade_amount:.2f}")

        # 2. Execute (Sequential)
        try:
            quantity = safe_trade_amount / opportunity.buy_price
            
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

    async def execute_parallel_trade(self, opportunity: ArbitrageOpportunity) -> bool:
        """
        Execute trade using HFT Parallel Mode.
        Sends Buy and Sell orders SIMULTANEOUSLY.
        Handles emergency rollback if one leg fails.
        """
        print(f"⚡ HFT EXECUTING PARALLEL TRADE: {opportunity.pair}")
        
        buy_exec = self.executors.get(opportunity.buy_exchange)
        sell_exec = self.executors.get(opportunity.sell_exchange)
        
        if not buy_exec or not sell_exec:
            return False
            
        # --- DYNAMIC SIZING ---
        buy_balance = self.balances.get(opportunity.buy_exchange, 0.0)
        if buy_balance < 10.0:
            print(f"❌ HFT Skipped: Insufficient funds on {opportunity.buy_exchange}")
            return False
            
        safe_trade_amount = min(self.max_trade_size, buy_balance * 0.99)
        quantity = safe_trade_amount / opportunity.buy_price
        
        # Prepare Coroutines (Fire both at once)
        buy_task = buy_exec.place_market_order(
            self.bot.exchanges[opportunity.buy_exchange].normalize_pair(opportunity.pair),
            'buy',
            quantity
        )
        sell_task = sell_exec.place_market_order(
            self.bot.exchanges[opportunity.sell_exchange].normalize_pair(opportunity.pair),
            'sell',
            quantity
        )
        
        print(f"   🔥 Firing orders to {opportunity.buy_exchange} and {opportunity.sell_exchange}...")
        results = await asyncio.gather(buy_task, sell_task, return_exceptions=True)
        
        buy_res, sell_res = results[0], results[1]
        
        # Check for Exceptions
        if isinstance(buy_res, Exception): buy_res = {'success': False, 'error': str(buy_res)}
        if isinstance(sell_res, Exception): sell_res = {'success': False, 'error': str(sell_res)}
        
        buy_ok = buy_res.get('success')
        sell_ok = sell_res.get('success')
        
        # Scenario 1: Both Success (Perfect)
        if buy_ok and sell_ok:
            profit = self.max_trade_size * opportunity.actual_profit_percentage / 100
            self.total_pnl += profit
            print(f"   ✅ HFT SUCCESS! ⚡ Profit: ${profit:.4f}")
            return True
            
        # Scenario 2: Both Failed
        if not buy_ok and not sell_ok:
            print("   ❌ Both legs failed. No exposure.")
            return False
            
        # Scenario 3: Buy OK, Sell FAILED (We hold asset, need to dump)
        if buy_ok and not sell_ok:
            print(f"   ⚠️  PARTIAL EXECUTION: Bought on {opportunity.buy_exchange} but Sell failed!")
            print("   🚨 INITIATING EMERGENCY ROLLBACK (SELL BACK)...")
            
            rollback_res = await buy_exec.place_market_order(
                 self.bot.exchanges[opportunity.buy_exchange].normalize_pair(opportunity.pair),
                 'sell', # Sell back to close
                 quantity
            )
            
            if rollback_res.get('success'):
                print("   ✅ Rollback Success: Position Closed (Loss realized).")
            else:
                print("   ❌❌ CRITICAL: ROLLBACK FAILED. MANUAL INTERVENTION REQUIRED!")
            return False
            
        # Scenario 4: Buy FAILED, Sell OK (We sold short, need to buy back)
        if not buy_ok and sell_ok:
            print(f"   ⚠️  PARTIAL EXECUTION: Sold on {opportunity.sell_exchange} but Buy failed!")
            print("   🚨 INITIATING EMERGENCY ROLLBACK (BUY BACK)...")
            
            rollback_res = await sell_exec.place_market_order(
                 self.bot.exchanges[opportunity.sell_exchange].normalize_pair(opportunity.pair),
                 'buy', # Buy back to close
                 quantity
            )
            
            if rollback_res.get('success'):
                print("   ✅ Rollback Success: Position Closed (Loss realized).")
            else:
                print("   ❌❌ CRITICAL: ROLLBACK FAILED. MANUAL INTERVENTION REQUIRED!")
            return False
            
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
