use std::collections::HashMap;
use std::sync::Arc;

use anyhow::Result;
use tracing::{info, instrument};
use wasmcloud_provider_sdk::Provider;

use crate::evaluator::EvalLimits;
use crate::nats_listener::{NatsEvalListener, NatsEvalListenerConfig};

/// Polars Eval Provider (AST evaluation only)
///
/// - Subscribes: `alerts.eval.request.*`
/// - Publishes:  `alerts.eval.response.{request_id}` (and replies on request-reply subjects)
#[derive(Clone)]
pub struct PolarsEvalProvider {
    limits: EvalLimits,
    config: NatsEvalListenerConfig,
}

impl PolarsEvalProvider {
    #[instrument]
    pub fn new() -> Self {
        Self {
            limits: EvalLimits::default(),
            config: NatsEvalListenerConfig::from_env(),
        }
    }

    #[instrument]
    pub fn with_config(config: NatsEvalListenerConfig) -> Self {
        Self {
            limits: EvalLimits::default(),
            config,
        }
    }

    #[instrument]
    pub fn from_properties(props: &HashMap<String, String>) -> Self {
        Self::with_config(NatsEvalListenerConfig::from_properties(props))
    }

    #[instrument(skip(self))]
    pub async fn start(self: Arc<Self>) -> Result<()> {
        info!("Starting Polars Eval Provider");

        let listener = NatsEvalListener::new(self.config.clone(), self.limits.clone());
        listener.start().await
    }
}

impl Default for PolarsEvalProvider {
    fn default() -> Self {
        Self::new()
    }
}

impl Provider for PolarsEvalProvider {}

#[cfg(test)]
mod tests {
    use super::*;
    use wasmcloud_provider_sdk::Provider;

    #[test]
    fn test_provider_traits() {
        fn assert_provider<T: Provider + Clone>() {}
        assert_provider::<PolarsEvalProvider>();
    }
}
