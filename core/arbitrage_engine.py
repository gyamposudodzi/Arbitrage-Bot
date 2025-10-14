import asyncio
import time
from typing import Dict, List
from models.data_models import ArbitrageOpportunity

class ArbitrageEngine:
    def __init__(self, bot):
        self.bot = bot
        self.min_spread = bot.config["min_spread_percentage"]
    
    async def find_opportunities(self) -> List[ArbitrageOpportunity]:
        opportunities = []
        exchange_prices = {}
        
        # Get prices from all exchanges
        tasks = []
        for exchange_name, exchange in self.bot.exchanges.items():
            tasks.append(self.get_exchange_prices(exchange_name, exchange))
        
        results = await asyncio.gather(*tasks)
        
        # Organize prices by exchange
        for exchange_name, prices in results:
            exchange_prices[exchange_name] = prices
        
        # Find arbitrage opportunities for each pair
        for pair in self.bot.config["trading_pairs"]:
            pair_opportunities = self.analyze_pair(pair, exchange_prices)
            opportunities.extend(pair_opportunities)
        
        # Sort by highest spread percentage
        opportunities.sort(key=lambda x: x.spread_percentage, reverse=True)
        
        return opportunities[:self.bot.config["max_opportunities"]]
    
    async def get_exchange_prices(self, exchange_name: str, exchange):
        prices = await exchange.get_prices(self.bot.config["trading_pairs"])
        return (exchange_name, prices)
    
    import asyncio
import time
from typing import Dict, List
from models.data_models import ArbitrageOpportunity

class ArbitrageEngine:
    def __init__(self, bot):
        self.bot = bot
        self.min_spread = bot.config["min_spread_percentage"]
    
    async def find_opportunities(self) -> List[ArbitrageOpportunity]:
        opportunities = []
        exchange_prices = {}
        
        # Get prices from all exchanges
        tasks = []
        for exchange_name, exchange in self.bot.exchanges.items():
            tasks.append(self.get_exchange_prices(exchange_name, exchange))
        
        results = await asyncio.gather(*tasks)
        
        # Organize prices by exchange
        for exchange_name, prices in results:
            exchange_prices[exchange_name] = prices
        
        # Find arbitrage opportunities for each pair
        for pair in self.bot.config["trading_pairs"]:
            pair_opportunities = self.analyze_pair(pair, exchange_prices)
            opportunities.extend(pair_opportunities)
        
        # Sort by highest spread percentage
        opportunities.sort(key=lambda x: x.spread_percentage, reverse=True)
        
        return opportunities[:self.bot.config["max_opportunities"]]
    
    async def get_exchange_prices(self, exchange_name: str, exchange):
        prices = await exchange.get_prices(self.bot.config["trading_pairs"])
        return (exchange_name, prices)
    
    def analyze_pair(self, pair: str, exchange_prices: Dict) -> List[ArbitrageOpportunity]:
        opportunities = []
        exchanges_with_price = []
        
        # Import your existing FeeCalculator
        from core.fee_calculator import FeeCalculator
        
        # Collect all exchanges that have this pair
        for exchange_name, prices in exchange_prices.items():
            if pair in prices and prices[pair] > 0:
                exchanges_with_price.append((exchange_name, prices[pair]))
        
        if len(exchanges_with_price) < 2:
            return opportunities
        
        # DEBUG: Show exact prices for this pair
        if pair == "ONE-USDT":  # Only debug the problematic pair
            print(f"🔍 DEBUG {pair} exact prices:")
            for exchange, price in exchanges_with_price:
                print(f"  {exchange}: ${price:.8f}")
        
        # Find best buy (lowest price) and best sell (highest price)
        for i, (buy_exchange, buy_price) in enumerate(exchanges_with_price):
            for j, (sell_exchange, sell_price) in enumerate(exchanges_with_price):
                if i != j and sell_price > buy_price:
                    spread = sell_price - buy_price
                    spread_percentage = (spread / buy_price) * 100
                    
                    # USE EXISTING FEE CALCULATOR
                    net_profit_percentage = FeeCalculator.calculate_net_profit(
                        buy_exchange, sell_exchange, spread_percentage
                    )
                    buy_fee = FeeCalculator.get_exchange_fee(buy_exchange)
                    sell_fee = FeeCalculator.get_exchange_fee(sell_exchange)
                    
                    # DEBUG: Show calculation for problematic pairs
                    if pair == "ONE-USDT" and spread_percentage >= 0.1:
                        print(f"  💰 {buy_exchange}→{sell_exchange}: {buy_price:.8f}→{sell_price:.8f} = {spread:.8f} ({spread_percentage:.4f}%)")
                        print(f"  📊 Fees: {buy_fee*100:.2f}% + {sell_fee*100:.2f}% = {(buy_fee+sell_fee)*100:.2f}% | Net: {net_profit_percentage:.4f}%")
                    
                    # Only consider opportunities with actual profit (0.1% minimum net profit)
                    if net_profit_percentage >= 0.1:  # Minimum 0.1% net profit after fees
                        opportunity = ArbitrageOpportunity(
                            pair=pair,
                            buy_exchange=buy_exchange,
                            sell_exchange=sell_exchange,
                            buy_price=buy_price,
                            sell_price=sell_price,
                            spread=spread,
                            spread_percentage=spread_percentage,
                            buy_fee=buy_fee,
                            sell_fee=sell_fee,
                            net_spread_percentage=net_profit_percentage,
                            actual_profit_percentage=net_profit_percentage,
                            timestamp=time.time()
                        )
                        opportunities.append(opportunity)
        
        return opportunities