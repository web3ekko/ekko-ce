//! Validation utilities for notification requests and configurations
//!
//! This module provides comprehensive validation for notification data,
//! user settings, and provider configurations.

use crate::{
    ChannelSettings, GroupNotificationSettings, NotificationChannel, NotificationContent,
    NotificationPriority, NotificationRequest, UserNotificationSettings,
};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Validation errors
#[derive(Debug, Error, Clone)]
pub enum ValidationError {
    #[error("Missing required field: {field}")]
    MissingField { field: String },

    #[error("Invalid format for field {field}: {reason}")]
    InvalidFormat { field: String, reason: String },

    #[error("Field {field} exceeds maximum length of {max_length}")]
    TooLong { field: String, max_length: usize },

    #[error("Field {field} is below minimum length of {min_length}")]
    TooShort { field: String, min_length: usize },

    #[error("Invalid channel configuration: {0}")]
    InvalidChannelConfig(String),

    #[error("Channel {0} is disabled")]
    ChannelDisabled(String),

    #[error("Missing channel configuration for: {0}")]
    MissingChannelConfig(String),

    #[error("Invalid email address: {0}")]
    InvalidEmail(String),

    #[error("Invalid phone number: {0}")]
    InvalidPhoneNumber(String),

    #[error("Invalid URL: {0}")]
    InvalidUrl(String),

    #[error("Invalid time format: {0}")]
    InvalidTimeFormat(String),

    #[error("Invalid timezone: {0}")]
    InvalidTimezone(String),

    #[error("Quiet hours configuration error: {0}")]
    QuietHoursError(String),

    #[error("Template variable missing: {0}")]
    MissingTemplateVariable(String),

    #[error("Content validation error: {0}")]
    ContentError(String),
}

/// Validation result type
pub type ValidationResult<T> = Result<T, ValidationError>;

/// Trait for validating notification-related data
pub trait Validate {
    fn validate(&self) -> ValidationResult<()>;
}

impl Validate for NotificationRequest {
    fn validate(&self) -> ValidationResult<()> {
        // Validate context
        if let Some(context) = &self.context {
            context.validate()?;
        }

        // Validate content
        if let Some(content) = &self.content {
            content.validate()?;
        }

        // Validate template name
        if let Some(template_name) = &self.template_name {
            if template_name.is_empty() {
                return Err(ValidationError::MissingField {
                    field: "template_name".to_string(),
                });
            }

            if template_name.len() > 100 {
                return Err(ValidationError::TooLong {
                    field: "template_name".to_string(),
                    max_length: 100,
                });
            }
        }

        // Validate target channels
        if self.target_channels.is_empty() {
            return Err(ValidationError::MissingField {
                field: "target_channels".to_string(),
            });
        }

        // Validate delivery options
        self.delivery_options.validate()?;

        Ok(())
    }
}

impl Validate for crate::NotificationContext {
    fn validate(&self) -> ValidationResult<()> {
        if self.user_id.is_empty() {
            return Err(ValidationError::MissingField {
                field: "user_id".to_string(),
            });
        }

        if self.alert_id.is_empty() {
            return Err(ValidationError::MissingField {
                field: "alert_id".to_string(),
            });
        }

        if self.request_id.is_empty() {
            return Err(ValidationError::MissingField {
                field: "request_id".to_string(),
            });
        }

        // Validate UUID format for request_id
        if uuid::Uuid::parse_str(&self.request_id).is_err() {
            return Err(ValidationError::InvalidFormat {
                field: "request_id".to_string(),
                reason: "Must be a valid UUID".to_string(),
            });
        }

        Ok(())
    }
}

impl Validate for NotificationContent {
    fn validate(&self) -> ValidationResult<()> {
        if self.subject.is_empty() {
            return Err(ValidationError::MissingField {
                field: "subject".to_string(),
            });
        }

        if self.subject.len() > 200 {
            return Err(ValidationError::TooLong {
                field: "subject".to_string(),
                max_length: 200,
            });
        }

        if self.text_content.is_empty() && self.html_content.is_none() {
            return Err(ValidationError::ContentError(
                "Either text_content or html_content must be provided".to_string(),
            ));
        }

        if self.text_content.len() > 4000 {
            return Err(ValidationError::TooLong {
                field: "text_content".to_string(),
                max_length: 4000,
            });
        }

        if let Some(html) = &self.html_content {
            if html.len() > 8000 {
                return Err(ValidationError::TooLong {
                    field: "html_content".to_string(),
                    max_length: 8000,
                });
            }
        }

        // Validate actions if present
        if let Some(actions) = &self.actions {
            for (i, action) in actions.iter().enumerate() {
                if action.label.is_empty() {
                    return Err(ValidationError::MissingField {
                        field: format!("actions[{}].label", i),
                    });
                }

                if action.url.is_empty() {
                    return Err(ValidationError::MissingField {
                        field: format!("actions[{}].url", i),
                    });
                }

                validate_url(&action.url)?;
            }
        }

        Ok(())
    }
}

impl Validate for crate::DeliveryOptions {
    fn validate(&self) -> ValidationResult<()> {
        // Validate sender email if provided
        if let Some(email) = &self.sender_email {
            validate_email(email)?;
        }

        // Validate reply-to email if provided
        if let Some(reply_to) = &self.reply_to {
            validate_email(reply_to)?;
        }

        // Validate sender phone if provided
        if let Some(phone) = &self.sender_phone {
            validate_phone_number(phone)?;
        }

        Ok(())
    }
}

impl Validate for UserNotificationSettings {
    fn validate(&self) -> ValidationResult<()> {
        if self.user_id.is_empty() {
            return Err(ValidationError::MissingField {
                field: "user_id".to_string(),
            });
        }

        // Validate channel settings
        for (channel_name, settings) in &self.channels {
            validate_channel_settings(channel_name, settings)?;
        }

        // Validate quiet hours if present
        if let Some(quiet_hours) = &self.quiet_hours {
            quiet_hours.validate()?;
        }

        Ok(())
    }
}

impl Validate for GroupNotificationSettings {
    fn validate(&self) -> ValidationResult<()> {
        if self.group_id.is_empty() {
            return Err(ValidationError::MissingField {
                field: "group_id".to_string(),
            });
        }

        if self.group_name.is_empty() {
            return Err(ValidationError::MissingField {
                field: "group_name".to_string(),
            });
        }

        // Validate shared channel settings
        for (channel_name, settings) in &self.shared_channels {
            validate_channel_settings(channel_name, settings)?;
        }

        Ok(())
    }
}

impl Validate for crate::QuietHours {
    fn validate(&self) -> ValidationResult<()> {
        // Validate time formats (HH:MM)
        validate_time_format(&self.start_time)?;
        validate_time_format(&self.end_time)?;

        // Validate timezone
        if self.timezone.is_empty() {
            return Err(ValidationError::MissingField {
                field: "timezone".to_string(),
            });
        }

        // Basic timezone validation (could be enhanced with chrono-tz)
        if !self.timezone.contains('/') && !self.timezone.starts_with("UTC") {
            return Err(ValidationError::InvalidTimezone(self.timezone.clone()));
        }

        Ok(())
    }
}

/// Validate email address format
pub fn validate_email(email: &str) -> ValidationResult<()> {
    let email_regex = Regex::new(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
        .map_err(|_| ValidationError::InvalidEmail("Regex compilation failed".to_string()))?;

    if !email_regex.is_match(email) {
        return Err(ValidationError::InvalidEmail(email.to_string()));
    }

    if email.len() > 254 {
        return Err(ValidationError::TooLong {
            field: "email".to_string(),
            max_length: 254,
        });
    }

    Ok(())
}

/// Validate phone number format (basic validation)
pub fn validate_phone_number(phone: &str) -> ValidationResult<()> {
    // Remove common formatting characters
    let cleaned = phone
        .chars()
        .filter(|c| c.is_ascii_digit() || *c == '+')
        .collect::<String>();

    if cleaned.is_empty() {
        return Err(ValidationError::InvalidPhoneNumber(
            "Phone number cannot be empty".to_string(),
        ));
    }

    // Basic length check (international format)
    if cleaned.len() < 7 || cleaned.len() > 15 {
        return Err(ValidationError::InvalidPhoneNumber(format!(
            "Phone number length must be between 7 and 15 digits, got {}",
            cleaned.len()
        )));
    }

    // Must start with + or digit
    if !cleaned.starts_with('+') && !cleaned.chars().next().unwrap().is_ascii_digit() {
        return Err(ValidationError::InvalidPhoneNumber(
            "Phone number must start with + or a digit".to_string(),
        ));
    }

    Ok(())
}

/// Validate URL format
pub fn validate_url(url: &str) -> ValidationResult<()> {
    if url.is_empty() {
        return Err(ValidationError::InvalidUrl(
            "URL cannot be empty".to_string(),
        ));
    }

    // Basic URL validation
    if !url.starts_with("http://") && !url.starts_with("https://") {
        return Err(ValidationError::InvalidUrl(
            "URL must start with http:// or https://".to_string(),
        ));
    }

    if url.len() > 2048 {
        return Err(ValidationError::TooLong {
            field: "url".to_string(),
            max_length: 2048,
        });
    }

    Ok(())
}

/// Validate time format (HH:MM)
fn validate_time_format(time: &str) -> ValidationResult<()> {
    let time_regex = Regex::new(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
        .map_err(|_| ValidationError::InvalidTimeFormat("Regex compilation failed".to_string()))?;

    if !time_regex.is_match(time) {
        return Err(ValidationError::InvalidTimeFormat(format!(
            "Time must be in HH:MM format, got: {}",
            time
        )));
    }

    Ok(())
}

/// Validate channel-specific settings
fn validate_channel_settings(
    channel_name: &str,
    settings: &ChannelSettings,
) -> ValidationResult<()> {
    match channel_name {
        "email" => {
            if settings.enabled {
                if let Some(address) = settings.config.get("address") {
                    if let Some(addr_str) = address.as_str() {
                        validate_email(addr_str)?;
                    } else {
                        return Err(ValidationError::InvalidChannelConfig(
                            "Email address must be a string".to_string(),
                        ));
                    }
                } else {
                    return Err(ValidationError::MissingChannelConfig(
                        "Email address is required when email is enabled".to_string(),
                    ));
                }
            }
        }
        "sms" => {
            if settings.enabled {
                if let Some(phone) = settings.config.get("phone") {
                    if let Some(phone_str) = phone.as_str() {
                        validate_phone_number(phone_str)?;
                    } else {
                        return Err(ValidationError::InvalidChannelConfig(
                            "Phone number must be a string".to_string(),
                        ));
                    }
                } else {
                    return Err(ValidationError::MissingChannelConfig(
                        "Phone number is required when SMS is enabled".to_string(),
                    ));
                }
            }
        }
        "slack" => {
            if settings.enabled {
                if let Some(channel) = settings.config.get("channel") {
                    if let Some(channel_str) = channel.as_str() {
                        if channel_str.is_empty() {
                            return Err(ValidationError::InvalidChannelConfig(
                                "Slack channel cannot be empty".to_string(),
                            ));
                        }
                    } else {
                        return Err(ValidationError::InvalidChannelConfig(
                            "Slack channel must be a string".to_string(),
                        ));
                    }
                }
            }
        }
        "webhook" => {
            if settings.enabled {
                if let Some(url) = settings.config.get("url") {
                    if let Some(url_str) = url.as_str() {
                        validate_url(url_str)?;
                    } else {
                        return Err(ValidationError::InvalidChannelConfig(
                            "Webhook URL must be a string".to_string(),
                        ));
                    }
                } else {
                    return Err(ValidationError::MissingChannelConfig(
                        "Webhook URL is required when webhook is enabled".to_string(),
                    ));
                }
            }
        }
        "discord" => {
            if settings.enabled {
                if let Some(webhook_url) = settings.config.get("webhook_url") {
                    if let Some(url_str) = webhook_url.as_str() {
                        validate_url(url_str)?;
                        if !url_str.contains("discord") || !url_str.contains("webhooks") {
                            return Err(ValidationError::InvalidChannelConfig(
                                "Discord webhook URL format is invalid".to_string(),
                            ));
                        }
                    } else {
                        return Err(ValidationError::InvalidChannelConfig(
                            "Discord webhook URL must be a string".to_string(),
                        ));
                    }
                } else {
                    return Err(ValidationError::MissingChannelConfig(
                        "Discord webhook URL is required when Discord is enabled".to_string(),
                    ));
                }
            }
        }
        _ => {
            // Allow other channels with basic validation
        }
    }

    Ok(())
}

/// Validate template variables are present
pub fn validate_template_variables(
    template_name: &str,
    variables: &HashMap<String, serde_json::Value>,
    required_vars: &[&str],
) -> ValidationResult<()> {
    for required_var in required_vars {
        if !variables.contains_key(*required_var) {
            return Err(ValidationError::MissingTemplateVariable(format!(
                "Template '{}' requires variable '{}'",
                template_name, required_var
            )));
        }
    }

    Ok(())
}

/// Sanitize text content for different channels
pub fn sanitize_for_channel(content: &str, channel: &NotificationChannel) -> String {
    match channel {
        NotificationChannel::Sms => {
            // Remove HTML tags and limit to 160 characters
            let text = strip_html_tags(content);
            if text.len() > 160 {
                format!("{}...", &text[..157])
            } else {
                text
            }
        }
        NotificationChannel::Email => {
            // Allow HTML but escape dangerous content
            escape_html_dangerous_content(content)
        }
        NotificationChannel::Slack => {
            // Convert HTML to Slack markdown
            convert_html_to_slack_markdown(content)
        }
        _ => content.to_string(),
    }
}

/// Strip HTML tags from content
fn strip_html_tags(content: &str) -> String {
    let tag_regex = Regex::new(r"<[^>]*>").unwrap();
    tag_regex.replace_all(content, "").to_string()
}

/// Escape dangerous HTML content
fn escape_html_dangerous_content(content: &str) -> String {
    content
        .replace("<script", "&lt;script")
        .replace("</script>", "&lt;/script&gt;")
        .replace("javascript:", "")
        .replace("vbscript:", "")
}

/// Convert HTML to Slack markdown (basic conversion)
fn convert_html_to_slack_markdown(content: &str) -> String {
    content
        .replace("<strong>", "*")
        .replace("</strong>", "*")
        .replace("<b>", "*")
        .replace("</b>", "*")
        .replace("<em>", "_")
        .replace("</em>", "_")
        .replace("<i>", "_")
        .replace("</i>", "_")
        .replace("<br>", "\n")
        .replace("<br/>", "\n")
        .replace("<br />", "\n")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{NotificationContext, NotificationPriority};
    use std::collections::HashMap;

    #[test]
    fn test_email_validation() {
        assert!(validate_email("user@example.com").is_ok());
        assert!(validate_email("test.user+tag@domain.co.uk").is_ok());
        assert!(validate_email("invalid-email").is_err());
        assert!(validate_email("@domain.com").is_err());
        assert!(validate_email("user@").is_err());
    }

    #[test]
    fn test_phone_validation() {
        assert!(validate_phone_number("+1234567890").is_ok());
        assert!(validate_phone_number("1234567890").is_ok());
        assert!(validate_phone_number("+44 20 7123 4567").is_ok()); // With spaces
        assert!(validate_phone_number("123").is_err()); // Too short
        assert!(validate_phone_number("12345678901234567890").is_err()); // Too long
        assert!(validate_phone_number("abc123").is_err()); // Contains letters
    }

    #[test]
    fn test_url_validation() {
        assert!(validate_url("https://example.com").is_ok());
        assert!(validate_url("http://localhost:3000/webhook").is_ok());
        assert!(validate_url("ftp://example.com").is_err());
        assert!(validate_url("not-a-url").is_err());
        assert!(validate_url("").is_err());
    }

    #[test]
    fn test_time_format_validation() {
        assert!(validate_time_format("09:30").is_ok());
        assert!(validate_time_format("23:59").is_ok());
        assert!(validate_time_format("00:00").is_ok());
        assert!(validate_time_format("25:00").is_err()); // Invalid hour
        assert!(validate_time_format("12:60").is_err()); // Invalid minute
        assert!(validate_time_format("9:30").is_ok()); // Single digit hour
    }

    #[test]
    fn test_notification_context_validation() {
        let mut context = NotificationContext::new(
            "user123".to_string(),
            "alert456".to_string(),
            NotificationPriority::Normal,
        );
        assert!(context.validate().is_ok());

        // Test empty user_id
        context.user_id = "".to_string();
        assert!(context.validate().is_err());

        // Reset and test empty alert_id
        context.user_id = "user123".to_string();
        context.alert_id = "".to_string();
        assert!(context.validate().is_err());
    }

    #[test]
    fn test_sanitize_for_channel() {
        let html_content =
            "<strong>Alert:</strong> <em>Balance</em> is <script>alert('xss')</script>low";

        // SMS should strip tags and limit length
        let sms_result = sanitize_for_channel(html_content, &NotificationChannel::Sms);
        assert!(!sms_result.contains("<strong>"));
        assert!(!sms_result.contains("<script>"));

        // Email should escape dangerous content but keep formatting
        let email_result = sanitize_for_channel(html_content, &NotificationChannel::Email);
        assert!(email_result.contains("<strong>"));
        assert!(email_result.contains("&lt;script"));

        // Slack should convert to markdown
        let slack_result = sanitize_for_channel(html_content, &NotificationChannel::Slack);
        assert!(slack_result.contains("*Alert:*"));
        assert!(slack_result.contains("_Balance_"));
    }
}
