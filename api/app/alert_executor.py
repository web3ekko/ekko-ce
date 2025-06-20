"""
Alert Executor - Background task for executing Polars DSL

This module provides the alert execution engine that listens to NATS subjects
and executes Polars DSL code against mock data sources.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import uuid

import polars as pl
import nats
from nats.errors import TimeoutError as NatsTimeoutError

from .logging_config import job_spec_logger as logger

# ═══════════════════════════════════════════════════════════════════════════════
# Message Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class AlertExecutionRequest:
    def __init__(self, data: Dict[str, Any]):
        self.execution_id = data.get("execution_id", str(uuid.uuid4()))
        self.alert_id = data.get("alert_id", "unknown")
        self.polars_dsl = data.get("polars_dsl", "")
        self.data_sources = data.get("data_sources", [])
        self.output_mapping = data.get("output_mapping", {})
        self.parameters_used = data.get("parameters_used", {})
        self.timeout_seconds = data.get("timeout_seconds", 30)
        self.priority = data.get("priority", "Normal")
        self.requested_at = data.get("requested_at", datetime.now(timezone.utc).isoformat())

class AlertExecutionResult:
    def __init__(self, execution_id: str, alert_id: str, result: bool, value: str, metadata: Dict[str, Any]):
        self.execution_id = execution_id
        self.alert_id = alert_id
        self.result = result
        self.value = value
        self.metadata = metadata
        self.completed_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "alert_id": self.alert_id,
            "result": self.result,
            "value": self.value,
            "metadata": self.metadata,
            "completed_at": self.completed_at
        }

class AlertExecutionError:
    def __init__(self, execution_id: str, alert_id: str, error_type: str, error_message: str, metadata: Dict[str, Any]):
        self.execution_id = execution_id
        self.alert_id = alert_id
        self.error_type = error_type
        self.error_message = error_message
        self.metadata = metadata
        self.failed_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "alert_id": self.alert_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "failed_at": self.failed_at
        }

# ═══════════════════════════════════════════════════════════════════════════════
# Mock Data Sources
# ═══════════════════════════════════════════════════════════════════════════════

def create_mock_wallet_balances() -> pl.DataFrame:
    """Create mock wallet balance data"""
    return pl.DataFrame({
        "address": [
            "0x1234567890abcdef1234567890abcdef12345678",
            "0xabcdef1234567890abcdef1234567890abcdef12",
            "0x9876543210fedcba9876543210fedcba98765432",
            "0xfedcba0987654321fedcba0987654321fedcba09"
        ],
        "balance": [15.5, 8.2, 25.8, 3.1],
        "token_symbol": ["AVAX", "AVAX", "AVAX", "AVAX"],
        "network": ["avalanche", "avalanche", "avalanche", "avalanche"],
        "timestamp": [
            "2025-06-20T08:00:00Z",
            "2025-06-20T08:00:00Z", 
            "2025-06-20T08:00:00Z",
            "2025-06-20T08:00:00Z"
        ]
    })

def create_mock_transactions() -> pl.DataFrame:
    """Create mock transaction data"""
    return pl.DataFrame({
        "hash": ["0xabc123", "0xdef456", "0x789xyz", "0x321fed"],
        "from": [
            "0x1234567890abcdef1234567890abcdef12345678",
            "0xabcdef1234567890abcdef1234567890abcdef12",
            "0x9876543210fedcba9876543210fedcba98765432",
            "0x1234567890abcdef1234567890abcdef12345678"
        ],
        "to": [
            "0xabcdef1234567890abcdef1234567890abcdef12",
            "0x1234567890abcdef1234567890abcdef12345678",
            "0xfedcba0987654321fedcba0987654321fedcba09",
            "0x9876543210fedcba9876543210fedcba98765432"
        ],
        "value": [12.5, 3.8, 7.2, 18.9],
        "token_symbol": ["AVAX", "AVAX", "AVAX", "AVAX"],
        "timestamp": [
            "2025-06-20T08:00:00Z",
            "2025-06-20T08:01:00Z",
            "2025-06-20T08:02:00Z",
            "2025-06-20T08:03:00Z"
        ],
        "gas_price": [25.0, 23.5, 26.8, 24.2],
        "network": ["avalanche", "avalanche", "avalanche", "avalanche"],
        "subnet": ["mainnet", "mainnet", "mainnet", "mainnet"]
    })

def create_mock_price_feeds() -> pl.DataFrame:
    """Create mock price feed data"""
    return pl.DataFrame({
        "symbol": ["AVAX", "ETH", "BTC", "USDC"],
        "price": [45.2, 3200.5, 67500.0, 1.0],
        "timestamp": [
            "2025-06-20T08:00:00Z",
            "2025-06-20T08:00:00Z",
            "2025-06-20T08:00:00Z",
            "2025-06-20T08:00:00Z"
        ],
        "exchange": ["binance", "coinbase", "kraken", "binance"],
        "volume_24h": [1250000.0, 2800000.0, 890000.0, 5600000.0]
    })

def create_mock_defi_yields() -> pl.DataFrame:
    """Create mock DeFi yield data"""
    return pl.DataFrame({
        "protocol": ["aave", "compound", "traderjoe", "benqi"],
        "pool": ["AVAX", "USDC", "AVAX-USDC", "AVAX"],
        "apr": [8.5, 4.2, 12.8, 6.9],
        "tvl": [125000000.0, 89000000.0, 45000000.0, 78000000.0],
        "timestamp": [
            "2025-06-20T08:00:00Z",
            "2025-06-20T08:00:00Z",
            "2025-06-20T08:00:00Z",
            "2025-06-20T08:00:00Z"
        ]
    })

# ═══════════════════════════════════════════════════════════════════════════════
# Polars Execution Engine
# ═══════════════════════════════════════════════════════════════════════════════

class PolarsExecutor:
    def __init__(self):
        self.worker_id = f"worker-{str(uuid.uuid4())[:8]}"
        self.data_cache = {}
        
    def load_data_sources(self, data_sources: List[str]) -> Dict[str, pl.DataFrame]:
        """Load mock data sources"""
        data_frames = {}
        
        for source in data_sources:
            if source == "wallet_balances":
                data_frames[source] = create_mock_wallet_balances()
            elif source == "transactions":
                data_frames[source] = create_mock_transactions()
            elif source == "price_feeds":
                data_frames[source] = create_mock_price_feeds()
            elif source == "defi_yields":
                data_frames[source] = create_mock_defi_yields()
            else:
                # Generic empty DataFrame
                data_frames[source] = pl.DataFrame({"id": [1, 2], "value": ["test1", "test2"]})
                
        return data_frames
    
    def validate_dsl(self, dsl: str) -> bool:
        """Basic DSL validation"""
        # Check for dangerous patterns
        dangerous_patterns = ["import ", "exec(", "eval(", "__", "subprocess", "os.system"]
        for pattern in dangerous_patterns:
            if pattern in dsl:
                raise ValueError(f"DSL contains dangerous pattern: {pattern}")
        
        # Check for remaining template placeholders
        if "{{" in dsl or "}}" in dsl:
            raise ValueError("DSL contains unsubstituted template placeholders")
        
        return True
    
    def execute_dsl(self, dsl: str, data_frames: Dict[str, pl.DataFrame]) -> pl.DataFrame:
        """Execute simplified Polars DSL"""
        # This is a simplified DSL interpreter
        # In production, you'd want a proper DSL parser
        
        # For now, we'll handle basic wallet balance queries
        if "wallet_balances" in dsl and "filter" in dsl:
            df = data_frames.get("wallet_balances", pl.DataFrame())
            
            # Simple pattern matching for common operations
            if "below_threshold" in dsl and "current_value" in dsl:
                # This is a wallet balance threshold check
                # Extract the first wallet address and threshold from the DSL
                # This is a simplified implementation
                
                result_df = df.with_columns([
                    (pl.col("balance") < 10.0).alias("below_threshold"),
                    pl.col("balance").alias("current_value")
                ]).limit(1)
                
                return result_df
        
        # Fallback: return a simple result
        return pl.DataFrame({
            "result": [True],
            "value": ["mock_result"]
        })
    
    def extract_result(self, df: pl.DataFrame, output_mapping: Dict[str, Any]) -> tuple[bool, str]:
        """Extract result and value from DataFrame"""
        if df.height == 0:
            return False, "0"
        
        result_column = output_mapping.get("result_column", "result")
        value_column = output_mapping.get("value_column", "value")
        
        # Extract result (boolean)
        try:
            result_value = df.select(pl.col(result_column)).item(0, 0)
            result = bool(result_value)
        except:
            result = False
        
        # Extract value (as string)
        try:
            value_data = df.select(pl.col(value_column)).item(0, 0)
            value = str(value_data)
        except:
            value = "0"
        
        return result, value
    
    async def execute_alert(self, request: AlertExecutionRequest) -> AlertExecutionResult:
        """Execute an alert request"""
        start_time = time.time()
        
        try:
            # Load data sources
            data_frames = self.load_data_sources(request.data_sources)
            
            # Validate DSL
            self.validate_dsl(request.polars_dsl)
            
            # Execute DSL
            result_df = self.execute_dsl(request.polars_dsl, data_frames)
            
            # Extract result and value
            result, value = self.extract_result(result_df, request.output_mapping)
            
            # Build metadata
            execution_time = int((time.time() - start_time) * 1000)
            metadata = {
                "execution_time_ms": execution_time,
                "rows_processed": result_df.height,
                "data_sources_used": request.data_sources,
                "worker_id": self.worker_id,
                "cache_hit": False,
                "validation_warnings": []
            }
            
            return AlertExecutionResult(
                request.execution_id,
                request.alert_id,
                result,
                value,
                metadata
            )
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            metadata = {
                "execution_time_ms": execution_time,
                "worker_id": self.worker_id,
                "error_details": str(e)
            }
            
            raise AlertExecutionError(
                request.execution_id,
                request.alert_id,
                "EXECUTION_FAILED",
                str(e),
                metadata
            )

# ═══════════════════════════════════════════════════════════════════════════════
# NATS Consumer & Background Task Manager
# ═══════════════════════════════════════════════════════════════════════════════

class AlertExecutorService:
    def __init__(self, nats_url: str = "nats://localhost:4222"):
        self.nats_url = nats_url
        self.nc = None
        self.executor = PolarsExecutor()
        self.running = False
        self.max_concurrent_executions = 10
        self.active_executions = 0

    async def connect(self):
        """Connect to NATS"""
        try:
            self.nc = await nats.connect(self.nats_url)
            logger.info(f"Connected to NATS at {self.nats_url}")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def disconnect(self):
        """Disconnect from NATS"""
        if self.nc:
            await self.nc.close()
            logger.info("Disconnected from NATS")

    async def send_result(self, result: AlertExecutionResult):
        """Send execution result to NATS"""
        if not self.nc:
            logger.warning("NATS not connected, cannot send result")
            return

        try:
            message = json.dumps(result.to_dict())
            await self.nc.publish("alert.result", message.encode())
            logger.info(f"Sent result for execution {result.execution_id}")
        except Exception as e:
            logger.error(f"Failed to send result: {e}")

    async def send_error(self, error: AlertExecutionError):
        """Send execution error to NATS"""
        if not self.nc:
            logger.warning("NATS not connected, cannot send error")
            return

        try:
            message = json.dumps(error.to_dict())
            await self.nc.publish("alert.error", message.encode())
            logger.info(f"Sent error for execution {error.execution_id}")
        except Exception as e:
            logger.error(f"Failed to send error: {e}")

    async def handle_execution_request(self, msg):
        """Handle incoming execution request"""
        if self.active_executions >= self.max_concurrent_executions:
            logger.warning("Max concurrent executions reached, rejecting request")
            return

        self.active_executions += 1

        try:
            # Parse request
            data = json.loads(msg.data.decode())
            request = AlertExecutionRequest(data)

            logger.info(f"Processing execution request {request.execution_id} for alert {request.alert_id}")

            # Execute alert
            result = await self.executor.execute_alert(request)
            await self.send_result(result)

            logger.info(f"Completed execution {request.execution_id}: result={result.result}, value={result.value}")

        except AlertExecutionError as e:
            await self.send_error(e)
            logger.error(f"Execution failed {e.execution_id}: {e.error_message}")

        except Exception as e:
            # Create generic error
            execution_id = data.get("execution_id", "unknown") if 'data' in locals() else "unknown"
            alert_id = data.get("alert_id", "unknown") if 'data' in locals() else "unknown"

            error = AlertExecutionError(
                execution_id,
                alert_id,
                "PROCESSING_ERROR",
                str(e),
                {"worker_id": self.executor.worker_id}
            )
            await self.send_error(error)
            logger.error(f"Processing error for execution {execution_id}: {e}")

        finally:
            self.active_executions -= 1

    async def start_consumer(self):
        """Start the NATS consumer"""
        if not self.nc:
            await self.connect()

        self.running = True

        # Subscribe to alert execution requests
        await self.nc.subscribe("alert.execute", cb=self.handle_execution_request)

        logger.info("Alert executor service started, listening for execution requests")

        # Keep the consumer running
        while self.running:
            await asyncio.sleep(1)

    async def stop_consumer(self):
        """Stop the NATS consumer"""
        self.running = False
        await self.disconnect()
        logger.info("Alert executor service stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "active_executions": self.active_executions,
            "max_concurrent_executions": self.max_concurrent_executions,
            "worker_id": self.executor.worker_id,
            "connected": self.nc is not None and not self.nc.is_closed,
            "running": self.running
        }

# ═══════════════════════════════════════════════════════════════════════════════
# Global Service Instance
# ═══════════════════════════════════════════════════════════════════════════════

# Global instance to be used by FastAPI
alert_executor_service = None

async def get_alert_executor_service() -> AlertExecutorService:
    """Get or create the global alert executor service"""
    global alert_executor_service

    if alert_executor_service is None:
        # Get NATS URL from environment or use default
        import os
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        alert_executor_service = AlertExecutorService(nats_url)

    return alert_executor_service

async def start_alert_executor():
    """Start the alert executor service"""
    service = await get_alert_executor_service()
    await service.start_consumer()

async def stop_alert_executor():
    """Stop the alert executor service"""
    global alert_executor_service
    if alert_executor_service:
        await alert_executor_service.stop_consumer()
        alert_executor_service = None
