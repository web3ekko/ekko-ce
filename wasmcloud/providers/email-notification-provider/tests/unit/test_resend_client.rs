use email_notification_provider::client::{ResendClient, ResendResponseWrapper};
use email_notification_provider::formatter::EmailPayload;
use notification_common::provider_base::ProviderError;
use wiremock::{MockServer, Mock, ResponseTemplate};
use wiremock::matchers::{method, path, header};
use std::collections::HashMap;

async fn setup_mock_server() -> MockServer {
    MockServer::start().await
}

fn create_test_payload() -> EmailPayload {
    EmailPayload {
        to: "recipient@example.com".to_string(),
        from: "sender@ekko.zone".to_string(),
        subject: "Test Email".to_string(),
        text_content: "This is a test email".to_string(),
        html_content: Some("<html><body>This is a test email</body></html>".to_string()),
        reply_to: Some("reply@ekko.zone".to_string()),
        cc: vec![],
        bcc: vec![],
        attachments: vec![],
        headers: HashMap::new(),
    }
}

#[tokio::test]
async fn test_successful_email_send() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("POST"))
        .and(path("/emails"))
        .and(header("Authorization", "Bearer test-api-key"))
        .and(header("Content-Type", "application/json"))
        .respond_with(
            ResponseTemplate::new(200)
                .set_body_json(serde_json::json!({
                    "id": "test-message-id-123"
                }))
        )
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let payload = create_test_payload();
    let result = client.send(payload).await;

    assert!(result.is_ok());
    let response = result.unwrap();
    assert_eq!(response.message_id, Some("test-message-id-123".to_string()));
    assert_eq!(response.status_code, 200);
}

#[tokio::test]
async fn test_authentication_failure() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("POST"))
        .and(path("/emails"))
        .respond_with(
            ResponseTemplate::new(401)
                .set_body_json(serde_json::json!({
                    "statusCode": 401,
                    "message": "API key is invalid",
                    "name": "unauthorized"
                }))
        )
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "invalid-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let payload = create_test_payload();
    let result = client.send(payload).await;

    assert!(result.is_err());
    match result.unwrap_err() {
        ProviderError::InvalidAuthentication => {}
        e => panic!("Expected InvalidAuthentication error, got {:?}", e),
    }
}

#[tokio::test]
async fn test_forbidden_domain_not_verified() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("POST"))
        .and(path("/emails"))
        .respond_with(
            ResponseTemplate::new(403)
                .set_body_json(serde_json::json!({
                    "statusCode": 403,
                    "message": "You can only send emails from verified domains",
                    "name": "forbidden"
                }))
        )
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let payload = create_test_payload();
    let result = client.send(payload).await;

    assert!(result.is_err());
    match result.unwrap_err() {
        ProviderError::ExternalServiceError(msg) => {
            assert!(msg.contains("Domain not verified"));
        }
        e => panic!("Expected ExternalServiceError error, got {:?}", e),
    }
}

#[tokio::test]
async fn test_rate_limit_exceeded() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("POST"))
        .and(path("/emails"))
        .respond_with(
            ResponseTemplate::new(429)
                .set_body_json(serde_json::json!({
                    "statusCode": 429,
                    "message": "Too many requests",
                    "name": "rate_limit_exceeded"
                }))
                .insert_header("Retry-After", "60")
        )
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let payload = create_test_payload();
    let result = client.send(payload).await;

    assert!(result.is_err());
    match result.unwrap_err() {
        ProviderError::RateLimitExceeded { retry_after } => {
            assert_eq!(retry_after.num_seconds(), 60);
        }
        e => panic!("Expected RateLimitExceeded error, got {:?}", e),
    }
}

#[tokio::test]
async fn test_invalid_recipient_email() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("POST"))
        .and(path("/emails"))
        .respond_with(
            ResponseTemplate::new(400)
                .set_body_json(serde_json::json!({
                    "statusCode": 400,
                    "message": "Invalid `to` field. Expected array of email addresses.",
                    "name": "validation_error"
                }))
        )
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let mut payload = create_test_payload();
    payload.to = "invalid-email".to_string();

    let result = client.send(payload).await;

    assert!(result.is_err());
    match result.unwrap_err() {
        ProviderError::MalformedPayload(msg) => {
            assert!(msg.contains("to"));
        }
        e => panic!("Expected MalformedPayload error, got {:?}", e),
    }
}

#[tokio::test]
async fn test_validation_error() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("POST"))
        .and(path("/emails"))
        .respond_with(
            ResponseTemplate::new(422)
                .set_body_json(serde_json::json!({
                    "statusCode": 422,
                    "message": "Missing required field: subject",
                    "name": "unprocessable_entity"
                }))
        )
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let payload = create_test_payload();
    let result = client.send(payload).await;

    assert!(result.is_err());
    match result.unwrap_err() {
        ProviderError::MalformedPayload(msg) => {
            assert!(msg.contains("Validation error"));
        }
        e => panic!("Expected MalformedPayload error, got {:?}", e),
    }
}

#[tokio::test]
async fn test_service_unavailable() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("POST"))
        .and(path("/emails"))
        .respond_with(ResponseTemplate::new(503))
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let payload = create_test_payload();
    let result = client.send(payload).await;

    assert!(result.is_err());
    match result.unwrap_err() {
        ProviderError::ServiceUnavailable => {}
        e => panic!("Expected ServiceUnavailable error, got {:?}", e),
    }
}

#[tokio::test]
async fn test_internal_server_error() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("POST"))
        .and(path("/emails"))
        .respond_with(ResponseTemplate::new(500))
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let payload = create_test_payload();
    let result = client.send(payload).await;

    assert!(result.is_err());
    match result.unwrap_err() {
        ProviderError::ServiceUnavailable => {}
        e => panic!("Expected ServiceUnavailable error, got {:?}", e),
    }
}

#[tokio::test]
async fn test_network_timeout() {
    // Create a client with an unreachable endpoint
    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some("http://192.0.2.0:1234".to_string()), // Non-routable IP
        Some("Ekko Zone".to_string()),
    );

    let payload = create_test_payload();
    let result = tokio::time::timeout(
        std::time::Duration::from_secs(2),
        client.send(payload)
    ).await;

    assert!(result.is_err() || result.unwrap().is_err());
}

#[tokio::test]
async fn test_health_check_success() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("GET"))
        .and(path("/domains"))
        .and(header("Authorization", "Bearer test-api-key"))
        .respond_with(
            ResponseTemplate::new(200)
                .set_body_json(serde_json::json!({
                    "data": []
                }))
        )
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let result = client.health_check().await;
    assert!(result.is_ok());
    assert!(result.unwrap());
}

#[tokio::test]
async fn test_health_check_failure() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("GET"))
        .and(path("/domains"))
        .respond_with(ResponseTemplate::new(401))
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "invalid-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let result = client.health_check().await;
    assert!(result.is_ok());
    assert!(!result.unwrap());
}

#[tokio::test]
async fn test_email_with_attachments() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("POST"))
        .and(path("/emails"))
        .respond_with(
            ResponseTemplate::new(200)
                .set_body_json(serde_json::json!({
                    "id": "attachment-test-id"
                }))
        )
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let mut payload = create_test_payload();
    payload.attachments = vec![
        email_notification_provider::formatter::EmailAttachment {
            filename: "report.pdf".to_string(),
            content: base64::encode(b"PDF content here"),
            content_type: "application/pdf".to_string(),
            disposition: "attachment".to_string(),
        }
    ];

    let result = client.send(payload).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_email_with_multiple_recipients() {
    let mock_server = setup_mock_server().await;

    Mock::given(method("POST"))
        .and(path("/emails"))
        .respond_with(
            ResponseTemplate::new(200)
                .set_body_json(serde_json::json!({
                    "id": "multi-recipient-test-id"
                }))
        )
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let mut payload = create_test_payload();
    payload.cc = vec!["cc@example.com".to_string()];
    payload.bcc = vec!["bcc@example.com".to_string()];

    let result = client.send(payload).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_batch_send() {
    let mock_server = setup_mock_server().await;

    // Mock multiple successful responses
    Mock::given(method("POST"))
        .and(path("/emails"))
        .respond_with(
            ResponseTemplate::new(200)
                .set_body_json(serde_json::json!({
                    "id": "batch-message-id"
                }))
        )
        .expect(3)
        .mount(&mock_server)
        .await;

    let client = ResendClient::new(
        "test-api-key".to_string(),
        Some(mock_server.uri()),
        Some("Ekko Zone".to_string()),
    );

    let payloads = vec![
        create_test_payload(),
        create_test_payload(),
        create_test_payload(),
    ];

    let results = client.send_batch(payloads).await;
    assert!(results.is_ok());

    let responses = results.unwrap();
    assert_eq!(responses.len(), 3);
    for response in responses {
        assert_eq!(response.status_code, 200);
    }
}
