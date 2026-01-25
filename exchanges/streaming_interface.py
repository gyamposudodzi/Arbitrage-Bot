from abc import ABC, abstractmethod
from typing import List, Callable, Awaitable

class StreamingExchangeInterface(ABC):
    """
    Interface for exchanges that support WebSocket streaming.
    """
    
    @abstractmethod
    async def start_stream(self, pairs: List[str], callback: Callable[[str, float, str], Awaitable[None]]):
        """
        Start the WebSocket stream for the given pairs.
        
        Args:
            pairs: List of trading pairs to subscribe to (e.g., ["BTC-USDT"]).
            callback: Async function to call when a price update is received.
                      Signature: callback(pair: str, price: float, exchange_name: str)
        """
        pass
        
    @abstractmethod
    async def stop_stream(self):
        """Stop the WebSocket stream and clean up resources."""
        pass
