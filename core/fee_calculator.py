class FeeCalculator:
    """Calculate trading fees for each exchange"""
    
    # Trading fees (maker/taker averages)
    EXCHANGE_FEES = {
        "binance": 0.0010,  # 0.10%
        "coinbase": 0.0050, # 0.50%
        "kraken": 0.0026,   # 0.26%
        "kucoin": 0.0010,   # 0.10%
        "bybit": 0.0010,    # 0.10%
        "okx": 0.0008,      # 0.08%
        "gateio": 0.0020,   # 0.20%
    }
    
    @classmethod
    def calculate_net_profit(cls, buy_exchange: str, sell_exchange: str, 
                        spread_percentage: float) -> float:
        """Calculate actual profit after fees - CORRECTED VERSION"""
        buy_fee = cls.EXCHANGE_FEES.get(buy_exchange, 0.002)  # 0.002 = 0.2%
        sell_fee = cls.EXCHANGE_FEES.get(sell_exchange, 0.002)  # 0.002 = 0.2%
        
        total_fees = buy_fee + sell_fee
        
        # Convert fees from decimal to percentage for correct calculation
        total_fees_percentage = total_fees * 100  # Convert 0.0030 to 0.30%
        
        net_profit = spread_percentage - total_fees_percentage
        
        return net_profit
    
    @classmethod
    def get_exchange_fee(cls, exchange_name: str) -> float:
        """Get fee for a specific exchange"""
        return cls.EXCHANGE_FEES.get(exchange_name, 0.002)  # Default 0.2%