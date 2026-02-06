use crate::types::{
    NatsNotification, NotificationPayload, SlackBlock, SlackElement, SlackMessage, SlackText,
};

/// Format notification as rich Slack message with Block Kit
pub fn format_slack_message(notification: &NatsNotification) -> SlackMessage {
    let priority_emoji = notification.priority.emoji();
    let priority_color = notification.priority.slack_color();

    // Header with alert name and priority emoji
    let header_text = format!("{} {}", priority_emoji, notification.alert_name);

    // Main message text
    let main_text = format_main_text(&notification.payload);

    // Transaction details
    let detail_fields = build_detail_fields(&notification.payload);

    // Context footer
    let context_text = format!(
        "Alert ID: {} | {}",
        notification.alert_id,
        notification.timestamp.format("%Y-%m-%d %H:%M:%S UTC")
    );

    SlackMessage {
        text: format!("{} - {}", header_text, main_text), // Fallback text
        blocks: Some(vec![
            // Header block with priority emoji and alert name
            SlackBlock::Header {
                text: SlackText::plain_text(header_text),
            },
            // Divider
            SlackBlock::Divider,
            // Main notification message
            SlackBlock::Section {
                text: SlackText::markdown(main_text),
                fields: Some(detail_fields),
            },
            // Divider before footer
            SlackBlock::Divider,
            // Context footer with metadata
            SlackBlock::Context {
                elements: vec![SlackElement::Markdown { text: context_text }],
            },
        ]),
    }
}

/// Format the main notification text
fn format_main_text(payload: &NotificationPayload) -> String {
    let mut parts = Vec::new();

    // Triggered value vs threshold
    parts.push(format!(
        "*Value:* `{}` (threshold: `{}`)",
        payload.triggered_value, payload.threshold
    ));

    // Chain
    parts.push(format!("*Chain:* {}", payload.chain));

    // Transaction hash if available
    if let Some(ref tx_hash) = payload.transaction_hash {
        let short_hash = if tx_hash.len() > 16 {
            format!("{}...{}", &tx_hash[..8], &tx_hash[tx_hash.len() - 8..])
        } else {
            tx_hash.clone()
        };
        parts.push(format!("*Transaction:* `{}`", short_hash));
    }

    parts.join("\n")
}

/// Build detail fields for Slack section block
fn build_detail_fields(payload: &NotificationPayload) -> Vec<SlackText> {
    let mut fields = Vec::new();

    // Wallet address (shortened)
    let short_wallet = if payload.wallet.len() > 16 {
        format!(
            "{}...{}",
            &payload.wallet[..8],
            &payload.wallet[payload.wallet.len() - 8..]
        )
    } else {
        payload.wallet.clone()
    };
    fields.push(SlackText::markdown(format!(
        "*Wallet:*\n`{}`",
        short_wallet
    )));

    // Block number if available
    if let Some(block_number) = payload.block_number {
        fields.push(SlackText::markdown(format!("*Block:*\n`{}`", block_number)));
    }

    fields
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{NotificationPayload, NotificationPriority};
    use chrono::Utc;

    #[test]
    fn test_format_slack_message() {
        let notification = NatsNotification {
            notification_id: None,
            user_id: "user123".to_string(),
            alert_id: "alert456".to_string(),
            alert_name: "Large Transfer Alert".to_string(),
            notification_type: "transaction".to_string(),
            priority: NotificationPriority::High,
            payload: NotificationPayload {
                triggered_value: "5.5 ETH".to_string(),
                threshold: "5.0 ETH".to_string(),
                transaction_hash: Some("0x1234567890abcdef1234567890abcdef12345678".to_string()),
                chain: "ethereum".to_string(),
                wallet: "0xabcdef1234567890abcdef1234567890abcdef12".to_string(),
                block_number: Some(18234567),
            },
            timestamp: Utc::now(),
        };

        let message = format_slack_message(&notification);

        // Verify fallback text contains key info
        assert!(message.text.contains("⚠️"));
        assert!(message.text.contains("Large Transfer Alert"));

        // Verify blocks exist
        assert!(message.blocks.is_some());
        let blocks = message.blocks.unwrap();
        assert!(blocks.len() >= 4); // Header, Divider, Section, Context minimum
    }

    #[test]
    fn test_format_main_text() {
        let payload = NotificationPayload {
            triggered_value: "10.0 ETH".to_string(),
            threshold: "5.0 ETH".to_string(),
            transaction_hash: Some("0x1234".to_string()),
            chain: "ethereum".to_string(),
            wallet: "0xabcd".to_string(),
            block_number: Some(12345),
        };

        let text = format_main_text(&payload);

        assert!(text.contains("10.0 ETH"));
        assert!(text.contains("5.0 ETH"));
        assert!(text.contains("ethereum"));
    }

    #[test]
    fn test_priority_emoji() {
        assert_eq!(NotificationPriority::Critical.emoji(), "🚨");
        assert_eq!(NotificationPriority::High.emoji(), "⚠️");
        assert_eq!(NotificationPriority::Normal.emoji(), "ℹ️");
        assert_eq!(NotificationPriority::Low.emoji(), "📋");
    }
}
