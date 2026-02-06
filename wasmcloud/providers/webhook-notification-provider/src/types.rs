use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Webhook notification request from NATS
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebhookNotificationRequest {
    pub notification_id: String,
    pub user_id: String,
    pub alert_id: String,
    pub alert_name: String,
    pub priority: AlertPriority,
    pub payload: serde_json::Value,
    pub timestamp: i64,
}

/// Alert priority levels
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum AlertPriority {
    Low,
    Normal,
    High,
    Critical,
}

/// Webhook configuration from Redis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebhookConfig {
    pub user_id: String,
    pub webhook_url: String,
    pub fallback_url: Option<String>,
    pub http_method: HttpMethod,
    pub headers: HashMap<String, String>,
    pub auth_type: AuthType,
    pub hmac_secret: Option<String>,
    pub jwt_secret: Option<String>,
    pub timeout_seconds: u64,
    pub retry_config: RetryConfig,
    pub enabled: bool,
}

/// HTTP methods for webhook
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "UPPERCASE")]
pub enum HttpMethod {
    POST,
    PUT,
    PATCH,
}

/// Authentication types
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum AuthType {
    None,
    Bearer,
    Hmac,
    Jwt,
}

/// Retry configuration with exponential backoff
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetryConfig {
    pub max_attempts: u32,
    pub initial_delay_ms: u64,
    pub max_delay_ms: u64,
    pub exponential_base: f64,
    pub jitter: bool,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_attempts: 3,
            initial_delay_ms: 1000,
            max_delay_ms: 30000,
            exponential_base: 2.0,
            jitter: true,
        }
    }
}

/// Webhook delivery status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryStatus {
    pub notification_id: String,
    pub status: DeliveryResult,
    pub attempts: u32,
    pub last_error: Option<String>,
    pub delivered_at: Option<i64>,
    pub response_code: Option<u16>,
    pub response_body: Option<String>,
}

/// Delivery result enum
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum DeliveryResult {
    Pending,
    Delivered,
    Failed,
    Retrying,
}

/// Health check metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthMetrics {
    pub endpoint_url: String,
    pub success_count: u64,
    pub failure_count: u64,
    pub avg_response_time_ms: u64,
    pub last_success_at: Option<i64>,
    pub last_failure_at: Option<i64>,
    pub last_error: Option<String>,
    pub consecutive_failures: u32,
    pub is_healthy: bool,
}

impl HealthMetrics {
    pub fn new(endpoint_url: String) -> Self {
        Self {
            endpoint_url,
            success_count: 0,
            failure_count: 0,
            avg_response_time_ms: 0,
            last_success_at: None,
            last_failure_at: None,
            last_error: None,
            consecutive_failures: 0,
            is_healthy: true,
        }
    }

    pub fn record_success(&mut self, response_time_ms: u64, timestamp: i64) {
        self.success_count += 1;
        self.consecutive_failures = 0;
        self.last_success_at = Some(timestamp);
        self.is_healthy = true;

        // Update average response time with exponential moving average
        if self.success_count == 1 {
            self.avg_response_time_ms = response_time_ms;
        } else {
            self.avg_response_time_ms = (self.avg_response_time_ms * 7 + response_time_ms) / 8;
        }
    }

    pub fn record_failure(&mut self, error: String, timestamp: i64) {
        self.failure_count += 1;
        self.consecutive_failures += 1;
        self.last_failure_at = Some(timestamp);
        self.last_error = Some(error);

        // Mark unhealthy after 3 consecutive failures
        if self.consecutive_failures >= 3 {
            self.is_healthy = false;
        }
    }
}

/// Delivery event for DuckLake analytics (matches notification_deliveries schema)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryEvent {
    // Partition columns
    pub delivery_date: String, // YYYY-MM-DD format
    pub channel_type: String,  // "webhook"
    pub shard: i32,

    // Primary identifiers
    pub notification_id: String,
    pub channel_id: String,
    pub endpoint_url: Option<String>,

    // Delivery attempt tracking
    pub attempt_number: i32,
    pub max_attempts: i32,
    pub delivery_status: String, // DELIVERED, FAILED, PENDING, RETRYING

    // Timing metrics
    pub started_at: i64,           // Microseconds timestamp
    pub completed_at: Option<i64>, // Microseconds timestamp
    pub response_time_ms: Option<i64>,

    // Response data
    pub http_status_code: Option<i32>,
    pub response_body: Option<String>, // Truncated to 1KB
    pub error_message: Option<String>,
    pub error_type: Option<String>, // NETWORK, TIMEOUT, AUTH, RATE_LIMIT

    // Notification content metadata
    pub alert_id: Option<String>,
    pub transaction_hash: Option<String>,
    pub severity: Option<String>,
    pub message_size_bytes: Option<i32>,

    // Retry and fallback tracking
    pub used_fallback: bool,
    pub fallback_url: Option<String>,
    pub retry_delay_ms: Option<i64>,

    // Provider metadata
    pub provider_id: Option<String>,
    pub provider_version: Option<String>,

    // Processing metadata
    pub ingested_at: i64, // Microseconds timestamp
}
