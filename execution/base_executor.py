import abc
import aiohttp
import time
import hmac
import hashlib
from typing import Dict, Optional

class BaseOrderExecutor(abc.ABC):
    """Abstract base class for all exchange order execution"""
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.session = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    @abc.abstractmethod
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """Place a market order - must be implemented by subclasses"""
        pass
    
    @abc.abstractmethod
    async def get_balance(self, asset: str) -> float:
        """Get account balance - must be implemented by subclasses"""
        pass
    
    @abc.abstractmethod
    async def get_order_status(self, order_id: str) -> Dict:
        """Check order status - must be implemented by subclasses"""
        pass
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order - optional to implement"""
        raise NotImplementedError("Cancel order not implemented for this exchange")