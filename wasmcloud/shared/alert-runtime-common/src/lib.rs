//! Shared alert runtime message contracts.
//!
//! This crate is the Rust source of truth for the JSON contracts defined in:
//! - `docs/prd/schemas/SCHEMA-AlertTemplate.md`
//! - `docs/prd/schemas/SCHEMA-EvaluationContext.md`
//! - `docs/prd/wasmcloud/PRD-NATS-Subjects-Alert-System.md`

pub mod evaluation_context;
pub mod executable;
pub mod jobs;
pub mod keys;
pub mod polars_eval;
pub mod schedule;
pub mod template;
pub mod triggered;

pub use evaluation_context::*;
pub use executable::*;
pub use jobs::*;
pub use keys::*;
pub use polars_eval::*;
pub use schedule::*;
pub use template::*;
pub use triggered::*;
