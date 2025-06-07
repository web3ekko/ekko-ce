"""Base repository with DuckDB + JetStream synchronization."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Type, TypeVar
from datetime import datetime
from pydantic import BaseModel

from ..database.connection import get_db_connection
from ..events import publish_event

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class BaseRepository(ABC):
    """Base repository class with DuckDB primary storage and JetStream sync."""
    
    def __init__(self, model_class: Type[T], table_name: str, jetstream_bucket: str):
        self.model_class = model_class
        self.table_name = table_name
        self.jetstream_bucket = jetstream_bucket
        self.db_connection = get_db_connection()
        self._js = None  # Will be set by dependency injection
    
    def set_jetstream(self, js):
        """Set the JetStream context for synchronization."""
        self._js = js
    
    async def create(self, entity: T) -> T:
        """Create a new entity in DuckDB and sync to JetStream."""
        try:
            # Ensure entity has an ID
            if not hasattr(entity, 'id') or not entity.id:
                import uuid
                entity.id = str(uuid.uuid4())
            
            # Set timestamps
            now = datetime.now().isoformat()
            if hasattr(entity, 'created_at') and not entity.created_at:
                entity.created_at = now
            if hasattr(entity, 'updated_at'):
                entity.updated_at = now
            
            # Insert into DuckDB
            await self._insert_to_db(entity)
            
            # Sync to JetStream KV (async, non-blocking)
            try:
                await self._sync_to_jetstream(entity.id, entity)
            except Exception as sync_error:
                logger.warning(f"JetStream sync failed for {self.table_name}:{entity.id}: {sync_error}")
            
            # Publish event
            try:
                await publish_event(f"{self.table_name}.created", {
                    "id": entity.id,
                    "table": self.table_name
                }, ignore_errors=True)
            except Exception as event_error:
                logger.warning(f"Event publishing failed for {self.table_name}.created: {event_error}")
            
            logger.info(f"Created {self.table_name} entity: {entity.id}")
            return entity
            
        except Exception as e:
            logger.error(f"Error creating {self.table_name} entity: {e}")
            raise
    
    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """Get entity by ID from DuckDB."""
        try:
            query = f"SELECT * FROM {self.table_name} WHERE id = ?"
            result = self.db_connection.execute(query, [entity_id]).fetchone()
            
            if result:
                # Convert row to dictionary
                columns = [desc[0] for desc in self.db_connection.description]
                data = dict(zip(columns, result))
                
                # Handle JSON fields
                data = self._deserialize_json_fields(data)
                
                return self.model_class(**data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting {self.table_name} by ID {entity_id}: {e}")
            raise
    
    async def update(self, entity_id: str, updates: Dict[str, Any]) -> Optional[T]:
        """Update entity in DuckDB and sync to JetStream."""
        try:
            # Add updated timestamp
            updates['updated_at'] = datetime.now().isoformat()
            
            # Build update query
            set_clauses = []
            values = []
            for key, value in updates.items():
                set_clauses.append(f"{key} = ?")
                # Serialize JSON fields
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                values.append(value)
            
            values.append(entity_id)  # For WHERE clause
            
            query = f"UPDATE {self.table_name} SET {', '.join(set_clauses)} WHERE id = ?"
            self.db_connection.execute(query, values)
            
            # Get updated entity
            updated_entity = await self.get_by_id(entity_id)
            
            if updated_entity:
                # Sync to JetStream KV
                try:
                    await self._sync_to_jetstream(entity_id, updated_entity)
                except Exception as sync_error:
                    logger.warning(f"JetStream sync failed for {self.table_name}:{entity_id}: {sync_error}")
                
                # Publish event
                try:
                    await publish_event(f"{self.table_name}.updated", {
                        "id": entity_id,
                        "table": self.table_name,
                        "updates": list(updates.keys())
                    }, ignore_errors=True)
                except Exception as event_error:
                    logger.warning(f"Event publishing failed for {self.table_name}.updated: {event_error}")
                
                logger.info(f"Updated {self.table_name} entity: {entity_id}")
            
            return updated_entity
            
        except Exception as e:
            logger.error(f"Error updating {self.table_name} entity {entity_id}: {e}")
            raise
    
    async def delete(self, entity_id: str) -> bool:
        """Delete entity from DuckDB and JetStream."""
        try:
            # Check if entity exists
            entity = await self.get_by_id(entity_id)
            if not entity:
                return False
            
            # Delete from DuckDB
            query = f"DELETE FROM {self.table_name} WHERE id = ?"
            self.db_connection.execute(query, [entity_id])
            
            # Delete from JetStream KV
            try:
                await self._delete_from_jetstream(entity_id)
            except Exception as sync_error:
                logger.warning(f"JetStream deletion failed for {self.table_name}:{entity_id}: {sync_error}")
            
            # Publish event
            try:
                await publish_event(f"{self.table_name}.deleted", {
                    "id": entity_id,
                    "table": self.table_name
                }, ignore_errors=True)
            except Exception as event_error:
                logger.warning(f"Event publishing failed for {self.table_name}.deleted: {event_error}")
            
            logger.info(f"Deleted {self.table_name} entity: {entity_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting {self.table_name} entity {entity_id}: {e}")
            raise
    
    async def list(self, filters: Optional[Dict[str, Any]] = None, 
                   limit: Optional[int] = None, 
                   offset: Optional[int] = None,
                   order_by: Optional[str] = None) -> List[T]:
        """List entities with optional filtering, pagination, and ordering."""
        try:
            query = f"SELECT * FROM {self.table_name}"
            values = []
            
            # Add WHERE clause for filters
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if isinstance(value, list):
                        placeholders = ', '.join(['?' for _ in value])
                        where_clauses.append(f"{key} IN ({placeholders})")
                        values.extend(value)
                    else:
                        where_clauses.append(f"{key} = ?")
                        values.append(value)
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
            
            # Add ORDER BY clause
            if order_by:
                query += f" ORDER BY {order_by}"
            else:
                query += " ORDER BY created_at DESC"
            
            # Add LIMIT and OFFSET
            if limit:
                query += f" LIMIT {limit}"
            if offset:
                query += f" OFFSET {offset}"
            
            results = self.db_connection.execute(query, values).fetchall()
            
            # Convert results to model instances
            entities = []
            if results:
                columns = [desc[0] for desc in self.db_connection.description]
                for row in results:
                    data = dict(zip(columns, row))
                    data = self._deserialize_json_fields(data)
                    entities.append(self.model_class(**data))
            
            return entities
            
        except Exception as e:
            logger.error(f"Error listing {self.table_name} entities: {e}")
            raise
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities with optional filtering."""
        try:
            query = f"SELECT COUNT(*) FROM {self.table_name}"
            values = []
            
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if isinstance(value, list):
                        placeholders = ', '.join(['?' for _ in value])
                        where_clauses.append(f"{key} IN ({placeholders})")
                        values.extend(value)
                    else:
                        where_clauses.append(f"{key} = ?")
                        values.append(value)
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
            
            result = self.db_connection.execute(query, values).fetchone()
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"Error counting {self.table_name} entities: {e}")
            raise
    
    @abstractmethod
    async def _insert_to_db(self, entity: T):
        """Insert entity to database. Must be implemented by subclasses."""
        pass
    
    def _serialize_json_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize JSON fields for database storage."""
        # Override in subclasses if needed
        return data
    
    def _deserialize_json_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize JSON fields from database."""
        # Override in subclasses if needed
        return data
    
    async def _sync_to_jetstream(self, entity_id: str, entity: T):
        """Sync entity to JetStream KV store."""
        if not self._js:
            logger.warning("JetStream context not available for sync")
            return
        
        try:
            kv = await self._js.key_value(bucket=self.jetstream_bucket)
            entity_data = entity.model_dump() if hasattr(entity, 'model_dump') else entity.dict()
            json_data = json.dumps(entity_data, default=str)
            await kv.put(entity_id, json_data.encode('utf-8'))
            logger.debug(f"Synced {self.table_name}:{entity_id} to JetStream")
        except Exception as e:
            logger.error(f"Failed to sync {self.table_name}:{entity_id} to JetStream: {e}")
            raise
    
    async def _delete_from_jetstream(self, entity_id: str):
        """Delete entity from JetStream KV store."""
        if not self._js:
            logger.warning("JetStream context not available for deletion")
            return
        
        try:
            kv = await self._js.key_value(bucket=self.jetstream_bucket)
            await kv.delete(entity_id)
            logger.debug(f"Deleted {self.table_name}:{entity_id} from JetStream")
        except Exception as e:
            logger.error(f"Failed to delete {self.table_name}:{entity_id} from JetStream: {e}")
            raise
