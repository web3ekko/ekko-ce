use email_notification_provider::formatter::{EmailFormatter, EmailPayload};
use notification_common::{
    NotificationChannel, NotificationPriority, NotificationRequest,
    UserNotificationSettings, NotificationAction, DeliveryOptions,
    provider_base::ProviderError,
};
use chrono::Utc;
use std::collections::HashMap;
use uuid::Uuid;

fn create_test_request() -> NotificationRequest {
    NotificationRequest {
        notification_id: Uuid::new_v4(),
        user_id: "user123".to_string(),
        group_id: None,
        alert_id: "alert456".to_string(),
        alert_name: "High CPU Usage".to_string(),
        channel: NotificationChannel::Email,
        priority: NotificationPriority::High,
        title: "Alert: High CPU Usage Detected".to_string(),
        message: "CPU usage has exceeded 90% on server prod-web-01".to_string(),
        details: {
            let mut details = HashMap::new();
            details.insert("server".to_string(), serde_json::json!("prod-web-01"));
            details.insert("cpu_usage".to_string(), serde_json::json!(92.5));
            details.insert("threshold".to_string(), serde_json::json!(90));
            details
        },
        template_name: Some("alert_triggered".to_string()),
        template_variables: {
            let mut vars = HashMap::new();
            vars.insert("alert_type".to_string(), "performance".to_string());
            vars.insert("severity".to_string(), "high".to_string());
            vars
        },
        actions: vec![],
        delivery_options: DeliveryOptions {
            max_retries: 3,
            retry_delay_seconds: 60,
            timeout_seconds: 30,
            priority_boost: false,
        },
        timestamp: Utc::now(),
    }
}

fn create_test_settings() -> UserNotificationSettings {
    UserNotificationSettings {
        user_id: "user123".to_string(),
        websocket_enabled: true,
        notifications_enabled: true,
        channels: {
            let mut channels = HashMap::new();
            channels.insert(
                "email".to_string(),
                {
                    let mut config = HashMap::new();
                    config.insert("enabled".to_string(), serde_json::json!(true));
                    config.insert("address".to_string(), serde_json::json!("user@example.com"));
                    config
                },
            );
            channels
        },
        priority_routing: HashMap::new(),
        quiet_hours: None,
        created_at: Utc::now(),
        updated_at: Utc::now(),
    }
}

#[test]
fn test_format_basic_email() {
    let formatter = EmailFormatter::new();
    let request = create_test_request();
    let settings = create_test_settings();
    
    let result = formatter.format_message(&request, &settings);
    assert!(result.is_ok());
    
    let payload = result.unwrap();
    assert_eq!(payload.to, "user@example.com");
    assert_eq!(payload.subject, "Alert: High CPU Usage Detected");
    assert!(payload.text_content.contains("CPU usage has exceeded 90%"));
    assert!(payload.html_content.is_some());
}

#[test]
fn test_format_email_with_priority_prefix() {
    let formatter = EmailFormatter::new();
    let mut request = create_test_request();
    request.priority = NotificationPriority::Critical;
    let settings = create_test_settings();
    
    let result = formatter.format_message(&request, &settings);
    assert!(result.is_ok());
    
    let payload = result.unwrap();
    assert!(payload.subject.starts_with("[CRITICAL]"));
}

#[test]
fn test_format_email_with_html_content() {
    let formatter = EmailFormatter::new();
    let request = create_test_request();
    let settings = create_test_settings();
    
    let result = formatter.format_message(&request, &settings);
    assert!(result.is_ok());
    
    let payload = result.unwrap();
    assert!(payload.html_content.is_some());
    
    let html = payload.html_content.unwrap();
    assert!(html.contains("<html"));
    assert!(html.contains("High CPU Usage"));
    assert!(html.contains("prod-web-01"));
}

#[test]
fn test_format_email_missing_address() {
    let formatter = EmailFormatter::new();
    let request = create_test_request();
    let mut settings = create_test_settings();
    
    // Remove email address from settings
    settings.channels.get_mut("email").unwrap().remove("address");
    
    let result = formatter.format_message(&request, &settings);
    assert!(result.is_err());
    
    match result.unwrap_err() {
        ProviderError::InvalidConfiguration(msg) => {
            assert!(msg.contains("email address"));
        }
        _ => panic!("Expected InvalidConfiguration error"),
    }
}

#[test]
fn test_format_email_disabled_channel() {
    let formatter = EmailFormatter::new();
    let request = create_test_request();
    let mut settings = create_test_settings();
    
    // Disable email channel
    settings.channels.get_mut("email").unwrap()
        .insert("enabled".to_string(), serde_json::json!(false));
    
    let result = formatter.format_message(&request, &settings);
    assert!(result.is_err());
    
    match result.unwrap_err() {
        ProviderError::ChannelDisabled => {}
        _ => panic!("Expected ChannelDisabled error"),
    }
}

#[test]
fn test_validate_email_payload() {
    let formatter = EmailFormatter::new();
    
    let valid_payload = EmailPayload {
        to: "user@example.com".to_string(),
        from: "noreply@ekko.zone".to_string(),
        subject: "Test Subject".to_string(),
        text_content: "Test content".to_string(),
        html_content: Some("<html><body>Test</body></html>".to_string()),
        reply_to: None,
        cc: vec![],
        bcc: vec![],
        attachments: vec![],
        headers: HashMap::new(),
    };
    
    assert!(formatter.validate_payload(&valid_payload).is_ok());
}

#[test]
fn test_validate_invalid_email_address() {
    let formatter = EmailFormatter::new();
    
    let invalid_payload = EmailPayload {
        to: "not-an-email".to_string(),
        from: "noreply@ekko.zone".to_string(),
        subject: "Test Subject".to_string(),
        text_content: "Test content".to_string(),
        html_content: None,
        reply_to: None,
        cc: vec![],
        bcc: vec![],
        attachments: vec![],
        headers: HashMap::new(),
    };
    
    let result = formatter.validate_payload(&invalid_payload);
    assert!(result.is_err());
    
    match result.unwrap_err() {
        ProviderError::MalformedPayload(msg) => {
            assert!(msg.contains("Invalid email address"));
        }
        _ => panic!("Expected MalformedPayload error"),
    }
}

#[test]
fn test_validate_empty_subject() {
    let formatter = EmailFormatter::new();
    
    let invalid_payload = EmailPayload {
        to: "user@example.com".to_string(),
        from: "noreply@ekko.zone".to_string(),
        subject: "".to_string(),
        text_content: "Test content".to_string(),
        html_content: None,
        reply_to: None,
        cc: vec![],
        bcc: vec![],
        attachments: vec![],
        headers: HashMap::new(),
    };
    
    let result = formatter.validate_payload(&invalid_payload);
    assert!(result.is_err());
    
    match result.unwrap_err() {
        ProviderError::MalformedPayload(msg) => {
            assert!(msg.contains("subject"));
        }
        _ => panic!("Expected MalformedPayload error"),
    }
}

#[test]
fn test_format_with_template_rendering() {
    let formatter = EmailFormatter::new();
    let mut request = create_test_request();
    request.template_name = Some("alert_email".to_string());
    request.template_variables.insert("alert_url".to_string(), "https://ekko.zone/alerts/456".to_string());
    
    let settings = create_test_settings();
    
    let result = formatter.format_message(&request, &settings);
    assert!(result.is_ok());
    
    let payload = result.unwrap();
    // Template should be rendered with variables
    assert!(payload.html_content.is_some());
    let html = payload.html_content.unwrap();
    assert!(html.contains("https://ekko.zone/alerts/456"));
}

#[test]
fn test_format_with_actions() {
    let formatter = EmailFormatter::new();
    let mut request = create_test_request();
    request.actions = vec![
        NotificationAction {
            label: "View Alert".to_string(),
            url: "https://ekko.zone/alerts/456".to_string(),
        },
        NotificationAction {
            label: "Acknowledge".to_string(),
            url: "https://ekko.zone/alerts/456/ack".to_string(),
        },
    ];
    
    let settings = create_test_settings();
    
    let result = formatter.format_message(&request, &settings);
    assert!(result.is_ok());
    
    let payload = result.unwrap();
    assert!(payload.html_content.is_some());
    let html = payload.html_content.unwrap();
    
    // Check that action buttons are included
    assert!(html.contains("View Alert"));
    assert!(html.contains("Acknowledge"));
    assert!(html.contains("https://ekko.zone/alerts/456"));
}

#[test]
fn test_format_with_cc_bcc() {
    let formatter = EmailFormatter::new();
    let request = create_test_request();
    let mut settings = create_test_settings();
    
    // Add CC and BCC to settings
    settings.channels.get_mut("email").unwrap()
        .insert("cc".to_string(), serde_json::json!(["manager@example.com"]));
    settings.channels.get_mut("email").unwrap()
        .insert("bcc".to_string(), serde_json::json!(["archive@example.com"]));
    
    let result = formatter.format_message(&request, &settings);
    assert!(result.is_ok());
    
    let payload = result.unwrap();
    assert_eq!(payload.cc, vec!["manager@example.com"]);
    assert_eq!(payload.bcc, vec!["archive@example.com"]);
}

#[test]
fn test_html_sanitization() {
    let formatter = EmailFormatter::new();
    let mut request = create_test_request();
    // Inject potentially dangerous HTML
    request.message = "Alert: <script>alert('xss')</script> detected".to_string();
    
    let settings = create_test_settings();
    
    let result = formatter.format_message(&request, &settings);
    assert!(result.is_ok());
    
    let payload = result.unwrap();
    assert!(payload.html_content.is_some());
    let html = payload.html_content.unwrap();
    
    // Script tags should be removed
    assert!(!html.contains("<script"));
    assert!(!html.contains("alert('xss')"));
    // But the text content should remain
    assert!(html.contains("Alert:"));
    assert!(html.contains("detected"));
}