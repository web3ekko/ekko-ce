import json
import redis
from typing import Dict, Any
import duckdb

class AlertProcessor:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    def _get_alert_rules(self, blockchain_symbol: str) -> list:
        """Get all alert rules for a specific blockchain from Redis"""
        rules = []
        pattern = f"alert:{blockchain_symbol.lower()}:*"
        
        # Get all alert keys for this blockchain
        alert_keys = self.redis.keys(pattern)
        
        for key in alert_keys:
            alert_data = self.redis.hgetall(key)
            if alert_data and alert_data.get('status') == 'active':
                rules.append(alert_data)
                
        return rules

    def process_transaction(self, transaction: Dict[str, Any]) -> None:
        """Process a transaction against active alert rules"""
        # Extract blockchain symbol from transaction
        blockchain_symbol = transaction.get('blockchain_symbol')
        if not blockchain_symbol:
            return
            
        # Get alert rules for this blockchain
        rules = self._get_alert_rules(blockchain_symbol)
        
        for rule in rules:
            # Check if transaction matches alert conditions
            if self._matches_conditions(transaction, rule):
                # Create notification
                notification = {
                    "alert_id": rule["id"],
                    "blockchain_symbol": blockchain_symbol,
                    "wallet_id": rule["wallet_id"],
                    "transaction_hash": transaction["hash"],
                    "timestamp": transaction["timestamp"],
                    "details": json.dumps({
                        "from": transaction["from"],
                        "to": transaction["to"],
                        "value": transaction["value"],
                        "gas": transaction["gas"]
                    })
                }
                
                # Push to Redis notification streams
                self.redis.xadd(
                    f"notifications:{blockchain_symbol.lower()}:{rule['wallet_id']}",
                    notification
                )
                
                # Also push to a general notification stream for aggregation
                self.redis.xadd(
                    "notifications:all",
                    notification
                )

    def _matches_conditions(self, tx: Dict[str, Any], alert: Dict[str, str]) -> bool:
        """Check if transaction matches alert conditions"""
        conditions = json.loads(alert["conditions"])
        
        for condition in conditions:
            field = condition["field"]
            operator = condition["operator"]
            value = condition["value"]
            
            if field not in tx:
                continue
                
            tx_value = tx[field]
            
            if operator == "equals":
                if str(tx_value).lower() != str(value).lower():
                    return False
            elif operator == "contains":
                if str(value).lower() not in str(tx_value).lower():
                    return False
            elif operator == "greater_than":
                if float(tx_value) <= float(value):
                    return False
            elif operator == "less_than":
                if float(tx_value) >= float(value):
                    return False
                    
        return True
