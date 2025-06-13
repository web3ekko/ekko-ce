"""
Configuration settings for the API service.
"""

import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings."""
    
    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    # Database Settings
    DATABASE_URL: Optional[str] = None
    
    # MinIO/S3 Settings
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "blockchain-data"
    MINIO_BUCKET: str = "blockchain-data"  # Alternative name used in .env
    MINIO_REGION: str = "us-east-1"
    MINIO_SECURE: bool = False
    MINIO_USE_SSL: bool = False  # Alternative name used in .env

    # DuckLake Configuration (SQLite catalog + MinIO storage)
    DUCKLAKE_CATALOG_TYPE: str = "sqlite"  # sqlite, duckdb, postgres, mysql
    DUCKLAKE_CATALOG_PATH: str = "/data/ducklake/catalog.sqlite"
    DUCKLAKE_DATA_PATH: str = "s3://ducklake-data/data"
    DUCKLAKE_BUCKET_NAME: str = "ducklake-data"

    # JWT Settings
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # CORS Settings
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Cache Settings
    CACHE_TTL: int = 300  # 5 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()
