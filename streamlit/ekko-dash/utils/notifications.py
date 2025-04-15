import requests
import os

def send_ntfy_notification(topic: str, message: str, priority: str = "default", title: str = None, tags: list = None):
    """
    Send a notification via ntfy.
    
    Args:
        topic (str): The ntfy topic to publish to
        message (str): The notification message
        priority (str, optional): Priority level (default, low, high, urgent). Defaults to "default".
        title (str, optional): Title of the notification. Defaults to None.
        tags (list, optional): List of emoji tags. Defaults to None.
    """
    ntfy_url = os.getenv("NTFY_URL", "http://localhost:8070")
    
    headers = {
        "Priority": priority,
        "Title": title if title else "Ekko Alert",
        "Tags": ",".join(tags) if tags else "bell"
    }
    
    try:
        response = requests.post(
            f"{ntfy_url}/{topic}",
            data=message.encode(encoding='utf-8'),
            headers=headers
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Failed to send notification: {str(e)}")
        return False
