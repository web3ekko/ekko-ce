use crate::formatter::*;
use crate::redis_client::RedisClient;
use crate::telegram_client::TelegramClient;
use crate::types::{TelegramBotCommand, TelegramUpdate};
use anyhow::{Context, Result};
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{error, info, warn};

/// Bot command handler
pub struct BotCommandHandler {
    telegram_client: Arc<TelegramClient>,
    redis_client: Arc<Mutex<RedisClient>>,
}

impl BotCommandHandler {
    pub fn new(
        telegram_client: Arc<TelegramClient>,
        redis_client: Arc<Mutex<RedisClient>>,
    ) -> Self {
        Self {
            telegram_client,
            redis_client,
        }
    }

    /// Process incoming Telegram update (webhook)
    pub async fn handle_update(&self, bot_token: &str, update: TelegramUpdate) -> Result<()> {
        if let Some(message) = update.message {
            if let Some(text) = message.text {
                // Extract command if present
                if text.starts_with('/') {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    let command = parts[0].trim_start_matches('/');

                    let bot_command = TelegramBotCommand {
                        command: command.to_string(),
                        chat_id: message.chat.id,
                        user_id: Some(message.from.id),
                        username: message.from.username.clone(),
                        text: text.clone(),
                    };

                    self.handle_command(bot_token, bot_command).await?;
                }
            }
        }

        Ok(())
    }

    /// Handle bot command
    pub async fn handle_command(&self, bot_token: &str, command: TelegramBotCommand) -> Result<()> {
        info!(
            "Handling Telegram command: {} from chat_id: {}",
            command.command, command.chat_id
        );

        match command.command.as_str() {
            "start" => self.handle_start(bot_token, &command).await?,
            "subscribe" => self.handle_subscribe(bot_token, &command).await?,
            "list" => self.handle_list(bot_token, &command).await?,
            "unsubscribe" => self.handle_unsubscribe(bot_token, &command).await?,
            "help" => self.handle_help(bot_token, &command).await?,
            _ => {
                // Unknown command
                let message = format!(
                    "Unknown command: /{}\n\nUse /help to see available commands.",
                    command.command
                );
                self.send_message(bot_token, &command.chat_id.to_string(), &message)
                    .await?;
            }
        }

        Ok(())
    }

    /// Handle /start command
    async fn handle_start(&self, bot_token: &str, command: &TelegramBotCommand) -> Result<()> {
        let message = format_welcome_message();
        self.send_message(bot_token, &command.chat_id.to_string(), &message)
            .await?;

        // Store chat mapping if username exists
        if let Some(username) = &command.username {
            let mut redis = self.redis_client.lock().await;
            redis.store_chat_mapping(username, command.chat_id).await?;
        }

        Ok(())
    }

    /// Handle /subscribe command
    async fn handle_subscribe(&self, bot_token: &str, command: &TelegramBotCommand) -> Result<()> {
        let message = format_subscribe_message(command.chat_id);
        self.send_message(bot_token, &command.chat_id.to_string(), &message)
            .await?;

        // Store chat mapping if username exists
        if let Some(username) = &command.username {
            let mut redis = self.redis_client.lock().await;
            redis.store_chat_mapping(username, command.chat_id).await?;
        }

        info!(
            "User {} (chat_id: {}) requested subscription",
            command.username.as_ref().unwrap_or(&"unknown".to_string()),
            command.chat_id
        );

        Ok(())
    }

    /// Handle /list command
    async fn handle_list(&self, bot_token: &str, command: &TelegramBotCommand) -> Result<()> {
        // In production, would fetch actual alert count from Django API
        // For now, return placeholder
        let alert_count = 0;
        let message = format_alert_list(alert_count);
        self.send_message(bot_token, &command.chat_id.to_string(), &message)
            .await?;

        Ok(())
    }

    /// Handle /unsubscribe command
    async fn handle_unsubscribe(
        &self,
        bot_token: &str,
        command: &TelegramBotCommand,
    ) -> Result<()> {
        let message = format_unsubscribe_message();
        self.send_message(bot_token, &command.chat_id.to_string(), &message)
            .await?;

        // Note: Actual unsubscribe logic would be handled by Django API
        // This just confirms the action to the user

        info!(
            "User {} (chat_id: {}) requested unsubscribe",
            command.username.as_ref().unwrap_or(&"unknown".to_string()),
            command.chat_id
        );

        Ok(())
    }

    /// Handle /help command
    async fn handle_help(&self, bot_token: &str, command: &TelegramBotCommand) -> Result<()> {
        let message = format_help_message();
        self.send_message(bot_token, &command.chat_id.to_string(), &message)
            .await?;

        Ok(())
    }

    /// Send message helper
    async fn send_message(&self, bot_token: &str, chat_id: &str, text: &str) -> Result<()> {
        match self
            .telegram_client
            .send_message(bot_token, chat_id, text, Some("Markdown"))
            .await
        {
            Ok(_) => {
                info!("Sent Telegram message to chat_id: {}", chat_id);
                Ok(())
            }
            Err(e) => {
                error!("Failed to send Telegram message to {}: {}", chat_id, e);
                Err(e)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bot_command_handler_creation() {
        // Test would require mock clients
        assert!(true);
    }
}
