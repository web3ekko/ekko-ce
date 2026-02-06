//! Alert Scheduler Provider (AlertTemplate v1 Runtime)
//!
//! Authoritative behavior and message contracts are defined in:
//! - `docs/prd/wasmcloud/providers/PRD-Alert-Scheduler-Provider-v2-USDT.md`
//! - `docs/prd/wasmcloud/PRD-NATS-Subjects-Alert-System.md`
//! - `docs/prd/schemas/SCHEMA-EvaluationContext.md`

pub mod config;
pub mod error;
pub mod nats_client;
pub mod provider;
pub mod redis_ops;
pub mod runtime_store;
pub mod schedule_request_handler;
pub mod schedule_scanner;

pub use config::AlertSchedulerConfig;
pub use error::AlertSchedulerError;
pub use nats_client::NatsClient;
pub use provider::AlertSchedulerProvider;
pub use redis_ops::RedisManager;
pub use runtime_store::RuntimeStore;
pub use schedule_request_handler::ScheduleRequestHandler;
pub use schedule_scanner::ScheduleScanner;

// Re-export Result type for convenience
pub type Result<T> = std::result::Result<T, AlertSchedulerError>;
