import aiohttp
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
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        raise NotImplementedError("Subclasses must implement this method")
    
    def normalize_pair(self, pair: str) -> str:
        """Normalize trading pair format for specific exchange"""
        return pair