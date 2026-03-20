import asyncio
import json
import os
from dotenv import load_dotenv
from core.arbitrage_bot import ArbitrageBot

# Load environment variables
load_dotenv()

def create_config_template():
    """Create a configuration template file"""
    config = {
        "execution_mode": "normal",
        "order_type": "taker",
        "exchanges": {
            "binance": {
                "enabled": True,
                "api_key": os.getenv('BINANCE_API_KEY', ''),
                "api_secret": os.getenv('BINANCE_API_SECRET', '')
            },
            "coinbase": {
                "enabled": False,
                "api_key": os.getenv('COINBASE_API_KEY', ''),
                "api_secret": os.getenv('COINBASE_API_SECRET', '')
            },
            "kraken": {
                "enabled": False,
                "api_key": os.getenv('KRAKEN_API_KEY', ''),
                "api_secret": os.getenv('KRAKEN_API_SECRET', '')
            },
            "kucoin": {
                "enabled": False,
                "api_key": os.getenv('KUCOIN_API_KEY', ''),
                "api_secret": os.getenv('KUCOIN_API_SECRET', ''),
                "api_passphrase": os.getenv('KUCOIN_API_PASSPHRASE', '')
            },
            "bybit": {
                "enabled": False,
                "api_key": os.getenv('BYBIT_API_KEY', ''),
                "api_secret": os.getenv('BYBIT_API_SECRET', '')
            },
            "okx": {
                "enabled": False,
                "api_key": os.getenv('OKX_API_KEY', ''),
                "api_secret": os.getenv('OKX_API_SECRET', ''),
                "api_passphrase": os.getenv('OKX_API_PASSPHRASE', '')
            },
            "gateio": {
                "enabled": False,
                "api_key": os.getenv('GATEIO_API_KEY', ''),
                "api_secret": os.getenv('GATEIO_API_SECRET', '')
            }
        },
        "trading_pairs": [
            "BTC-USDT",
            "ETH-USDT",
            "ADA-USDT",
            "DOT-USDT",
            "LINK-USDT",
            "SOL-USDT",
            "AVAX-USDT",
            "MATIC-USDT",
            "ATOM-USDT",
            "XRP-USDT",
            "DOGE-USDT",
            "NEAR-USDT",
            "ALGO-USDT",
            "FTM-USDT",
            "SAND-USDT",
            "MANA-USDT",
            "ENJ-USDT",
            "CHZ-USDT",
            "BAT-USDT",
            "ONE-USDT",
            "VET-USDT",
            "GALA-USDT",
            "IMX-USDT",
            "RUNE-USDT",
            "INJ-USDT",
            "RNDR-USDT",
            "ARB-USDT",
            "OP-USDT",
            "APT-USDT",
            "SEI-USDT",
            "SUI-USDT"
        ],
        "min_spread_percentage": 0.3,
        "min_triangular_profit_percent": 0.0,
        "update_interval": 3,
        "max_opportunities": 20,
        "paper_trading": {
            "enabled": False,
            "initial_balance": 1000,
            "auto_trade_threshold": 0.3
        },
        "live_trading": {
            "enabled": False,
            "max_trade_size": 10,
            "daily_loss_limit": 5,
            "cooldown_seconds": 30,
            "enable_spot_arbitrage": False,
            "min_spot_profit_percent": 1.0,
            "enable_triangular_arbitrage": True,
            "min_triangular_profit_percent": 1.0,
            "enable_funding_arbitrage": False,
            "min_funding_apy": 25.0,
            "manual_approval": True
        },
        "rebalance": {
            "enabled": False,
            "min_balance": 200,
            "target_balance": 1000,
            "check_interval": 300,
            "allowed_assets": ["USDT"],
            "deposit_addresses": {
                "binance": {
                    "USDT": "YOUR_TRC20_ADDRESS_HERE"
                }
            }
        }
    }
    
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("Config template created: config.json")

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
    else:
        print(f"✅ Found {len(opportunities)} opportunities!")
        for i, opp in enumerate(opportunities, 1):
            print(f"{i}. {opp.pair}: {opp.buy_exchange}→{opp.sell_exchange} - {opp.spread_percentage:.2f}%")
    
    await bot.cleanup()

async def main():
    # Create config template if it doesn't exist
    try:
        with open('config.json', 'r'):
            pass
    except FileNotFoundError:
        create_config_template()
        print("Please edit .env file with your API keys before running the bot.")
        return
    
    print("🤖 ARBITRAGE BOT - Choose Mode:")
    print("1. 🔍 Debug - Show all exchange prices")
    print("2. 🎯 Debug - Test arbitrage engine") 
    print("3. 🚀 Live - Run arbitrage bot")
    print("4. 🧪 Test - Single exchange test")
    
    choice = input("Enter choice (1/2/3/4): ").strip()
    
    if choice == "1":
        await debug_all_prices()
    elif choice == "2":
        await debug_arbitrage_engine()
    elif choice == "3":
        bot = ArbitrageBot()
        await bot.run()
    elif choice == "4":
        bot = ArbitrageBot()
        await bot.run_single_exchange_test()
    else:
        print("Invalid choice")

if __name__ == "__main__":
    asyncio.run(main())
