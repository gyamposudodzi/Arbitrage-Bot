from typing import Dict, Optional
from execution.manager import ExecutionManager

class FeeManager:
    """
    Manages calculation of network withdrawal fees.
    Uses ExecutionManager to fetch real-time fees from exchanges.
    """
    
    def __init__(self, execution_manager: ExecutionManager):
        self.executor = execution_manager
        # Fallback Estimations (in Asset Amount approx)
        self.default_fees = {
            'USDT': 1.0, # $1 standard
            'BTC': 0.0001, # ~$10
            'ETH': 0.005, # ~$10-15
        }
        
    async def get_withdrawal_fee(self, exchange: str, asset: str) -> float:
        """
        Get the withdrawal fee for a specific asset on an exchange.
        Returns amount in ASSET (e.g., 1.0 USDT).
        """
        # 1. Try to get real-time fee
        if exchange in self.executor.executors:
            exec_instance = self.executor.executors[exchange]
            if hasattr(exec_instance, 'get_withdrawal_info'):
                info = await exec_instance.get_withdrawal_info(asset)
                if info and 'fee' in info:
                    print(f"   ℹ️  Fetched {exchange} fee for {asset}: {info['fee']} (Net: {info.get('network')})")
                    return float(info['fee'])
        
        # 2. Fallback
        fallback = self.default_fees.get(asset.upper(), 0.1)
        # print(f"   ⚠️  Using fallback fee for {exchange} {asset}: {fallback}")
        return fallback

    async def calculate_net_profit(self, opportunity) -> float:
        """
        Calculate Net Profit after withdrawal fees.
        Logic: Buy on A -> Withdraw -> Deposit on B -> Sell on B.
        Cost = Trading Fees (already in opp) + Withdrawal Fee from A.
        """
        # Getting asset name (e.g., 'BTC' from 'BTC-USDT')
        # Simplified: usually base currency is the asset being transferred?
        # NO.
        # Arbitrage Cycle:
        # Start with USDT on Exchange A.
        # Buy BTC on A.
        # Withdraw BTC from A to B. (Withdrawal Fee in BTC)
        # Sell BTC on B for USDT.
        # Withdraw USDT from B to A? (Or keep on B).
        # "Simple" arb P&L usually assumes ending state is USDT on B.
        # So we only pay withdrawal fee of the BASE asset (BTC).
        
        pair = opportunity.pair
        base_currency = pair.split("-")[0].replace("USDT","").replace("USD","") # Very rough parsing
        if "-" in pair:
             base_currency = pair.split("-")[0]
        
        # Fee is in Base Currency (e.g. 0.0005 BTC)
        fee_in_base = await self.get_withdrawal_fee(opportunity.buy_exchange, base_currency)
        
        # Convert Fee to USDT value
        # We need Price. Opportunity has 'buy_price'.
        fee_in_usdt = fee_in_base * opportunity.buy_price
        
        # Gross Profit (in USDT)
        gross_profit = (opportunity.sell_price - opportunity.buy_price) * (100 / opportunity.buy_price) # Wait this is %, we need $
        # opportunity.profit_percentage is %.
        # Let's assume trade size $100.
        
        # Net Profit $ = (Gross Profit $) - (Withdrawal Cost $)
        return fee_in_usdt
