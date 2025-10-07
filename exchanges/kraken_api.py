import aiohttp
from typing import Dict, List
from .base_exchange import BaseExchangeAPI

class KrakenAPI(BaseExchangeAPI):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "kraken"
        self.base_url = "https://api.kraken.com/0"
    
    def normalize_pair(self, pair: str) -> str:
        # Based on our discovery, these pairs work with simple USDT format
        working_pairs = {
            "BTC-USDT": "BTCUSDT",
            "ETH-USDT": "ETHUSDT",
            "ADA-USDT": "ADAUSDT", 
            "DOT-USDT": "DOTUSDT",
            "LINK-USDT": "LINKUSDT",
            "SOL-USDT": "SOLUSDT",
            "AVAX-USDT": "AVAXUSDT",
            "ATOM-USDT": "ATOMUSDT",
            "XRP-USDT": "XRPUSDT",
            "DOGE-USDT": "DOGEUSDT",
            "NEAR-USDT": "NEARUSDT", 
            "ALGO-USDT": "ALGOUSDT",
            "SAND-USDT": "SANDUSDT",
            "MANA-USDT": "MANAUSDT",
            "ENJ-USDT": "ENJUSDT",
            "CHZ-USDT": "CHZUSDT",
            "BAT-USDT": "BATUSDT",
            "GALA-USDT": "GALAUSDT",
            "IMX-USDT": "IMXUSDT",
            "RUNE-USDT": "RUNEUSDT",
            "INJ-USDT": "INJUSDT",
            "ARB-USDT": "ARBUSDT",
            "OP-USDT": "OPUSDT",
            "APT-USDT": "APTUSDT",
            "SEI-USDT": "SEIUSDT",
            "SUI-USDT": "SUIUSDT",
        }
        return working_pairs.get(pair)
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            # Only query pairs we know work
            supported_pairs = []
            for pair in pairs:
                normalized = self.normalize_pair(pair)
                if normalized:
                    supported_pairs.append(normalized)
            
            if not supported_pairs:
                return prices
            
            # Query all supported pairs at once (more efficient)
            pairs_param = ",".join(supported_pairs)
            url = f"{self.base_url}/public/Ticker?pair={pairs_param}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'error' in data and data['error']:
                        # Log non-pair errors only
                        non_pair_errors = [err for err in data['error'] if 'Unknown asset pair' not in err]
                        if non_pair_errors:
                            print(f"❌ Kraken API error: {non_pair_errors}")
                        return prices
                    
                    if 'result' in data:
                        # Create reverse mapping
                        reverse_map = {v: k for k, v in self.working_pairs.items()}
                        
                        for kraken_pair, ticker_data in data['result'].items():
                            if kraken_pair in reverse_map:
                                original_pair = reverse_map[kraken_pair]
                                bid_price = ticker_data['b'][0]
                                if bid_price:
                                    prices[original_pair] = float(bid_price)
                    
        except Exception as e:
            print(f"❌ Kraken error: {e}")
        
        return prices
    
    # Class variable for the working pairs mapping
    working_pairs = {
        "BTC-USDT": "BTCUSDT",
        "ETH-USDT": "ETHUSDT",
        "ADA-USDT": "ADAUSDT", 
        "DOT-USDT": "DOTUSDT",
        "LINK-USDT": "LINKUSDT",
        "SOL-USDT": "SOLUSDT",
        "AVAX-USDT": "AVAXUSDT",
        "ATOM-USDT": "ATOMUSDT",
        "XRP-USDT": "XRPUSDT",
        "DOGE-USDT": "DOGEUSDT",
        "NEAR-USDT": "NEARUSDT", 
        "ALGO-USDT": "ALGOUSDT",
        "SAND-USDT": "SANDUSDT",
        "MANA-USDT": "MANAUSDT",
        "ENJ-USDT": "ENJUSDT",
        "CHZ-USDT": "CHZUSDT",
        "BAT-USDT": "BATUSDT",
        "GALA-USDT": "GALAUSDT",
        "IMX-USDT": "IMXUSDT",
        "RUNE-USDT": "RUNEUStDT",
        "INJ-USDT": "INJUSDT",
        "ARB-USDT": "ARBUSDT",
        "OP-USDT": "OPUSDT",
        "APT-USDT": "APTUSDT",
        "SEI-USDT": "SEIUSDT",
        "SUI-USDT": "SUIUSDT",
    }