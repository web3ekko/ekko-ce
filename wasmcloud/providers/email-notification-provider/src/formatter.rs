use crate::config::EmailConfig;
use ammonia::clean;
use handlebars::Handlebars;
use notification_common::{
    provider_base::ProviderError, NotificationChannel, NotificationPriority, NotificationRequest,
    UserNotificationSettings,
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailPayload {
    pub to: String,
    pub from: String,
    pub subject: String,
    pub text_content: String,
    pub html_content: Option<String>,
    pub reply_to: Option<String>,
    pub cc: Vec<String>,
    pub bcc: Vec<String>,
    pub attachments: Vec<EmailAttachment>,
    pub headers: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailAttachment {
    pub filename: String,
    pub content: String, // Base64 encoded
    pub content_type: String,
    pub disposition: String,
}

pub struct EmailFormatter {
    templates: Handlebars<'static>,
    default_from: String,
}

impl EmailFormatter {
    pub fn new() -> Self {
        let mut templates = Handlebars::new();
        templates.set_strict_mode(false);

        // Register default templates
        let _ = templates
            .register_template_string("alert_email", include_str!("../templates/alert_email.hbs"));

        Self {
            templates,
            default_from: "noreply@ekko.zone".to_string(),
        }
    }

    pub fn format_message(
        &self,
        request: &NotificationRequest,
        settings: &UserNotificationSettings,
    ) -> Result<EmailPayload, ProviderError> {
        // Check if email channel is enabled
        let email_config = settings
            .channels
            .get("email")
            .ok_or(ProviderError::ChannelDisabled)?;

        if !email_config.enabled {
            return Err(ProviderError::ChannelDisabled);
        }

        // Extract email address from config HashMap
        let to_address = email_config
            .config
            .get("address")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                ProviderError::InvalidConfiguration(
                    "Missing email address in user settings".to_string(),
                )
            })?
            .to_string();

        // Build subject with priority prefix
        let subject = match request.priority {
            NotificationPriority::Critical => format!("[CRITICAL] {}", request.title),
            NotificationPriority::High => format!("[HIGH] {}", request.title),
            _ => request.title.clone(),
        };

        // Generate HTML content
        let html_content = self.generate_html_content(request, settings)?;

        // Extract CC and BCC from config HashMap
        let cc = email_config
            .config
            .get("cc")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();

        let bcc = email_config
            .config
            .get("bcc")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();

        // Build payload
        let payload = EmailPayload {
            to: to_address,
            from: self.default_from.clone(),
            subject,
            text_content: request.message.clone(),
            html_content: Some(html_content),
            reply_to: None,
            cc,
            bcc,
            attachments: vec![],
            headers: HashMap::new(),
        };

        self.validate_payload(&payload)?;

        Ok(payload)
    }

    fn generate_html_content(
        &self,
        request: &NotificationRequest,
        settings: &UserNotificationSettings,
    ) -> Result<String, ProviderError> {
        let template_name = request.template_name.as_deref().unwrap_or("alert_email");

        // Build template context
        let mut context = HashMap::new();
        context.insert("title", request.title.clone());
        context.insert("message", self.sanitize_html(&request.message));
        context.insert("alert_name", request.alert_name.clone());
        context.insert("priority", format!("{:?}", request.priority));

        // Add template variables
        for (key, value) in &request.template_variables {
            context.insert(key.as_str(), value.clone());
        }

        // Add details
        for (key, value) in &request.details {
            context.insert(key.as_str(), value.to_string());
        }

        // Add actions as HTML
        if !request.actions.is_empty() {
            let actions_html = request.actions.iter()
                .map(|action| {
                    format!(
                        r#"<a href="{}" style="display: inline-block; padding: 10px 20px; margin: 5px; background-color: #007bff; color: white; text-decoration: none; border-radius: 4px;">{}</a>"#,
                        action.url, action.label
                    )
                })
                .collect::<Vec<_>>()
                .join(" ");
            context.insert("actions", actions_html);
        }

        // Try to render with template, fallback to basic HTML
        match self.templates.render(template_name, &context) {
            Ok(html) => Ok(html),
            Err(_) => {
                // Fallback to basic HTML template
                Ok(self.generate_basic_html(request))
            }
        }
    }

    fn generate_basic_html(&self, request: &NotificationRequest) -> String {
        let sanitized_message = self.sanitize_html(&request.message);

        let mut html = format!(
            r#"<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
        .content {{ margin: 20px 0; }}
        .details {{ background-color: #f0f0f0; padding: 10px; border-radius: 3px; }}
        .actions {{ margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>{}</h2>
        <p><strong>Alert:</strong> {}</p>
    </div>
    <div class="content">
        <p>{}</p>
    </div>"#,
            request.title, request.alert_name, sanitized_message
        );

        // Add details if present
        if !request.details.is_empty() {
            html.push_str(r#"<div class="details"><h3>Details:</h3><ul>"#);
            for (key, value) in &request.details {
                html.push_str(&format!("<li><strong>{}:</strong> {}</li>", key, value));
            }
            html.push_str("</ul></div>");
        }

        // Add actions if present
        if !request.actions.is_empty() {
            html.push_str(r#"<div class="actions">"#);
            for action in &request.actions {
                html.push_str(&format!(
                    r#"<a href="{}" style="display: inline-block; padding: 10px 20px; margin: 5px; background-color: #007bff; color: white; text-decoration: none; border-radius: 4px;">{}</a>"#,
                    action.url, action.label
                ));
            }
            html.push_str("</div>");
        }

        html.push_str("</body></html>");
        html
    }

    fn sanitize_html(&self, input: &str) -> String {
        // Remove script tags and dangerous HTML
        clean(input)
    }

    pub fn validate_payload(&self, payload: &EmailPayload) -> Result<(), ProviderError> {
        // Validate email addresses
        if !self.is_valid_email(&payload.to) {
            return Err(ProviderError::MalformedPayload(format!(
                "Invalid email address: {}",
                payload.to
            )));
        }

        if !self.is_valid_email(&payload.from) {
            return Err(ProviderError::MalformedPayload(format!(
                "Invalid email address: {}",
                payload.from
            )));
        }

        // Validate subject
        if payload.subject.is_empty() {
            return Err(ProviderError::MalformedPayload(
                "Email subject cannot be empty".to_string(),
            ));
        }

        // Validate content
        if payload.text_content.is_empty() && payload.html_content.is_none() {
            return Err(ProviderError::MalformedPayload(
                "Email must have either text or HTML content".to_string(),
            ));
        }

        // Validate CC addresses
        for cc in &payload.cc {
            if !self.is_valid_email(cc) {
                return Err(ProviderError::MalformedPayload(format!(
                    "Invalid CC email address: {}",
                    cc
                )));
            }
        }

        // Validate BCC addresses
        for bcc in &payload.bcc {
            if !self.is_valid_email(bcc) {
                return Err(ProviderError::MalformedPayload(format!(
                    "Invalid BCC email address: {}",
                    bcc
                )));
            }
        }

        Ok(())
    }

    fn is_valid_email(&self, email: &str) -> bool {
        // Use email_address crate for validation
        email_address::EmailAddress::is_valid(email)
    }
}

impl Default for EmailFormatter {
    fn default() -> Self {
        Self::new()
    }
}
