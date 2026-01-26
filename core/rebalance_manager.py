import asyncio
import time
from typing import Dict, List, Optional

class RebalanceManager:
    """
    Manages inventory rebalancing between exchanges.
    Transfers funds from 'Rich' exchanges to 'Poor' exchanges.
    """
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config.get("rebalance", {})
        self.enabled = self.config.get("enabled", False)
        self.min_balance = self.config.get("min_balance", 200)
        self.target_balance = self.config.get("target_balance", 1000)
        self.allowed_assets = self.config.get("allowed_assets", ["USDT"])
        self.last_check = 0
        self.check_interval = self.config.get("check_interval", 300) # 5 mins
        
    async def check_and_rebalance(self):
        """Main loop to check imbalances and trigger transfers"""
        if not self.enabled:
            return
            
        if time.time() - self.last_check < self.check_interval:
            return
            
        self.last_check = time.time()
        print("⚖️  Checking Inventory Health...")
        
        # 1. Get Balances (Use cached from ExecutionManager)
        # We assume ExecutionManager has fresh-ish balances.
        # Ideally we force refresh if critically reliable, but cache is fine for status check.
        balances = self.bot.executor.balances
        if not balances:
            print("   ⚠️  No balances available to check.")
            return

        # 2. Analyze
        rich_exchanges = []
        poor_exchanges = []
        
        # Only checks USDT for now
        asset = "USDT" 
        
        for name, balance in balances.items():
            if balance < self.min_balance:
                poor_exchanges.append({'name': name, 'balance': balance, 'shortfall': self.target_balance - balance})
            elif balance > (self.target_balance + 200): # Buffer
                rich_exchanges.append({'name': name, 'balance': balance, 'surplus': balance - self.target_balance})
                
        if not poor_exchanges:
            print("   ✅ Inventory Healthy. No rebalance needed.")
            return
            
        print(f"   ⚠️  Found {len(poor_exchanges)} Deficit Exchanges: {[p['name'] for p in poor_exchanges]}")
        
        # 3. Match Surplus to Deficit
        # Simple Logic: Take from Richest, Give to Poorest
        # Sort by magnitude
        rich_exchanges.sort(key=lambda x: x['surplus'], reverse=True)
        poor_exchanges.sort(key=lambda x: x['shortfall'], reverse=True)
        
        for poor in poor_exchanges:
            if not rich_exchanges:
                print(f"   ❌ No Rich exchanges available to help {poor['name']}!")
                break
                
            rich = rich_exchanges[0] # Richest
            
            # Amount to transfer
            # Don't drain the rich one below target
            safe_transfer = min(rich['surplus'], poor['shortfall'])
            
            if safe_transfer < 50: # Min transfer threshold
                print(f"   ⚠️ Transfer amount too small (${safe_transfer:.2f}). Skipping.")
                continue
                
            # Execute Transfer
            await self.execute_transfer(rich['name'], poor['name'], asset, safe_transfer)
            
            # Deduct from local tracking to avoid double spending in this loop
            rich['surplus'] -= safe_transfer
            if rich['surplus'] < 50:
                rich_exchanges.pop(0)
                
    async def execute_transfer(self, source: str, destination: str, asset: str, amount: float):
        """Execute the actual withdrawal"""
        print(f"   🔄 INITIATING REBALANCE: Sending ${amount:.2f} {asset} from {source.upper()} -> {destination.upper()}")
        
        # 1. Get Destination Address
        deposit_addrs = self.config.get("deposit_addresses", {})
        dest_addr = deposit_addrs.get(destination, {}).get(asset)
        
        if not dest_addr or "YOUR_" in dest_addr:
            print(f"   ❌ Missing Deposit Address for {destination} {asset}. Please configure config.json!")
            return
            
        # 2. Get Source Executor
        executor = self.bot.executor.executors.get(source)
        if not executor:
            print(f"   ❌ Executor for {source} not active.")
            return
            
        # 3. Call Withdraw
        # Note: 'network' param usually needed. Defaulting to 'TRX' (TRC20) for USDT if supported, or generic.
        # We will require executors to handle default network or pass it in config.
        # Hardcoding 'TRX' (Tron) for USDT efficiency for now as user requested.
        network = "TRX" if asset == "USDT" else None
        
        success = await executor.withdraw(asset, amount, dest_addr, network)
        
        if success:
            print(f"   ✅ Transfer Submitted! Monitoring status...")
        else:
            print(f"   ❌ Transfer Failed.")
