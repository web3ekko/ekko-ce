"""Database initialization module"""
from src.config.settings import Settings
from utils.models import Database, Alert, Agent, Cache

# Initialize settings and database
settings = Settings()
db = Database(settings)

# Initialize models
alert_model = Alert(db)
agent_model = Agent(db)
cache = Cache()

# Export initialized instances
__all__ = ['db', 'alert_model', 'agent_model', 'cache', 'settings']
