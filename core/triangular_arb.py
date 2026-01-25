import asyncio
import time
import math
from typing import Dict, List, Tuple
from models.data_models import TriangularOpportunity

class TriangularArbitrageEngine:
    def __init__(self, bot):
        self.bot = bot
        self.min_profit = bot.config.get("min_triangular_profit_percent", 0.5)
        # Graph structure: graph[currency][target_currency] = {'rate': float, 'action': 'BUY'/'SELL'}
        self.graphs: Dict[str, Dict] = {} 
        
    def build_graph(self, exchange_name: str, tickers: Dict[str, float]) -> None:
        """
        Constructs a directed graph of exchange rates for a specific exchange.
        tickers format: {"BTC-USDT": 45000.0, "ETH-USDT": 3000.0}
        """
        graph = {}
        
        for pair, price in tickers.items():
            try:
                # Assuming pairs are format "BASE-QUOTE" e.g. "BTC-USDT"
                base, quote = pair.split('-')
                
                # Edge 1: Sell Base -> Buy Quote
                # 1 BASE = price QUOTE
                if base not in graph: graph[base] = {}
                graph[base][quote] = {'rate': price, 'action': 'SELL', 'pair': pair}
                
                # Edge 2: Sell Quote -> Buy Base
                # 1 QUOTE = 1/price BASE
                if price > 0:
                    if quote not in graph: graph[quote] = {}
                    graph[quote][base] = {'rate': 1.0 / price, 'action': 'BUY', 'pair': pair}
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
                    
                    # Calculate potential profit
                    # (Simple calc, ignoring fees for speed, real logic would subtract fees)
                    profit_pct = (total_rate - 1.0) * 100
                    
                    if profit_pct > self.min_profit:
                        opp = TriangularOpportunity(
                            exchange=exchange_name,
                            path=[start_currency, b_currency, c_currency, start_currency],
                            rates=[rate_ab, rate_bc, rate_ca],
                            actions=[edge_ab['action'], edge_bc['action'], edge_ca['action']],
                            initial_amount=100.0, # Example amount
                            final_amount=100.0 * total_rate,
                            profit=100.0 * (total_rate - 1.0),
                            profit_percentage=profit_pct,
                            timestamp=time.time()
                        )
                        opportunities.append(opp)
                        
        return opportunities
