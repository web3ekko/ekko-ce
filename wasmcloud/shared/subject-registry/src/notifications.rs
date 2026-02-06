//! Notification Subject Patterns
//!
//! Subject hierarchy for notification delivery (from PRD-NATS-Task-Queue-System-USDT.md §B.2):
//! ```text
//! notifications.send.immediate.{channel}     # Immediate notification delivery
//! notifications.send.digest.{channel}        # Digest notification delivery
//! notifications.retry.{delivery_id}          # Failed notification retry
//! notifications.delivered.{user_id}          # Delivery confirmations
//! notifications.failed.{delivery_id}         # Dead letter queue
//! notifications.inbox.{user_id}              # In-app real-time notifications
//! ```

/// Immediate notification subject - for real-time delivery
///
/// Example: `notifications.send.immediate.email`
pub fn send_immediate(channel: &str) -> String {
    format!("notifications.send.immediate.{}", channel)
}

/// Digest notification subject - for batched delivery
///
/// Example: `notifications.send.digest.email`
pub fn send_digest(channel: &str) -> String {
    format!("notifications.send.digest.{}", channel)
}

/// Notification retry subject - for failed deliveries
///
/// Example: `notifications.retry.delivery-uuid-12345`
pub fn retry(delivery_id: &str) -> String {
    format!("notifications.retry.{}", delivery_id)
}

/// Delivery confirmation subject
///
/// Example: `notifications.delivered.user-uuid-12345`
pub fn delivered(user_id: &str) -> String {
    format!("notifications.delivered.{}", user_id)
}

/// Failed notification subject (dead letter queue)
///
/// Example: `notifications.failed.delivery-uuid-12345`
pub fn failed(delivery_id: &str) -> String {
    format!("notifications.failed.{}", delivery_id)
}

/// In-app notification inbox subject
///
/// Example: `notifications.inbox.user-uuid-12345`
pub fn inbox(user_id: &str) -> String {
    format!("notifications.inbox.{}", user_id)
}

/// Subscription patterns for handlers

/// Pattern for all immediate notifications
pub fn pattern_send_immediate_all() -> &'static str {
    "notifications.send.immediate.>"
}

/// Pattern for all digest notifications
pub fn pattern_send_digest_all() -> &'static str {
    "notifications.send.digest.>"
}

/// Pattern for all send operations (immediate + digest)
pub fn pattern_send_all() -> &'static str {
    "notifications.send.>"
}

/// Pattern for all delivery confirmations
pub fn pattern_delivered_all() -> &'static str {
    "notifications.delivered.>"
}

/// Pattern for all failed notifications
pub fn pattern_failed_all() -> &'static str {
    "notifications.failed.>"
}

/// Pattern for all inbox notifications
pub fn pattern_inbox_all() -> &'static str {
    "notifications.inbox.>"
}

/// Pattern for all notifications (use with caution)
pub fn pattern_notifications_all() -> &'static str {
    "notifications.>"
}

/// Channel-specific patterns

/// Pattern for email notifications (immediate + digest)
pub fn pattern_channel_email() -> &'static str {
    "notifications.send.*.email"
}

/// Pattern for websocket notifications
pub fn pattern_channel_websocket() -> &'static str {
    "notifications.send.*.websocket"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_send_immediate() {
        assert_eq!(
            send_immediate("email"),
            "notifications.send.immediate.email"
        );
        assert_eq!(
            send_immediate("slack"),
            "notifications.send.immediate.slack"
        );
    }

    #[test]
    fn test_send_digest() {
        assert_eq!(
            send_digest("email"),
            "notifications.send.immediate.email".replace("immediate", "digest")
        );
    }

    #[test]
    fn test_inbox() {
        assert_eq!(inbox("user-123"), "notifications.inbox.user-123");
    }
}
