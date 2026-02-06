use crate::types::SlackMessage;
use anyhow::{Context, Result};
use reqwest::{Client, StatusCode};
use serde::Deserialize;
use tracing::{debug, warn};

/// Slack API client for sending webhook messages
pub struct SlackClient {
    http_client: Client,
}

/// Slack webhook response
#[derive(Debug, Deserialize)]
struct SlackResponse {
    ok: bool,
    #[serde(default)]
    error: Option<String>,
}

impl SlackClient {
    /// Create new Slack client
    pub fn new() -> Self {
        Self {
            http_client: Client::builder()
                .timeout(std::time::Duration::from_secs(10))
                .build()
                .expect("Failed to create HTTP client"),
        }
    }

    /// Send message to Slack via webhook
    pub async fn send_message(&self, webhook_url: &str, message: &SlackMessage) -> Result<()> {
        debug!("Sending message to Slack webhook");

        let response = self
            .http_client
            .post(webhook_url)
            .json(message)
            .send()
            .await
            .context("Failed to send request to Slack")?;

        let status = response.status();

        if status == StatusCode::OK {
            let text = response
                .text()
                .await
                .context("Failed to read Slack response")?;

            if text == "ok" {
                debug!("Slack message sent successfully");
                Ok(())
            } else {
                warn!("Unexpected Slack response: {}", text);
                Err(anyhow::anyhow!("Unexpected Slack response: {}", text))
            }
        } else {
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            Err(anyhow::anyhow!(
                "Slack webhook returned status {}: {}",
                status,
                error_text
            ))
        }
    }

    /// Test webhook URL by sending a simple message
    pub async fn test_webhook(&self, webhook_url: &str) -> Result<()> {
        debug!("Testing Slack webhook");

        let test_message = SlackMessage {
            text: "🎉 Ekko Alert System - Slack integration test successful!".to_string(),
            blocks: None,
        };

        self.send_message(webhook_url, &test_message).await
    }
}

impl Default for SlackClient {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_slack_client_creation() {
        let client = SlackClient::new();
        // Just verify it can be created without panic
        assert!(true);
    }

    #[tokio::test]
    async fn test_send_message_invalid_url() {
        let client = SlackClient::new();
        let message = SlackMessage {
            text: "Test".to_string(),
            blocks: None,
        };

        let result = client
            .send_message("https://invalid.example.com/webhook", &message)
            .await;

        // Should fail for invalid webhook
        assert!(result.is_err());
    }
}
