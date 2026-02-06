use crate::connections::ConnectionManager;
use crate::redis_client::RedisClient;
use crate::types::{
    NatsEvent, NatsNotification, NotificationAction, NotificationPriority, ServerMessage,
};
use anyhow::Result;
use async_nats::{Client, Message, Subscriber};
use chrono::{DateTime, Utc};
use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::select;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

#[cfg(test)]
use mockall::{automock, predicate::*};

/// Trait for sending messages to WebSocket connections (for testing)
#[cfg_attr(test, automock)]
#[async_trait::async_trait]
pub trait MessageSender: Send + Sync {
    async fn send_to_connection(&self, connection_id: &str, message: ServerMessage) -> Result<()>;
    async fn send_to_user(&self, user_id: &str, message: ServerMessage) -> Result<usize>;
}

/// NATS handler for receiving and routing notifications
pub struct NatsHandler {
    client: Client,
    connection_manager: Arc<ConnectionManager>,
    message_sender: Arc<dyn MessageSender>,
    redis_client: Arc<RedisClient>,
}

const LEGACY_NOTIFICATION_SUBJECT: &str = "notifications.websocket";
const IMMEDIATE_NOTIFICATION_SUBJECT: &str = "notifications.send.immediate.websocket";
const DIGEST_NOTIFICATION_SUBJECT: &str = "notifications.send.digest.websocket";
const DIRECT_NOTIFICATION_SUBJECT: &str = "notifications.send.websocket";
const EVENT_SUBJECT: &str = "ws.events";

#[derive(Debug, Clone, Serialize, Deserialize)]
struct DeliveryRequest {
    pub user_id: String,
    #[serde(default)]
    pub alert_id: Option<String>,
    #[serde(default)]
    pub subject: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
    #[serde(default)]
    pub template: Option<String>,
    #[serde(default)]
    pub variables: HashMap<String, String>,
    #[serde(default)]
    pub priority: Option<NotificationPriority>,
    #[serde(default)]
    pub channel: Option<String>,
    #[serde(default)]
    pub channel_config: HashMap<String, String>,
    #[serde(default)]
    pub timestamp: Option<String>,
}

impl NatsHandler {
    pub fn new(
        client: Client,
        connection_manager: Arc<ConnectionManager>,
        message_sender: Arc<dyn MessageSender>,
        redis_client: Arc<RedisClient>,
    ) -> Self {
        Self {
            client,
            connection_manager,
            message_sender,
            redis_client,
        }
    }

    /// Subscribe to notification subjects and start processing
    pub async fn start(&self) -> Result<()> {
        // Subscribe to legacy and current notification subjects
        let legacy_subscriber = self.client.subscribe(LEGACY_NOTIFICATION_SUBJECT).await?;
        info!("Subscribed to {}", LEGACY_NOTIFICATION_SUBJECT);

        let immediate_subscriber = self
            .client
            .subscribe(IMMEDIATE_NOTIFICATION_SUBJECT)
            .await?;
        info!("Subscribed to {}", IMMEDIATE_NOTIFICATION_SUBJECT);

        let digest_subscriber = self.client.subscribe(DIGEST_NOTIFICATION_SUBJECT).await?;
        info!("Subscribed to {}", DIGEST_NOTIFICATION_SUBJECT);

        let direct_subscriber = self.client.subscribe(DIRECT_NOTIFICATION_SUBJECT).await?;
        info!("Subscribed to {}", DIRECT_NOTIFICATION_SUBJECT);

        let event_subscriber = self.client.subscribe(EVENT_SUBJECT).await?;
        info!(
            "Subscribed to {} (Phase 1: NLP progress events)",
            EVENT_SUBJECT
        );

        // Process both streams concurrently
        self.process_all_messages(
            legacy_subscriber,
            immediate_subscriber,
            digest_subscriber,
            direct_subscriber,
            event_subscriber,
        )
        .await
    }

    /// Process both notification and event streams concurrently
    async fn process_all_messages(
        &self,
        mut legacy_subscriber: Subscriber,
        mut immediate_subscriber: Subscriber,
        mut digest_subscriber: Subscriber,
        mut direct_subscriber: Subscriber,
        mut event_subscriber: Subscriber,
    ) -> Result<()> {
        loop {
            select! {
                Some(message) = legacy_subscriber.next() => {
                    if let Err(e) = self.handle_notification(message).await {
                        error!("Error handling notification: {}", e);
                    }
                }
                Some(message) = immediate_subscriber.next() => {
                    if let Err(e) = self.handle_notification(message).await {
                        error!("Error handling notification: {}", e);
                    }
                }
                Some(message) = digest_subscriber.next() => {
                    if let Err(e) = self.handle_notification(message).await {
                        error!("Error handling notification: {}", e);
                    }
                }
                Some(message) = direct_subscriber.next() => {
                    if let Err(e) = self.handle_notification(message).await {
                        error!("Error handling notification: {}", e);
                    }
                }
                Some(message) = event_subscriber.next() => {
                    if let Err(e) = self.handle_event(message).await {
                        error!("Error handling event: {}", e);
                    }
                }
                else => break,
            }
        }
        Ok(())
    }

    /// Handle ws.events messages (Phase 1: NLP progress, etc.)
    pub async fn handle_event(&self, message: Message) -> Result<()> {
        // Parse the NATS event
        let event: NatsEvent = serde_json::from_slice(&message.payload)?;

        debug!(
            "Received event {} for user {} (job: {:?})",
            event.event_type, event.user_id, event.job_id
        );

        // Get user's connections
        let connections = self
            .connection_manager
            .get_user_connections(&event.user_id)
            .await;

        if connections.is_empty() {
            debug!(
                "No active connections for user {} (event: {})",
                event.user_id, event.event_type
            );
            // Don't queue events - they are ephemeral progress updates
            return Ok(());
        }

        // Convert to WebSocket message
        let ws_message = ServerMessage::Event {
            event_type: event.event_type.clone(),
            job_id: event.job_id.clone(),
            payload: event.payload,
            timestamp: event.timestamp,
        };

        // Send to all user's connections
        let sent_count = self
            .message_sender
            .send_to_user(&event.user_id, ws_message)
            .await?;

        info!(
            "Delivered event {} to {} connections for user {}",
            event.event_type, sent_count, event.user_id
        );

        Ok(())
    }

    /// Process incoming notifications (legacy method for backward compatibility)
    #[allow(dead_code)]
    async fn process_notifications(&self, mut subscriber: Subscriber) -> Result<()> {
        while let Some(message) = subscriber.next().await {
            if let Err(e) = self.handle_notification(message).await {
                error!("Error handling notification: {}", e);
            }
        }
        Ok(())
    }

    /// Handle a single notification message
    pub async fn handle_notification(&self, message: Message) -> Result<()> {
        let subject = message.subject.to_string();
        if subject.starts_with("notifications.send.") {
            let request: DeliveryRequest = serde_json::from_slice(&message.payload)?;
            let priority = request
                .priority
                .clone()
                .unwrap_or(NotificationPriority::Normal);
            let user_id = request.user_id.clone();
            let queue_payload = serde_json::to_string(&request)?;
            let ws_message = self.convert_delivery_request_to_websocket_message(request);
            self.deliver_to_user(&user_id, ws_message, priority, queue_payload)
                .await
        } else {
            let nats_notification: NatsNotification = serde_json::from_slice(&message.payload)?;
            let queue_payload = serde_json::to_string(&nats_notification)?;
            let ws_message = self.convert_to_websocket_message(nats_notification.clone());
            self.deliver_to_user(
                &nats_notification.user_id,
                ws_message,
                nats_notification.priority,
                queue_payload,
            )
            .await
        }
    }

    async fn deliver_to_user(
        &self,
        user_id: &str,
        ws_message: ServerMessage,
        priority: NotificationPriority,
        queue_payload: String,
    ) -> Result<()> {
        // Check if user has WebSocket notifications enabled
        match self
            .redis_client
            .is_websocket_enabled_for_user(&user_id)
            .await
        {
            Ok(enabled) => {
                if !enabled {
                    debug!("WebSocket notifications disabled for user {}", user_id);
                    return Ok(());
                }
            }
            Err(e) => {
                warn!(
                    "Failed to check WebSocket settings for user {}: {}. Defaulting to enabled.",
                    user_id, e
                );
                // Continue with delivery on error (fail-safe)
            }
        }

        // Check if user is in quiet hours (unless priority can override)
        let priority_str = format!("{:?}", priority).to_lowercase();
        match self.redis_client.is_user_in_quiet_hours(&user_id).await {
            Ok(in_quiet_hours) => {
                if in_quiet_hours {
                    // Check if this priority can override quiet hours
                    match self
                        .redis_client
                        .can_override_quiet_hours(&user_id, &priority_str)
                        .await
                    {
                        Ok(can_override) => {
                            if !can_override {
                                debug!(
                                    "User {} in quiet hours, notification blocked (priority: {})",
                                    user_id, priority_str
                                );

                                if let Err(e) =
                                    self.queue_missed_payload(&user_id, &queue_payload).await
                                {
                                    warn!("Failed to queue missed notification: {}", e);
                                }

                                return Ok(());
                            } else {
                                debug!(
                                    "User {} in quiet hours but priority {} overrides",
                                    user_id, priority_str
                                );
                            }
                        }
                        Err(e) => {
                            warn!(
                                "Failed to check priority override for user {}: {}. Delivering notification.",
                                user_id, e
                            );
                        }
                    }
                }
            }
            Err(e) => {
                warn!(
                    "Failed to check quiet hours for user {}: {}. Delivering notification.",
                    user_id, e
                );
            }
        }

        // Get user's connections
        let connections = self.connection_manager.get_user_connections(user_id).await;
        if connections.is_empty() {
            debug!("No active connections for user {}", user_id);

            if let Err(e) = self.queue_missed_payload(user_id, &queue_payload).await {
                warn!("Failed to queue missed notification: {}", e);
            }

            return Ok(());
        }

        // Send to all user's connections
        let sent_count = self
            .message_sender
            .send_to_user(user_id, ws_message)
            .await?;

        // Update delivery statistics
        let delivered = sent_count > 0;
        if let Err(e) = self
            .redis_client
            .update_user_notification_stats(user_id, "websocket", delivered)
            .await
        {
            warn!("Failed to update notification stats: {}", e);
        }

        info!(
            "Delivered notification to {} connections for user {}",
            sent_count, user_id
        );

        Ok(())
    }

    /// Queue notification for later delivery when user is offline
    async fn queue_missed_payload(&self, user_id: &str, payload: &str) -> Result<()> {
        self.redis_client
            .queue_missed_message(user_id, payload, 3600)
            .await?;
        debug!("Queued missed notification for user {}", user_id);
        Ok(())
    }

    /// Convert NATS notification to WebSocket message
    fn convert_to_websocket_message(&self, notification: NatsNotification) -> ServerMessage {
        let mut details = HashMap::new();

        // Clone values that need to be used multiple times
        let triggered_value = notification.payload.triggered_value.clone();
        let threshold = notification.payload.threshold.clone();

        details.insert(
            "current_value".to_string(),
            serde_json::Value::String(triggered_value.clone()),
        );
        details.insert(
            "threshold".to_string(),
            serde_json::Value::String(threshold.clone()),
        );
        details.insert(
            "chain".to_string(),
            serde_json::Value::String(notification.payload.chain.clone()),
        );
        details.insert(
            "wallet".to_string(),
            serde_json::Value::String(notification.payload.wallet),
        );

        if let Some(tx_hash) = notification.payload.transaction_hash {
            details.insert(
                "transaction_hash".to_string(),
                serde_json::Value::String(tx_hash.clone()),
            );

            // Add transaction URL based on chain
            let tx_url = self.get_transaction_url(&notification.payload.chain, &tx_hash);
            details.insert(
                "transaction_url".to_string(),
                serde_json::Value::String(tx_url),
            );
        }

        if let Some(block_number) = notification.payload.block_number {
            details.insert(
                "block_number".to_string(),
                serde_json::Value::Number(block_number.into()),
            );
        }

        ServerMessage::Notification {
            id: format!("notif_{}", Uuid::new_v4()),
            alert_id: notification.alert_id.clone(),
            alert_name: notification.alert_name,
            priority: notification.priority,
            message: format!(
                "Alert triggered: {} exceeded {}",
                triggered_value, threshold
            ),
            details,
            timestamp: notification.timestamp,
            actions: vec![
                NotificationAction {
                    label: "View Transaction".to_string(),
                    url: format!("/alerts/{}/transactions", notification.alert_id),
                },
                NotificationAction {
                    label: "Adjust Alert".to_string(),
                    url: format!("/alerts/{}/edit", notification.alert_id),
                },
            ],
        }
    }

    fn convert_delivery_request_to_websocket_message(
        &self,
        request: DeliveryRequest,
    ) -> ServerMessage {
        let alert_id = request.alert_id.unwrap_or_default();
        let alert_name = request
            .subject
            .clone()
            .unwrap_or_else(|| "Alert Notification".to_string());
        let message = request
            .message
            .clone()
            .unwrap_or_else(|| alert_name.clone());
        let priority = request
            .priority
            .clone()
            .unwrap_or(NotificationPriority::Normal);
        let timestamp = parse_timestamp(request.timestamp.as_deref());

        let mut details = HashMap::new();
        for (key, value) in request.variables {
            details.insert(key, serde_json::Value::String(value));
        }

        if let Some(subject) = request.subject {
            details.insert("subject".to_string(), serde_json::Value::String(subject));
        }

        if let Some(template) = request.template {
            details.insert("template".to_string(), serde_json::Value::String(template));
        }

        if let Some(channel) = request.channel {
            details.insert("channel".to_string(), serde_json::Value::String(channel));
        }

        if !request.channel_config.is_empty() {
            match serde_json::to_value(request.channel_config) {
                Ok(value) => {
                    details.insert("channel_config".to_string(), value);
                }
                Err(e) => {
                    warn!("Failed to serialize channel config: {}", e);
                }
            }
        }

        let actions = if alert_id.is_empty() {
            Vec::new()
        } else {
            vec![
                NotificationAction {
                    label: "View Alert".to_string(),
                    url: format!("/alerts/{}", alert_id),
                },
                NotificationAction {
                    label: "Adjust Alert".to_string(),
                    url: format!("/alerts/{}/edit", alert_id),
                },
            ]
        };

        ServerMessage::Notification {
            id: format!("notif_{}", Uuid::new_v4()),
            alert_id,
            alert_name,
            priority,
            message,
            details,
            timestamp,
            actions,
        }
    }

    /// Get block explorer URL for transaction
    fn get_transaction_url(&self, chain: &str, tx_hash: &str) -> String {
        match chain.to_lowercase().as_str() {
            "ethereum" => format!("https://etherscan.io/tx/{}", tx_hash),
            "polygon" => format!("https://polygonscan.com/tx/{}", tx_hash),
            "avalanche" => format!("https://snowtrace.io/tx/{}", tx_hash),
            "arbitrum" => format!("https://arbiscan.io/tx/{}", tx_hash),
            "bitcoin" => format!("https://blockstream.info/tx/{}", tx_hash),
            "solana" => format!("https://solscan.io/tx/{}", tx_hash),
            _ => format!("/tx/{}", tx_hash),
        }
    }

    /// Check if notification passes user's filters
    pub fn should_send_notification(
        &self,
        notification: &NatsNotification,
        filters: &crate::types::NotificationFilters,
    ) -> bool {
        // Check priority filter
        if let Some(ref priorities) = filters.priorities {
            if !priorities.contains(&notification.priority) {
                debug!(
                    "Notification filtered by priority: {:?} not in {:?}",
                    notification.priority, priorities
                );
                return false;
            }
        }

        // Check alert ID filter
        if let Some(ref alert_ids) = filters.alert_ids {
            if !alert_ids.contains(&notification.alert_id) {
                debug!(
                    "Notification filtered by alert_id: {} not in {:?}",
                    notification.alert_id, alert_ids
                );
                return false;
            }
        }

        // Check chain filter
        if let Some(ref chains) = filters.chains {
            if !chains.contains(&notification.payload.chain) {
                debug!(
                    "Notification filtered by chain: {} not in {:?}",
                    notification.payload.chain, chains
                );
                return false;
            }
        }

        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{NotificationFilters, NotificationPayload};
    use chrono::Utc;

    // Helper struct for testing without NATS connection
    struct TestHandler {
        connection_manager: Arc<ConnectionManager>,
        message_sender: Arc<MockMessageSender>,
    }

    impl TestHandler {
        fn new() -> Self {
            Self {
                connection_manager: Arc::new(ConnectionManager::new()),
                message_sender: Arc::new(MockMessageSender::new()),
            }
        }

        // Copy of the convert_to_websocket_message function for testing
        fn convert_to_websocket_message(&self, notification: NatsNotification) -> ServerMessage {
            let mut details = HashMap::new();

            let triggered_value = notification.payload.triggered_value.clone();
            let threshold = notification.payload.threshold.clone();

            details.insert(
                "current_value".to_string(),
                serde_json::Value::String(triggered_value.clone()),
            );
            details.insert(
                "threshold".to_string(),
                serde_json::Value::String(threshold.clone()),
            );
            details.insert(
                "chain".to_string(),
                serde_json::Value::String(notification.payload.chain.clone()),
            );
            details.insert(
                "wallet".to_string(),
                serde_json::Value::String(notification.payload.wallet),
            );

            if let Some(tx_hash) = notification.payload.transaction_hash {
                details.insert(
                    "transaction_hash".to_string(),
                    serde_json::Value::String(tx_hash.clone()),
                );

                let tx_url = self.get_transaction_url(&notification.payload.chain, &tx_hash);
                details.insert(
                    "transaction_url".to_string(),
                    serde_json::Value::String(tx_url),
                );
            }

            if let Some(block_number) = notification.payload.block_number {
                details.insert(
                    "block_number".to_string(),
                    serde_json::Value::Number(block_number.into()),
                );
            }

            ServerMessage::Notification {
                id: format!("notif_{}", Uuid::new_v4()),
                alert_id: notification.alert_id.clone(),
                alert_name: notification.alert_name,
                priority: notification.priority,
                message: format!(
                    "Alert triggered: {} exceeded {}",
                    triggered_value, threshold
                ),
                details,
                timestamp: notification.timestamp,
                actions: vec![
                    NotificationAction {
                        label: "View Transaction".to_string(),
                        url: format!("/alerts/{}/transactions", notification.alert_id),
                    },
                    NotificationAction {
                        label: "Adjust Alert".to_string(),
                        url: format!("/alerts/{}/edit", notification.alert_id),
                    },
                ],
            }
        }

        fn get_transaction_url(&self, chain: &str, tx_hash: &str) -> String {
            match chain.to_lowercase().as_str() {
                "ethereum" => format!("https://etherscan.io/tx/{}", tx_hash),
                "polygon" => format!("https://polygonscan.com/tx/{}", tx_hash),
                "avalanche" => format!("https://snowtrace.io/tx/{}", tx_hash),
                "arbitrum" => format!("https://arbiscan.io/tx/{}", tx_hash),
                "bitcoin" => format!("https://blockstream.info/tx/{}", tx_hash),
                "solana" => format!("https://solscan.io/tx/{}", tx_hash),
                _ => format!("/tx/{}", tx_hash),
            }
        }

        fn should_send_notification(
            &self,
            notification: &NatsNotification,
            filters: &NotificationFilters,
        ) -> bool {
            // Check priority filter
            if let Some(ref priorities) = filters.priorities {
                if !priorities.contains(&notification.priority) {
                    return false;
                }
            }

            // Check alert ID filter
            if let Some(ref alert_ids) = filters.alert_ids {
                if !alert_ids.contains(&notification.alert_id) {
                    return false;
                }
            }

            // Check chain filter
            if let Some(ref chains) = filters.chains {
                if !chains.contains(&notification.payload.chain) {
                    return false;
                }
            }

            true
        }

        fn convert_delivery_request_to_websocket_message(
            &self,
            request: DeliveryRequest,
        ) -> ServerMessage {
            let alert_id = request.alert_id.unwrap_or_default();
            let alert_name = request
                .subject
                .clone()
                .unwrap_or_else(|| "Alert Notification".to_string());
            let message = request
                .message
                .clone()
                .unwrap_or_else(|| alert_name.clone());
            let priority = request
                .priority
                .clone()
                .unwrap_or(NotificationPriority::Normal);
            let timestamp = parse_timestamp(request.timestamp.as_deref());

            let mut details = HashMap::new();
            for (key, value) in request.variables {
                details.insert(key, serde_json::Value::String(value));
            }

            if let Some(subject) = request.subject {
                details.insert("subject".to_string(), serde_json::Value::String(subject));
            }

            if let Some(template) = request.template {
                details.insert("template".to_string(), serde_json::Value::String(template));
            }

            if let Some(channel) = request.channel {
                details.insert("channel".to_string(), serde_json::Value::String(channel));
            }

            if !request.channel_config.is_empty() {
                if let Ok(value) = serde_json::to_value(request.channel_config) {
                    details.insert("channel_config".to_string(), value);
                }
            }

            let actions = if alert_id.is_empty() {
                Vec::new()
            } else {
                vec![
                    NotificationAction {
                        label: "View Alert".to_string(),
                        url: format!("/alerts/{}", alert_id),
                    },
                    NotificationAction {
                        label: "Adjust Alert".to_string(),
                        url: format!("/alerts/{}/edit", alert_id),
                    },
                ]
            };

            ServerMessage::Notification {
                id: format!("notif_{}", Uuid::new_v4()),
                alert_id,
                alert_name,
                priority,
                message,
                details,
                timestamp,
                actions,
            }
        }
    }

    fn create_test_notification() -> NatsNotification {
        NatsNotification {
            user_id: "user_123".to_string(),
            alert_id: "alert_456".to_string(),
            alert_name: "AVAX Balance Alert".to_string(),
            notification_type: "alert_triggered".to_string(),
            priority: NotificationPriority::High,
            payload: NotificationPayload {
                triggered_value: "15.5".to_string(),
                threshold: "10".to_string(),
                transaction_hash: Some("0xabc123".to_string()),
                chain: "avalanche".to_string(),
                wallet: "0xwallet123".to_string(),
                block_number: Some(12345678),
            },
            timestamp: Utc::now(),
        }
    }

    fn create_test_delivery_request() -> DeliveryRequest {
        DeliveryRequest {
            user_id: "user_456".to_string(),
            alert_id: Some("alert_789".to_string()),
            subject: Some("Balance Threshold".to_string()),
            message: Some("Balance exceeded threshold".to_string()),
            template: Some("threshold_template".to_string()),
            variables: HashMap::from([
                ("wallet".to_string(), "0xwallet456".to_string()),
                ("threshold".to_string(), "10".to_string()),
            ]),
            priority: Some(NotificationPriority::Critical),
            channel: Some("websocket".to_string()),
            channel_config: HashMap::from([("mode".to_string(), "immediate".to_string())]),
            timestamp: Some("2025-01-07T10:30:00Z".to_string()),
        }
    }

    #[test]
    fn test_message_routing() {
        let handler = TestHandler::new();
        let notification = create_test_notification();
        let ws_message = handler.convert_to_websocket_message(notification);

        match ws_message {
            ServerMessage::Notification {
                alert_id,
                alert_name,
                priority,
                details,
                ..
            } => {
                assert_eq!(alert_id, "alert_456");
                assert_eq!(alert_name, "AVAX Balance Alert");
                assert_eq!(priority, NotificationPriority::High);
                assert!(details.contains_key("current_value"));
                assert!(details.contains_key("threshold"));
                assert!(details.contains_key("chain"));
                assert!(details.contains_key("transaction_url"));
            }
            _ => panic!("Expected Notification message"),
        }
    }

    #[test]
    fn test_delivery_request_conversion() {
        let handler = TestHandler::new();
        let request = create_test_delivery_request();
        let ws_message = handler.convert_delivery_request_to_websocket_message(request);

        match ws_message {
            ServerMessage::Notification {
                alert_id,
                alert_name,
                priority,
                details,
                message,
                ..
            } => {
                assert_eq!(alert_id, "alert_789");
                assert_eq!(alert_name, "Balance Threshold");
                assert_eq!(priority, NotificationPriority::Critical);
                assert_eq!(message, "Balance exceeded threshold");
                assert_eq!(
                    details.get("wallet"),
                    Some(&serde_json::Value::String("0xwallet456".to_string()))
                );
                assert_eq!(
                    details.get("threshold"),
                    Some(&serde_json::Value::String("10".to_string()))
                );
                assert!(details.contains_key("channel_config"));
            }
            _ => panic!("Expected Notification message"),
        }
    }

    #[test]
    fn test_message_delivery() {
        let handler = TestHandler::new();
        let notification = create_test_notification();

        // Test conversion
        let ws_message = handler.convert_to_websocket_message(notification.clone());

        if let ServerMessage::Notification { message, .. } = ws_message {
            assert!(message.contains("Alert triggered"));
            assert!(message.contains("15.5"));
            assert!(message.contains("10"));
        } else {
            panic!("Expected Notification message");
        }
    }

    #[test]
    fn test_transaction_url_generation() {
        let handler = TestHandler::new();

        // Test various chains
        assert_eq!(
            handler.get_transaction_url("ethereum", "0x123"),
            "https://etherscan.io/tx/0x123"
        );
        assert_eq!(
            handler.get_transaction_url("avalanche", "0x456"),
            "https://snowtrace.io/tx/0x456"
        );
        assert_eq!(
            handler.get_transaction_url("bitcoin", "abc123"),
            "https://blockstream.info/tx/abc123"
        );
        assert_eq!(
            handler.get_transaction_url("solana", "sig123"),
            "https://solscan.io/tx/sig123"
        );
        assert_eq!(handler.get_transaction_url("unknown", "0x789"), "/tx/0x789");
    }

    #[test]
    fn test_priority_filtering() {
        let handler = TestHandler::new();

        let notification = create_test_notification();

        // Test with matching priority filter
        let filters = NotificationFilters {
            priorities: Some(vec![
                NotificationPriority::High,
                NotificationPriority::Critical,
            ]),
            alert_ids: None,
            chains: None,
        };
        assert!(handler.should_send_notification(&notification, &filters));

        // Test with non-matching priority filter
        let filters = NotificationFilters {
            priorities: Some(vec![NotificationPriority::Low]),
            alert_ids: None,
            chains: None,
        };
        assert!(!handler.should_send_notification(&notification, &filters));
    }

    #[test]
    fn test_alert_id_filtering() {
        let handler = TestHandler::new();

        let notification = create_test_notification();

        // Test with matching alert ID filter
        let filters = NotificationFilters {
            priorities: None,
            alert_ids: Some(vec!["alert_456".to_string(), "alert_789".to_string()]),
            chains: None,
        };
        assert!(handler.should_send_notification(&notification, &filters));

        // Test with non-matching alert ID filter
        let filters = NotificationFilters {
            priorities: None,
            alert_ids: Some(vec!["alert_999".to_string()]),
            chains: None,
        };
        assert!(!handler.should_send_notification(&notification, &filters));
    }

    #[test]
    fn test_chain_filtering() {
        let handler = TestHandler::new();

        let notification = create_test_notification();

        // Test with matching chain filter
        let filters = NotificationFilters {
            priorities: None,
            alert_ids: None,
            chains: Some(vec!["avalanche".to_string(), "ethereum".to_string()]),
        };
        assert!(handler.should_send_notification(&notification, &filters));

        // Test with non-matching chain filter
        let filters = NotificationFilters {
            priorities: None,
            alert_ids: None,
            chains: Some(vec!["bitcoin".to_string()]),
        };
        assert!(!handler.should_send_notification(&notification, &filters));
    }

    #[test]
    fn test_combined_filtering() {
        let handler = TestHandler::new();

        let notification = create_test_notification();

        // Test with all filters matching
        let filters = NotificationFilters {
            priorities: Some(vec![NotificationPriority::High]),
            alert_ids: Some(vec!["alert_456".to_string()]),
            chains: Some(vec!["avalanche".to_string()]),
        };
        assert!(handler.should_send_notification(&notification, &filters));

        // Test with one filter not matching
        let filters = NotificationFilters {
            priorities: Some(vec![NotificationPriority::Low]), // Doesn't match
            alert_ids: Some(vec!["alert_456".to_string()]),
            chains: Some(vec!["avalanche".to_string()]),
        };
        assert!(!handler.should_send_notification(&notification, &filters));
    }

    #[test]
    fn test_no_filters() {
        let handler = TestHandler::new();

        let notification = create_test_notification();

        // Test with no filters (should pass everything)
        let filters = NotificationFilters::default();
        assert!(handler.should_send_notification(&notification, &filters));
    }
}

fn parse_timestamp(timestamp: Option<&str>) -> DateTime<Utc> {
    if let Some(ts) = timestamp {
        if let Ok(parsed) = DateTime::parse_from_rfc3339(ts) {
            return parsed.with_timezone(&Utc);
        }
    }

    Utc::now()
}
