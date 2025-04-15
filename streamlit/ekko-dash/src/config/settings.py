"""Application configuration management."""
from pathlib import Path
from typing import Optional, Dict, Any
import os
import yaml

class Settings:
    _instance: Optional['Settings'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._init_settings()
        return cls._instance
    
    def _init_settings(self):
        """Initialize settings from config file and environment variables."""
        self.base_dir = Path(__file__).parent.parent.parent
        self.config_file = self.base_dir / 'config.yaml'
        
        # Default settings
        self._settings = {
            'database': {
                'host': 'localhost',
                'path': '/data/ekko.db',  # Docker volume mount point
                'pool_size': 5
            },
            'redis': {
                'url': 'redis://localhost:6379',  # Will be overridden by REDIS_URL
                'db': 0
            },
            'minio': {
                'url': 'http://localhost:9000',  # Will be overridden by MINIO_URL
                'access_key': 'minioadmin',
                'secret_key': 'minioadmin',
                'secure': False,
                'bucket': 'ekko-data'
            },
            'cache': {
                'enabled': True,
                'ttl': 300  # 5 minutes
            },
            'app': {
                'theme': 'Light',
                'notifications_enabled': True,
                'auto_refresh': True,
                'cache_duration': 15,  # minutes
                'refresh_interval': 60  # seconds
            },
            'api': {
                'key': '',
                'endpoint': 'http://bento:8000'  # Default to Bento API service
            }
        }
        
        # Load from config file if exists
        if self.config_file.exists():
            with open(self.config_file) as f:
                try:
                    file_settings = yaml.safe_load(f)
                    if file_settings:
                        self._settings.update(file_settings)
                except yaml.YAMLError as e:
                    import streamlit as st
                    st.error(f"Error loading config.yaml: {e}")
        else:
            # Create default config file if it doesn't exist
            with open(self.config_file, 'w') as f:
                yaml.dump(self._settings, f, default_flow_style=False)
        
        # Override with environment variables
        self._apply_env_overrides()
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to settings."""
        # Docker environment variables take precedence
        if redis_url := os.getenv('REDIS_URL'):
            self._settings['redis']['url'] = redis_url
            
        if minio_url := os.getenv('MINIO_URL'):
            self._settings['minio']['url'] = minio_url
            
        if minio_access := os.getenv('MINIO_ACCESS_KEY'):
            self._settings['minio']['access_key'] = minio_access
            
        if minio_secret := os.getenv('MINIO_SECRET_KEY'):
            self._settings['minio']['secret_key'] = minio_secret
            
        if bento_url := os.getenv('BENTO_API_URL'):
            self._settings['api']['endpoint'] = bento_url
            
        # Legacy environment variables
        env_mappings = {
            'EKKO_DB_HOST': ('database', 'host'),
            'EKKO_DB_PATH': ('database', 'path'),
            'EKKO_DB_POOL_SIZE': ('database', 'pool_size', int),
            'EKKO_REDIS_DB': ('redis', 'db', int),
            'EKKO_CACHE_ENABLED': ('cache', 'enabled', lambda x: x.lower() == 'true'),
            'EKKO_CACHE_TTL': ('cache', 'ttl', int)
        }
        
        for env_var, (section, key, *transform) in env_mappings.items():
            if value := os.getenv(env_var):
                transform_func = transform[0] if transform else lambda x: x
                try:
                    self._settings[section][key] = transform_func(value)
                except (KeyError, ValueError) as e:
                    import streamlit as st
                    st.warning(f"Error applying environment variable {env_var}: {e}")
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a specific setting value.
        
        Args:
            section: The settings section (e.g., 'database', 'redis')
            key: The specific setting key
            default: Default value if not found
            
        Returns:
            The setting value or default if not found
        """
        try:
            return self._settings[section][key]
        except KeyError:
            return default
    
    @property
    def database(self) -> Dict[str, Any]:
        """Get database settings."""
        return self._settings['database'].copy()
    
    @property
    def redis(self) -> Dict[str, Any]:
        """Get Redis settings."""
        return self._settings['redis'].copy()
    
    @property
    def cache(self) -> Dict[str, Any]:
        """Get cache settings."""
        return self._settings['cache'].copy()

    @property
    def app(self) -> Dict[str, Any]:
        """Get application settings."""
        return self._settings['app'].copy()

    @property
    def api(self) -> Dict[str, Any]:
        """Get API settings."""
        return self._settings['api'].copy()

# Global settings instance
settings = Settings()
