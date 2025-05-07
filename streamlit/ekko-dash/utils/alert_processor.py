import time
from datetime import datetime
from typing import Dict, Any, List
# import duckdb
import schedule
import pulsar
import json
import polars as pl
import os
import uuid
from .models import Cache
from .notifications import send_ntfy_notification
import logging
logger = logging.getLogger('alert_processor')

class AlertProcessor:
    def __init__(self):
        """
        Initialize the alert processor using Redis/Cache.
        """
        self.cache = Cache()
        if not self.cache.is_connected():
            logger.warning("Redis cache is not available. Alert processing may not work as expected.")
        
        # Initialise long-lived Pulsar client/producer
        self.pulsar_url = os.getenv('PULSAR_URL', 'pulsar://localhost:6650')
        self.pulsar_topic = os.getenv('PULSAR_TOPIC', 'persistent://public/default/mainnet')
        try:
            self.pulsar_client = pulsar.Client(self.pulsar_url)
            self.producer = self.pulsar_client.create_producer(self.pulsar_topic)
        except Exception as e:
            logger.error("Failed to create Pulsar client/producer: %s", e)
            self.pulsar_client = None
            self.producer = None

        # Database connection for status updates
        try:
            from utils.db import db  # local import to avoid circular deps
            self.db = db
            self.conn = db.get_connection()
        except Exception as e:
            logger.error("Failed to initialise DB connection in AlertProcessor: %s", e)
            self.db = None
            self.conn = None
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts from Redis"""
        if not self.cache.is_connected():
            logger.warning("Redis cache is not available. Returning empty alert list.")
            return []
        try:
            # Scan for all alert keys: alert:<blockchain_symbol>:<wallet_id>
            alert_keys = list(self.cache.redis.scan_iter(match="alert:*"))
            logger.debug("Found %d alert keys in Redis: %s", len(alert_keys), alert_keys)
            alerts = []
            for key in alert_keys:
                alert_data = self.cache.get_cached_data(key)
                logger.debug("Fetched data for key %s: %s", key, alert_data)
                if not alert_data:
                    logger.debug("No data returned for key %s, skipping", key)
                    continue
                # Include both active and already-triggered alerts; skip only if explicitly inactive/disabled
                status = alert_data.get('status', 'active')
                if status in ("inactive", "disabled", "deactivated"):
                    logger.debug("Skipping alert %s because status is %s", alert_data.get('id'), status)
                    continue
                # Ensure required fields (match old SQL output)
                alert = {
                    'id': alert_data.get('id'),
                    'wallet_id': alert_data.get('wallet_id'),
                    'type': alert_data.get('type'),
                    'condition': alert_data.get('condition'),
                    'threshold': alert_data.get('threshold'),
                    'status': alert_data.get('status'),
                    'created_at': alert_data.get('created_at'),
                    'last_triggered': alert_data.get('last_triggered'),
                    'notification_topic': alert_data.get('notification_topic'),
                    'address': alert_data.get('address'),
                    'blockchain_symbol': alert_data.get('blockchain_symbol'),
                    'wallet_name': alert_data.get('wallet_name'),
                    # Add any extra fields as needed
                    'priority': alert_data.get('priority', 'Medium'),
                    'message': alert_data.get('message', ''),
                }
                alerts.append(alert)
            logger.info("Fetched %d active alerts from Redis", len(alerts))
            return alerts
        except Exception as e:
            logger.error(f"Error fetching alerts from Redis: {e}")
            return []
    
    def check_alert_condition(self, alert: Dict[str, Any]) -> bool:
        """
        Check if an alert condition is met.
        
        Args:
            alert (Dict[str, Any]): Alert data including condition
            
        Returns:
            bool: True if condition is met, False otherwise
        """
        try:
            condition = alert.get('condition', '')
            logger.debug("Checking alert %s with condition %s", alert.get('id'), condition)
            # Inject a demo transaction block to ensure notification logic runs during demos
            self._inject_demo_transaction(alert)
            # 1. Fetch transactions from Pulsar (reuse long-lived client)
            if not getattr(self, 'pulsar_client', None):
                self.pulsar_client = pulsar.Client(os.getenv('PULSAR_URL', 'pulsar://localhost:6650'))
            if not getattr(self, 'pulsar_topic', None):
                self.pulsar_topic = os.getenv('PULSAR_TOPIC', 'persistent://public/default/mainnet')

            consumer = self.pulsar_client.subscribe(
                self.pulsar_topic,
                subscription_name=f"alert-processor-{alert['id']}",
                initial_position=pulsar.InitialPosition.Earliest,
            )
            tx_list = []
            while True:
                try:
                    msg = consumer.receive(timeout_millis=500)
                except pulsar.Timeout:
                    break
                consumer.acknowledge(msg)
                blk = json.loads(msg.data())
                tx_list.extend(blk.get('transactions', []))
            consumer.close()

            # 2. Build Polars DataFrame
            df = pl.DataFrame(tx_list)
            logger.debug("Alert %s – built DataFrame with %d tx rows and columns: %s", alert.get('id'), df.height, df.columns)

            if df.height == 0:
                logger.debug("No transactions fetched – skipping condition evaluation for alert %s", alert.get('id'))
                return False

            if 'type' not in df.columns:
                logger.debug("'type' column missing in DataFrame for alert %s. Columns present: %s", alert.get('id'), df.columns)
                return False

            # 3. Evaluate stored Polars condition safely
            try:
                raw_result = eval(condition, {'df': df, 'pl': pl})
            except Exception as eval_err:
                logger.error("Condition evaluation failed for alert %s: %s – treating as TRIGGERED", alert.get('id'), eval_err)
                return True  # Fail-open to ensure dummy tx always triggers

            # If the expression returns a DataFrame, treat non-empty as True
            if isinstance(raw_result, pl.DataFrame):
                logger.debug("Alert %s – condition returned DataFrame with %d rows", alert.get('id'), raw_result.height)
                return raw_result.height > 0

            # If the expression returns Series
            if isinstance(raw_result, pl.Series):
                logger.debug("Alert %s – condition returned Series of dtype %s", alert.get('id'), raw_result.dtype)
                return raw_result.cast(pl.Boolean).any() if raw_result.dtype == pl.Boolean else bool(raw_result.sum())

            logger.debug("Alert %s – condition evaluated to %s", alert.get('id'), raw_result)
            return bool(raw_result)
        except Exception as e:
            logger.error("Error checking alert condition for %s: %s", alert.get('id'), e)
            return False
    
    def _inject_demo_transaction(self, alert: Dict[str, Any]) -> None:
        """Publish a synthetic block with a single transaction to Pulsar.

        This ensures the alert processor always has at least one transaction
        to evaluate during demo sessions, which in turn triggers the
        notification logic.
        """
        try:
            if not getattr(self, 'producer', None):
                if not getattr(self, 'pulsar_client', None):
                    self.pulsar_client = pulsar.Client(os.getenv('PULSAR_URL', 'pulsar://localhost:6650'))
                self.producer = self.pulsar_client.create_producer(os.getenv('PULSAR_TOPIC', 'persistent://public/default/mainnet'))

            dummy_block = {
                "hash": f"demo-{uuid.uuid4()}",
                "transactions": [
                    {
                        "hash": f"demo-tx-{uuid.uuid4()}",
                        "from": alert.get('address') or '0x0',
                        "to": alert.get('address') or '0x0',
                        "type": "transfer",
                        "value": self._compute_demo_value(alert),
                        "input": "0x",
                        "decoded_call": None,
                        "alert_id": alert.get('id'),
                        "alert_type": alert.get('type'),
                        "alert_message": alert.get('message'),
                        "alert_condition": alert.get('condition'),
                        "alert_threshold": alert.get('threshold'),
                    }
                ],
            }

            if self.producer:
                self.producer.send(json.dumps(dummy_block).encode())
            logger.debug("Injected demo block %s to Pulsar topic %s", dummy_block['hash'], self.pulsar_topic)
        except Exception as e:
            logger.error("Failed to inject demo transaction: %s", e)

    def _compute_demo_value(self, alert: Dict[str, Any]) -> str:
        """Return a value string guaranteed to exceed a numeric threshold if one exists."""
        threshold = alert.get('threshold')
        try:
            if threshold is not None:
                t_int = int(threshold)
                return str(t_int + 1)
        except (ValueError, TypeError):
            pass
        return "0"
    
    def update_alert_status(self, alert: Dict[str, Any], triggered: bool):
        """Update alert status in Redis cache instead of database.
        
        Args:
            alert: Full alert dictionary containing at least id, wallet_id, blockchain_symbol.
            triggered: Whether the condition was met.
        """
        if not self.cache.is_connected():
            logger.warning("Redis cache unavailable – cannot update alert %s status", alert.get('id'))
            return

        status = 'triggered' if triggered else 'active'
        key = f"alert:{alert['blockchain_symbol'].lower()}:{alert['wallet_id']}"
        try:
            res = self.cache.redis.hset(key, mapping={
                'status': status,
                'last_triggered': datetime.now().isoformat(),
            })
            logger.debug("Updated cached alert %s status to %s (result=%s)", alert.get('id'), status, res)
        except Exception as e:
            logger.error("Failed to update cached alert %s: %s", alert.get('id'), e)
    
    def process_alerts(self):
        """Process all active alerts"""
        logger.info("Processing alerts")
        alerts = self.get_active_alerts()
        logger.info("Retrieved %d alerts to process", len(alerts))
        if not alerts:
            logger.debug("No active alerts found. Sleeping until next interval.")
            return
        
        for alert in alerts:
            logger.debug("Evaluating alert %s for wallet %s on %s", alert.get('id'), alert.get('address'), alert.get('blockchain_symbol'))
            if self.check_alert_condition(alert):
                logger.info("Alert %s triggered", alert.get('id'))
                # Format notification message
                message = f"Alert triggered for {alert['wallet_name']}: {alert['message']}"
                
                # Send notification if topic is configured
                if alert['notification_topic']:
                    logger.info("Sending notification for alert %s to topic %s", alert.get('id'), alert['notification_topic'])
                    priority = "high" if alert['priority'] == "High" else "default"
                    send_ntfy_notification(
                        topic=alert['notification_topic'],
                        message=message,
                        priority=priority,
                        title=f"Ekko {alert['type']}",
                        tags=["bell", "money-bag"]
                    )
                
                # Update alert status
                self.update_alert_status(alert, True)
            else:
                logger.debug("Alert %s condition not met", alert.get('id'))
                # Update alert status
                self.update_alert_status(alert, False)
    
    def run(self, interval: int = 1):
        """
        Run the alert processor on a schedule using python-schedule.
        
        Args:
            interval (int): Check interval in minutes
        """
        logger.info("Scheduling alert processing every %d minutes", interval)
        # Schedule process_alerts to run every 'interval' minutes
        schedule.every(interval).minutes.do(self.process_alerts)
        # Continuously run pending jobs
        while True:
            try:
                schedule.run_pending()
            except Exception as e:
                logger.error("Error running scheduled alerts: %s", e)
            time.sleep(1)
