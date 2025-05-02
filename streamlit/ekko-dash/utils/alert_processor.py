import time
from datetime import datetime
from typing import Dict, Any, List
import duckdb
import schedule
import pulsar
import json
import polars as pl
import os
from .models import Alert
from .notifications import send_ntfy_notification

class AlertProcessor:
    def __init__(self, db_path: str):
        """
        Initialize the alert processor.
        
        Args:
            db_path (str): Path to the DuckDB database
        """
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts"""
        query = """
        SELECT 
            a.id, a.wallet_id, a.type, a.condition, a.threshold,
            a.status, a.created_at, a.last_triggered, a.notification_topic,
            w.address, w.blockchain_symbol, w.name as wallet_name
        FROM alert a
        JOIN wallet w ON a.wallet_id = w.id
        WHERE a.status = 'active'
        """
        result = self.conn.execute(query).fetchall()
        return [dict(row) for row in result]
    
    def check_alert_condition(self, alert: Dict[str, Any]) -> bool:
        """
        Check if an alert condition is met.
        
        Args:
            alert (Dict[str, Any]): Alert data including condition
            
        Returns:
            bool: True if condition is met, False otherwise
        """
        try:
            # 1. Fetch transactions from Pulsar
            url = os.getenv('PULSAR_URL', 'pulsar://localhost:6650')
            topic = os.getenv('PULSAR_TOPIC', 'persistent://public/default/transactions')
            client = pulsar.Client(url)
            consumer = client.subscribe(
                topic,
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
            client.close()

            # 2. Build Polars DataFrame
            df = pl.DataFrame(tx_list)

            # 3. Evaluate stored Polars condition
            condition = alert.get('condition', '')
            result = eval(condition, {'df': df, 'pl': pl})
            return bool(result)
        except Exception as e:
            print(f"Error checking alert condition: {str(e)}")
            return False
    
    def update_alert_status(self, alert_id: str, triggered: bool):
        """Update alert status after checking"""
        status = 'triggered' if triggered else 'active'
        query = """
        UPDATE alert
        SET status = ?, last_triggered = ?
        WHERE id = ?
        """
        self.conn.execute(query, [status, datetime.now(), alert_id])
    
    def process_alerts(self):
        """Process all active alerts"""
        alerts = self.get_active_alerts()
        
        for alert in alerts:
            if self.check_alert_condition(alert):
                # Format notification message
                message = f"Alert triggered for {alert['wallet_name']}: {alert['message']}"
                
                # Send notification if topic is configured
                if alert['notification_topic']:
                    priority = "high" if alert['priority'] == "High" else "default"
                    send_ntfy_notification(
                        topic=alert['notification_topic'],
                        message=message,
                        priority=priority,
                        title=f"Ekko {alert['type']}",
                        tags=["bell", "money-bag"]
                    )
                
                # Update alert status
                self.update_alert_status(alert['id'], True)
    
    def run(self, interval: int = 1):
        """
        Run the alert processor on a schedule using python-schedule.
        
        Args:
            interval (int): Check interval in minutes
        """
        # Schedule process_alerts to run every 'interval' minutes
        schedule.every(interval).minutes.do(self.process_alerts)
        # Continuously run pending jobs
        while True:
            try:
                schedule.run_pending()
            except Exception as e:
                print(f"Error running scheduled alerts: {e}")
            time.sleep(1)
