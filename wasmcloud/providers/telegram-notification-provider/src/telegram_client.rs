use crate::types::{TelegramApiResponse, TelegramSendMessageRequest};
use anyhow::{anyhow, Context, Result};
use reqwest::Client;
use tracing::{debug, error, info};

/// Telegram Bot API client
pub struct TelegramClient {
    http_client: Client,
}

impl TelegramClient {
    pub fn new() -> Self {
        let http_client = Client::builder()
            .timeout(std::time::Duration::from_secs(10))
            .build()
            .expect("Failed to create HTTP client");

        Self { http_client }
    }

    /// Send message via Telegram Bot API
    pub async fn send_message(
        &self,
        bot_token: &str,
        chat_id: &str,
        text: &str,
        parse_mode: Option<&str>,
    ) -> Result<TelegramApiResponse> {
        let url = format!("https://api.telegram.org/bot{}/sendMessage", bot_token);

        let request = TelegramSendMessageRequest {
            chat_id: chat_id.to_string(),
            text: text.to_string(),
            parse_mode: parse_mode.unwrap_or("Markdown").to_string(),
            disable_web_page_preview: Some(true),
            disable_notification: Some(false),
        };

        debug!("Sending Telegram message to chat_id: {}", chat_id);

        let response = self
            .http_client
            .post(&url)
            .json(&request)
            .send()
            .await
            .context("Failed to send Telegram API request")?;

        let status = response.status();
        let response_text = response
            .text()
            .await
            .context("Failed to read Telegram API response")?;

        debug!(
            "Telegram API response (status {}): {}",
            status, response_text
        );

        let api_response: TelegramApiResponse = serde_json::from_str(&response_text)
            .context("Failed to parse Telegram API response")?;

        if !api_response.ok {
            let error_msg = api_response
                .description
                .unwrap_or_else(|| "Unknown error".to_string());
            error!("Telegram API error: {}", error_msg);
            return Err(anyhow!("Telegram API error: {}", error_msg));
        }

        info!("Successfully sent Telegram message to chat_id: {}", chat_id);
        Ok(api_response)
    }

    /// Get bot info
    pub async fn get_me(&self, bot_token: &str) -> Result<serde_json::Value> {
        let url = format!("https://api.telegram.org/bot{}/getMe", bot_token);

        let response = self
            .http_client
            .get(&url)
            .send()
            .await
            .context("Failed to get bot info")?;

        let response_json: serde_json::Value = response
            .json()
            .await
            .context("Failed to parse bot info response")?;

        Ok(response_json)
    }

    /// Set webhook for bot commands
    pub async fn set_webhook(&self, bot_token: &str, webhook_url: &str) -> Result<()> {
        let url = format!("https://api.telegram.org/bot{}/setWebhook", bot_token);

        let payload = serde_json::json!({
            "url": webhook_url,
            "allowed_updates": ["message"]
        });

        let response = self
            .http_client
            .post(&url)
            .json(&payload)
            .send()
            .await
            .context("Failed to set webhook")?;

        let api_response: TelegramApiResponse = response
            .json()
            .await
            .context("Failed to parse webhook response")?;

        if !api_response.ok {
            let error_msg = api_response
                .description
                .unwrap_or_else(|| "Unknown error".to_string());
            return Err(anyhow!("Failed to set webhook: {}", error_msg));
        }

        info!("Successfully set Telegram webhook: {}", webhook_url);
        Ok(())
    }

    /// Delete webhook
    pub async fn delete_webhook(&self, bot_token: &str) -> Result<()> {
        let url = format!("https://api.telegram.org/bot{}/deleteWebhook", bot_token);

        let response = self
            .http_client
            .post(&url)
            .send()
            .await
            .context("Failed to delete webhook")?;

        let api_response: TelegramApiResponse = response
            .json()
            .await
            .context("Failed to parse delete webhook response")?;

        if !api_response.ok {
            let error_msg = api_response
                .description
                .unwrap_or_else(|| "Unknown error".to_string());
            return Err(anyhow!("Failed to delete webhook: {}", error_msg));
        }

        info!("Successfully deleted Telegram webhook");
        Ok(())
    }

    /// Get webhook info
    pub async fn get_webhook_info(&self, bot_token: &str) -> Result<serde_json::Value> {
        let url = format!("https://api.telegram.org/bot{}/getWebhookInfo", bot_token);

        let response = self
            .http_client
            .get(&url)
            .send()
            .await
            .context("Failed to get webhook info")?;

        let response_json: serde_json::Value = response
            .json()
            .await
            .context("Failed to parse webhook info response")?;

        Ok(response_json)
    }
}

impl Default for TelegramClient {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_telegram_client_creation() {
        let client = TelegramClient::new();
        assert!(true); // Client created successfully
    }
}
