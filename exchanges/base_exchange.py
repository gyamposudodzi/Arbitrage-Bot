import aiohttp
import socket
from typing import Dict, List

class BaseExchangeAPI:
    def __init__(self, config: Dict):
        self.name = ""
        self.base_url = ""
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.session = None
        
    async def get_session(self) -> aiohttp.ClientSession:
        if not self.session:
            resolver = aiohttp.ThreadedResolver()
            timeout = aiohttp.ClientTimeout(
                total=20,
                connect=10,
                sock_connect=10,
                sock_read=20
            )
            connector = aiohttp.TCPConnector(
                resolver=resolver,
                family=socket.AF_INET,
                ttl_dns_cache=300
            )
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self.session
    
    async def close_session(self):
        if self.session:
            await self.session.close()

    async def get_funding_rates(self) -> List[Dict]:
        """
        Fetch real-time funding rates.
        Returns empty list if not supported.
        """
        return []

    async def get_all_tickers(self) -> Dict[str, float]:
        """
        Fetch all prices for the exchange (used for Triangular Arb).
        Returns empty dict if not supported.
        """
        return {}

    async def get_trading_pairs(self) -> set:
        """
        Fetch all supported trading pairs for the exchange.
        Returns normalized set of strings {'BTC-USDT', ...}
        """
        return set()
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        raise NotImplementedError("Subclasses must implement this method")
    
    def normalize_pair(self, pair: str) -> str:
        """Normalize trading pair format for specific exchange"""
        return pair
