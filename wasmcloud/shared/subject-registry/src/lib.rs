//! Centralized NATS Subject Registry for Ekko Platform
//!
//! This module defines all NATS subject patterns used across the Ekko platform.
//! Subject patterns follow the PRD-defined hierarchy from:
//! - `/docs/prd/integration/PRD-NATS-Task-Queue-System-USDT.md`
//!
//! # Subject Hierarchy Overview
//!
//! ```text
//! blockchain.{chain}.transactions.{stage}     # Transaction processing
//! blockchain.{chain}.contracts.{type}         # Contract-specific events
//! alerts.jobs.{action}.{param}                # Alert job processing
//! notifications.send.{mode}.{channel}         # Notification delivery
//! ducklake.{table}.{operation}                # Data lake operations
//! system.{component}                          # System health/status
//! ```

pub mod alerts;
pub mod blockchain;
pub mod ducklake;
pub mod notifications;
pub mod system;

// Re-export all modules at crate root for convenience
pub use alerts::*;
pub use blockchain::*;
pub use ducklake::*;
pub use notifications::*;
pub use system::*;

/// Constants for supported blockchain chains
pub mod chains {
    pub const ETHEREUM: &str = "ethereum";
    pub const BITCOIN: &str = "bitcoin";
    pub const SOLANA: &str = "solana";
    pub const COSMOS: &str = "cosmos";
}

/// Constants for notification channels
pub mod channels {
    pub const EMAIL: &str = "email";
    pub const SLACK: &str = "slack";
    pub const TELEGRAM: &str = "telegram";
    pub const DISCORD: &str = "discord";
    pub const WEBHOOK: &str = "webhook";
    pub const WEBSOCKET: &str = "websocket";
    pub const SMS: &str = "sms";
    pub const PUSH: &str = "push";
    pub const INAPP: &str = "inapp";
}

/// Constants for alert priorities
pub mod priorities {
    pub const CRITICAL: &str = "critical";
    pub const HIGH: &str = "high";
    pub const NORMAL: &str = "normal";
    pub const LOW: &str = "low";
    pub const BACKGROUND: &str = "background";
}

/// Constants for trigger types
pub mod trigger_types {
    pub const EVENT_DRIVEN: &str = "event_driven";
    pub const PERIODIC: &str = "periodic";
    pub const ONE_TIME: &str = "one_time";
}
