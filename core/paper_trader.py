import json
import time
from typing import Dict, List
from models.data_models import ArbitrageOpportunity

class PaperTrader:
    def __init__(self, initial_balance: float = 1000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions = {}
        self.trade_history = []
        self.total_trades = 0
        self.profitable_trades = 0
        
    def execute_trade(self, opportunity: ArbitrageOpportunity, trade_amount: float = 100):
        """Simulate executing an arbitrage trade"""
        
        # Calculate quantities
        buy_quantity = trade_amount / opportunity.buy_price
        sell_revenue = buy_quantity * opportunity.sell_price
        
        # Calculate fees
        buy_fee = trade_amount * opportunity.buy_fee
        sell_fee = sell_revenue * opportunity.sell_fee
        
        # Calculate net profit
        gross_profit = sell_revenue - trade_amount
        total_fees = buy_fee + sell_fee
        net_profit = gross_profit - total_fees
        net_profit_percentage = (net_profit / trade_amount) * 100
        
        # Update balance
        self.balance += net_profit
        self.total_trades += 1
        
        if net_profit > 0:
            self.profitable_trades += 1
        
        # Record trade
        trade_record = {
            'timestamp': time.time(),
            'pair': opportunity.pair,
            'buy_exchange': opportunity.buy_exchange,
            'sell_exchange': opportunity.sell_exchange,
            'buy_price': opportunity.buy_price,
            'sell_price': opportunity.sell_price,
            'quantity': buy_quantity,
            'trade_amount': trade_amount,
            'gross_profit': gross_profit,
            'fees': total_fees,
            'net_profit': net_profit,
            'net_profit_percentage': net_profit_percentage,
            'balance_after': self.balance
        }
        
        self.trade_history.append(trade_record)
        
        print(f"📊 PAPER TRADE EXECUTED:")
        print(f"   {opportunity.pair}: {opportunity.buy_exchange} → {opportunity.sell_exchange}")
        print(f"   Amount: ${trade_amount:.2f} | Net Profit: ${net_profit:.4f} ({net_profit_percentage:.4f}%)")
        print(f"   New Balance: ${self.balance:.2f}")
        
        return trade_record
    
    def get_performance_stats(self):
        """Get paper trading performance statistics"""
        total_net_profit = self.balance - self.initial_balance
        win_rate = (self.profitable_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            'initial_balance': self.initial_balance,
            'current_balance': self.balance,
            'total_net_profit': total_net_profit,
            'total_trades': self.total_trades,
            'profitable_trades': self.profitable_trades,
            'win_rate': win_rate,
            'return_percentage': (total_net_profit / self.initial_balance) * 100
        }
    
    def save_trade_history(self, filename: str = "paper_trades.json"):
        """Save trade history to file"""
        with open(filename, 'w') as f:
            json.dump(self.trade_history, f, indent=2)