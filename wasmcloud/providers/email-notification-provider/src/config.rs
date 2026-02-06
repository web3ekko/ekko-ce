use config::{Config, ConfigError, Environment, File};
use serde::{Deserialize, Serialize};
use std::env;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmailConfig {
    pub resend_api_key: String,
    pub resend_base_url: Option<String>,
    pub default_from_email: String,
    pub default_from_name: String,
    pub max_retries: u32,
    pub retry_delay_ms: u64,
    pub rate_limit_per_minute: u32,
    pub batch_size: usize,
    pub template_directory: Option<String>,
}

impl Default for EmailConfig {
    fn default() -> Self {
        Self {
            resend_api_key: String::new(),
            resend_base_url: None,
            default_from_email: "noreply@ekko.zone".to_string(),
            default_from_name: "Ekko Zone".to_string(),
            max_retries: 3,
            retry_delay_ms: 1000,
            rate_limit_per_minute: 100,
            batch_size: 10,
            template_directory: None,
        }
    }
}

impl EmailConfig {
    /// Create configuration from a properties map (for wasmCloud HostData)
    pub fn from_properties(
        props: &std::collections::HashMap<String, String>,
    ) -> Result<Self, ConfigError> {
        let resend_api_key = props
            .get("resend_api_key")
            .or_else(|| props.get("RESEND_API_KEY"))
            .cloned()
            .ok_or_else(|| ConfigError::Message("resend_api_key is required".to_string()))?;

        Ok(Self {
            resend_api_key,
            resend_base_url: props.get("resend_base_url").cloned(),
            default_from_email: props
                .get("default_from_email")
                .cloned()
                .unwrap_or_else(|| "noreply@ekko.zone".to_string()),
            default_from_name: props
                .get("default_from_name")
                .cloned()
                .unwrap_or_else(|| "Ekko Zone".to_string()),
            max_retries: props
                .get("max_retries")
                .and_then(|s| s.parse().ok())
                .unwrap_or(3),
            retry_delay_ms: props
                .get("retry_delay_ms")
                .and_then(|s| s.parse().ok())
                .unwrap_or(1000),
            rate_limit_per_minute: props
                .get("rate_limit_per_minute")
                .and_then(|s| s.parse().ok())
                .unwrap_or(100),
            batch_size: props
                .get("batch_size")
                .and_then(|s| s.parse().ok())
                .unwrap_or(10),
            template_directory: props.get("template_directory").cloned(),
        })
    }

    pub fn from_env() -> Result<Self, ConfigError> {
        let mut builder = Config::builder()
            .set_default("default_from_email", "noreply@ekko.zone")?
            .set_default("default_from_name", "Ekko Zone")?
            .set_default("max_retries", 3)?
            .set_default("retry_delay_ms", 1000)?
            .set_default("rate_limit_per_minute", 100)?
            .set_default("batch_size", 10)?;

        // Try to load from config file if it exists
        if let Ok(config_path) = env::var("EMAIL_CONFIG_PATH") {
            builder = builder.add_source(File::with_name(&config_path));
        }

        // Override with environment variables
        builder = builder.add_source(
            Environment::with_prefix("EMAIL")
                .separator("__")
                .try_parsing(true),
        );

        // Resend API key must come from environment
        if let Ok(api_key) = env::var("RESEND_API_KEY") {
            builder = builder.set_override("resend_api_key", api_key)?;
        }

        let config = builder.build()?;
        let email_config: EmailConfig = config.try_deserialize()?;

        // Validate required fields
        if email_config.resend_api_key.is_empty() {
            return Err(ConfigError::Message(
                "RESEND_API_KEY environment variable is required".to_string(),
            ));
        }

        Ok(email_config)
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.resend_api_key.is_empty() {
            return Err("Resend API key is required".to_string());
        }

        if self.default_from_email.is_empty() {
            return Err("Default from email is required".to_string());
        }

        if !email_address::EmailAddress::is_valid(&self.default_from_email) {
            return Err(format!(
                "Invalid default from email: {}",
                self.default_from_email
            ));
        }

        if self.max_retries > 10 {
            return Err("Max retries should not exceed 10".to_string());
        }

        if self.rate_limit_per_minute == 0 {
            return Err("Rate limit must be greater than 0".to_string());
        }

        if self.batch_size == 0 || self.batch_size > 100 {
            return Err("Batch size must be between 1 and 100".to_string());
        }

        Ok(())
    }
}
