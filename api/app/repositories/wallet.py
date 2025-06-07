"""Wallet repository implementation."""

import logging
from typing import Optional, Dict, Any, List
from ..models import Wallet
from .base import BaseRepository

logger = logging.getLogger(__name__)


class WalletRepository(BaseRepository):
    """Repository for Wallet entities with DuckDB storage and JetStream sync."""
    
    def __init__(self):
        super().__init__(
            model_class=Wallet,
            table_name="wallets",
            jetstream_bucket="wallets"
        )
    
    async def _insert_to_db(self, entity: Wallet):
        """Insert wallet entity to database."""
        query = """
            INSERT INTO wallets (
                id, blockchain_symbol, address, name, balance, 
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        values = [
            entity.id,
            entity.blockchain_symbol,
            entity.address,
            entity.name,
            entity.balance,
            entity.status,
            entity.created_at,
            entity.updated_at
        ]
        
        self.db_connection.execute(query, values)
        logger.debug(f"Inserted wallet {entity.id} into database")
    
    async def get_by_address(self, blockchain_symbol: str, address: str) -> Optional[Wallet]:
        """Get wallet by blockchain symbol and address."""
        try:
            query = "SELECT * FROM wallets WHERE blockchain_symbol = ? AND address = ?"
            result = self.db_connection.execute(query, [blockchain_symbol, address]).fetchone()
            
            if result:
                columns = [desc[0] for desc in self.db_connection.description]
                data = dict(zip(columns, result))
                return Wallet(**data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting wallet by address {blockchain_symbol}:{address}: {e}")
            raise
    
    async def get_by_blockchain(self, blockchain_symbol: str) -> List[Wallet]:
        """Get all wallets for a specific blockchain."""
        return await self.list(filters={"blockchain_symbol": blockchain_symbol})
    
    async def get_active_wallets(self) -> List[Wallet]:
        """Get all active wallets."""
        return await self.list(filters={"status": "active"})
    
    async def update_balance(self, wallet_id: str, new_balance: float) -> Optional[Wallet]:
        """Update wallet balance."""
        return await self.update(wallet_id, {"balance": new_balance})
    
    async def update_status(self, wallet_id: str, status: str) -> Optional[Wallet]:
        """Update wallet status."""
        return await self.update(wallet_id, {"status": status})
    
    async def search_wallets(self, search_term: str, limit: Optional[int] = None) -> List[Wallet]:
        """Search wallets by name or address."""
        try:
            query = """
                SELECT * FROM wallets 
                WHERE name ILIKE ? OR address ILIKE ?
                ORDER BY created_at DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            search_pattern = f"%{search_term}%"
            results = self.db_connection.execute(query, [search_pattern, search_pattern]).fetchall()
            
            # Convert results to Wallet models
            wallets = []
            if results:
                columns = [desc[0] for desc in self.db_connection.description]
                for row in results:
                    data = dict(zip(columns, row))
                    wallets.append(Wallet(**data))
            
            return wallets
            
        except Exception as e:
            logger.error(f"Error searching wallets with term '{search_term}': {e}")
            raise
    
    async def address_exists(self, blockchain_symbol: str, address: str, 
                           exclude_wallet_id: Optional[str] = None) -> bool:
        """Check if an address already exists for a blockchain."""
        try:
            query = "SELECT COUNT(*) FROM wallets WHERE blockchain_symbol = ? AND address = ?"
            values = [blockchain_symbol, address]
            
            if exclude_wallet_id:
                query += " AND id != ?"
                values.append(exclude_wallet_id)
            
            result = self.db_connection.execute(query, values).fetchone()
            return result[0] > 0
            
        except Exception as e:
            logger.error(f"Error checking address existence for {blockchain_symbol}:{address}: {e}")
            raise
    
    async def get_wallet_stats(self) -> Dict[str, Any]:
        """Get wallet statistics."""
        try:
            stats = {}
            
            # Total wallets
            total_result = self.db_connection.execute("SELECT COUNT(*) FROM wallets").fetchone()
            stats["total_wallets"] = total_result[0]
            
            # Active wallets
            active_result = self.db_connection.execute(
                "SELECT COUNT(*) FROM wallets WHERE status = 'active'"
            ).fetchone()
            stats["active_wallets"] = active_result[0]
            
            # Wallets by blockchain
            blockchain_results = self.db_connection.execute("""
                SELECT blockchain_symbol, COUNT(*) as count 
                FROM wallets 
                GROUP BY blockchain_symbol 
                ORDER BY count DESC
            """).fetchall()
            
            stats["wallets_by_blockchain"] = {}
            for blockchain, count in blockchain_results:
                stats["wallets_by_blockchain"][blockchain] = count
            
            # Total balance by blockchain
            balance_results = self.db_connection.execute("""
                SELECT blockchain_symbol, SUM(balance) as total_balance 
                FROM wallets 
                WHERE status = 'active'
                GROUP BY blockchain_symbol 
                ORDER BY total_balance DESC
            """).fetchall()
            
            stats["total_balance_by_blockchain"] = {}
            for blockchain, total_balance in balance_results:
                stats["total_balance_by_blockchain"][blockchain] = float(total_balance or 0)
            
            # Wallets by status
            status_results = self.db_connection.execute("""
                SELECT status, COUNT(*) as count 
                FROM wallets 
                GROUP BY status 
                ORDER BY count DESC
            """).fetchall()
            
            stats["wallets_by_status"] = {}
            for status, count in status_results:
                stats["wallets_by_status"][status] = count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting wallet statistics: {e}")
            raise
    
    async def get_low_balance_wallets(self, threshold: float = 0.01) -> List[Wallet]:
        """Get wallets with balance below threshold."""
        return await self.list(filters={"status": "active"})  # Will need custom query
    
    async def get_wallets_with_custom_filter(self, custom_query: str, params: List[Any]) -> List[Wallet]:
        """Execute custom query for wallets."""
        try:
            results = self.db_connection.execute(custom_query, params).fetchall()
            
            wallets = []
            if results:
                columns = [desc[0] for desc in self.db_connection.description]
                for row in results:
                    data = dict(zip(columns, row))
                    wallets.append(Wallet(**data))
            
            return wallets
            
        except Exception as e:
            logger.error(f"Error executing custom wallet query: {e}")
            raise
    
    async def bulk_update_status(self, wallet_ids: List[str], status: str) -> int:
        """Bulk update status for multiple wallets."""
        try:
            if not wallet_ids:
                return 0
            
            placeholders = ', '.join(['?' for _ in wallet_ids])
            query = f"UPDATE wallets SET status = ?, updated_at = ? WHERE id IN ({placeholders})"
            
            from datetime import datetime
            updated_at = datetime.now().isoformat()
            params = [status, updated_at] + wallet_ids
            
            self.db_connection.execute(query, params)
            
            # Sync updated wallets to JetStream
            for wallet_id in wallet_ids:
                try:
                    updated_wallet = await self.get_by_id(wallet_id)
                    if updated_wallet:
                        await self._sync_to_jetstream(wallet_id, updated_wallet)
                except Exception as sync_error:
                    logger.warning(f"JetStream sync failed for wallet {wallet_id}: {sync_error}")
            
            logger.info(f"Bulk updated status to '{status}' for {len(wallet_ids)} wallets")
            return len(wallet_ids)
            
        except Exception as e:
            logger.error(f"Error bulk updating wallet status: {e}")
            raise
