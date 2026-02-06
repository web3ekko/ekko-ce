//! Common provider interface and traits
//!
//! This module defines the standard interface that all notification providers must implement.

use crate::provider_base::ProviderError;
use crate::{
    DeliveryStatus, HealthStatus, NotificationChannel, NotificationContext, NotificationRequest,
    ProviderConfig, ProviderMetrics,
};
use async_trait::async_trait;
use std::sync::Arc;

/// Legacy provider trait - DO NOT USE - use provider_base::NotificationProvider instead
#[async_trait]
pub trait LegacyNotificationProvider: Send + Sync {
    /// Initialize the provider with configuration
    async fn initialize(&mut self, config: ProviderConfig) -> Result<(), LegacyProviderError>;

    /// Send a single notification
    async fn send_notification(
        &self,
        request: NotificationRequest,
    ) -> Result<DeliveryStatus, LegacyProviderError>;

    /// Send multiple notifications in batch (optional optimization)
    async fn send_batch(
        &self,
        requests: Vec<NotificationRequest>,
    ) -> Result<Vec<DeliveryStatus>, LegacyProviderError> {
        let mut results = Vec::new();
        for request in requests {
            results.push(self.send_notification(request).await?);
        }
        Ok(results)
    }

    /// Check provider health status
    async fn health_check(&self) -> Result<HealthStatus, LegacyProviderError>;

    /// Get provider metrics for monitoring
    async fn get_metrics(&self) -> Result<ProviderMetrics, LegacyProviderError>;

    /// Get the channel this provider handles
    fn channel(&self) -> NotificationChannel;

    /// Validate a notification request for this channel
    fn validate_request(&self, request: &NotificationRequest) -> Result<(), LegacyProviderError> {
        // Default validation - providers can override
        if request.target_channels.is_empty() || !request.target_channels.contains(&self.channel())
        {
            return Err(LegacyProviderError::InvalidChannel {
                expected: self.channel(),
                actual: request.target_channels.clone(),
            });
        }

        if let Some(context) = &request.context {
            if context.user_id.is_empty() {
                return Err(LegacyProviderError::ValidationFailed(
                    "user_id cannot be empty".to_string(),
                ));
            }

            if context.alert_id.is_empty() {
                return Err(LegacyProviderError::ValidationFailed(
                    "alert_id cannot be empty".to_string(),
                ));
            }
        } else {
            return Err(LegacyProviderError::ValidationFailed(
                "context cannot be None".to_string(),
            ));
        }

        if let Some(content) = &request.content {
            if content.text_content.is_empty() && content.html_content.is_none() {
                return Err(LegacyProviderError::ValidationFailed(
                    "notification content cannot be empty".to_string(),
                ));
            }
        } else {
            return Err(LegacyProviderError::ValidationFailed(
                "content cannot be None".to_string(),
            ));
        }

        Ok(())
    }

    /// Handle provider shutdown gracefully
    async fn shutdown(&self) -> Result<(), LegacyProviderError> {
        Ok(())
    }
}

/// Legacy error type - DO NOT USE - use provider_base::ProviderError instead
#[derive(Debug, thiserror::Error)]
pub enum LegacyProviderError {
    #[error("Configuration error: {0}")]
    ConfigurationError(String),

    #[error("Connection error: {0}")]
    ConnectionError(String),

    #[error("Authentication error: {0}")]
    AuthenticationError(String),

    #[error("Rate limit exceeded: {0}")]
    RateLimitExceeded(String),

    #[error("Invalid channel - expected {expected:?}, got {actual:?}")]
    InvalidChannel {
        expected: NotificationChannel,
        actual: Vec<NotificationChannel>,
    },

    #[error("Validation failed: {0}")]
    ValidationFailed(String),

    #[error("External service error: {0}")]
    ExternalServiceError(String),

    #[error("Timeout error: {0}")]
    TimeoutError(String),

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("Redis error: {0}")]
    RedisError(#[from] redis::RedisError),

    #[error("NATS error: {0}")]
    NatsError(String),

    #[error("HTTP error: {0}")]
    HttpError(String),

    #[error("Template error: {0}")]
    TemplateError(String),

    #[error("Unknown error: {0}")]
    Unknown(String),
}

impl LegacyProviderError {
    /// Check if the error is retryable
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            LegacyProviderError::ConnectionError(_)
                | LegacyProviderError::TimeoutError(_)
                | LegacyProviderError::ExternalServiceError(_)
                | LegacyProviderError::HttpError(_)
        )
    }

    /// Get error code for logging/monitoring
    pub fn error_code(&self) -> &'static str {
        match self {
            LegacyProviderError::ConfigurationError(_) => "CONFIGURATION_ERROR",
            LegacyProviderError::ConnectionError(_) => "CONNECTION_ERROR",
            LegacyProviderError::AuthenticationError(_) => "AUTHENTICATION_ERROR",
            LegacyProviderError::RateLimitExceeded(_) => "RATE_LIMIT_EXCEEDED",
            LegacyProviderError::InvalidChannel { .. } => "INVALID_CHANNEL",
            LegacyProviderError::ValidationFailed(_) => "VALIDATION_FAILED",
            LegacyProviderError::ExternalServiceError(_) => "EXTERNAL_SERVICE_ERROR",
            LegacyProviderError::TimeoutError(_) => "TIMEOUT_ERROR",
            LegacyProviderError::SerializationError(_) => "SERIALIZATION_ERROR",
            LegacyProviderError::RedisError(_) => "REDIS_ERROR",
            LegacyProviderError::NatsError(_) => "NATS_ERROR",
            LegacyProviderError::HttpError(_) => "HTTP_ERROR",
            LegacyProviderError::TemplateError(_) => "TEMPLATE_ERROR",
            LegacyProviderError::Unknown(_) => "UNKNOWN_ERROR",
        }
    }
}

/// Provider factory trait for dynamic provider creation
#[async_trait]
pub trait ProviderFactory: Send + Sync {
    async fn create_provider(
        &self,
        config: ProviderConfig,
    ) -> Result<Arc<dyn LegacyNotificationProvider>, LegacyProviderError>;
    fn supported_channel(&self) -> NotificationChannel;
}

/// Provider registry for managing multiple providers
#[derive(Default)]
pub struct ProviderRegistry {
    providers: std::collections::HashMap<NotificationChannel, Arc<dyn LegacyNotificationProvider>>,
}

impl ProviderRegistry {
    pub fn new() -> Self {
        Self {
            providers: std::collections::HashMap::new(),
        }
    }

    pub async fn register_provider(&mut self, provider: Arc<dyn LegacyNotificationProvider>) {
        let channel = provider.channel();
        self.providers.insert(channel, provider);
    }

    pub fn get_provider(
        &self,
        channel: &NotificationChannel,
    ) -> Option<&Arc<dyn LegacyNotificationProvider>> {
        self.providers.get(channel)
    }

    pub fn get_all_providers(&self) -> Vec<&Arc<dyn LegacyNotificationProvider>> {
        self.providers.values().collect()
    }

    pub async fn health_check_all(
        &self,
    ) -> std::collections::HashMap<NotificationChannel, Result<HealthStatus, LegacyProviderError>>
    {
        let mut results = std::collections::HashMap::new();

        for (channel, provider) in &self.providers {
            let health = provider.health_check().await;
            results.insert(channel.clone(), health);
        }

        results
    }

    pub async fn get_all_metrics(
        &self,
    ) -> std::collections::HashMap<NotificationChannel, Result<ProviderMetrics, LegacyProviderError>>
    {
        let mut results = std::collections::HashMap::new();

        for (channel, provider) in &self.providers {
            let metrics = provider.get_metrics().await;
            results.insert(channel.clone(), metrics);
        }

        results
    }

    pub async fn shutdown_all(&self) -> Result<(), Vec<LegacyProviderError>> {
        let mut errors = Vec::new();

        for provider in self.providers.values() {
            if let Err(e) = provider.shutdown().await {
                errors.push(e);
            }
        }

        if errors.is_empty() {
            Ok(())
        } else {
            Err(errors)
        }
    }
}

/// Utility trait for provider implementations
pub trait ProviderUtils {
    /// Generate a unique message ID
    fn generate_message_id() -> String {
        uuid::Uuid::new_v4().to_string()
    }

    /// Create a context for internal operations
    fn create_internal_context(provider_name: &str) -> NotificationContext {
        NotificationContext {
            request_id: Self::generate_message_id(),
            user_id: "system".to_string(),
            group_id: None,
            alert_id: format!("{}-internal", provider_name),
            priority: crate::NotificationPriority::Normal,
            timestamp: chrono::Utc::now(),
            retry_count: 0,
            correlation_id: None,
        }
    }
}

// Blanket implementation for all types
impl<T> ProviderUtils for T {}
