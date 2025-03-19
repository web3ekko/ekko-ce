"""Database initialization module"""
from src.config.settings import Settings
from utils.models import Database, Alert, Cache

# Initialize settings and database
settings = Settings()
db = Database(settings)
alert_model = Alert(db)
cache = Cache()

# Export initialized instances
__all__ = ['db', 'alert_model', 'cache', 'settings']
