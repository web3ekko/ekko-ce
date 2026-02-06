//! Alerts Processor Actor (AlertTemplate v1 Runtime)
//!
//! Consumes `AlertEvaluationJobV1` jobs (`alerts.jobs.create.*`) and orchestrates:
//! - loading pinned instance + template from Redis (keyvalue)
//! - executing runtime DatasourceCatalog SQL via DuckLake Read (NATS request/reply)
//! - building a pre-joined Arrow IPC frame (1 row per target_key)
//! - calling Polars Eval provider (NATS request/reply)
//! - publishing `alert_triggered_batch_v1` match batches (`alerts.triggered.*`)

mod arrow_frame;
mod catalog;
mod runtime;

pub use runtime::{handle_nats_message, ProcessorError, RuntimeIO};

#[cfg(target_arch = "wasm32")]
wit_bindgen::generate!({ generate_all });

#[cfg(target_arch = "wasm32")]
use exports::wasmcloud::messaging::handler::Guest as MessageHandler;

#[cfg(target_arch = "wasm32")]
use wasmcloud::messaging::types as nats_types;

#[cfg(target_arch = "wasm32")]
use wasi::keyvalue::store;

#[cfg(target_arch = "wasm32")]
struct Component;

#[cfg(target_arch = "wasm32")]
export!(Component);

#[cfg(target_arch = "wasm32")]
struct WasmRuntime;

#[cfg(target_arch = "wasm32")]
impl RuntimeIO for WasmRuntime {
    fn kv_get(&self, key: &str) -> Result<Option<Vec<u8>>, ProcessorError> {
        let bucket = store::open("default").map_err(|e| {
            ProcessorError::nats(format!("failed to open keyvalue bucket: {:?}", e))
        })?;
        bucket
            .get(key)
            .map_err(|e| ProcessorError::nats(format!("keyvalue get failed: {:?}", e)))
    }

    fn nats_request(
        &self,
        subject: &str,
        body: Vec<u8>,
        timeout_ms: u32,
    ) -> Result<Vec<u8>, ProcessorError> {
        let resp = wasmcloud::messaging::consumer::request(subject, &body, timeout_ms)
            .map_err(|e| ProcessorError::nats(format!("nats request failed: {:?}", e)))?;
        Ok(resp.body)
    }

    fn nats_publish(&self, subject: &str, body: Vec<u8>) -> Result<(), ProcessorError> {
        let msg = nats_types::BrokerMessage {
            subject: subject.to_string(),
            body,
            reply_to: None,
        };
        wasmcloud::messaging::consumer::publish(&msg)
            .map_err(|e| ProcessorError::nats(format!("nats publish failed: {:?}", e)))?;
        Ok(())
    }

    fn now(&self) -> chrono::DateTime<chrono::Utc> {
        chrono::Utc::now()
    }
}

#[cfg(target_arch = "wasm32")]
impl MessageHandler for Component {
    fn handle_message(msg: nats_types::BrokerMessage) -> std::result::Result<(), String> {
        let io = WasmRuntime;
        runtime::handle_nats_message(&io, &msg.subject, &msg.body).map_err(|e| e.to_string())
    }
}
