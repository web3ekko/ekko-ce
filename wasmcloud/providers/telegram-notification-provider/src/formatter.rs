use crate::types::NatsNotification;

/// Format notification as Telegram message with Markdown
pub fn format_telegram_message(notification: &NatsNotification) -> String {
    let priority_emoji = notification.priority.emoji();
    let priority_label = notification.priority.label();

    // Build header
    let header = format!(
        "{} *{}* - {}",
        priority_emoji, priority_label, notification.alert_name
    );

    // Build main message
    let mut parts = vec![
        header,
        String::new(), // Empty line
        notification.message.clone(),
        String::new(), // Empty line
    ];

    // Add blockchain details
    let mut details = vec![format!("*Chain:* `{}`", notification.chain)];

    if let Some(tx_hash) = &notification.transaction_hash {
        // Shorten transaction hash for readability
        let short_hash = if tx_hash.len() > 16 {
            format!("{}...{}", &tx_hash[0..10], &tx_hash[tx_hash.len() - 6..])
        } else {
            tx_hash.clone()
        };
        details.push(format!("*Transaction:* `{}`", short_hash));
    }

    if let Some(wallet) = &notification.wallet_address {
        // Shorten wallet address
        let short_wallet = if wallet.len() > 16 {
            format!("{}...{}", &wallet[0..8], &wallet[wallet.len() - 6..])
        } else {
            wallet.clone()
        };
        details.push(format!("*Wallet:* `{}`", short_wallet));
    }

    if let Some(block) = notification.block_number {
        details.push(format!("*Block:* `{}`", block));
    }

    parts.push(details.join("\n"));

    // Add footer
    parts.push(String::new());
    parts.push(format!("_Alert ID: {}_", notification.alert_id));
    parts.push(format!("_Time: {}_", notification.timestamp));

    parts.join("\n")
}

/// Format verification message
pub fn format_verification_message(code: &str) -> String {
    format!(
        "🔐 *Ekko Verification*\n\n\
        Your verification code is:\n\n\
        `{}`\n\n\
        This code expires in 15 minutes.\n\n\
        _Don't share this code with anyone._",
        code
    )
}

/// Format welcome message for /start command
pub fn format_welcome_message() -> String {
    "👋 *Welcome to Ekko Alerts!*\n\n\
    I'll send you blockchain alerts directly to Telegram.\n\n\
    *Available Commands:*\n\
    /start - Show this welcome message\n\
    /subscribe - Subscribe to alerts\n\
    /list - List your active alerts\n\
    /unsubscribe - Unsubscribe from alerts\n\
    /help - Get help\n\n\
    To get started, use /subscribe and follow the instructions in the Ekko Dashboard."
        .to_string()
}

/// Format subscription confirmation message
pub fn format_subscribe_message(chat_id: i64) -> String {
    format!(
        "✅ *Subscription Request Received*\n\n\
        Your Chat ID is: `{}`\n\n\
        Please go to the Ekko Dashboard and:\n\
        1. Navigate to Settings → Notifications\n\
        2. Select the Telegram tab\n\
        3. Enter this Chat ID\n\
        4. Complete the verification\n\n\
        _You'll receive a verification code here once you've added your Telegram channel in the dashboard._",
        chat_id
    )
}

/// Format alert list message
pub fn format_alert_list(alert_count: usize) -> String {
    if alert_count == 0 {
        "📋 *Your Active Alerts*\n\n\
        You don't have any active alerts yet.\n\n\
        Visit the Ekko Dashboard to create your first alert!"
            .to_string()
    } else {
        format!(
            "📋 *Your Active Alerts*\n\n\
            You have {} active alert{}.\n\n\
            Visit the Ekko Dashboard to manage your alerts.",
            alert_count,
            if alert_count == 1 { "" } else { "s" }
        )
    }
}

/// Format unsubscribe confirmation
pub fn format_unsubscribe_message() -> String {
    "❌ *Unsubscribed*\n\n\
    You've been unsubscribed from Ekko alerts.\n\n\
    You can resubscribe anytime using /subscribe or from the Ekko Dashboard."
        .to_string()
}

/// Format help message
pub fn format_help_message() -> String {
    "ℹ️ *Ekko Help*\n\n\
    *Commands:*\n\
    /start - Welcome message\n\
    /subscribe - Subscribe to alerts\n\
    /list - List active alerts\n\
    /unsubscribe - Unsubscribe from alerts\n\
    /help - Show this help\n\n\
    *About Ekko:*\n\
    Ekko is a blockchain monitoring platform that sends real-time alerts \
    for transactions, price changes, and on-chain events.\n\n\
    *Need Support?*\n\
    Visit https://ekko.zone/help"
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{NatsNotification, NotificationPriority};

    #[test]
    fn test_format_telegram_message() {
        let notification = NatsNotification {
            notification_id: None,
            user_id: "test-user".to_string(),
            alert_id: "alert-123".to_string(),
            alert_name: "Test Alert".to_string(),
            priority: NotificationPriority::High,
            message: "Test message".to_string(),
            chain: "ethereum".to_string(),
            transaction_hash: Some("0x1234567890abcdef".to_string()),
            wallet_address: Some("0xabcdef123456".to_string()),
            block_number: Some(12345678),
            timestamp: "2024-01-01T12:00:00Z".to_string(),
        };

        let formatted = format_telegram_message(&notification);
        assert!(formatted.contains("⚠️"));
        assert!(formatted.contains("Test Alert"));
        assert!(formatted.contains("ethereum"));
    }

    #[test]
    fn test_format_verification_message() {
        let formatted = format_verification_message("123456");
        assert!(formatted.contains("123456"));
        assert!(formatted.contains("Verification"));
    }

    #[test]
    fn test_format_welcome_message() {
        let formatted = format_welcome_message();
        assert!(formatted.contains("Welcome"));
        assert!(formatted.contains("/start"));
    }
}
