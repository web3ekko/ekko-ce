//! Polars Eval Provider (AlertTemplate v1 Runtime)
//!
//! This provider evaluates AlertTemplate v1 expression ASTs using Polars.
//! It does not fetch data; it only evaluates a pre-joined dataframe provided
//! by the Alerts Processor.

pub mod evaluator;
pub mod nats_listener;
pub mod provider;

pub use nats_listener::NatsEvalListenerConfig;
pub use provider::PolarsEvalProvider;
