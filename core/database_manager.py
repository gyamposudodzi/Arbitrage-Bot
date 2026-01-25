import sqlite3
import time
import os
from typing import Dict, Any, List
from models.data_models import ArbitrageOpportunity, TriangularOpportunity

class DatabaseManager:
    def __init__(self, db_path: str = "data/trades.db", schema_path: str = "models/schema.sql"):
        self.db_path = db_path
        self.schema_path = schema_path
        self._init_db()

    def _init_db(self):
        """Initialize database with schema"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Read schema file
            with open(self.schema_path, "r") as f:
                schema = f.read()
                
            cursor.executescript(schema)
            conn.commit()
            conn.close()
            print(f"✅ Database initialized at {self.db_path}")
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")

    def log_trade(self, opportunity: ArbitrageOpportunity, amount: float, profit: float):
        """Log a standard arbitrage trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO trades (
                    timestamp, strategy_type, pair, buy_exchange, sell_exchange, 
                    buy_price, sell_price, spread, spread_percentage, net_profit, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                time.time(),
                "STANDARD",
                opportunity.pair,
                opportunity.buy_exchange,
                opportunity.sell_exchange,
                opportunity.buy_price,
                opportunity.sell_price,
                opportunity.spread,
                opportunity.spread_percentage,
                profit,
                "EXECUTED"
            ))
            conn.commit()
        except Exception as e:
            print(f"❌ Failed to log trade: {e}")
        finally:
            conn.close()

    def log_triangular_trade(self, opportunity: TriangularOpportunity):
        """Log a triangular arbitrage trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            path_str = "->".join(opportunity.path)
            cursor.execute("""
                INSERT INTO trades (
                    timestamp, strategy_type, pair, buy_exchange, sell_exchange, 
                    buy_price, sell_price, spread, spread_percentage, net_profit, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                time.time(),
                "TRIANGULAR",
                path_str,
                opportunity.exchange,
                opportunity.exchange,  # Buy/Sell exchange is the same
                0.0, # Not applicable in same way
                0.0,
                0.0,
                opportunity.profit_percentage,
                opportunity.profit,
                "EXECUTED"
            ))
            conn.commit()
        except Exception as e:
            print(f"❌ Failed to log triangular trade: {e}")
        finally:
            conn.close()
            
    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Fetch recent trades"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
