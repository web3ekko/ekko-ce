//! Notification Router Actor (AlertTemplate v1 Runtime)
//!
//! Consumes `AlertTriggeredBatchV1` messages (`alerts.triggered.>`) and:
//! - loads pinned instance snapshot from Redis (wasi:keyvalue/store)
//! - renders notification templates per matched target
//! - enforces dedupe/cooldown (wasi:keyvalue/atomics + store)
//! - publishes channel delivery requests (v1: webhook)

mod runtime;

pub use runtime::{handle_nats_message, RouterError, RuntimeIO};

#[cfg(target_arch = "wasm32")]
wit_bindgen::generate!({ generate_all });

#[cfg(target_arch = "wasm32")]
use exports::wasmcloud::messaging::handler::Guest as MessageHandler;

#[cfg(target_arch = "wasm32")]
use wasmcloud::messaging::types as nats_types;

#[cfg(target_arch = "wasm32")]
use wasi::keyvalue::{atomics, store};

#[cfg(target_arch = "wasm32")]
struct Component;

#[cfg(target_arch = "wasm32")]
export!(Component);

#[cfg(target_arch = "wasm32")]
struct WasmRuntime;

#[cfg(target_arch = "wasm32")]
impl RuntimeIO for WasmRuntime {
    fn kv_get(&self, key: &str) -> Result<Option<Vec<u8>>, RouterError> {
        let bucket = store::open("default")
            .map_err(|e| RouterError::store(format!("failed to open keyvalue bucket: {:?}", e)))?;
        bucket
            .get(key)
            .map_err(|e| RouterError::store(format!("keyvalue get failed: {:?}", e)))
    }

    fn kv_set(&self, key: &str, value: Vec<u8>) -> Result<(), RouterError> {
        let bucket = store::open("default")
            .map_err(|e| RouterError::store(format!("failed to open keyvalue bucket: {:?}", e)))?;
        bucket
            .set(key, &value)
            .map_err(|e| RouterError::store(format!("keyvalue set failed: {:?}", e)))
    }

    fn kv_exists(&self, key: &str) -> Result<bool, RouterError> {
        Ok(self.kv_get(key)?.is_some())
    }

    fn kv_incr(&self, key: &str, delta: u64) -> Result<u64, RouterError> {
        let bucket = store::open("default")
            .map_err(|e| RouterError::store(format!("failed to open keyvalue bucket: {:?}", e)))?;
        atomics::increment(&bucket, key, delta)
            .map_err(|e| RouterError::store(format!("keyvalue increment failed: {:?}", e)))
    }

    fn nats_publish(&self, subject: &str, body: Vec<u8>) -> Result<(), RouterError> {
        let msg = nats_types::BrokerMessage {
            subject: subject.to_string(),
            body,
            reply_to: None,
        };
        wasmcloud::messaging::consumer::publish(&msg)
            .map_err(|e| RouterError::store(format!("nats publish failed: {:?}", e)))?;
        Ok(())
    }

    fn now_unix_secs(&self) -> i64 {
        chrono::Utc::now().timestamp()
    }
}

#[cfg(target_arch = "wasm32")]
impl MessageHandler for Component {
    fn handle_message(msg: nats_types::BrokerMessage) -> std::result::Result<(), String> {
        let io = WasmRuntime;
        runtime::handle_nats_message(&io, &msg.subject, &msg.body).map_err(|e| e.to_string())
    }
}
