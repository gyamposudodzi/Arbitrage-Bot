class ArbitrageBot:
    # ... (previous code)
    
    async def run(self):
        """Main execution loop"""
        engine = ArbitrageEngine(self)
        
        print("Arbitrage Bot Started!")
        print("=" * 80)
        
        try:
            while True:
                start_time = time.time()
                
                opportunities = await engine.find_opportunities()
                self.display_opportunities(opportunities)
                
                # Calculate sleep time to maintain consistent interval
                processing_time = time.time() - start_time
                sleep_time = max(0, self.config["update_interval"] - processing_time)
                
                await asyncio.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("\nBot stopped by user")
        finally:
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
        """Clean up resources"""
        for exchange in self.exchanges.values():
            await exchange.close_session()

# Configuration file template
def create_config_template():
    config = {
        "exchanges": {
            "binance": {
                "enabled": True,
                "api_key": "your_binance_api_key",
                "api_secret": "your_binance_api_secret"
            },
            "coinbase": {
                "enabled": True,
                "api_key": "your_coinbase_api_key",
                "api_secret": "your_coinbase_api_secret"
            },
            "kraken": {
                "enabled": True,
                "api_key": "your_kraken_api_key",
                "api_secret": "your_kraken_api_secret"
            }
        },
        "trading_pairs": ["BTC-USDT", "ETH-USDT", "ADA-USDT", "DOT-USDT", "LINK-USDT"],
        "min_spread_percentage": 0.5,
        "update_interval": 5,
        "max_opportunities": 10
    }
    
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("Config template created: config.json")

async def main():
    # Create config template if it doesn't exist
    try:
        with open('config.json', 'r'):
            pass
    except FileNotFoundError:
        create_config_template()
        print("Please edit config.json with your API keys before running the bot.")
        return
    
    bot = ArbitrageBot()
    await bot.run()

if _name_ == "_main_":
    # Install required packages first:
    # pip install aiohttp
    asyncio.run(main())