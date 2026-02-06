use anyhow::{Context, Result};
use chrono::Utc;
use hmac::{Hmac, Mac};
use rand::Rng;
use reqwest::Client;
use sha2::Sha256;
use std::time::{Duration, Instant};
use tokio::time::sleep;
use tracing::{debug, error, info, warn};

use crate::types::{
    AuthType, DeliveryResult, DeliveryStatus, HttpMethod, RetryConfig, WebhookConfig,
    WebhookNotificationRequest,
};

type HmacSha256 = Hmac<Sha256>;

/// Webhook HTTP client with retry logic
pub struct WebhookClient {
    client: Client,
}

impl WebhookClient {
    /// Create new webhook client
    pub fn new() -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .context("Failed to build HTTP client")?;

        Ok(Self { client })
    }

    /// Send webhook notification with retry logic
    pub async fn send_notification(
        &self,
        config: &WebhookConfig,
        request: &WebhookNotificationRequest,
    ) -> Result<DeliveryStatus> {
        let mut attempts = 0;
        let mut last_error: Option<String> = None;
        let retry_config = &config.retry_config;

        // Try primary endpoint
        while attempts < retry_config.max_attempts {
            attempts += 1;

            debug!(
                "Attempting webhook delivery {}/{} to {}",
                attempts, retry_config.max_attempts, config.webhook_url
            );

            match self.try_send(config, request, &config.webhook_url).await {
                Ok(response) => {
                    info!(
                        "Webhook delivered successfully on attempt {} to {}",
                        attempts, config.webhook_url
                    );

                    return Ok(DeliveryStatus {
                        notification_id: request.notification_id.clone(),
                        status: DeliveryResult::Delivered,
                        attempts,
                        last_error: None,
                        delivered_at: Some(Utc::now().timestamp()),
                        response_code: Some(response.status),
                        response_body: response.body,
                    });
                }
                Err(e) => {
                    let error_msg = format!("Attempt {} failed: {}", attempts, e);
                    warn!("{}", error_msg);
                    last_error = Some(error_msg);

                    if attempts < retry_config.max_attempts {
                        let delay = self.calculate_backoff(attempts, retry_config);
                        debug!("Waiting {}ms before retry", delay);
                        sleep(Duration::from_millis(delay)).await;
                    }
                }
            }
        }

        // Try fallback endpoint if configured
        if let Some(fallback_url) = &config.fallback_url {
            info!("Primary endpoint failed, trying fallback: {}", fallback_url);

            match self.try_send(config, request, fallback_url).await {
                Ok(response) => {
                    info!("Webhook delivered successfully to fallback endpoint");

                    return Ok(DeliveryStatus {
                        notification_id: request.notification_id.clone(),
                        status: DeliveryResult::Delivered,
                        attempts: attempts + 1,
                        last_error: Some("Primary failed, fallback succeeded".to_string()),
                        delivered_at: Some(Utc::now().timestamp()),
                        response_code: Some(response.status),
                        response_body: response.body,
                    });
                }
                Err(e) => {
                    error!("Fallback endpoint also failed: {}", e);
                    last_error = Some(format!("Fallback failed: {}", e));
                }
            }
        }

        // All attempts failed
        error!(
            "All webhook delivery attempts failed for notification {}",
            request.notification_id
        );

        Ok(DeliveryStatus {
            notification_id: request.notification_id.clone(),
            status: DeliveryResult::Failed,
            attempts,
            last_error,
            delivered_at: None,
            response_code: None,
            response_body: None,
        })
    }

    /// Try to send webhook to a specific URL
    async fn try_send(
        &self,
        config: &WebhookConfig,
        request: &WebhookNotificationRequest,
        url: &str,
    ) -> Result<WebhookResponse> {
        let start = Instant::now();

        // Build request body
        let body = serde_json::to_vec(&request).context("Failed to serialize webhook payload")?;

        // Build HTTP request
        let mut req_builder = match config.http_method {
            HttpMethod::POST => self.client.post(url),
            HttpMethod::PUT => self.client.put(url),
            HttpMethod::PATCH => self.client.patch(url),
        };

        // Add custom headers
        for (key, value) in &config.headers {
            req_builder = req_builder.header(key, value);
        }

        // Add content type
        req_builder = req_builder.header("Content-Type", "application/json");

        // Add authentication
        req_builder = match &config.auth_type {
            AuthType::None => req_builder,
            AuthType::Bearer => {
                if let Some(token) = config.headers.get("Authorization") {
                    req_builder.header("Authorization", format!("Bearer {}", token))
                } else {
                    req_builder
                }
            }
            AuthType::Hmac => {
                if let Some(secret) = &config.hmac_secret {
                    let signature = self.generate_hmac_signature(&body, secret)?;
                    req_builder
                        .header("X-Webhook-Signature", signature)
                        .header("X-Webhook-Timestamp", Utc::now().timestamp().to_string())
                } else {
                    return Err(anyhow::anyhow!("HMAC secret not configured"));
                }
            }
            AuthType::Jwt => {
                // JWT signing would go here (simplified for now)
                if let Some(_jwt_secret) = &config.jwt_secret {
                    // In production, generate proper JWT token
                    req_builder.header("Authorization", "Bearer <jwt-token>")
                } else {
                    return Err(anyhow::anyhow!("JWT secret not configured"));
                }
            }
        };

        // Set timeout
        req_builder = req_builder.timeout(Duration::from_secs(config.timeout_seconds));

        // Send request
        let response = req_builder
            .body(body)
            .send()
            .await
            .context("Failed to send webhook request")?;

        let status = response.status().as_u16();
        let duration = start.elapsed().as_millis() as u64;

        debug!(
            "Webhook response: status={}, duration={}ms",
            status, duration
        );

        // Check if successful (2xx status codes)
        if response.status().is_success() {
            let body = response.text().await.ok();

            Ok(WebhookResponse {
                status,
                body,
                duration_ms: duration,
            })
        } else {
            let error_body = response.text().await.unwrap_or_default();
            Err(anyhow::anyhow!(
                "Webhook returned error status {}: {}",
                status,
                error_body
            ))
        }
    }

    /// Generate HMAC SHA-256 signature
    fn generate_hmac_signature(&self, payload: &[u8], secret: &str) -> Result<String> {
        let mut mac = HmacSha256::new_from_slice(secret.as_bytes())
            .context("Failed to create HMAC instance")?;

        mac.update(payload);

        let result = mac.finalize();
        let signature = hex::encode(result.into_bytes());

        Ok(signature)
    }

    /// Calculate exponential backoff delay with optional jitter
    fn calculate_backoff(&self, attempt: u32, config: &RetryConfig) -> u64 {
        let base_delay = config.initial_delay_ms as f64;
        let exponential = config.exponential_base.powi(attempt as i32 - 1);
        let mut delay = (base_delay * exponential) as u64;

        // Cap at max delay
        delay = delay.min(config.max_delay_ms);

        // Add jitter if enabled (±25% random variance)
        if config.jitter {
            let mut rng = rand::thread_rng();
            let jitter_factor = rng.gen_range(0.75..1.25);
            delay = (delay as f64 * jitter_factor) as u64;
        }

        delay
    }
}

/// Webhook response data
struct WebhookResponse {
    status: u16,
    body: Option<String>,
    duration_ms: u64,
}
