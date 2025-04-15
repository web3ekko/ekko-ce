import time
from datetime import datetime
from typing import Dict, Any, List
import duckdb
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
            # The condition is already in SQL format from the LLM conversion
            result = self.conn.execute(alert['condition']).fetchone()
            return bool(result[0]) if result else False
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
    
    def run(self, interval: int = 60):
        """
        Run the alert processor in a loop.
        
        Args:
            interval (int): Check interval in seconds
        """
        while True:
            try:
                self.process_alerts()
            except Exception as e:
                print(f"Error processing alerts: {str(e)}")
            
            time.sleep(interval)
