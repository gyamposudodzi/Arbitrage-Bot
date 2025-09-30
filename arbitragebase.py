import asyncio
import aiohttp
import time
import json
from typing import Dict, List, Tuple
import hmac
import hashlib
import base64
from dataclasses import dataclass

@dataclass
class ArbitrageOpportunity:
    pair: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread: float
    spread_percentage: float
    timestamp: float

class ArbitrageBot:
    def _init_(self, config_file: str = "config.json"):
        self.config = self.load_config(config_file)
        self.exchanges = {}
        self.opportunities = []
        self.setup_exchanges()
        
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Default configuration
                return {
                "exchanges": {
                    "binance": {"enabled": True, "api_key": "", "api_secret": ""},
                    "coinbase": {"enabled": True, "api_key": "", "api_secret": ""},
                    "kraken": {"enabled": True, "api_key": "", "api_secret": ""}
                },
                "trading_pairs": ["BTC-USDT", "ETH-USDT", "ADA-USDT"],
                "min_spread_percentage": 0.5,
                "update_interval": 5,
                "max_opportunities": 10
            }
    
    def setup_exchanges(self):
        """Initialize exchange connectors"""
        if self.config["exchanges"]["binance"]["enabled"]:
            self.exchanges["binance"] = BinanceAPI(self.config["exchanges"]["binance"])
        if self.config["exchanges"]["coinbase"]["enabled"]:
            self.exchanges["coinbase"] = CoinbaseAPI(self.config["exchanges"]["coinbase"])
        if self.config["exchanges"]["kraken"]["enabled"]:
            self.exchanges["kraken"] = KrakenAPI(self.config["exchanges"]["kraken"])