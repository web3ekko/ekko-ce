//! # Health Check Actor
//!
//! WasmCloud actor that provides health check responses via NATS messaging.
//! This actor receives health check requests and responds with system status information.

use serde::{Deserialize, Serialize};
use serde_json::json;

// Generate WIT bindings for the health-check world
wit_bindgen::generate!({ generate_all });

use exports::ekko::messaging::consumer::Guest as MessageConsumer;

/// Health check request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthCheckRequest {
    /// Type of health check ("health", "ready", "live", "detailed")
    pub check_type: String,
    /// Request ID for tracking
    pub request_id: String,
    /// Service name to check (optional)
    pub service: Option<String>,
}

/// Health check response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthCheckResponse {
    /// Status ("healthy", "unhealthy", "ready", "alive")
    pub status: String,
    /// Service name
    pub service: String,
    /// Version
    pub version: String,
    /// Timestamp
    pub timestamp: String,
    /// Additional details
    pub details: std::collections::HashMap<String, serde_json::Value>,
    /// Request ID for tracking
    pub request_id: String,
}

impl HealthCheckRequest {
    /// Parse health check request from JSON
    pub fn from_json(data: &[u8]) -> Result<Self, String> {
        serde_json::from_slice(data)
            .map_err(|e| format!("Failed to parse health check request: {}", e))
    }
}

impl HealthCheckResponse {
    /// Generate a healthy response
    pub fn healthy(request_id: String, check_type: &str) -> Self {
        let mut details = std::collections::HashMap::new();

        match check_type {
            "detailed" => {
                details.insert(
                    "system".to_string(),
                    json!({
                        "memory": "available",
                        "cpu": "normal",
                        "disk": "available"
                    }),
                );
                details.insert(
                    "components".to_string(),
                    json!({
                        "wasmcloud_runtime": "healthy",
                        "messaging": "healthy"
                    }),
                );
                details.insert("uptime".to_string(), json!("running"));
            }
            "ready" => {
                details.insert(
                    "message".to_string(),
                    json!("Service is ready to accept requests"),
                );
            }
            "live" => {
                details.insert(
                    "message".to_string(),
                    json!("Service is alive and responding"),
                );
            }
            _ => {
                details.insert(
                    "message".to_string(),
                    json!("Health check service is running"),
                );
            }
        }

        Self {
            status: "healthy".to_string(),
            service: "ekko-health-check".to_string(),
            version: "1.0.0".to_string(),
            timestamp: chrono::Utc::now().to_rfc3339(),
            details,
            request_id,
        }
    }

    /// Convert to JSON bytes
    pub fn to_json(&self) -> Result<Vec<u8>, String> {
        serde_json::to_vec(self)
            .map_err(|e| format!("Failed to serialize health check response: {}", e))
    }
}

/// Main Health Check Actor Component
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl MessageConsumer for Component {
    /// Handle incoming NATS messages containing health check requests
    fn handle_message(subject: String, payload: Vec<u8>) -> Result<(), String> {
        // Only process health check messages
        if !subject.starts_with("health.") {
            return Ok(()); // Ignore non-health messages
        }

        eprintln!(
            "Health check actor received message on subject: {}",
            subject
        );

        // Parse the health check request
        let request = match HealthCheckRequest::from_json(&payload) {
            Ok(req) => req,
            Err(e) => {
                eprintln!("Failed to parse health check request: {}", e);
                return Err(e);
            }
        };

        // Generate health response based on check type
        let response = HealthCheckResponse::healthy(request.request_id, &request.check_type);

        // Convert response to JSON
        let response_json = match response.to_json() {
            Ok(json) => json,
            Err(e) => {
                eprintln!("Failed to serialize health check response: {}", e);
                return Err(e);
            }
        };

        // Send response back via NATS
        let response_subject = format!("health.response.{}", request.check_type);

        // Use the messaging handler to publish response
        use ekko::messaging::handler::publish;

        match publish(&response_subject, &response_json) {
            Ok(_) => {
                eprintln!("Health check response sent to: {}", response_subject);
                Ok(())
            }
            Err(e) => {
                eprintln!("Failed to send health check response: {}", e);
                Err(format!("Failed to send response: {}", e))
            }
        }
    }
}

#[cfg(not(target_arch = "wasm32"))]
fn main() {
    // This function is never called in the WASM build
    println!("Health check actor - use as WASM component");
}
