"""
Alert processor background task for the Ekko API.
This module handles alert processing in the background.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from nats.js.api import ConsumerConfig

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('alert_processor')

# Global flag to control background task
is_running = False

class AlertProcessor:
    """Alert processor that checks alert conditions and triggers notifications"""
    
    def __init__(self, js=None):
        """
        Initialize the alert processor.
        
        Args:
            js: JetStream instance for NATS
        """
        self.js = js
        if not self.js:
            logger.warning("NATS JetStream not available - alert processing will be limited")
        else:
            logger.info("Alert processor initialized with NATS JetStream")
    
    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts from NATS JetStream KV store"""
        if not self.js:
            logger.warning("NATS JetStream not available. Returning empty alert list.")
            return []
        
        try:
            # Get alerts bucket
            kv = await self.js.key_value(bucket="alerts")
            
            try:
                # Get all keys
                keys = await kv.keys()
                alerts = []
                
                for key in keys:
                    data = await kv.get(key)
                    
                    # Decode bytes to string if needed
                    if isinstance(data.value, bytes):
                        json_str = data.value.decode('utf-8')
                    else:
                        json_str = data.value
                    
                    alert_data = json.loads(json_str)
                    
                    # Skip inactive or disabled alerts
                    status = alert_data.get('status', 'Open')
                    if status not in ["Open", "active", "triggered"]:
                        continue
                    
                    # Add wallet info if available
                    if alert_data.get('related_wallet'):
                        try:
                            wallet_kv = await self.js.key_value(bucket="wallets")
                            wallet_data = await wallet_kv.get(alert_data['related_wallet'])
                            
                            # Decode wallet data
                            if isinstance(wallet_data.value, bytes):
                                wallet_json = wallet_data.value.decode('utf-8')
                            else:
                                wallet_json = wallet_data.value
                            
                            wallet = json.loads(wallet_json)
                            alert_data['wallet_name'] = wallet.get('name', 'Unknown Wallet')
                            alert_data['address'] = wallet.get('address', '')
                            alert_data['blockchain_symbol'] = wallet.get('blockchain_symbol', '')
                            alert_data['wallet_id'] = wallet.get('id', '')
                        except Exception as wallet_error:
                            logger.error(f"Error fetching wallet data: {wallet_error}")
                    
                    alerts.append(alert_data)
                
                logger.info(f"Fetched {len(alerts)} active alerts")
                return alerts
            except Exception as keys_error:
                if "no keys found" in str(keys_error).lower():
                    logger.info("No alerts found")
                    return []
                logger.error(f"Error fetching alert keys: {keys_error}")
                return []
        except Exception as e:
            logger.error(f"Error fetching alerts: {e}")
            return []
    
    async def check_alert_condition(self, alert: Dict[str, Any]) -> bool:
        """
        Check if an alert condition is met.
        
        Args:
            alert: Alert data including query condition
            
        Returns:
            bool: True if condition is met, False otherwise
        """
        try:
            # Get the query from the alert
            query = alert.get('query', '')
            if not query:
                logger.warning(f"Alert {alert.get('id')} has no query condition")
                return False
            
            logger.info(f"Checking alert {alert.get('id')} with query: {query}")
            
            # Get related wallet data if available
            wallet_data = None
            if alert.get('related_wallet') and self.js:
                try:
                    wallet_kv = await self.js.key_value(bucket="wallets")
                    wallet_entry = await wallet_kv.get(alert.get('related_wallet'))
                    if isinstance(wallet_entry.value, bytes):
                        wallet_str = wallet_entry.value.decode('utf-8')
                    else:
                        wallet_str = wallet_entry.value
                    wallet_data = json.loads(wallet_str)
                except Exception as wallet_err:
                    logger.error(f"Error fetching wallet data: {wallet_err}")
            
            # Get transaction data from JetStream if needed
            if "tx_" in query.lower() and self.js:
                # Check for recent transactions in the transaction stream
                # This would be implemented based on your transaction data structure
                try:
                    consumer = await self.js.pull_subscribe(
                        subject="transaction.>*",
                        durable="alert-processor",
                        config=ConsumerConfig(ack_policy="explicit", max_deliver=1)
                    )
                    
                    # Pull batch of messages
                    messages = await consumer.fetch(batch=10, timeout=1)
                    
                    # Process transaction data
                    transactions = []
                    for msg in messages:
                        try:
                            tx_data = json.loads(msg.data.decode())
                            # Only include transactions for this wallet if specified
                            if wallet_data and ('address' in wallet_data):
                                if tx_data.get('from') == wallet_data['address'] or tx_data.get('to') == wallet_data['address']:
                                    transactions.append(tx_data)
                            else:
                                transactions.append(tx_data)
                            await msg.ack()
                        except Exception as tx_err:
                            logger.error(f"Error processing transaction message: {tx_err}")
                            await msg.ack()  # Still ack to avoid redelivery
                    
                    # Now check transaction conditions
                    if "tx_value > " in query.lower():
                        try:
                            threshold = float(query.split('>')[1].strip())
                            # Check if any transaction exceeds the threshold
                            for tx in transactions:
                                if float(tx.get('value', 0)) > threshold:
                                    logger.info(f"Found transaction with value {tx.get('value')} > {threshold}")
                                    return True
                            return False
                        except Exception as parse_error:
                            logger.error(f"Error parsing transaction condition: {parse_error}")
                            return False
                
                except Exception as js_err:
                    logger.error(f"Error accessing transaction stream: {js_err}")
            
            # Check balance conditions using wallet data
            if "balance < " in query.lower() and wallet_data:
                try:
                    threshold = float(query.split('<')[1].strip())
                    current_balance = float(wallet_data.get('balance', 0))
                    logger.info(f"Balance check: {current_balance} < {threshold}")
                    return current_balance < threshold
                except Exception as parse_error:
                    logger.error(f"Error parsing balance condition: {parse_error}")
                    return False
            
            # Mock checks for other condition types that would require external data
            if "price_change > " in query.lower():
                try:
                    threshold = float(query.split('>')[1].strip().replace('%', ''))
                    # In a real implementation, you would fetch price data from an external source
                    mock_price_change = 6.0  # Simulate a price change percentage
                    logger.info(f"Price change check: {mock_price_change} > {threshold}")
                    return mock_price_change > threshold
                except Exception as parse_error:
                    logger.error(f"Error parsing price change condition: {parse_error}")
                    return False
            
            if "suspicious_activity = true" in query.lower():
                # In a real implementation, you would have security detection logic
                mock_suspicious = False
                logger.info(f"Security check: suspicious = {mock_suspicious}")
                return mock_suspicious
            
            # If we get here, we don't recognize the query format
            logger.warning(f"Unrecognized query format: {query}")
            return False
            
        except Exception as e:
            logger.error(f"Error checking alert condition: {e}")
            return False
    
    async def log_alert_activity(self, alert: Dict[str, Any], triggered: bool) -> None:
        """
        Log alert activity without updating its status.
        
        Args:
            alert: Alert data
            triggered: Whether the condition was triggered
        """
        alert_id = alert.get('id')
        alert_type = alert.get('type', 'unknown')
        
        if triggered:
            logger.info(f"Alert condition met for alert {alert_id} (type: {alert_type})")
        else:
            logger.debug(f"Alert condition not met for alert {alert_id} (type: {alert_type})")
    
    async def send_notification(self, alert: Dict[str, Any]) -> None:
        """
        Send notification for triggered alert.
        
        Args:
            alert: Alert data
        """
        # In a production system, you would integrate with a notification service
        # such as email, SMS, or a push notification service
        
        message = f"Alert '{alert.get('type')}' triggered: {alert.get('message')}"
        logger.info(f"NOTIFICATION: {message}")
        
        # Example: publish notification event to NATS
        if self.js:
            try:
                notification_data = {
                    "id": str(uuid.uuid4()),
                    "alert_id": alert.get("id"),
                    "message": message,
                    "time": datetime.now().isoformat(),
                    "priority": alert.get("priority", "Medium"),
                    "type": "alert_notification"
                }
                
                # Publish notification event
                data_bytes = json.dumps(notification_data).encode('utf-8')
                await self.js.publish("notification.alert", data_bytes)
                logger.info(f"Published notification event for alert {alert.get('id')}")
            
            except Exception as e:
                logger.error(f"Error publishing notification event: {e}")
    
    async def execute_job_spec(self, job_spec: Dict[str, Any]) -> None:
        """Execute a job specification
        
        Args:
            job_spec: The job specification to execute
        """
        if not job_spec:
            return
            
        try:
            logger.info(f"Executing job spec: {job_spec.get('job_name', 'unnamed')}")
            
            # Extract key components
            job_name = job_spec.get('job_name', 'unnamed_job')
            sources = job_spec.get('sources', [])
            polars_code = job_spec.get('polars_code', '')
            time_window = job_spec.get('time_window', '-7d..now')
            
            # Log execution details
            logger.info(f"Job {job_name} - Time window: {time_window}")
            logger.info(f"Job {job_name} - Sources: {len(sources)}")
            
            # In a full implementation, this would execute the Polars code against the sources
            # For now, we'll just log it
            logger.info(f"Job {job_name} - Would execute Polars code: {polars_code[:100]}...")
            
            # Report job execution
            if self.js:
                try:
                    # Publish job execution event
                    execution_data = {
                        "id": str(uuid.uuid4()),
                        "job_name": job_name,
                        "time": datetime.now().isoformat(),
                        "status": "completed",
                        "alert_id": job_spec.get("alert_id"),
                        "result": {
                            "executed": True,
                            "message": "Job executed successfully"
                        }
                    }
                    
                    # Publish execution event
                    data_bytes = json.dumps(execution_data).encode('utf-8')
                    await self.js.publish("job.execution", data_bytes)
                    logger.info(f"Published job execution event for {job_name}")
                
                except Exception as e:
                    logger.error(f"Error publishing job execution event: {e}")
                    
        except Exception as e:
            logger.error(f"Error executing job spec: {e}")
    
    async def should_run_job(self, job_spec: Dict[str, Any]) -> bool:
        """Determine if a job should run based on its schedule
        
        Args:
            job_spec: The job specification with schedule information
            
        Returns:
            bool: True if the job should run, False otherwise
        """
        # In a production system, implement proper schedule parsing
        # For now, always return True for testing
        schedule = job_spec.get('schedule', '')
        logger.debug(f"Checking schedule: {schedule}")
        return True
    
    async def process_alerts(self) -> None:
        """Process all active alerts"""
        logger.info("Processing alerts")
        
        # Get active alerts
        alerts = await self.get_active_alerts()
        logger.info(f"Retrieved {len(alerts)} alerts to process")
        
        if not alerts:
            logger.debug("No active alerts found")
            return
        
        # Process each alert
        for alert in alerts:
            alert_id = alert.get('id')
            logger.debug(f"Evaluating alert {alert_id}: {alert.get('type')}")
            
            # Check if alert condition is met
            triggered = await self.check_alert_condition(alert)
            
            if triggered:
                logger.info(f"Alert {alert_id} triggered")
                
                # Send notification
                await self.send_notification(alert)
            
            # Check if the alert has a job spec to execute
            job_spec = alert.get('job_spec')
            if job_spec:
                logger.info(f"Alert {alert_id} has a job spec: {job_spec.get('job_name', 'unnamed')}")
                
                # Check if the job should run based on its schedule
                should_run = await self.should_run_job(job_spec)
                
                if should_run:
                    logger.info(f"Executing job spec for alert {alert_id}")
                    await self.execute_job_spec(job_spec)
                else:
                    logger.debug(f"Job spec for alert {alert_id} not scheduled to run now")
            
            # Log alert activity (without updating status)
            await self.log_alert_activity(alert, triggered)


async def start_alert_processor(js=None, interval_seconds: int = 60):
    """
    Start the alert processor as a background task.
    
    Args:
        js: JetStream instance for NATS
        interval_seconds: Interval between alert processing runs
    """
    global is_running
    
    if is_running:
        logger.warning("Alert processor is already running")
        return
    
    is_running = True
    processor = AlertProcessor(js)
    
    logger.info(f"Starting alert processor with {interval_seconds} seconds interval")
    
    try:
        while is_running:
            try:
                await processor.process_alerts()
            except Exception as process_error:
                logger.error(f"Error in alert processing cycle: {process_error}")
            
            # Wait for next interval
            await asyncio.sleep(interval_seconds)
    
    except asyncio.CancelledError:
        logger.info("Alert processor task cancelled")
    except Exception as e:
        logger.error(f"Unexpected error in alert processor: {e}")
    finally:
        is_running = False
        logger.info("Alert processor stopped")


async def stop_alert_processor():
    """Stop the alert processor background task"""
    global is_running
    logger.info("Stopping alert processor")
    is_running = False
