import asyncio
import json
from core.arbitrage_bot import ArbitrageBot

async def debug_all_prices():
    """Debug script to see all exchange prices"""
    bot = ArbitrageBot()
    
    print("🔍 DEBUG: Checking all exchange prices...")
    print("=" * 60)
    
    for exchange_name, exchange in bot.exchanges.items():
        try:
            prices = await exchange.get_prices(bot.config["trading_pairs"])
            print(f"\n📊 {exchange_name.upper():10} Prices:")
            print("-" * 40)
            for pair, price in prices.items():
                print(f"  {pair}: ${price:.4f}")
        except Exception as e:
            print(f"❌ {exchange_name}: Error - {e}")
    
    await bot.cleanup()

async def debug_arbitrage_engine():
    """Test the arbitrage engine directly"""
    bot = ArbitrageBot()
    
    print("\n🎯 DEBUG: Testing Arbitrage Engine...")
    print("=" * 60)
    
    from core.arbitrage_engine import ArbitrageEngine
    engine = ArbitrageEngine(bot)
    
    opportunities = await engine.find_opportunities()
    
    if not opportunities:
        print("❌ No opportunities found - checking why...")
        
        # Get all prices
        exchange_prices = {}
        for exchange_name, exchange in bot.exchanges.items():
            prices = await exchange.get_prices(bot.config["trading_pairs"])
            exchange_prices[exchange_name] = prices
            print(f"\n{exchange_name}: {len(prices)} pairs found")
        
        # Check each pair
        for pair in bot.config["trading_pairs"]:
            print(f"\n🔍 Analyzing {pair}:")
            prices_by_exchange = []
            for exchange_name, prices in exchange_prices.items():
                if pair in prices:
                    prices_by_exchange.append((exchange_name, prices[pair]))
                    print(f"  {exchange_name}: ${prices[pair]:.4f}")
            
            if len(prices_by_exchange) >= 2:
                # Calculate potential spread
                min_price = min(prices_by_exchange, key=lambda x: x[1])
                max_price = max(prices_by_exchange, key=lambda x: x[1])
                spread = max_price[1] - min_price[1]
                spread_percentage = (spread / min_price[1]) * 100
                
                print(f"  💰 Potential: {min_price[0]}→{max_price[0]}: {spread_percentage:.2f}%")
    
    await bot.cleanup()

if __name__ == "__main__":
    print("Running arbitrage bot diagnostics...")
    asyncio.run(debug_all_prices())
    asyncio.run(debug_arbitrage_engine())