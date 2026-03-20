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
from core.basis_arb import BasisArbitrageEngine # NEW
from core.rebalance_manager import RebalanceManager # NEW
from core.logger import setup_logger

class ArbitrageBot:
    def __init__(self, config_file: str = "config.json"):
        self.logger = setup_logger("ArbitrageBot")
        self.config = self.load_config(config_file)
        self.exchanges = {}
        self.exchange_pairs = {} # NEW: Smart Pair Cache
        self.opportunities = []
        self.setup_exchanges()
        self.db = DatabaseManager()  # NEW: Initialize Database
        self.paper_trader = PaperTrader(initial_balance=1000, db_manager=self.db)
        self.executor = ExecutionManager(self)  # NEW
        self.executor.is_live = self.config.get("live_trading", {}).get("enabled", False)
        self.fee_manager = FeeManager(self.executor) # NEW
        self.tri_engine = TriangularArbitrageEngine(self)
        self.funding_engine = FundingRateArbitrageEngine(self)
        self.basis_engine = BasisArbitrageEngine(self) # NEW
        self.rebalancer = RebalanceManager(self) # NEW
        
            

        
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file and merge with env vars"""
        config = {}
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            # Fallback (should be handled by main.py)
            pass

        # IMPORTANT: Override secrets from Environment Variables if present
        # This fixes the issue where config.json is stale/empty but .env has keys.
        from os import getenv
        
        env_map = {
            "binance": ["BINANCE_API_KEY", "BINANCE_API_SECRET"],
            "coinbase": ["COINBASE_API_KEY", "COINBASE_API_SECRET"],
            "kraken": ["KRAKEN_API_KEY", "KRAKEN_API_SECRET"],
            "kucoin": ["KUCOIN_API_KEY", "KUCOIN_API_SECRET", "KUCOIN_API_PASSPHRASE"],
            "bybit": ["BYBIT_API_KEY", "BYBIT_API_SECRET"],
            "okx": ["OKX_API_KEY", "OKX_API_SECRET", "OKX_API_PASSPHRASE"],
            "gateio": ["GATEIO_API_KEY", "GATEIO_API_SECRET"]
        }
        
        if "exchanges" in config:
            for exchange, vars in env_map.items():
                if exchange in config["exchanges"]:
                    # Key
                    key_val = getenv(vars[0])
                    if key_val: config["exchanges"][exchange]["api_key"] = key_val
                    
                    # Secret
                    sec_val = getenv(vars[1])
                    if sec_val: config["exchanges"][exchange]["api_secret"] = sec_val
                    
                    # Passphrase (if applicable)
                    if len(vars) > 2:
                        pass_val = getenv(vars[2])
                        if pass_val: config["exchanges"][exchange]["api_passphrase"] = pass_val

        return config
    
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
        
        # --- SMART PAIR RETRIEVAL (Auto-Discovery) ---
        self.logger.info("🧠 Performing Smart Pair Retrieval...")
        
        # 1. Fetch supported pairs per exchange
        for name, exchange in self.exchanges.items():
            self.logger.info(f"   Fetching pairs for {name}...")
            supported = await exchange.get_trading_pairs()
            
            if supported:
                # Intersect with config
                valid_pairs = []
                for p in self.config["trading_pairs"]:
                    # Check exact match OR fallback match (e.g. BTC-USD for Coinbase)
                    if p in supported:
                        valid_pairs.append(p)
                    elif name == "coinbase" and p.replace("USDT", "USD") in supported:
                        valid_pairs.append(p)
                
                self.exchange_pairs[name] = valid_pairs
                self.logger.info(f"   ✅ {name}: Verified {len(valid_pairs)}/{len(self.config['trading_pairs'])} pairs")
            else:
                # Fallback if fetch fails (e.g. not implemented yet)
                self.exchange_pairs[name] = self.config["trading_pairs"]
                self.logger.info(f"   ⚠️ {name}: Using full config list (Auto-discovery skipped)")

        # 2. Start Streaming with VALIDATED lists
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
            
            # Initial Balance Check
            await self.executor.refresh_balances()
        
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
                    await self.display_opportunities(verified_opportunities)
                    
                    if self.executor.is_live:
                         best_opportunity = verified_opportunities[0]
                         live_spot_enabled = self.config.get("live_trading", {}).get("enable_spot_arbitrage", False)
                         live_spot_min_profit = self.config.get("live_trading", {}).get("min_spot_profit_percent", 1.0)
                         if (
                             live_spot_enabled
                             and best_opportunity.actual_profit_percentage >= live_spot_min_profit
                             and self.executor.can_execute_strategy("spot_arbitrage")
                         ):
                             self.executor.mark_strategy_execution("spot_arbitrage")
                             await self.executor.execute_trade(best_opportunity, manual_approval=True)
                         elif live_spot_enabled and best_opportunity.actual_profit_percentage < live_spot_min_profit:
                             self.logger.info(
                                 f"   ⏭️ Skipping live spot arbitrage: best net profit "
                                 f"{best_opportunity.actual_profit_percentage:.2f}% below live threshold "
                                 f"{live_spot_min_profit:.2f}%"
                             )
                else:
                    await self.display_opportunities(opportunities)
                
                # Paper Trading (Run only if enabled)
                if self.config.get("paper_trading", {}).get("enabled", False):
                    trade_list = verified_opportunities if verified_opportunities else opportunities
                    if trade_list:
                        for opportunity in trade_list[:2]:
                             if opportunity.actual_profit_percentage >= 0.3:
                                 self.paper_trader.execute_trade(opportunity, trade_amount=100)
                             
                # --- PHASE 5: Funding Rate Arbitrage (Binance Futures) ---
                # Run this check less frequently or every cycle (1 call)
                # --- PHASE 5: Funding Rate Arbitrage (All Exchanges) ---
                if cycle_count % 6 == 0:
                    for exchange_name, exchange in self.exchanges.items():
                        try:
                            # Polymorphic call - will be empty for non-supported exchanges
                            funding_data = await exchange.get_funding_rates()
                            if not funding_data: continue

                            funding_ops = self.funding_engine.find_opportunities(funding_data, exchange_name)
                            if funding_ops:
                                self.logger.info(f"\n🔮 {exchange_name.upper()} FUNDING OPS (Top {min(3, len(funding_ops))})")
                                self.logger.info("=" * 60)
                                for i, op in enumerate(funding_ops[:3], 1):
                                    self.logger.info(f"{i}. {op.pair:<10} | APY: {op.annualized_rate:>6.2f}% 🔥")
                                    self.logger.info(f"   Rate: {op.funding_rate*100:>6.4f}% | Next: {time.strftime('%H:%M', time.localtime(op.next_funding_time))}")
                                    self.logger.info("   " + "-" * 56)
                                self.logger.info("")
                                
                                # EXECUTING FUNDING ARB (If Live)
                                if (
                                    self.executor.is_live
                                    and self.config.get("live_trading", {}).get("enable_funding_arbitrage", False)
                                    and self.executor.can_execute_strategy("funding_arbitrage")
                                ):
                                    best_opp = funding_ops[0]
                                    min_funding_apy = self.config.get("live_trading", {}).get("min_funding_apy", 25.0)
                                    if best_opp.annualized_rate >= min_funding_apy:
                                        self.executor.mark_strategy_execution("funding_arbitrage")
                                        await self.executor.execute_funding_trade(best_opp, manual_approval=True)
                                    else:
                                        self.logger.info(
                                            f"   ⏭️ Skipping live funding arbitrage: best APY "
                                            f"{best_opp.annualized_rate:.2f}% below live threshold "
                                            f"{min_funding_apy:.2f}%"
                                        )
                        except Exception as e:
                            self.logger.error(f"⚠️ {exchange_name} Funding Error: {e}")

                # --- PHASE 10: Spot-Future Basis Arbitrage (Binance Only for now) ---
                if cycle_count % 12 == 0: # Every ~60s
                    try:
                        # Only Binance has deep liquid Dated Futures for now
                        binance = self.exchanges.get("binance")
                        if binance:
                            # 1. Get Delivery Prices
                            delivery_data = await binance.get_delivery_prices()
                            
                            # 2. Get Spot Prices (we already have them cached implicitly or can fetch)
                            # Ideally pass the latest we found in 'find_opportunities' but let's fetch fresh for accuracy
                            spot_prices = await binance.get_prices(self.config["trading_pairs"])
                            
                            # 3. Find Ops
                            basis_ops = self.basis_engine.find_opportunities(delivery_data, spot_prices)
                            
                            if basis_ops:
                                self.logger.info(f"\n📉 BASIS ARBITRAGE (Risk-Free Yield) - Top {min(3, len(basis_ops))}")
                                self.logger.info("=" * 60)
                                for i, op in enumerate(basis_ops[:3], 1):
                                    self.logger.info(f"{i}. {op.future_symbol:<15} (Exp: {op.days_to_expiry}d) | APR: {op.apr:>6.2f}% 💰")
                                    self.logger.info(f"   Spot: ${op.spot_price:<8.2f} | Future: ${op.future_price:<8.2f} | Basis: {op.basis_percent:.2f}%")
                                    self.logger.info("   " + "-" * 56)
                                self.logger.info("")
                    except Exception as e:
                        self.logger.error(f"⚠️ Basis Arb Error: {e}")
                    except Exception as e:
                        self.logger.error(f"⚠️ Basis Arb Error: {e}")

                # --- PHASE 15: Inventory Rebalancer ---
                # Check periodically (check_and_rebalance handles internal timer)
                try:
                    await self.rebalancer.check_and_rebalance()
                except Exception as e:
                    self.logger.error(f"⚠️ Rebalance Error: {e}")
                
                # Show performance every 10 cycles
                if cycle_count % 10 == 0:
                    if self.executor.is_live:
                        self.show_live_performance()
                    else:
                        self.show_paper_performance()
                
                processing_time = time.time() - start_time
                sleep_time = max(0, self.config["update_interval"] - processing_time)
                await asyncio.sleep(sleep_time)
                
                # --- PHASE 2: Check Triangular Arbitrage (All Exchanges) ---
                for exchange_name, exchange in self.exchanges.items():
                    try:
                        # Polymorphic call
                        all_prices = await exchange.get_all_tickers()
                        if not all_prices: continue
                        
                        # Build graph
                        self.tri_engine.build_graph(exchange_name, all_prices)
                        
                        # Find opportunities
                        tri_ops = self.tri_engine.find_opportunities(exchange_name)
                        
                        if tri_ops:
                            self.logger.info(f"\n📐 {exchange_name.upper()} TRIANGULAR OPS ({len(tri_ops)})")
                            self.logger.info("=" * 60)
                            for i, op in enumerate(tri_ops[:3], 1):
                                path_str = " -> ".join(op.path)
                                self.logger.info(f"{i}. 🔄 Path  : {path_str}")
                                self.logger.info(f"   💰 Net Profit: {op.profit_percentage:>6.2f}%")
                                self.logger.info(f"   📊 Gross: {op.gross_profit_percentage:>6.2f}% | Fees: {op.estimated_fee_percentage:>4.2f}%")
                                self.logger.info("   " + "-" * 56)
                                
                                if op.profit_percentage > 1.0:
                                    self.db.log_triangular_trade(op)
                                    self.logger.info("   💾 Logged to DB")
                            self.logger.info("")

                            if self.executor.is_live and exchange_name == "binance":
                                best_tri_opp = tri_ops[0]
                                live_tri_min_profit = self.config.get("live_trading", {}).get("min_triangular_profit_percent", 1.0)
                                live_tri_enabled = self.config.get("live_trading", {}).get("enable_triangular_arbitrage", True)
                                if (
                                    live_tri_enabled
                                    and best_tri_opp.profit_percentage >= live_tri_min_profit
                                    and self.executor.can_execute_strategy("triangular_arbitrage")
                                ):
                                    self.executor.mark_strategy_execution("triangular_arbitrage")
                                    await self.executor.execute_triangular_trade(best_tri_opp, manual_approval=True)
                                elif live_tri_enabled:
                                    self.logger.info(
                                        f"   ⏭️ Skipping live triangular trade: best net profit "
                                        f"{best_tri_opp.profit_percentage:.2f}% below live threshold "
                                        f"{live_tri_min_profit:.2f}%"
                                    )
                    except Exception as e:
                        print(f"⚠️ {exchange_name} Triangular Error: {e}")

                
                
        except asyncio.CancelledError:
            self.logger.info("\n🛑 Bot task cancelled")
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
    
    async def display_opportunities(self, opportunities: List[ArbitrageOpportunity]):
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
                if hasattr(exchange, 'stop_stream'):
                    await exchange.stop_stream()
                await exchange.close_session()
                self.logger.info(f"✅ Closed {exchange_name} session")
            except Exception as e:
                self.logger.error(f"❌ Error closing {exchange_name}: {e}")
        
        # Close Execution Manager sessions
        if hasattr(self, 'executor'):
            await self.executor.cleanup()
            
        self.logger.info("✅ Cleanup complete!")
