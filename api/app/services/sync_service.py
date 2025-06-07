"""Synchronization service for JetStream KV store operations."""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SyncService:
    """Service for managing synchronization between DuckDB and JetStream KV stores."""
    
    def __init__(self, jetstream_context: Any):
        self.js = jetstream_context
    
    async def sync_entity_to_kv(self, bucket: str, entity_id: str, entity_data: Dict[str, Any]) -> bool:
        """Sync a single entity to JetStream KV store."""
        try:
            kv = await self.js.key_value(bucket=bucket)
            json_data = json.dumps(entity_data, default=str)
            await kv.put(entity_id, json_data.encode('utf-8'))
            logger.debug(f"Synced entity {entity_id} to bucket {bucket}")
            return True
        except Exception as e:
            logger.error(f"Failed to sync entity {entity_id} to bucket {bucket}: {e}")
            return False
    
    async def delete_entity_from_kv(self, bucket: str, entity_id: str) -> bool:
        """Delete an entity from JetStream KV store."""
        try:
            kv = await self.js.key_value(bucket=bucket)
            await kv.delete(entity_id)
            logger.debug(f"Deleted entity {entity_id} from bucket {bucket}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete entity {entity_id} from bucket {bucket}: {e}")
            return False
    
    async def get_entity_from_kv(self, bucket: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get an entity from JetStream KV store."""
        try:
            kv = await self.js.key_value(bucket=bucket)
            data = await kv.get(entity_id)
            
            if data and data.value:
                if isinstance(data.value, bytes):
                    json_str = data.value.decode('utf-8')
                else:
                    json_str = data.value
                
                return json.loads(json_str)
            
            return None
        except Exception as e:
            logger.error(f"Failed to get entity {entity_id} from bucket {bucket}: {e}")
            return None
    
    async def list_entities_from_kv(self, bucket: str) -> List[Dict[str, Any]]:
        """List all entities from a JetStream KV store."""
        try:
            kv = await self.js.key_value(bucket=bucket)
            keys = await kv.keys()
            entities = []
            
            for key in keys:
                entity_data = await self.get_entity_from_kv(bucket, key)
                if entity_data:
                    entities.append(entity_data)
            
            return entities
        except Exception as e:
            logger.error(f"Failed to list entities from bucket {bucket}: {e}")
            return []
    
    async def bulk_sync_to_kv(self, bucket: str, entities: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """Bulk sync multiple entities to JetStream KV store."""
        results = {}
        
        for entity_id, entity_data in entities.items():
            success = await self.sync_entity_to_kv(bucket, entity_id, entity_data)
            results[entity_id] = success
        
        successful_syncs = sum(1 for success in results.values() if success)
        logger.info(f"Bulk sync to {bucket}: {successful_syncs}/{len(entities)} successful")
        
        return results
    
    async def verify_sync_integrity(self, bucket: str, db_entities: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Verify synchronization integrity between DuckDB and JetStream KV."""
        try:
            kv_entities = {}
            kv = await self.js.key_value(bucket=bucket)
            keys = await kv.keys()
            
            # Get all entities from KV store
            for key in keys:
                entity_data = await self.get_entity_from_kv(bucket, key)
                if entity_data:
                    kv_entities[key] = entity_data
            
            # Compare entities
            integrity_report = {
                "bucket": bucket,
                "timestamp": datetime.now().isoformat(),
                "db_count": len(db_entities),
                "kv_count": len(kv_entities),
                "missing_in_kv": [],
                "missing_in_db": [],
                "data_mismatches": [],
                "status": "unknown"
            }
            
            # Find entities missing in KV
            for entity_id in db_entities:
                if entity_id not in kv_entities:
                    integrity_report["missing_in_kv"].append(entity_id)
            
            # Find entities missing in DB
            for entity_id in kv_entities:
                if entity_id not in db_entities:
                    integrity_report["missing_in_db"].append(entity_id)
            
            # Check for data mismatches (simplified comparison)
            for entity_id in db_entities:
                if entity_id in kv_entities:
                    db_data = db_entities[entity_id]
                    kv_data = kv_entities[entity_id]
                    
                    # Compare key fields (excluding timestamps which might differ slightly)
                    key_fields = ["id", "name", "status", "type", "email"]
                    for field in key_fields:
                        if field in db_data and field in kv_data:
                            if str(db_data[field]) != str(kv_data[field]):
                                integrity_report["data_mismatches"].append({
                                    "entity_id": entity_id,
                                    "field": field,
                                    "db_value": db_data[field],
                                    "kv_value": kv_data[field]
                                })
            
            # Determine overall status
            if (integrity_report["missing_in_kv"] or 
                integrity_report["missing_in_db"] or 
                integrity_report["data_mismatches"]):
                integrity_report["status"] = "inconsistent"
            else:
                integrity_report["status"] = "consistent"
            
            logger.info(f"Sync integrity check for {bucket}: {integrity_report['status']}")
            return integrity_report
            
        except Exception as e:
            logger.error(f"Error verifying sync integrity for bucket {bucket}: {e}")
            return {
                "bucket": bucket,
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }
    
    async def repair_sync_inconsistencies(self, bucket: str, db_entities: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Repair synchronization inconsistencies by syncing DB data to KV."""
        try:
            integrity_report = await self.verify_sync_integrity(bucket, db_entities)
            
            if integrity_report["status"] == "consistent":
                logger.info(f"No sync repairs needed for bucket {bucket}")
                return {"status": "no_repairs_needed", "bucket": bucket}
            
            repair_results = {
                "bucket": bucket,
                "timestamp": datetime.now().isoformat(),
                "repairs_attempted": 0,
                "repairs_successful": 0,
                "repairs_failed": 0,
                "failed_entities": []
            }
            
            # Sync missing entities to KV
            for entity_id in integrity_report["missing_in_kv"]:
                if entity_id in db_entities:
                    repair_results["repairs_attempted"] += 1
                    success = await self.sync_entity_to_kv(bucket, entity_id, db_entities[entity_id])
                    if success:
                        repair_results["repairs_successful"] += 1
                    else:
                        repair_results["repairs_failed"] += 1
                        repair_results["failed_entities"].append(entity_id)
            
            # Fix data mismatches by overwriting KV with DB data
            for mismatch in integrity_report["data_mismatches"]:
                entity_id = mismatch["entity_id"]
                if entity_id in db_entities:
                    repair_results["repairs_attempted"] += 1
                    success = await self.sync_entity_to_kv(bucket, entity_id, db_entities[entity_id])
                    if success:
                        repair_results["repairs_successful"] += 1
                    else:
                        repair_results["repairs_failed"] += 1
                        if entity_id not in repair_results["failed_entities"]:
                            repair_results["failed_entities"].append(entity_id)
            
            # Remove entities from KV that don't exist in DB
            for entity_id in integrity_report["missing_in_db"]:
                repair_results["repairs_attempted"] += 1
                success = await self.delete_entity_from_kv(bucket, entity_id)
                if success:
                    repair_results["repairs_successful"] += 1
                else:
                    repair_results["repairs_failed"] += 1
                    repair_results["failed_entities"].append(entity_id)
            
            repair_results["status"] = "completed"
            logger.info(f"Sync repair for {bucket}: {repair_results['repairs_successful']}/{repair_results['repairs_attempted']} successful")
            
            return repair_results
            
        except Exception as e:
            logger.error(f"Error repairing sync inconsistencies for bucket {bucket}: {e}")
            return {
                "bucket": bucket,
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }
    
    async def get_kv_bucket_info(self, bucket: str) -> Dict[str, Any]:
        """Get information about a JetStream KV bucket."""
        try:
            kv = await self.js.key_value(bucket=bucket)
            keys = await kv.keys()
            
            return {
                "bucket": bucket,
                "key_count": len(keys),
                "keys": keys[:10],  # First 10 keys as sample
                "total_keys": len(keys)
            }
        except Exception as e:
            logger.error(f"Error getting KV bucket info for {bucket}: {e}")
            return {
                "bucket": bucket,
                "error": str(e)
            }
