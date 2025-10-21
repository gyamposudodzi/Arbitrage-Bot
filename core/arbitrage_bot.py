import asyncio
import time
import json
from typing import Dict, List
from exchanges import BinanceAPI, CoinbaseAPI, KrakenAPI, KuCoinAPI, GateIOAPI, BybitAPI, OKXAPI
from core.arbitrage_engine import ArbitrageEngine
from models.data_models import ArbitrageOpportunity
from core.paper_trader import PaperTrader
from core.live_trader import LiveTrader  # NEW

class ArbitrageBot:
    def __init__(self, config_file: str = "config.json"):
        self.config = self.load_config(config_file)
        self.exchanges = {}
        self.opportunities = []
        self.setup_exchanges()
        self.paper_trader = PaperTrader(initial_balance=1000)
        self.live_trader = LiveTrader(self)  # NEW
        self.live_trader.is_live = self.config.get("live_trading", {}).get("enabled", False)
        
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
        
        mode = "LIVE TRADING 🚀" if self.live_trader.is_live else "PAPER TRADING 💰"
        print(f"Arbitrage Bot Started! {mode}")
        print("=" * 80)
        
        if self.live_trader.is_live:
            print("🔐 LIVE TRADING ENABLED - Trades will execute with REAL MONEY!")
            print("💰 Starting with safety limits:")
            print(f"   Max trade size: ${self.live_trader.max_trade_size}")
            print(f"   Daily loss limit: ${self.live_trader.daily_loss_limit}")
            print("   Manual approval required for each trade")
        
        try:
            cycle_count = 0
            while True:
                start_time = time.time()
                cycle_count += 1
                
                opportunities = await engine.find_opportunities()
                self.display_opportunities(opportunities)
                
                if opportunities and self.live_trader.is_live:
                    # Execute live trades for high-confidence opportunities
                    best_opportunity = opportunities[0]  # Highest profit opportunity
                    if best_opportunity.actual_profit_percentage >= 0.3:
                        await self.live_trader.execute_live_trade(best_opportunity, manual_approval=True)
                
                elif opportunities:  # Paper trading
                    for opportunity in opportunities[:2]:  # Top 2 opportunities
                        if opportunity.actual_profit_percentage >= 0.3:
                            self.paper_trader.execute_trade(opportunity, trade_amount=100)
                
                # Show performance every 10 cycles
                if cycle_count % 10 == 0:
                    if self.live_trader.is_live:
                        self.show_live_performance()
                    else:
                        self.show_paper_performance()
                
                processing_time = time.time() - start_time
                sleep_time = max(0, self.config["update_interval"] - processing_time)
                await asyncio.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user")
            if self.live_trader.is_live:
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
        print(f"   Total P&L: ${self.live_trader.total_pnl:.4f}")
        print(f"   Total Trades: {len(self.live_trader.trade_history)}")
        print(f"   Daily Loss Limit: ${self.live_trader.daily_loss_limit}")
        if self.live_trader.trade_history:
            last_trade = self.live_trader.trade_history[-1]
            print(f"   Last Trade: {last_trade['pair']} - ${last_trade.get('estimated_profit', 0):.4f}")
        print("-" * 50)
    
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
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - No PROFITABLE arbitrage opportunities found")
            return
        
        mode_indicator = "🚀 LIVE" if self.live_trader.is_live else "💰 PAPER"
        print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} - Found {len(opportunities)} PROFITABLE opportunities ({mode_indicator}):")
        print("-" * 80)
        
        for i, opp in enumerate(opportunities, 1):
            # Use more decimals for low-priced tokens
            if opp.buy_price < 1.0:
                price_format = ".6f"
            else:
                price_format = ".4f"
            
            print(f"{i}. {opp.pair}")
            print(f"   BUY : {opp.buy_exchange:10} @ ${opp.buy_price:{price_format}} (fee: {opp.buy_fee*100:.2f}%)")
            print(f"   SELL: {opp.sell_exchange:10} @ ${opp.sell_price:{price_format}} (fee: {opp.sell_fee*100:.2f}%)")
            print(f"   GROSS Spread: {opp.spread_percentage:.4f}%")
            print(f"   NET Profit: {opp.actual_profit_percentage:.4f}% ✅")
            print(f"   Total Fees: {(opp.buy_fee + opp.sell_fee)*100:.2f}%")
            
            # Show live trading indicator for top opportunity
            if i == 1 and self.live_trader.is_live and opp.actual_profit_percentage >= 0.3:
                print(f"   🎯 LIVE TRADE CANDIDATE - Will prompt for execution")
            print()
    
    async def cleanup(self):
        """Clean up resources properly"""
        print("Closing exchange sessions...")
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.close_session()
                print(f"✅ Closed {exchange_name} session")
            except Exception as e:
                print(f"❌ Error closing {exchange_name}: {e}")
        print("✅ Cleanup complete!")