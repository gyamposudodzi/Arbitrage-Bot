import asyncio
import time
import json
from typing import Dict, List
from exchanges import BinanceAPI, CoinbaseAPI, KrakenAPI
from core.arbitrage_engine import ArbitrageEngine
from models.data_models import ArbitrageOpportunity

class ArbitrageBot:
    def __init__(self, config_file: str = "config.json"):
        self.config = self.load_config(config_file)
        self.exchanges = {}
        self.opportunities = []
        self.setup_exchanges()
        
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
                    "kraken": {"enabled": True, "api_key": "", "api_secret": ""}
                },
                "trading_pairs": ["BTC-USDT", "ETH-USDT", "ADA-USDT"],
                "min_spread_percentage": 0.5,
                "update_interval": 5,
                "max_opportunities": 10
            }
    
    def setup_exchanges(self):
        """Initialize exchange connectors"""
        if self.config["exchanges"]["binance"]["enabled"]:
            self.exchanges["binance"] = BinanceAPI(self.config["exchanges"]["binance"])
        if self.config["exchanges"]["coinbase"]["enabled"]:
            self.exchanges["coinbase"] = CoinbaseAPI(self.config["exchanges"]["coinbase"])
        if self.config["exchanges"]["kraken"]["enabled"]:
            self.exchanges["kraken"] = KrakenAPI(self.config["exchanges"]["kraken"])
    
    async def run(self):
        """Main execution loop"""
        engine = ArbitrageEngine(self)
        
        print("Arbitrage Bot Started! Press Ctrl+C to stop.")
        print("=" * 80)
        
        try:
            while True:
                start_time = time.time()
                
                opportunities = await engine.find_opportunities()
                self.display_opportunities(opportunities)
                
                processing_time = time.time() - start_time
                sleep_time = max(0, self.config["update_interval"] - processing_time)
                
                # SIMPLE sleep - Ctrl+C will work naturally
                await asyncio.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user")
        finally:
            await self.cleanup()
    
    async def run_single_exchange_test(self):
            """Test with only one exchange (Binance)"""
            print("Single Exchange Test Mode - Binance Only")
            print("Press Ctrl+C to stop gracefully...")
            
            binance = self.exchanges["binance"]
            
            try:
                while True:
                    prices = await binance.get_prices(self.config["trading_pairs"])
                    print(f"\n{time.strftime('%H:%M:%S')} - Binance Prices:")
                    for pair, price in prices.items():
                        print(f"  {pair}: ${price:.4f}")
                    
                    # SIMPLE sleep that can be interrupted by Ctrl+C
                    try:
                        await asyncio.sleep(self.config["update_interval"])
                    except asyncio.CancelledError:
                        print("\nShutdown requested...")
                        break
                        
            except KeyboardInterrupt:
                print("\n🛑 Bot stopped by user (Ctrl+C)")
            finally:
                print("🧹 Cleaning up resources...")
                await self.cleanup()
    
    def display_opportunities(self, opportunities: List[ArbitrageOpportunity]):
        """Display found arbitrage opportunities"""
        if not opportunities:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - No arbitrage opportunities found")
            return
        
        print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} - Found {len(opportunities)} opportunities:")
        print("-" * 80)
        
        for i, opp in enumerate(opportunities, 1):
            print(f"{i}. {opp.pair}")
            print(f"   BUY : {opp.buy_exchange:10} @ ${opp.buy_price:.4f}")
            print(f"   SELL: {opp.sell_exchange:10} @ ${opp.sell_price:.4f}")
            print(f"   SPREAD: ${opp.spread:.4f} ({opp.spread_percentage:.2f}%)")
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