import asyncio
import time
import math
from typing import Dict, List, Tuple
from models.data_models import TriangularOpportunity
from core.fee_calculator import FeeCalculator

class TriangularArbitrageEngine:
    def __init__(self, bot):
        self.bot = bot
        self.min_profit = bot.config.get("min_triangular_profit_percent", 0.0)
        # Graph structure: graph[currency][target_currency] = {'rate': float, 'action': 'BUY'/'SELL'}
        self.graphs: Dict[str, Dict] = {} 
        
    def build_graph(self, exchange_name: str, tickers: Dict[str, Dict[str, float]]) -> None:
        """
        Constructs a directed graph of exchange rates for a specific exchange.
        tickers format:
        {"BTC-USDT": {"bid": 45000.0, "ask": 45001.0}}
        """
        graph = {}
        
        for pair, ticker in tickers.items():
            try:
                # Assuming pairs are format "BASE-QUOTE" e.g. "BTC-USDT"
                base, quote = pair.split('-')
                if isinstance(ticker, dict):
                    bid_price = float(ticker.get('bid', 0))
                    ask_price = float(ticker.get('ask', 0))
                else:
                    bid_price = float(ticker)
                    ask_price = float(ticker)
                
                # Edge 1: Sell Base -> Buy Quote
                # We receive bid when selling base for quote.
                if bid_price > 0:
                    if base not in graph: graph[base] = {}
                    graph[base][quote] = {'rate': bid_price, 'action': 'SELL', 'pair': pair}
                
                # Edge 2: Sell Quote -> Buy Base
                # We pay ask when buying base with quote.
                if ask_price > 0:
                    if quote not in graph: graph[quote] = {}
                    graph[quote][base] = {'rate': 1.0 / ask_price, 'action': 'BUY', 'pair': pair}
            except ValueError:
                continue # Skip invalid pair formats
                
        self.graphs[exchange_name] = graph

    def find_opportunities(self, exchange_name: str) -> List[TriangularOpportunity]:
        """
        Finds triangular arbitrage opportunities (A -> B -> C -> A)
        """
        opportunities = []
        if exchange_name not in self.graphs:
            return opportunities
            
        graph = self.graphs[exchange_name]
        
        # We only care about loops starting with 'USDT' (or other stablecoins) typically
        start_currency = 'USDT'
        
        if start_currency not in graph:
            return opportunities
            
        # Step 1: A -> B
        for b_currency, edge_ab in graph[start_currency].items():
            rate_ab = edge_ab['rate']
            
            # Step 2: B -> C
            if b_currency not in graph: continue
            for c_currency, edge_bc in graph[b_currency].items():
                if c_currency == start_currency: continue # Don't go back immediately
                
                rate_bc = edge_bc['rate']
                
                # Step 3: C -> A
                if c_currency not in graph: continue
                if start_currency in graph[c_currency]:
                    edge_ca = graph[c_currency][start_currency]
                    rate_ca = edge_ca['rate']
                    
                    # Calculate total path rate
                    total_rate = rate_ab * rate_bc * rate_ca
                    
                    # Calculate gross and fee-adjusted net profit.
                    gross_profit_pct = (total_rate - 1.0) * 100
                    fee_rate = FeeCalculator.get_exchange_fee(exchange_name)
                    estimated_fee_pct = fee_rate * 100 * 3
                    profit_pct = gross_profit_pct - estimated_fee_pct
                    
                    if profit_pct > self.min_profit:
                        opp = TriangularOpportunity(
                            exchange=exchange_name,
                            path=[start_currency, b_currency, c_currency, start_currency],
                            pairs=[edge_ab['pair'], edge_bc['pair'], edge_ca['pair']],
                            rates=[rate_ab, rate_bc, rate_ca],
                            actions=[edge_ab['action'], edge_bc['action'], edge_ca['action']],
                            initial_amount=100.0, # Example amount
                            final_amount=100.0 * (1 + (profit_pct / 100)),
                            profit=100.0 * (profit_pct / 100),
                            gross_profit_percentage=gross_profit_pct,
                            estimated_fee_percentage=estimated_fee_pct,
                            profit_percentage=profit_pct,
                            timestamp=time.time()
                        )
                        opportunities.append(opp)
        
        opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
        return opportunities
