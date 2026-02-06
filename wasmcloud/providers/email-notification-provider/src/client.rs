use crate::formatter::EmailPayload;
use notification_common::provider_base::ProviderError;
use reqwest::{Client, StatusCode};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, error, warn};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResendResponse {
    pub id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResendResponseWrapper {
    pub message_id: Option<String>,
    pub status_code: u16,
    pub message: Option<String>,
}

#[derive(Debug, Serialize)]
struct ResendRequest {
    from: String,
    to: Vec<String>,
    subject: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    text: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    html: Option<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    cc: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    bcc: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    reply_to: Option<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    attachments: Vec<ResendAttachment>,
}

#[derive(Debug, Serialize)]
struct ResendAttachment {
    filename: String,
    content: String,
}

#[derive(Debug, Deserialize)]
struct ResendError {
    #[serde(default)]
    statusCode: u16,
    #[serde(default)]
    message: String,
    #[serde(default)]
    name: String,
}

pub struct ResendClient {
    client: Client,
    api_key: String,
    base_url: String,
    default_from_name: String,
}

impl ResendClient {
    pub fn new(
        api_key: String,
        base_url: Option<String>,
        default_from_name: Option<String>,
    ) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");

        let base_url = base_url.unwrap_or_else(|| "https://api.resend.com".to_string());
        let default_from_name = default_from_name.unwrap_or_else(|| "Ekko Zone".to_string());

        Self {
            client,
            api_key,
            base_url,
            default_from_name,
        }
    }

    pub async fn send(
        &self,
        payload: EmailPayload,
    ) -> Result<ResendResponseWrapper, ProviderError> {
        let request = self.build_request(payload);

        let response = self
            .client
            .post(format!("{}/emails", self.base_url))
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await
            .map_err(|e| {
                error!("Failed to send email request: {}", e);
                if e.is_timeout() {
                    ProviderError::NetworkTimeout
                } else {
                    ProviderError::NetworkError(e.to_string())
                }
            })?;

        let status = response.status();

        match status {
            StatusCode::OK => {
                let resend_response: ResendResponse = response.json().await.map_err(|e| {
                    error!("Failed to parse Resend response: {}", e);
                    ProviderError::ExternalServiceError(format!("Invalid response format: {}", e))
                })?;
                debug!("Email sent successfully with ID: {}", resend_response.id);
                Ok(ResendResponseWrapper {
                    message_id: Some(resend_response.id),
                    status_code: 200,
                    message: Some("success".to_string()),
                })
            }
            StatusCode::UNAUTHORIZED => {
                error!("Authentication failed with Resend");
                Err(ProviderError::InvalidAuthentication)
            }
            StatusCode::FORBIDDEN => {
                let error_body = response.text().await.unwrap_or_default();
                error!("Forbidden - domain may not be verified: {}", error_body);
                Err(ProviderError::ExternalServiceError(
                    "Domain not verified or insufficient permissions".to_string(),
                ))
            }
            StatusCode::TOO_MANY_REQUESTS => {
                let retry_after = response
                    .headers()
                    .get("Retry-After")
                    .and_then(|v| v.to_str().ok())
                    .and_then(|v| v.parse::<i64>().ok())
                    .unwrap_or(60);

                warn!("Rate limit exceeded, retry after {} seconds", retry_after);
                Err(ProviderError::RateLimitExceeded {
                    retry_after: chrono::Duration::seconds(retry_after),
                })
            }
            StatusCode::BAD_REQUEST => {
                let error_body = response.text().await.unwrap_or_default();
                if let Ok(error) = serde_json::from_str::<ResendError>(&error_body) {
                    error!("Bad request: {}", error.message);
                    Err(ProviderError::MalformedPayload(error.message))
                } else {
                    error!("Bad request with unparseable error: {}", error_body);
                    Err(ProviderError::MalformedPayload(
                        "Invalid email request".to_string(),
                    ))
                }
            }
            StatusCode::UNPROCESSABLE_ENTITY => {
                let error_body = response.text().await.unwrap_or_default();
                error!("Validation error: {}", error_body);
                Err(ProviderError::MalformedPayload(format!(
                    "Validation error: {}",
                    error_body
                )))
            }
            StatusCode::INTERNAL_SERVER_ERROR | StatusCode::SERVICE_UNAVAILABLE => {
                error!("Resend service error: {}", status);
                Err(ProviderError::ServiceUnavailable)
            }
            _ => {
                error!("Unexpected response status: {}", status);
                Err(ProviderError::ExternalServiceError(format!(
                    "Unexpected status code: {}",
                    status
                )))
            }
        }
    }

    pub async fn send_batch(
        &self,
        payloads: Vec<EmailPayload>,
    ) -> Result<Vec<ResendResponseWrapper>, ProviderError> {
        let mut responses = Vec::new();

        for payload in payloads {
            let response = self.send(payload).await?;
            responses.push(response);

            // Resend has 2 req/sec default rate limit, add delay between sends
            tokio::time::sleep(Duration::from_millis(500)).await;
        }

        Ok(responses)
    }

    pub async fn health_check(&self) -> Result<bool, ProviderError> {
        // Resend doesn't have a dedicated health check endpoint
        // We'll check if the API key is valid by hitting the domains endpoint
        let response = self
            .client
            .get(format!("{}/domains", self.base_url))
            .header("Authorization", format!("Bearer {}", self.api_key))
            .send()
            .await
            .map_err(|e| {
                warn!("Health check failed: {}", e);
                ProviderError::NetworkError(e.to_string())
            })?;

        Ok(response.status() == StatusCode::OK)
    }

    fn build_request(&self, payload: EmailPayload) -> ResendRequest {
        // Resend uses "Name <email>" format for from address
        let from = format!("{} <{}>", self.default_from_name, payload.from);

        let attachments = payload
            .attachments
            .into_iter()
            .map(|att| ResendAttachment {
                filename: att.filename,
                content: att.content,
            })
            .collect();

        ResendRequest {
            from,
            to: vec![payload.to],
            subject: payload.subject,
            text: Some(payload.text_content),
            html: payload.html_content,
            cc: payload.cc,
            bcc: payload.bcc,
            reply_to: payload.reply_to,
            attachments,
        }
    }
}
