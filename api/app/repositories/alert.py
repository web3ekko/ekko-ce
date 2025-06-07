"""Alert repository implementation."""

import json
import logging
from typing import Optional, Dict, Any, List
from ..models import Alert
from .base import BaseRepository

logger = logging.getLogger(__name__)


class AlertRepository(BaseRepository):
    """Repository for Alert entities with DuckDB storage and JetStream sync."""
    
    def __init__(self):
        super().__init__(
            model_class=Alert,
            table_name="alerts",
            jetstream_bucket="alerts"
        )
    
    async def _insert_to_db(self, entity: Alert):
        """Insert alert entity to database."""
        query = """
            INSERT INTO alerts (
                id, type, message, time, status, icon, priority,
                related_wallet_id, query, job_spec, notifications_enabled,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # Serialize job_spec if it's a dict
        job_spec_json = None
        if entity.job_spec:
            job_spec_json = json.dumps(entity.job_spec) if isinstance(entity.job_spec, dict) else entity.job_spec
        
        values = [
            entity.id,
            entity.type,
            entity.message,
            entity.time,
            entity.status,
            entity.icon,
            entity.priority,
            entity.related_wallet_id,
            entity.query,
            job_spec_json,
            entity.notifications_enabled,
            entity.created_at if hasattr(entity, 'created_at') else None,
            entity.updated_at if hasattr(entity, 'updated_at') else None
        ]
        
        self.db_connection.execute(query, values)
        logger.debug(f"Inserted alert {entity.id} into database")
    
    def _deserialize_json_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize JSON fields from database."""
        if data.get('job_spec') and isinstance(data['job_spec'], str):
            try:
                data['job_spec'] = json.loads(data['job_spec'])
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse job_spec JSON for alert {data.get('id')}")
                data['job_spec'] = None
        
        return data
    
    async def get_by_wallet_id(self, wallet_id: str) -> List[Alert]:
        """Get all alerts for a specific wallet."""
        return await self.list(filters={"related_wallet_id": wallet_id})
    
    async def get_by_status(self, status: str) -> List[Alert]:
        """Get all alerts with a specific status."""
        return await self.list(filters={"status": status})
    
    async def get_by_type(self, alert_type: str) -> List[Alert]:
        """Get all alerts of a specific type."""
        return await self.list(filters={"type": alert_type})
    
    async def get_by_priority(self, priority: str) -> List[Alert]:
        """Get all alerts with a specific priority."""
        return await self.list(filters={"priority": priority})
    
    async def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return await self.list(filters={"status": "active"})
    
    async def get_pending_alerts(self) -> List[Alert]:
        """Get all pending alerts."""
        return await self.list(filters={"status": "pending"})
    
    async def update_status(self, alert_id: str, status: str) -> Optional[Alert]:
        """Update alert status."""
        return await self.update(alert_id, {"status": status})
    
    async def update_job_spec(self, alert_id: str, job_spec: Dict[str, Any]) -> Optional[Alert]:
        """Update alert job specification."""
        return await self.update(alert_id, {"job_spec": job_spec})
    
    async def search_alerts(self, search_term: str, limit: Optional[int] = None) -> List[Alert]:
        """Search alerts by message or type."""
        try:
            query = """
                SELECT * FROM alerts 
                WHERE message ILIKE ? OR type ILIKE ?
                ORDER BY created_at DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            search_pattern = f"%{search_term}%"
            results = self.db_connection.execute(query, [search_pattern, search_pattern]).fetchall()
            
            # Convert results to Alert models
            alerts = []
            if results:
                columns = [desc[0] for desc in self.db_connection.description]
                for row in results:
                    data = dict(zip(columns, row))
                    data = self._deserialize_json_fields(data)
                    alerts.append(Alert(**data))
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error searching alerts with term '{search_term}': {e}")
            raise
    
    async def get_alerts_by_time_range(self, start_time: str, end_time: str) -> List[Alert]:
        """Get alerts within a specific time range."""
        try:
            query = """
                SELECT * FROM alerts 
                WHERE time >= ? AND time <= ?
                ORDER BY time DESC
            """
            
            results = self.db_connection.execute(query, [start_time, end_time]).fetchall()
            
            alerts = []
            if results:
                columns = [desc[0] for desc in self.db_connection.description]
                for row in results:
                    data = dict(zip(columns, row))
                    data = self._deserialize_json_fields(data)
                    alerts.append(Alert(**data))
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting alerts by time range {start_time} to {end_time}: {e}")
            raise
    
    async def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        try:
            stats = {}
            
            # Total alerts
            total_result = self.db_connection.execute("SELECT COUNT(*) FROM alerts").fetchone()
            stats["total_alerts"] = total_result[0]
            
            # Alerts by status
            status_results = self.db_connection.execute("""
                SELECT status, COUNT(*) as count 
                FROM alerts 
                GROUP BY status 
                ORDER BY count DESC
            """).fetchall()
            
            stats["alerts_by_status"] = {}
            for status, count in status_results:
                stats["alerts_by_status"][status] = count
            
            # Alerts by type
            type_results = self.db_connection.execute("""
                SELECT type, COUNT(*) as count 
                FROM alerts 
                GROUP BY type 
                ORDER BY count DESC
            """).fetchall()
            
            stats["alerts_by_type"] = {}
            for alert_type, count in type_results:
                stats["alerts_by_type"][alert_type] = count
            
            # Alerts by priority
            priority_results = self.db_connection.execute("""
                SELECT priority, COUNT(*) as count 
                FROM alerts 
                WHERE priority IS NOT NULL
                GROUP BY priority 
                ORDER BY count DESC
            """).fetchall()
            
            stats["alerts_by_priority"] = {}
            for priority, count in priority_results:
                stats["alerts_by_priority"][priority] = count
            
            # Recent alerts (last 24 hours)
            recent_result = self.db_connection.execute("""
                SELECT COUNT(*) FROM alerts 
                WHERE created_at >= datetime('now', '-1 day')
            """).fetchone()
            stats["recent_alerts"] = recent_result[0]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting alert statistics: {e}")
            raise
    
    async def bulk_update_status(self, alert_ids: List[str], status: str) -> int:
        """Bulk update status for multiple alerts."""
        try:
            if not alert_ids:
                return 0
            
            placeholders = ', '.join(['?' for _ in alert_ids])
            query = f"UPDATE alerts SET status = ?, updated_at = ? WHERE id IN ({placeholders})"
            
            from datetime import datetime
            updated_at = datetime.now().isoformat()
            params = [status, updated_at] + alert_ids
            
            self.db_connection.execute(query, params)
            
            # Sync updated alerts to JetStream
            for alert_id in alert_ids:
                try:
                    updated_alert = await self.get_by_id(alert_id)
                    if updated_alert:
                        await self._sync_to_jetstream(alert_id, updated_alert)
                except Exception as sync_error:
                    logger.warning(f"JetStream sync failed for alert {alert_id}: {sync_error}")
            
            logger.info(f"Bulk updated status to '{status}' for {len(alert_ids)} alerts")
            return len(alert_ids)
            
        except Exception as e:
            logger.error(f"Error bulk updating alert status: {e}")
            raise
    
    async def get_alerts_with_notifications_enabled(self) -> List[Alert]:
        """Get all alerts with notifications enabled."""
        return await self.list(filters={"notifications_enabled": True})
    
    async def get_alerts_by_wallet_and_status(self, wallet_id: str, status: str) -> List[Alert]:
        """Get alerts for a specific wallet with a specific status."""
        return await self.list(filters={
            "related_wallet_id": wallet_id,
            "status": status
        })
    
    async def delete_old_alerts(self, days_old: int = 30) -> int:
        """Delete alerts older than specified days."""
        try:
            query = """
                DELETE FROM alerts 
                WHERE created_at < datetime('now', '-{} days')
            """.format(days_old)
            
            # Get count before deletion
            count_query = """
                SELECT COUNT(*) FROM alerts 
                WHERE created_at < datetime('now', '-{} days')
            """.format(days_old)
            
            count_result = self.db_connection.execute(count_query).fetchone()
            deleted_count = count_result[0]
            
            if deleted_count > 0:
                self.db_connection.execute(query)
                logger.info(f"Deleted {deleted_count} old alerts (older than {days_old} days)")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting old alerts: {e}")
            raise
