use anyhow::{Context, Result};
use futures::StreamExt;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Semaphore;
use tracing::{debug, error, info, instrument, warn};

use crate::evaluator::{evaluate_request, evaluate_request_v2, EvalLimits};

use alert_runtime_common::{
    polars_eval_request_schema_version_v1, polars_eval_request_schema_version_v2,
    PolarsEvalRequestV1, PolarsEvalRequestV2,
};

/// NATS listener configuration
#[derive(Debug, Clone)]
pub struct NatsEvalListenerConfig {
    pub nats_url: String,
    pub subscribe_subject: String,
    pub publish_prefix: String,
    pub max_concurrency: usize,
}

impl NatsEvalListenerConfig {
    const DEFAULT_NATS_URL: &'static str = "nats://localhost:4222";
    const DEFAULT_SUBSCRIBE_SUBJECT: &'static str = "alerts.eval.request.*";
    const DEFAULT_PUBLISH_PREFIX: &'static str = "alerts.eval.response";
    const DEFAULT_MAX_CONCURRENCY: usize = 32;

    pub fn from_env() -> Self {
        let nats_url =
            std::env::var("NATS_URL").unwrap_or_else(|_| Self::DEFAULT_NATS_URL.to_string());
        let subscribe_subject = std::env::var("POLARS_EVAL_SUBJECT")
            .unwrap_or_else(|_| Self::DEFAULT_SUBSCRIBE_SUBJECT.to_string());
        let publish_prefix = std::env::var("POLARS_EVAL_PUBLISH_PREFIX")
            .unwrap_or_else(|_| Self::DEFAULT_PUBLISH_PREFIX.to_string());
        let max_concurrency = std::env::var("POLARS_EVAL_MAX_CONCURRENCY")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(Self::DEFAULT_MAX_CONCURRENCY);

        Self {
            nats_url,
            subscribe_subject,
            publish_prefix,
            max_concurrency,
        }
    }

    pub fn from_properties(props: &HashMap<String, String>) -> Self {
        let nats_url = props
            .get("nats_url")
            .or_else(|| props.get("NATS_URL"))
            .cloned()
            .unwrap_or_else(|| Self::DEFAULT_NATS_URL.to_string());
        let subscribe_subject = props
            .get("polars_eval_subject")
            .or_else(|| props.get("POLARS_EVAL_SUBJECT"))
            .cloned()
            .unwrap_or_else(|| Self::DEFAULT_SUBSCRIBE_SUBJECT.to_string());
        let publish_prefix = props
            .get("polars_eval_publish_prefix")
            .or_else(|| props.get("POLARS_EVAL_PUBLISH_PREFIX"))
            .cloned()
            .unwrap_or_else(|| Self::DEFAULT_PUBLISH_PREFIX.to_string());
        let max_concurrency = props
            .get("polars_eval_max_concurrency")
            .or_else(|| props.get("POLARS_EVAL_MAX_CONCURRENCY"))
            .and_then(|value| value.parse().ok())
            .unwrap_or(Self::DEFAULT_MAX_CONCURRENCY);

        Self {
            nats_url,
            subscribe_subject,
            publish_prefix,
            max_concurrency,
        }
    }
}

pub struct NatsEvalListener {
    config: NatsEvalListenerConfig,
    limits: EvalLimits,
}

impl NatsEvalListener {
    pub fn new(config: NatsEvalListenerConfig, limits: EvalLimits) -> Self {
        Self { config, limits }
    }

    #[instrument(skip(self))]
    pub async fn start(self) -> Result<()> {
        info!("Connecting to NATS at {}", self.config.nats_url);
        let client = async_nats::connect(&self.config.nats_url)
            .await
            .context("failed to connect to NATS")?;

        info!("Subscribing to {}", self.config.subscribe_subject);
        let mut sub = client
            .subscribe(self.config.subscribe_subject.clone())
            .await
            .context("failed to subscribe")?;

        let sem = Arc::new(Semaphore::new(self.config.max_concurrency));

        info!("Polars Eval Provider ready");

        while let Some(message) = sub.next().await {
            let permit = match sem.clone().acquire_owned().await {
                Ok(p) => p,
                Err(_) => break,
            };

            let client = client.clone();
            let limits = self.limits.clone();
            let publish_prefix = self.config.publish_prefix.clone();

            tokio::spawn(async move {
                let _permit = permit;
                if let Err(e) = handle_message(&client, &publish_prefix, &limits, message).await {
                    error!("polars-eval handle_message failed: {e:?}");
                }
            });
        }

        warn!("NATS subscription ended");
        Ok(())
    }
}

async fn handle_message(
    client: &async_nats::Client,
    publish_prefix: &str,
    limits: &EvalLimits,
    message: async_nats::Message,
) -> Result<()> {
    let payload: serde_json::Value = match serde_json::from_slice(&message.payload) {
        Ok(value) => value,
        Err(e) => {
            debug!("failed to parse request: {e}");
            return Ok(());
        }
    };

    let schema_version = payload
        .get("schema_version")
        .and_then(|v| v.as_str())
        .unwrap_or_default();

    let (request_id, bytes) = match schema_version {
        v if v == polars_eval_request_schema_version_v1() => {
            let request: PolarsEvalRequestV1 =
                serde_json::from_value(payload).context("failed to parse PolarsEvalRequestV1")?;
            let response = evaluate_request(&request, limits);
            let bytes = serde_json::to_vec(&response).context("failed to serialize response")?;
            (request.request_id, bytes)
        }
        v if v == polars_eval_request_schema_version_v2() => {
            let request: PolarsEvalRequestV2 =
                serde_json::from_value(payload).context("failed to parse PolarsEvalRequestV2")?;
            let response = evaluate_request_v2(&request, limits);
            let bytes = serde_json::to_vec(&response).context("failed to serialize response")?;
            (request.request_id, bytes)
        }
        other => {
            debug!("ignoring unexpected schema_version {}", other);
            return Ok(());
        }
    };

    // Always publish to the canonical response subject for observability.
    let pub_subject = format!("{publish_prefix}.{}", request_id);
    client
        .publish(pub_subject, bytes.clone().into())
        .await
        .context("failed to publish response")?;

    // Reply to request-reply callers (Alerts Processor uses this).
    if let Some(reply) = message.reply {
        client
            .publish(reply, bytes.into())
            .await
            .context("failed to reply")?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::NatsEvalListenerConfig;
    use std::collections::HashMap;

    #[test]
    fn config_from_properties_uses_overrides() {
        let mut props = HashMap::new();
        props.insert("nats_url".to_string(), "nats://example:4222".to_string());
        props.insert(
            "polars_eval_subject".to_string(),
            "alerts.eval.request.test".to_string(),
        );
        props.insert(
            "polars_eval_publish_prefix".to_string(),
            "alerts.eval.response.test".to_string(),
        );
        props.insert("polars_eval_max_concurrency".to_string(), "12".to_string());

        let config = NatsEvalListenerConfig::from_properties(&props);

        assert_eq!(config.nats_url, "nats://example:4222");
        assert_eq!(config.subscribe_subject, "alerts.eval.request.test");
        assert_eq!(config.publish_prefix, "alerts.eval.response.test");
        assert_eq!(config.max_concurrency, 12);
    }

    #[test]
    fn config_from_properties_handles_invalid_concurrency() {
        let mut props = HashMap::new();
        props.insert(
            "polars_eval_max_concurrency".to_string(),
            "bogus".to_string(),
        );

        let config = NatsEvalListenerConfig::from_properties(&props);

        assert_eq!(config.max_concurrency, 32);
    }
}
