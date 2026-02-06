//! Error types for Alert Scheduler Provider

use thiserror::Error;

#[derive(Error, Debug)]
pub enum AlertSchedulerError {
    #[error("Redis connection error: {0}")]
    RedisConnection(#[from] redis::RedisError),

    #[error("Configuration error: {0}")]
    Configuration(String),

    #[error("Lua script execution error: {0}")]
    LuaScriptExecution(String),

    #[error("Job creation failed: {0}")]
    JobCreationFailed(String),

    #[error("Duplicate job detected for instance {instance_id}")]
    DuplicateJob { instance_id: String },

    #[error("Transaction matching error: {0}")]
    TransactionMatching(String),

    #[error("Batch update failed: {0}")]
    BatchUpdateFailed(String),

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    #[error("Provider initialization error: {0}")]
    Initialization(String),

    #[error("Timeout error: operation took longer than {timeout_ms}ms")]
    Timeout { timeout_ms: u64 },

    #[error("Capacity exceeded: {message}")]
    CapacityExceeded { message: String },

    #[error("NATS connection error: {0}")]
    NatsConnection(String),

    #[error("NATS publish error: {0}")]
    NatsPublish(String),

    #[error("Script not loaded: {0}")]
    ScriptNotLoaded(String),

    #[error("Unexpected response: {0}")]
    UnexpectedResponse(String),

    #[error("Alert not found: {0}")]
    AlertNotFound(String),

    #[error("Invalid alert data: {0}")]
    InvalidAlertData(String),

    #[error("Django API connection error: {0}")]
    ApiConnection(String),

    #[error("Configuration error: {0}")]
    ConfigError(String),
}

impl AlertSchedulerError {
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            AlertSchedulerError::RedisConnection(_)
                | AlertSchedulerError::Timeout { .. }
                | AlertSchedulerError::LuaScriptExecution(_)
                | AlertSchedulerError::NatsConnection(_)
                | AlertSchedulerError::NatsPublish(_)
                | AlertSchedulerError::ApiConnection(_)
        )
    }
}
