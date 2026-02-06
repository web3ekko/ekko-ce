pub mod client;
pub mod config;
pub mod formatter;
pub mod provider;

pub use client::{ResendClient, ResendResponse, ResendResponseWrapper};
pub use config::EmailConfig;
pub use formatter::{EmailAttachment, EmailFormatter, EmailPayload};
pub use provider::EmailProvider;
