import asyncio
import json
from core.arbitrage_bot import ArbitrageBot

def create_config_template():
    """Create a configuration template file"""
    config = {
        "exchanges": {
            "binance": {
                "enabled": True,
                "api_key": "6HbxsuJq3X4bqf7nl01zeDOG2v2Q69K41eJ4pXwoGbyPInSe6pxhakd3Uvj5hTQV",
                "api_secret": "Me307pBNCprWM9cd8gfZNenVPBXg3SPZO0KWj0apJEcPb4ve5aAAItFRiUZhGoNR"
            },
            "coinbase": {
                "enabled": False,
                "api_key": "your_coinbase_api_key",
                "api_secret": "your_coinbase_api_secret"
            },
            "kraken": {
                "enabled": True,
                "api_key": "pOVCGSomEdlE//5tgec1MC8nhXd85g3e8fIc2h0bExmQw42MT8NaFUHU",
                "api_secret": "hasrr0/XnBDl920XTr/tKvkVgiSmDaPrZdiVTkDWF8p1/s0pOe2V6FPA0DnVBA0FAbP9NnEXxEn/6S/NHxj91w=="
            },
            "kucoin": {
                "enabled": True,
                "api_key": "68e1b47997abe30001b0b09e",
                "api_secret": "dcfa0f53-4a6c-4912-bc60-e21fcbdb5d7a",
                "api_passphrase": "fgdhsj1029"
            },
            "bybit": {
                "enabled": True,
                "api_key": "pRlRUay1qabtDjhm65",
                "api_secret": "ojA0wTeXYVuvo38qPqHXDiltGRFvAPnUZN05"
                },
            "okx": {
                "enabled": True,
                "api_key": "1eec7b7a-05f2-4307-90cb-7369946ccf7b",
                "api_secret": "3388B82F398622F5E03C95EB9F28762C",
                "api_passphrase": "fgdhsj1029"
                },
            "gateio": {
                "enabled": True,
                "api_key": "10ca2fa3ebc2168d895a93ca3a4e06ee",
                "api_secret": "5f18833d7954d001c808c7898cd9b37ce6a3049bbb227f6e70324434d002c87c"
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
    #await bot.run_single_exchange_test()

if __name__ == "__main__":
    asyncio.run(main())