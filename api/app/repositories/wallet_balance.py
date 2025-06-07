"""WalletBalance repository implementation."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from ..models import WalletBalance
from .base import BaseRepository

logger = logging.getLogger(__name__)


class WalletBalanceRepository(BaseRepository):
    """Repository for WalletBalance entities with DuckDB storage and JetStream sync."""
    
    def __init__(self):
        super().__init__(
            model_class=WalletBalance,
            table_name="wallet_balances",
            jetstream_bucket="wallet_balances"
        )
    
    async def _insert_to_db(self, entity: WalletBalance):
        """Insert wallet balance entity to database."""
        query = """
            INSERT INTO wallet_balances (
                id, wallet_id, timestamp, balance, token_price, 
                fiat_value, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        values = [
            entity.id,
            entity.wallet_id,
            entity.timestamp,
            entity.balance,
            entity.token_price,
            entity.fiat_value,
            entity.created_at if hasattr(entity, 'created_at') else datetime.now().isoformat()
        ]
        
        self.db_connection.execute(query, values)
        logger.debug(f"Inserted wallet balance {entity.id} into database")
    
    async def get_by_wallet_id(self, wallet_id: str, limit: Optional[int] = None) -> List[WalletBalance]:
        """Get balance history for a specific wallet."""
        return await self.list(
            filters={"wallet_id": wallet_id},
            limit=limit,
            order_by="timestamp DESC"
        )
    
    async def get_latest_balance(self, wallet_id: str) -> Optional[WalletBalance]:
        """Get the most recent balance for a wallet."""
        balances = await self.get_by_wallet_id(wallet_id, limit=1)
        return balances[0] if balances else None
    
    async def get_balance_at_time(self, wallet_id: str, timestamp: str) -> Optional[WalletBalance]:
        """Get the balance closest to a specific timestamp."""
        try:
            query = """
                SELECT * FROM wallet_balances 
                WHERE wallet_id = ? AND timestamp <= ?
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            
            result = self.db_connection.execute(query, [wallet_id, timestamp]).fetchone()
            
            if result:
                columns = [desc[0] for desc in self.db_connection.description]
                data = dict(zip(columns, result))
                return WalletBalance(**data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting balance at time for wallet {wallet_id}: {e}")
            raise
    
    async def get_balance_history(self, wallet_id: str, start_time: str, 
                                end_time: str) -> List[WalletBalance]:
        """Get balance history within a time range."""
        try:
            query = """
                SELECT * FROM wallet_balances 
                WHERE wallet_id = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
            """
            
            results = self.db_connection.execute(query, [wallet_id, start_time, end_time]).fetchall()
            
            balances = []
            if results:
                columns = [desc[0] for desc in self.db_connection.description]
                for row in results:
                    data = dict(zip(columns, row))
                    balances.append(WalletBalance(**data))
            
            return balances
            
        except Exception as e:
            logger.error(f"Error getting balance history for wallet {wallet_id}: {e}")
            raise
    
    async def get_balance_changes(self, wallet_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get balance changes over the last N hours."""
        try:
            # Calculate time threshold
            threshold_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            query = """
                SELECT 
                    timestamp,
                    balance,
                    LAG(balance) OVER (ORDER BY timestamp) as previous_balance,
                    balance - LAG(balance) OVER (ORDER BY timestamp) as change
                FROM wallet_balances 
                WHERE wallet_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """
            
            results = self.db_connection.execute(query, [wallet_id, threshold_time]).fetchall()
            
            changes = []
            if results:
                columns = [desc[0] for desc in self.db_connection.description]
                for row in results:
                    data = dict(zip(columns, row))
                    if data['change'] is not None:  # Skip first row which has no previous balance
                        changes.append({
                            "timestamp": data['timestamp'],
                            "balance": float(data['balance']),
                            "previous_balance": float(data['previous_balance']),
                            "change": float(data['change'])
                        })
            
            return changes
            
        except Exception as e:
            logger.error(f"Error getting balance changes for wallet {wallet_id}: {e}")
            raise
    
    async def get_wallet_performance(self, wallet_id: str, days: int = 30) -> Dict[str, Any]:
        """Get wallet performance metrics over the last N days."""
        try:
            # Calculate time threshold
            threshold_time = (datetime.now() - timedelta(days=days)).isoformat()
            
            query = """
                SELECT 
                    MIN(balance) as min_balance,
                    MAX(balance) as max_balance,
                    AVG(balance) as avg_balance,
                    COUNT(*) as data_points,
                    MIN(timestamp) as first_timestamp,
                    MAX(timestamp) as last_timestamp
                FROM wallet_balances 
                WHERE wallet_id = ? AND timestamp >= ?
            """
            
            result = self.db_connection.execute(query, [wallet_id, threshold_time]).fetchone()
            
            if result:
                columns = [desc[0] for desc in self.db_connection.description]
                data = dict(zip(columns, result))
                
                # Get first and last balance for percentage change
                first_balance = None
                last_balance = None
                
                if data['data_points'] > 0:
                    first_query = """
                        SELECT balance FROM wallet_balances 
                        WHERE wallet_id = ? AND timestamp >= ?
                        ORDER BY timestamp ASC LIMIT 1
                    """
                    first_result = self.db_connection.execute(query, [wallet_id, threshold_time]).fetchone()
                    if first_result:
                        first_balance = float(first_result[0])
                    
                    last_query = """
                        SELECT balance FROM wallet_balances 
                        WHERE wallet_id = ? AND timestamp >= ?
                        ORDER BY timestamp DESC LIMIT 1
                    """
                    last_result = self.db_connection.execute(query, [wallet_id, threshold_time]).fetchone()
                    if last_result:
                        last_balance = float(last_result[0])
                
                # Calculate percentage change
                percentage_change = None
                if first_balance and last_balance and first_balance > 0:
                    percentage_change = ((last_balance - first_balance) / first_balance) * 100
                
                return {
                    "wallet_id": wallet_id,
                    "period_days": days,
                    "min_balance": float(data['min_balance']) if data['min_balance'] else 0,
                    "max_balance": float(data['max_balance']) if data['max_balance'] else 0,
                    "avg_balance": float(data['avg_balance']) if data['avg_balance'] else 0,
                    "first_balance": first_balance,
                    "last_balance": last_balance,
                    "percentage_change": percentage_change,
                    "data_points": data['data_points'],
                    "first_timestamp": data['first_timestamp'],
                    "last_timestamp": data['last_timestamp']
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting wallet performance for {wallet_id}: {e}")
            raise
    
    async def cleanup_old_balances(self, wallet_id: str, keep_days: int = 90) -> int:
        """Clean up old balance records, keeping only recent ones."""
        try:
            # Calculate cutoff time
            cutoff_time = (datetime.now() - timedelta(days=keep_days)).isoformat()
            
            # Count records to be deleted
            count_query = """
                SELECT COUNT(*) FROM wallet_balances 
                WHERE wallet_id = ? AND timestamp < ?
            """
            count_result = self.db_connection.execute(count_query, [wallet_id, cutoff_time]).fetchone()
            delete_count = count_result[0]
            
            if delete_count > 0:
                # Delete old records
                delete_query = """
                    DELETE FROM wallet_balances 
                    WHERE wallet_id = ? AND timestamp < ?
                """
                self.db_connection.execute(delete_query, [wallet_id, cutoff_time])
                
                logger.info(f"Cleaned up {delete_count} old balance records for wallet {wallet_id}")
            
            return delete_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old balances for wallet {wallet_id}: {e}")
            raise
    
    async def get_balance_stats(self) -> Dict[str, Any]:
        """Get wallet balance statistics."""
        try:
            stats = {}
            
            # Total balance records
            total_result = self.db_connection.execute("SELECT COUNT(*) FROM wallet_balances").fetchone()
            stats["total_balance_records"] = total_result[0]
            
            # Unique wallets with balance data
            wallets_result = self.db_connection.execute(
                "SELECT COUNT(DISTINCT wallet_id) FROM wallet_balances"
            ).fetchone()
            stats["wallets_with_balance_data"] = wallets_result[0]
            
            # Recent balance updates (last 24 hours)
            recent_result = self.db_connection.execute("""
                SELECT COUNT(*) FROM wallet_balances 
                WHERE created_at >= datetime('now', '-1 day')
            """).fetchone()
            stats["recent_balance_updates"] = recent_result[0]
            
            # Average balances by wallet (top 10)
            avg_balances = self.db_connection.execute("""
                SELECT wallet_id, AVG(balance) as avg_balance
                FROM wallet_balances 
                GROUP BY wallet_id 
                ORDER BY avg_balance DESC 
                LIMIT 10
            """).fetchall()
            
            stats["top_wallets_by_avg_balance"] = []
            for wallet_id, avg_balance in avg_balances:
                stats["top_wallets_by_avg_balance"].append({
                    "wallet_id": wallet_id,
                    "avg_balance": float(avg_balance)
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting balance statistics: {e}")
            raise
