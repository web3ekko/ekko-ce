//! Test utilities for notification providers
//!
//! This module provides common test utilities, fixtures, and mock objects
//! for testing notification providers and related functionality.

#[cfg(test)]
use crate::provider_base::ProviderMetrics;
#[cfg(test)]
use crate::{
    ChannelSettings, DeliveryOptions, DeliveryStatus, GroupNotificationSettings, HealthStatus,
    NotificationAction, NotificationChannel, NotificationContent, NotificationContext,
    NotificationPriority, NotificationRequest, ProviderConfig, QuietHours,
    UserNotificationSettings,
};
#[cfg(test)]
use chrono::{DateTime, Utc};
#[cfg(test)]
use serde_json::json;
#[cfg(test)]
use std::collections::HashMap;
#[cfg(test)]
use uuid::Uuid;

/// Create a test notification request with default values
#[cfg(test)]
pub fn create_test_notification_request() -> NotificationRequest {
    let mut template_variables = HashMap::new();
    template_variables.insert("alert_name".to_string(), "Balance Alert".to_string());
    template_variables.insert("wallet_address".to_string(), "0x1234...5678".to_string());
    template_variables.insert("threshold".to_string(), "10.0".to_string());
    template_variables.insert("current_value".to_string(), "8.5".to_string());

    let mut request = NotificationRequest::new(
        Uuid::new_v4(),
        "test_user_123".to_string(),
        "test_alert_456".to_string(),
        "Balance Alert".to_string(),
        NotificationChannel::Email,
        "Test Alert".to_string(),
        "This is a test notification message".to_string(),
    );

    // Add legacy fields for compatibility
    request.context = Some(NotificationContext::new(
        "test_user_123".to_string(),
        "test_alert_456".to_string(),
        NotificationPriority::Normal,
    ));

    request.content = Some(NotificationContent {
        subject: "Test Alert".to_string(),
        text_content: "This is a test notification message".to_string(),
        html_content: Some(
            "<p>This is a <strong>test</strong> notification message</p>".to_string(),
        ),
        structured_content: Some(json!({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "This is a *test* notification message"
            }
        })),
        embeds: None,
        actions: Some(vec![NotificationAction {
            id: "view_alert".to_string(),
            label: "View Alert".to_string(),
            url: "https://dashboard.ekko.zone/alerts/test_alert_456".to_string(),
            style: Some("primary".to_string()),
        }]),
    });

    request
        .with_variables(template_variables)
        .with_channels(vec![NotificationChannel::Email, NotificationChannel::Slack])
}

/// Create a test notification request for a specific channel
#[cfg(test)]
pub fn create_test_request_for_channel(channel: NotificationChannel) -> NotificationRequest {
    let mut request = create_test_notification_request();
    request.target_channels = vec![channel];
    request
}

/// Create a test notification context
#[cfg(test)]
pub fn create_test_context() -> NotificationContext {
    NotificationContext::new(
        "test_user_123".to_string(),
        "test_alert_456".to_string(),
        NotificationPriority::High,
    )
    .with_correlation_id("test_correlation_123".to_string())
}

/// Create test user notification settings
#[cfg(test)]
pub fn create_test_user_settings() -> UserNotificationSettings {
    let mut settings = UserNotificationSettings::default();
    settings.user_id = "test_user_123".to_string();
    settings.websocket_enabled = true;
    settings.notifications_enabled = true;

    // Email settings
    let mut email_config = HashMap::new();
    email_config.insert("address".to_string(), json!("test@example.com"));
    settings.channels.insert(
        "email".to_string(),
        ChannelSettings {
            enabled: true,
            config: email_config,
        },
    );

    // Slack settings
    let mut slack_config = HashMap::new();
    slack_config.insert("channel".to_string(), json!("#alerts"));
    slack_config.insert(
        "webhook_url".to_string(),
        json!("https://hooks.slack.com/test"),
    );
    settings.channels.insert(
        "slack".to_string(),
        ChannelSettings {
            enabled: true,
            config: slack_config,
        },
    );

    // SMS settings
    let mut sms_config = HashMap::new();
    sms_config.insert("phone".to_string(), json!("+1234567890"));
    settings.channels.insert(
        "sms".to_string(),
        ChannelSettings {
            enabled: true,
            config: sms_config,
        },
    );

    // WebSocket settings (enabled by default)
    settings.channels.insert(
        "websocket".to_string(),
        ChannelSettings {
            enabled: true,
            config: HashMap::new(),
        },
    );

    // Priority routing
    settings.priority_routing.insert(
        "critical".to_string(),
        vec![
            NotificationChannel::WebSocket,
            NotificationChannel::Email,
            NotificationChannel::Sms,
        ],
    );
    settings.priority_routing.insert(
        "high".to_string(),
        vec![NotificationChannel::WebSocket, NotificationChannel::Email],
    );

    // Quiet hours
    settings.quiet_hours = Some(QuietHours {
        start_time: "22:00".to_string(),
        end_time: "08:00".to_string(),
        timezone: "UTC".to_string(),
        enabled: true,
        priority_override: vec![NotificationPriority::Critical],
    });

    settings
}

/// Create test user settings with disabled email
#[cfg(test)]
pub fn create_disabled_email_settings() -> UserNotificationSettings {
    let mut settings = create_test_user_settings();
    if let Some(email_settings) = settings.channels.get_mut("email") {
        email_settings.enabled = false;
    }
    settings
}

/// Create test group notification settings
#[cfg(test)]
pub fn create_test_group_settings() -> GroupNotificationSettings {
    let mut shared_channels = HashMap::new();

    // Shared Slack channel
    let mut slack_config = HashMap::new();
    slack_config.insert("channel".to_string(), json!("#team-alerts"));
    slack_config.insert(
        "webhook_url".to_string(),
        json!("https://hooks.slack.com/team"),
    );
    shared_channels.insert(
        "slack".to_string(),
        ChannelSettings {
            enabled: true,
            config: slack_config,
        },
    );

    GroupNotificationSettings {
        group_id: "team_alpha".to_string(),
        group_name: "Alpha Team".to_string(),
        mandatory_channels: vec![NotificationChannel::WebSocket, NotificationChannel::Slack],
        escalation_rules: HashMap::new(),
        shared_channels,
        member_overrides_allowed: true,
        cached_at: Utc::now(),
    }
}

/// Create a successful delivery status
#[cfg(test)]
pub fn create_successful_delivery_status(channel: NotificationChannel) -> DeliveryStatus {
    DeliveryStatus {
        notification_id: Uuid::new_v4(),
        channel,
        delivered: true,
        delivered_at: Some(Utc::now()),
        error_message: None,
        provider_message_id: Some("test_msg_123".to_string()),
        retry_count: 0,
    }
}

/// Create a failed delivery status
#[cfg(test)]
pub fn create_failed_delivery_status(
    channel: NotificationChannel,
    retry_count: u32,
) -> DeliveryStatus {
    DeliveryStatus {
        notification_id: Uuid::new_v4(),
        channel,
        delivered: false,
        delivered_at: None,
        error_message: Some("Test error message".to_string()),
        provider_message_id: None,
        retry_count,
    }
}

/// Create a health status
#[cfg(test)]
pub fn create_health_status(healthy: bool) -> HealthStatus {
    HealthStatus {
        healthy,
        message: if healthy {
            "All systems operational".to_string()
        } else {
            "Service unavailable".to_string()
        },
        last_check: Utc::now(),
        details: if healthy {
            HashMap::new()
        } else {
            let mut details = HashMap::new();
            details.insert("error".to_string(), json!("Connection failed"));
            details
        },
    }
}

/// Create test provider metrics
#[cfg(test)]
pub fn create_test_provider_metrics(
    _channel: NotificationChannel,
) -> crate::provider_base::ProviderMetrics {
    ProviderMetrics {
        total_sent: 100,
        total_delivered: 95,
        total_failed: 5,
        total_retried: 2,
        avg_latency_ms: 150.5,
        p99_latency_ms: 500.0,
        circuit_breaker_trips: 0,
        last_error: None,
        last_error_time: None,
        last_activity: Some(Utc::now()),
        error_rate_percent: 5.0,
    }
}

/// Create legacy provider metrics from types.rs
#[cfg(test)]
pub fn create_legacy_provider_metrics(
    channel: NotificationChannel,
) -> crate::types::ProviderMetrics {
    crate::types::ProviderMetrics {
        channel,
        total_sent: 100,
        successful_deliveries: 95,
        failed_deliveries: 5,
        average_latency_ms: 150.5,
        last_activity: Utc::now(),
        error_rate_percent: 5.0,
    }
}

/// Create test provider config
#[cfg(test)]
pub fn create_test_provider_config(channel: NotificationChannel) -> ProviderConfig {
    let mut provider_settings = HashMap::new();

    match channel {
        NotificationChannel::Email => {
            provider_settings.insert("api_key".to_string(), json!("test_api_key"));
            provider_settings.insert("from_email".to_string(), json!("test@ekko.zone"));
        }
        NotificationChannel::Slack => {
            provider_settings.insert("bot_token".to_string(), json!("xoxb-test-token"));
        }
        NotificationChannel::Sms => {
            provider_settings.insert("account_sid".to_string(), json!("test_sid"));
            provider_settings.insert("auth_token".to_string(), json!("test_token"));
            provider_settings.insert("from_number".to_string(), json!("+1234567890"));
        }
        _ => {
            provider_settings.insert("test_key".to_string(), json!("test_value"));
        }
    }

    ProviderConfig {
        channel,
        redis_url: "redis://localhost:6379".to_string(),
        nats_url: "nats://localhost:4222".to_string(),
        provider_settings,
    }
}

/// Mock Redis responses for testing
#[cfg(test)]
pub mod redis_mocks {
    use super::*;

    pub fn user_settings_json(user_id: &str) -> String {
        let settings = create_test_user_settings();
        let mut settings_with_id = settings;
        settings_with_id.user_id = user_id.to_string();
        serde_json::to_string(&settings_with_id).unwrap()
    }

    pub fn group_settings_json(group_id: &str) -> String {
        let settings = create_test_group_settings();
        let mut settings_with_id = settings;
        settings_with_id.group_id = group_id.to_string();
        serde_json::to_string(&settings_with_id).unwrap()
    }
}

/// Test helper for async operations with timeout
#[cfg(test)]
pub async fn with_timeout<F, T>(
    future: F,
    timeout_ms: u64,
) -> Result<T, tokio::time::error::Elapsed>
where
    F: std::future::Future<Output = T>,
{
    tokio::time::timeout(std::time::Duration::from_millis(timeout_ms), future).await
}

/// Test helper for creating mock HTTP responses
#[cfg(test)]
pub mod http_mocks {
    use wiremock::{
        matchers::{method, path},
        Mock, ResponseTemplate,
    };

    pub fn success_response() -> ResponseTemplate {
        ResponseTemplate::new(200).set_body_json(serde_json::json!({
            "success": true,
            "message_id": "test_msg_123"
        }))
    }

    pub fn error_response(status: u16, error_message: &str) -> ResponseTemplate {
        ResponseTemplate::new(status).set_body_json(serde_json::json!({
            "error": {
                "message": error_message,
                "code": "TEST_ERROR"
            }
        }))
    }

    pub fn rate_limit_response() -> ResponseTemplate {
        ResponseTemplate::new(429)
            .append_header("retry-after", "60")
            .set_body_json(serde_json::json!({
                "error": {
                    "message": "Rate limit exceeded",
                    "code": "RATE_LIMIT_EXCEEDED"
                }
            }))
    }
}

/// Test helper for creating temporary files
#[cfg(test)]
pub fn create_temp_file_with_content(content: &str) -> tempfile::NamedTempFile {
    use std::io::Write;

    let mut temp_file = tempfile::NamedTempFile::new().expect("Failed to create temp file");
    temp_file
        .write_all(content.as_bytes())
        .expect("Failed to write to temp file");
    temp_file.flush().expect("Failed to flush temp file");
    temp_file
}

/// Test helper for asserting delivery status types
#[cfg(test)]
pub mod assertions {
    use super::*;

    pub fn assert_delivery_successful(status: &DeliveryStatus) {
        if !status.delivered {
            panic!("Expected successful delivery, got: {:?}", status);
        }
    }

    pub fn assert_delivery_failed(status: &DeliveryStatus, expected_has_error: bool) {
        if status.delivered {
            panic!("Expected failed delivery, got: {:?}", status);
        }
        if expected_has_error {
            assert!(status.error_message.is_some(), "Expected error message");
        }
    }

    pub fn assert_channel_disabled(
        status: &DeliveryStatus,
        expected_channel: &NotificationChannel,
    ) {
        if status.delivered {
            panic!(
                "Expected channel disabled (failed delivery), got: {:?}",
                status
            );
        }
        assert_eq!(&status.channel, expected_channel);
    }
}

/// Generate test data for load testing
#[cfg(test)]
pub struct TestDataGenerator;

#[cfg(test)]
impl TestDataGenerator {
    pub fn generate_notification_requests(count: usize) -> Vec<NotificationRequest> {
        (0..count)
            .map(|i| {
                let priority = if i % 4 == 0 {
                    NotificationPriority::Critical
                } else {
                    NotificationPriority::Normal
                };

                let mut request = NotificationRequest::new(
                    Uuid::new_v4(),
                    format!("user_{}", i),
                    format!("alert_{}", i),
                    format!("Test Alert #{}", i),
                    NotificationChannel::Email,
                    format!("Test Alert #{}", i),
                    format!("This is test message number {}", i),
                );

                request.priority = priority.clone();

                // Add legacy fields
                request.context = Some(NotificationContext::new(
                    format!("user_{}", i),
                    format!("alert_{}", i),
                    priority,
                ));

                request.content = Some(NotificationContent {
                    subject: format!("Test Alert #{}", i),
                    text_content: format!("This is test message number {}", i),
                    html_content: Some(format!(
                        "<p>This is test message number <strong>{}</strong></p>",
                        i
                    )),
                    structured_content: None,
                    embeds: None,
                    actions: None,
                });

                request.with_channels(vec![NotificationChannel::Email])
            })
            .collect()
    }

    pub fn generate_user_settings(count: usize) -> Vec<UserNotificationSettings> {
        (0..count)
            .map(|i| {
                let mut settings = create_test_user_settings();
                settings.user_id = format!("user_{}", i);

                // Vary settings for testing
                if i % 3 == 0 {
                    settings.websocket_enabled = false;
                }
                if i % 5 == 0 {
                    if let Some(email_settings) = settings.channels.get_mut("email") {
                        email_settings.enabled = false;
                    }
                }

                settings
            })
            .collect()
    }
}
