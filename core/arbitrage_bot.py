import asyncio
import time
import json
from typing import Dict, List
from exchanges import BinanceAPI, CoinbaseAPI, KrakenAPI, KuCoinAPI, GateIOAPI, BybitAPI, OKXAPI
from core.arbitrage_engine import ArbitrageEngine
from core.triangular_arb import TriangularArbitrageEngine
from core.database_manager import DatabaseManager
from core.funding_arb import FundingRateArbitrageEngine
from models.data_models import ArbitrageOpportunity
from core.paper_trader import PaperTrader
from execution.manager import ExecutionManager  # NEW
from core.fee_manager import FeeManager # NEW
from core.logger import setup_logger

class ArbitrageBot:
    def __init__(self, config_file: str = "config.json"):
        self.logger = setup_logger("ArbitrageBot")
        self.config = self.load_config(config_file)
        self.exchanges = {}
        self.opportunities = []
        self.setup_exchanges()
        self.db = DatabaseManager()  # NEW: Initialize Database
        self.paper_trader = PaperTrader(initial_balance=1000, db_manager=self.db)
        self.executor = ExecutionManager(self)  # NEW
        self.executor.is_live = self.config.get("live_trading", {}).get("enabled", False)
        self.fee_manager = FeeManager(self.executor) # NEW
        self.tri_engine = TriangularArbitrageEngine(self)
        self.funding_engine = FundingRateArbitrageEngine(self)
        
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Default configuration
            return {
                "exchanges": {
                    "binance": {"enabled": True, "api_key": "", "api_secret": ""},
                    "coinbase": {"enabled": True, "api_key": "", "api_secret": ""},
                    "kraken": {"enabled": True, "api_key": "", "api_secret": ""},
                    "kucoin": {"enabled": True, "api_key": "", "api_secret": "", "api_passphrase": ""},
                    "bybit": {"enabled": True, "api_key": "", "api_secret": ""},
                    "okx": {"enabled": True, "api_key": "", "api_secret": "", "api_passphrase": ""},
                    "gateio": {"enabled": True, "api_key": "", "api_secret": ""}
                },
                "trading_pairs": ["BTC-USDT", "ETH-USDT", "ADA-USDT"],
                "min_spread_percentage": 0.5,
                "update_interval": 5,
                "max_opportunities": 10,
                "live_trading": {  # NEW
                    "enabled": False,
                    "max_trade_size": 100,
                    "daily_loss_limit": 50,
                    "manual_approval": True
                }
            }
    
    def setup_exchanges(self):
        """Initialize exchange connectors"""
        if self.config["exchanges"]["binance"]["enabled"]:
            self.exchanges["binance"] = BinanceAPI(self.config["exchanges"]["binance"])
        if self.config["exchanges"]["coinbase"]["enabled"]:
            self.exchanges["coinbase"] = CoinbaseAPI(self.config["exchanges"]["coinbase"])
        if self.config["exchanges"]["kraken"]["enabled"]:
            self.exchanges["kraken"] = KrakenAPI(self.config["exchanges"]["kraken"])
        if self.config["exchanges"]["kucoin"]["enabled"]:
            self.exchanges["kucoin"] = KuCoinAPI(self.config["exchanges"]["kucoin"])
        if self.config["exchanges"]["bybit"]["enabled"]:
            self.exchanges["bybit"] = BybitAPI(self.config["exchanges"]["bybit"])
        if self.config["exchanges"]["okx"]["enabled"]:
            self.exchanges["okx"] = OKXAPI(self.config["exchanges"]["okx"])
        if self.config["exchanges"]["gateio"]["enabled"]:
            self.exchanges["gateio"] = GateIOAPI(self.config["exchanges"]["gateio"])
    
    async def run(self):
        """Main execution loop with live trading"""
        engine = ArbitrageEngine(self)
        
        # Start WebSocket Streams
        await engine.start_streaming()
        self.logger.info("⏳ Waiting 5 seconds for streams to warm up...")
        await asyncio.sleep(5)

        
        
        mode = "LIVE TRADING 🚀" if self.executor.is_live else "PAPER TRADING 💰"
        self.logger.info(f"Arbitrage Bot Started! {mode}")
        self.logger.info("=" * 80)
        
        if self.executor.is_live:
            print("🔐 LIVE TRADING ENABLED - Trades will execute with REAL MONEY!")
            print("💰 Starting with safety limits:")
            print(f"   Max trade size: ${self.executor.max_trade_size}")
            print(f"   Daily loss limit: ${self.executor.daily_loss_limit}")
            print("   Manual approval required for each trade")
        
        try:
            cycle_count = 0
            while True:
                start_time = time.time()
                cycle_count += 1
                
                opportunities = await engine.find_opportunities()
                
                # --- PHASE 4: Liquidity Verification (VWAP) ---
                # Check top 3 opportunities for actual liquidity depth
                verified_opportunities = []
                for opp in opportunities[:3]:
                    # Verify against $100 trade size (or config value)
                    verified_opp = await engine.verify_liquidity(opp, trade_amount=100.0)
                    if verified_opp.actual_profit_percentage > 0: # Still profitable?
                         verified_opportunities.append(verified_opp)
                
                # If we have verified ones, display them. Otherwise show raw.
                if verified_opportunities:
                    # Update the main list with verified versions at the top
                    self.display_opportunities(verified_opportunities)
                    
                    if self.executor.is_live:
                         best_opportunity = verified_opportunities[0]
                         if best_opportunity.actual_profit_percentage >= 0.3:
                             await self.executor.execute_trade(best_opportunity, manual_approval=True)
                else:
                    self.display_opportunities(opportunities)
                
                # Paper Trading (use verified if available)
                trade_list = verified_opportunities if verified_opportunities else opportunities
                if trade_list:
                    for opportunity in trade_list[:2]:
                         if opportunity.actual_profit_percentage >= 0.3:
                             self.paper_trader.execute_trade(opportunity, trade_amount=100)
                             
                # --- PHASE 5: Funding Rate Arbitrage (Binance Futures) ---
                # Run this check less frequently or every cycle (1 call)
                if cycle_count % 6 == 0 and "binance" in self.exchanges: # Every ~30s
                    try:
                        funding_data = await self.exchanges["binance"].get_funding_rates()
                        funding_ops = self.funding_engine.find_opportunities(funding_data)
                        
                        if funding_ops:
                            self.logger.info(f"\n🔮 FUNDING RATE OPPORTUNITIES (Top {min(3, len(funding_ops))})")
                            self.logger.info("=" * 60)
                            for i, op in enumerate(funding_ops[:3], 1):
                                self.logger.info(f"{i}. {op.pair:<10} | APY: {op.annualized_rate:>6.2f}% 🔥")
                                self.logger.info(f"   Rate: {op.funding_rate*100:>6.4f}% | Next: {time.strftime('%H:%M', time.localtime(op.next_funding_time))}")
                                self.logger.info("   " + "-" * 56)
                            self.logger.info("")
                            
                            # EXECUTING FUNDING ARB (If Live)
                            if self.executor.is_live:
                                best_opp = funding_ops[0]
                                # Only auto-execute if APY is very good (> 15%) to cover fees
                                if best_opp.annualized_rate > 15.0:
                                    # Execute with manual approval (safety first)
                                    await self.executor.execute_funding_trade(best_opp, manual_approval=True)
                                    
                    except Exception as e:
                        self.logger.error(f"⚠️ Funding Arb Error: {e}")
                
                # Show performance every 10 cycles
                if cycle_count % 10 == 0:
                    if self.executor.is_live:
                        self.show_live_performance()
                    else:
                        self.show_paper_performance()
                
                processing_time = time.time() - start_time
                sleep_time = max(0, self.config["update_interval"] - processing_time)
                await asyncio.sleep(sleep_time)
                
                # --- PHASE 2: Check Triangular Arbitrage (Binance Only) ---
                if "binance" in self.exchanges:
                    try:
                        # 1. Get all prices
                        all_prices = await self.exchanges["binance"].get_all_tickers()
                        
                        # 2. Build graph
                        self.tri_engine.build_graph("binance", all_prices)
                        
                        # 3. Find opportunities
                        tri_ops = self.tri_engine.find_opportunities("binance")
                        
                        if tri_ops:
                            self.logger.info(f"\n📐 TRIANGULAR OPPORTUNITIES ({len(tri_ops)})")
                            self.logger.info("=" * 60)
                            for i, op in enumerate(tri_ops[:3], 1):
                                path_str = " -> ".join(op.path)
                                self.logger.info(f"{i}. 🔄 Path  : {path_str}")
                                self.logger.info(f"   💰 Profit: {op.profit_percentage:>6.2f}%")
                                self.logger.info("   " + "-" * 56)
                                
                                # Log to DB if profitable enough
                                if op.profit_percentage > 1.0:
                                    self.db.log_triangular_trade(op)
                                    self.logger.info("   💾 Logged to DB")
                            self.logger.info("")
                    except Exception as e:
                        print(f"⚠️ Triangular Arb Error: {e}")

                
        except KeyboardInterrupt:
            self.logger.info("\n🛑 Bot stopped by user")
            if self.executor.is_live:
                self.show_live_performance()
            else:
                self.show_paper_performance()
                self.paper_trader.save_trade_history()
        finally:
            await self.cleanup()
    
    def show_paper_performance(self):
        """Show paper trading performance"""
        stats = self.paper_trader.get_performance_stats()
        print(f"\n📈 PAPER TRADING PERFORMANCE:")
        print(f"   Initial Balance: ${stats['initial_balance']:.2f}")
        print(f"   Current Balance: ${stats['current_balance']:.2f}")
        print(f"   Net Profit: ${stats['total_net_profit']:.2f} ({stats['return_percentage']:.2f}%)")
        print(f"   Trades: {stats['total_trades']} | Win Rate: {stats['win_rate']:.1f}%")
        print("-" * 50)
    
    def show_live_performance(self):
        """Show live trading performance"""
        print(f"\n📈 LIVE TRADING PERFORMANCE:")
        print(f"   Total P&L: ${self.executor.total_pnl:.4f}")
        print(f"   Total Trades: {len(self.executor.trade_history)}")
        print(f"   Daily Loss Limit: ${self.executor.daily_loss_limit}")
        if self.executor.trade_history:
            last_trade = self.executor.trade_history[-1]
            self.logger.info(f"   Last Trade: {last_trade['pair']} - ${last_trade.get('profit', 0):.4f}")
        self.logger.info("-" * 50)
    
    async def run_single_exchange_test(self):
        """Test with only specific exchanges"""
        print("Exchange Test Mode - Checking Multiple Exchanges")
        print("Press Ctrl+C to stop gracefully...")
        
        try:
            while True:
                print(f"\n{time.strftime('%H:%M:%S')} - Exchange Prices:")
                print("-" * 40)
                
                # Test multiple exchanges
                test_exchanges = ["binance", "kraken", "kucoin", "bybit"]
                for exchange_name in test_exchanges:
                    if exchange_name in self.exchanges:
                        prices = await self.exchanges[exchange_name].get_prices(self.config["trading_pairs"][:3])  # First 3 pairs
                        print(f"\n{exchange_name.upper():10}:")
                        for pair, price in prices.items():
                            print(f"  {pair}: ${price:.4f}")
                
                # Simple sleep that can be interrupted by Ctrl+C
                await asyncio.sleep(self.config["update_interval"])
                    
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user (Ctrl+C)")
        finally:
            print("🧹 Cleaning up resources...")
            await self.cleanup()
    
    def display_opportunities(self, opportunities: List[ArbitrageOpportunity]):
        """Display found arbitrage opportunities with profit info"""
        if not opportunities:
            self.logger.info(f"{time.strftime('%H:%M:%S')} - No opportunities found ")
            return
        
        mode_indicator = "🚀 LIVE" if self.executor.is_live else "💰 PAPER"
        self.logger.info(f"\n💎 FOUND {len(opportunities)} OPPORTUNITIES ({mode_indicator})")
        self.logger.info("=" * 60)
        
        for i, opp in enumerate(opportunities, 1):
            # Use more decimals for low-priced tokens
            if opp.buy_price < 1.0:
                price_format = ".6f"
            else:
                price_format = ".4f"
            
            # Icon based on net profit
            status_icon = "✅" if opp.actual_profit_percentage > 0 else "⚠️"
            if opp.actual_profit_percentage > 0.5: status_icon = "🔥"
            
            self.logger.info(f"{i}. {opp.pair} {status_icon}")
            self.logger.info(f"   🟢 BUY : {opp.buy_exchange:<12} @ ${opp.buy_price:{price_format}}")
            self.logger.info(f"   🔴 SELL: {opp.sell_exchange:<12} @ ${opp.sell_price:{price_format}}")
            self.logger.info(f"   📊 SPRD: {opp.spread_percentage:>6.2f}%  |  NET: {opp.actual_profit_percentage:>6.2f}%")
            self.logger.info("   " + "-" * 56)
            
            # Fee Calculation
            fee_cost = 0.0
            net_profit_pct = opp.actual_profit_percentage
            
            if self.executor.is_live and i == 1: # Only detailed check for top one to save APIs
                 # Estimate Withdrawal Fee
                 try:
                     pair_base = opp.pair.split("-")[0]
                     w_fee = await self.fee_manager.get_withdrawal_fee(opp.buy_exchange, pair_base)
                     w_cost_usdt = w_fee * opp.buy_price
                     
                     # Subtract from profit (assuming $100 trade)
                     trade_size = self.executor.max_trade_size
                     gross_profit_usd = trade_size * (opp.actual_profit_percentage / 100)
                     net_profit_usd = gross_profit_usd - w_cost_usdt
                     net_profit_pct = (net_profit_usd / trade_size) * 100
                     
                     self.logger.info(f"   💸 W.Fee: {w_fee:.5f} {pair_base} (~${w_cost_usdt:.2f})")
                     self.logger.info(f"   📉 Net Profit: ${net_profit_usd:.2f} ({net_profit_pct:.2f}%)")
                 except Exception as e:
                     self.logger.info(f"   ⚠️ Fee Calc Error: {e}")

            # Show live trading indicator for top opportunity
            if i == 1 and self.executor.is_live and net_profit_pct >= 0.3:
                self.logger.info(f"   🎯 EXECUTING LIVE TRADE...")
            self.logger.info("")
    
    async def cleanup(self):
        """Clean up resources properly"""
        self.logger.info("Closing exchange sessions...")
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.close_session()
                self.logger.info(f"✅ Closed {exchange_name} session")
            except Exception as e:
                self.logger.error(f"❌ Error closing {exchange_name}: {e}")
        self.logger.info("✅ Cleanup complete!")