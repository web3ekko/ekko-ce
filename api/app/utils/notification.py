import apprise
from typing import List, Dict, Any
from app.models.settings import NotificationChannel

class NotificationService:
    """
    Utility class for sending notifications using Apprise.
    Supports multiple notification channels (email, Slack, Telegram, etc.)
    """
    
    def __init__(self):
        self.apprise = apprise.Apprise()
    
    def add_channels(self, channels: List[NotificationChannel]):
        """
        Add notification channels to Apprise
        
        Args:
            channels: List of NotificationChannel objects
        """
        # Clear existing channels
        self.apprise.clear()
        
        # Add enabled channels
        for channel in channels:
            if channel.enabled:
                self.apprise.add(channel.url)
    
    def send_notification(self, title: str, body: str, channels: List[NotificationChannel] = None) -> Dict[str, Any]:
        """
        Send a notification to all configured channels
        
        Args:
            title: Notification title
            body: Notification body
            channels: Optional list of channels to use for this notification
                     If not provided, uses previously added channels
        
        Returns:
            Dictionary with notification status
        """
        if channels:
            # Use specific channels for this notification
            temp_apprise = apprise.Apprise()
            for channel in channels:
                if channel.enabled:
                    temp_apprise.add(channel.url)
            
            result = temp_apprise.notify(
                title=title,
                body=body
            )
        else:
            # Use previously configured channels
            result = self.apprise.notify(
                title=title,
                body=body
            )
        
        return {
            "success": result,
            "channels_count": len(self.apprise.servers()),
            "title": title,
            "body": body[:100] + "..." if len(body) > 100 else body
        }
    
    def test_channels(self, channels: List[NotificationChannel]) -> Dict[str, Any]:
        """
        Test notification channels by sending a test message
        
        Args:
            channels: List of NotificationChannel objects to test
        
        Returns:
            Dictionary with test results for each channel
        """
        results = {}
        
        for channel in channels:
            if not channel.enabled:
                results[channel.url] = {"success": False, "error": "Channel disabled"}
                continue
                
            try:
                # Create temporary Apprise instance for this test
                temp_apprise = apprise.Apprise()
                temp_apprise.add(channel.url)
                
                # Send test notification
                success = temp_apprise.notify(
                    title="Ekko Test Notification",
                    body=f"This is a test notification from Ekko for channel type: {channel.type}"
                )
                
                results[channel.url] = {"success": success}
                
            except Exception as e:
                results[channel.url] = {"success": False, "error": str(e)}
        
        return results

# Create a singleton instance
notification_service = NotificationService()
