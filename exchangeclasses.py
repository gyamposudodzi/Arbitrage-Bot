class BaseExchangeAPI:
    def _init_(self, config: Dict):
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
        raise NotImplementedError
    
    def normalize_pair(self, pair: str) -> str:
        """Normalize trading pair format for specific exchange"""
        return pair

class BinanceAPI(BaseExchangeAPI):
    def _init_(self, config: Dict):
        super()._init_(config)
        self.name = "binance"
        self.base_url = "https://api.binance.com/api/v3"
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTCUSDT
        return pair.replace("-", "")
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            async with session.get(f"{self.base_url}/ticker/bookTicker") as response:
                if response.status == 200:
                    data = await response.json()
                    # Convert to dict for easy lookup
                    price_dict = {item['symbol']: float(item['bidPrice']) for item in data}
                    
                    for pair in pairs:
                        normalized = self.normalize_pair(pair)
                        if normalized in price_dict:
                            prices[pair] = price_dict[normalized]
                else:
                    print(f"Binance API error: {response.status}")
        except Exception as e:
            print(f"Binance error: {e}")
        
        return prices

class CoinbaseAPI(BaseExchangeAPI):
    def _init_(self, config: Dict):
        super()._init_(config)
        self.name = "coinbase"
        self.base_url = "https://api.pro.coinbase.com"
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to BTC-USDT (Coinbase uses dashes)
        return pair.replace("-", "-")
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        for pair in pairs:
            try:
                normalized = self.normalize_pair(pair)
                async with session.get(f"{self.base_url}/products/{normalized}/ticker") as response:
                    if response.status == 200:
                        data = await response.json()
                        prices[pair] = float(data['bid'])
                    else:
                        print(f"Coinbase API error for {pair}: {response.status}")
            except Exception as e:
                print(f"Coinbase error for {pair}: {e}")
        
        return prices

class KrakenAPI(BaseExchangeAPI):
    def _init_(self, config: Dict):
        super()._init_(config)
        self.name = "kraken"
        self.base_url = "https://api.kraken.com/0"
    
    def normalize_pair(self, pair: str) -> str:
        # Convert BTC-USDT to XBTUSDT (Kraken uses different symbols)
        mapping = {
            "BTC-USDT": "XBTUSDT",
            "ETH-USDT": "ETHUSDT",
            "ADA-USDT": "ADAUSDT"
        }
        return mapping.get(pair, pair.replace("-", ""))
    
    async def get_prices(self, pairs: List[str]) -> Dict[str, float]:
        prices = {}
        session = await self.get_session()
        
        try:
            pairs_param = ",".join([self.normalize_pair(pair) for pair in pairs])
            async with session.get(f"{self.base_url}/public/Ticker?pair={pairs_param}") as response:
                if response.status == 200:
                    data = await response.json()
                    for pair in pairs:
                        normalized = self.normalize_pair(pair)
                        if normalized in data['result']:
                            # Kraken returns array with [bid, ask, ...]
                            prices[pair] = float(data['result'][normalized]['b'][0])
                else:
                    print(f"Kraken API error: {response.status}")
        except Exception as e:
            print(f"Kraken error: {e}")
        
        return prices