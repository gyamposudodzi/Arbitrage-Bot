import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchanges.binance_api import BinanceAPI
from core.funding_arb import FundingRateArbitrageEngine

async def test_funding():
    print("🧪 Testing Funding Rate Arbitrage...")
    
    # Setup
    config = {"api_key": "", "api_secret": ""}
    api = BinanceAPI(config)
    engine = FundingRateArbitrageEngine(None) # Bot not needed for simple logic test
    
    try:
        # 1. Fetch Rates
        print("   Fetching funding rates from Binance Futures...")
        rates = await api.get_funding_rates()
        print(f"   ✅ Fetched {len(rates)} records")
        
        # 2. Analyze
        print("   Analyzing opportunities...")
        ops = engine.find_opportunities(rates)
        print(f"   ✅ Found {len(ops)} positive opportunities")
        
        # 3. Show Top 5
        print("\n🏆 TOP 5 FUNDING OPPORTUNITIES:")
        for i, op in enumerate(ops[:5], 1):
            print(f"   {i}. {op.pair:<10} | Funding: {op.funding_rate*100:.4f}% | APY: {op.annualized_rate:.2f}%")
            
    finally:
        await api.close_session()

if __name__ == "__main__":
    asyncio.run(test_funding())
