import asyncio
import time
from typing import Dict, List
from models.data_models import ArbitrageOpportunity
from exchanges.streaming_interface import StreamingExchangeInterface

class ArbitrageEngine:
    def __init__(self, bot):
        self.bot = bot
        self.min_spread = bot.config["min_spread_percentage"]
        self.price_cache: Dict[str, Dict[str, float]] = {}
        self.streaming_exchanges = set()
    
    async def start_streaming(self):
        """Initialize WebSocket streams for supported exchanges"""
        for name, exchange in self.bot.exchanges.items():
            if isinstance(exchange, StreamingExchangeInterface):
                print(f"🌊 Starting stream for {name}...")
                self.streaming_exchanges.add(name)
                self.price_cache[name] = {}
                
                # Run stream in background
                asyncio.create_task(exchange.start_stream(
                    self.bot.config["trading_pairs"],
                    self.update_price_cache
                ))
    
    async def update_price_cache(self, pair: str, price: float, exchange_name: str):
        """Callback for WebSocket updates"""
        if exchange_name not in self.price_cache:
            self.price_cache[exchange_name] = {}
        self.price_cache[exchange_name][pair] = price
    
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
    
    async def verify_liquidity(self, opportunity: ArbitrageOpportunity, trade_amount: float = 100.0) -> ArbitrageOpportunity:
        """
        Verify liquidity using order book depth and calculating VWAP.
        Returns updated opportunity with VWAP prices.
        """
        # Only Binance supports depth currently
        if opportunity.buy_exchange == "binance" or opportunity.sell_exchange == "binance":
            pass # We can check
        else:
            return opportunity # Can't check, return as is
            
        buy_vwap = opportunity.buy_price
        sell_vwap = opportunity.sell_price
        
        # Check Buy Side (We are buying on this exchange)
        if opportunity.buy_exchange == "binance":
            book = await self.bot.exchanges["binance"].get_order_book(opportunity.pair)
            if 'asks' in book: # We buy from asks
                buy_vwap = self.calculate_vwap(book['asks'], trade_amount / opportunity.buy_price)
                
        # Check Sell Side (We are selling on this exchange)
        if opportunity.sell_exchange == "binance":
            book = await self.bot.exchanges["binance"].get_order_book(opportunity.pair)
            if 'bids' in book: # We sell to bids
                sell_vwap = self.calculate_vwap(book['bids'], trade_amount / opportunity.buy_price)
                
        # Update Opportunity
        if buy_vwap > 0 and sell_vwap > 0:
            opportunity.buy_price = buy_vwap
            opportunity.sell_price = sell_vwap
            opportunity.spread = sell_vwap - buy_vwap
            opportunity.spread_percentage = (opportunity.spread / buy_vwap) * 100
            
            # Recalculate net profit with new spread
            from core.fee_calculator import FeeCalculator
            opportunity.net_spread_percentage = FeeCalculator.calculate_net_profit(
                opportunity.buy_exchange, opportunity.sell_exchange, opportunity.spread_percentage
            )
            opportunity.actual_profit_percentage = opportunity.net_spread_percentage
            
        return opportunity

    @staticmethod
    def calculate_vwap(order_book: List[List[str]], trade_amount: float) -> float:
        """
        Calculate Volume-Weighted Average Price
        order_book: List of [price, qty] (bids or asks)
        trade_amount: Total amount of base currency we want to trade
        """
        remaining_amount = trade_amount
        total_cost = 0.0
        
        for price_str, qty_str in order_book:
            price = float(price_str)
            qty = float(qty_str)
            
            fill_amount = min(remaining_amount, qty)
            total_cost += fill_amount * price
            remaining_amount -= fill_amount
            
            if remaining_amount <= 0:
                break
        
        # If we couldn't fill the entire order, average price is based on what we filled
        # (In reality, you might reject this trade)
        filled_amount = trade_amount - remaining_amount
        if filled_amount == 0:
            return 0.0
            
        return total_cost / filled_amount

    async def get_exchange_prices(self, exchange_name: str, exchange):
        # Phase 1: Use cache if streaming
        if exchange_name in self.streaming_exchanges:
            # Return cached prices for requested pairs
            cached = self.price_cache.get(exchange_name, {})
            # Only return pairs we care about that we have data for
            filtered_prices = {
                p: cached[p] 
                for p in self.bot.config["trading_pairs"] 
                if p in cached
            }
            return (exchange_name, filtered_prices)
            
        # Fallback to REST API for non-streaming exchanges
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