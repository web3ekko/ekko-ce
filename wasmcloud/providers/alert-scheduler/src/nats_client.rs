use crate::{AlertSchedulerError, Result};
use alert_runtime_common::{job_create_subject, AlertEvaluationJobV1, JobPriorityV1};
use async_nats::jetstream;
use async_nats::Client;
use async_trait::async_trait;
use serde::Serialize;
use tracing::{debug, info, warn};

#[async_trait]
pub trait AlertSchedulerPublisher: Send + Sync {
    async fn publish_schedule_request_bytes(
        &self,
        subject: &str,
        msg_id: &str,
        payload: Vec<u8>,
    ) -> Result<()>;

    async fn publish_evaluation_job(
        &self,
        job: &AlertEvaluationJobV1,
        priority: &JobPriorityV1,
    ) -> Result<()>;
}

/// NATS JetStream client for alert scheduler runtime.
#[derive(Clone)]
pub struct NatsClient {
    client: Client,
    jetstream: jetstream::Context,
    jobs_stream_name: String,
}

impl NatsClient {
    pub async fn new(nats_url: &str, jobs_stream_name: String) -> Result<Self> {
        info!("Connecting to NATS at {}", nats_url);

        let client = async_nats::connect(nats_url).await.map_err(|e| {
            AlertSchedulerError::Configuration(format!("Failed to connect to NATS: {}", e))
        })?;

        let jetstream = jetstream::new(client.clone());
        Self::ensure_jobs_stream(&jetstream, &jobs_stream_name).await?;

        Ok(Self {
            client,
            jetstream,
            jobs_stream_name,
        })
    }

    async fn ensure_jobs_stream(js: &jetstream::Context, stream_name: &str) -> Result<()> {
        let stream_config = jetstream::stream::Config {
            name: stream_name.to_string(),
            description: Some("Alert evaluation job queue".to_string()),
            subjects: vec!["alerts.jobs.create.>".to_string()],
            retention: jetstream::stream::RetentionPolicy::WorkQueue,
            storage: jetstream::stream::StorageType::File,
            max_messages: 1_000_000,
            max_bytes: 10_737_418_240,
            max_age: std::time::Duration::from_secs(86400),
            max_message_size: 1_048_576,
            duplicate_window: std::time::Duration::from_secs(300),
            allow_rollup: false,
            deny_delete: false,
            deny_purge: false,
            ..Default::default()
        };

        match js.get_stream(stream_name).await {
            Ok(_) => {
                debug!("Jobs stream {} already exists", stream_name);
            }
            Err(_) => {
                info!("Creating jobs stream: {}", stream_name);
                js.create_stream(stream_config).await.map_err(|e| {
                    AlertSchedulerError::Configuration(format!(
                        "Failed to create stream {}: {}",
                        stream_name, e
                    ))
                })?;
            }
        }

        Ok(())
    }

    async fn ensure_schedule_requests_stream(js: &jetstream::Context) -> Result<()> {
        let stream_name = "ALERT_SCHEDULE_REQUESTS";
        let stream_config = jetstream::stream::Config {
            name: stream_name.to_string(),
            description: Some("Alert schedule requests".to_string()),
            subjects: vec!["alerts.schedule.>".to_string()],
            retention: jetstream::stream::RetentionPolicy::WorkQueue,
            storage: jetstream::stream::StorageType::File,
            max_messages: 500_000,
            max_bytes: 5_368_709_120,
            max_age: std::time::Duration::from_secs(7200),
            max_message_size: 524_288,
            duplicate_window: std::time::Duration::from_secs(300),
            allow_rollup: false,
            deny_delete: false,
            deny_purge: false,
            ..Default::default()
        };

        match js.get_stream(stream_name).await {
            Ok(_) => Ok(()),
            Err(_) => {
                info!("Creating schedule requests stream");
                js.create_stream(stream_config).await.map_err(|e| {
                    AlertSchedulerError::Configuration(format!(
                        "Failed to create schedule requests stream: {}",
                        e
                    ))
                })?;
                Ok(())
            }
        }
    }

    pub async fn subscribe_to_schedule_requests(
        &self,
    ) -> Result<jetstream::consumer::pull::Stream> {
        info!("Setting up subscription for schedule requests");
        Self::ensure_schedule_requests_stream(&self.jetstream).await?;

        let stream = self
            .jetstream
            .get_stream("ALERT_SCHEDULE_REQUESTS")
            .await
            .map_err(|e| {
                AlertSchedulerError::NatsConnection(format!("Failed to get stream: {}", e))
            })?;

        let consumer_config = jetstream::consumer::pull::Config {
            durable_name: Some("alert-scheduler-provider".to_string()),
            description: Some(
                "Alert Scheduler Provider consumer for schedule requests".to_string(),
            ),
            ack_policy: jetstream::consumer::AckPolicy::Explicit,
            ack_wait: std::time::Duration::from_secs(30),
            max_deliver: 5,
            filter_subject: "alerts.schedule.>".to_string(),
            replay_policy: jetstream::consumer::ReplayPolicy::Instant,
            ..Default::default()
        };

        let consumer_name = consumer_config
            .durable_name
            .clone()
            .unwrap_or_else(|| "alert-scheduler-provider".to_string());

        let consumer = create_or_get_consumer(
            || stream.create_consumer(consumer_config),
            || stream.get_consumer(&consumer_name),
        )
        .await?;

        let messages = consumer.messages().await.map_err(|e| {
            AlertSchedulerError::NatsConnection(format!("Failed to create message stream: {}", e))
        })?;

        Ok(messages)
    }

    pub async fn publish_schedule_request<T: Serialize>(
        &self,
        subject: &str,
        msg_id: &str,
        payload: &T,
    ) -> Result<()> {
        let bytes = serde_json::to_vec(payload)?;

        let mut headers = async_nats::HeaderMap::new();
        headers.insert("Nats-Msg-Id", msg_id);

        self.jetstream
            .publish_with_headers(subject.to_string(), headers, bytes.into())
            .await
            .map_err(|e| {
                AlertSchedulerError::NatsPublish(format!(
                    "Failed to publish schedule request: {}",
                    e
                ))
            })?
            .await
            .map_err(|e| AlertSchedulerError::NatsPublish(format!("Publish ack failed: {}", e)))?;

        Ok(())
    }

    pub async fn publish_schedule_request_bytes(
        &self,
        subject: &str,
        msg_id: &str,
        payload: Vec<u8>,
    ) -> Result<()> {
        let mut headers = async_nats::HeaderMap::new();
        headers.insert("Nats-Msg-Id", msg_id);

        self.jetstream
            .publish_with_headers(subject.to_string(), headers, payload.into())
            .await
            .map_err(|e| {
                AlertSchedulerError::NatsPublish(format!(
                    "Failed to publish schedule request: {}",
                    e
                ))
            })?
            .await
            .map_err(|e| AlertSchedulerError::NatsPublish(format!("Publish ack failed: {}", e)))?;

        Ok(())
    }

    pub async fn publish_evaluation_job(
        &self,
        job: &AlertEvaluationJobV1,
        priority: &JobPriorityV1,
    ) -> Result<()> {
        let trigger_type = job.evaluation_context.run.trigger_type.clone();
        let subject = job_create_subject(trigger_type, priority.clone());

        let bytes = serde_json::to_vec(job)?;
        if bytes.len() > 1_048_576 {
            warn!(
                "job payload too large ({} bytes) for job_id={}",
                bytes.len(),
                job.job.job_id
            );
        }

        let mut headers = async_nats::HeaderMap::new();
        headers.insert("Nats-Msg-Id", job.job.job_id.as_str());
        headers.insert("job-id", job.job.job_id.as_str());
        headers.insert(
            "instance-id",
            job.evaluation_context.instance.instance_id.as_str(),
        );
        headers.insert("run-id", job.evaluation_context.run.run_id.as_str());

        self.jetstream
            .publish_with_headers(subject, headers, bytes.into())
            .await
            .map_err(|e| {
                AlertSchedulerError::NatsPublish(format!(
                    "Failed to publish job {}: {}",
                    job.job.job_id, e
                ))
            })?
            .await
            .map_err(|e| {
                AlertSchedulerError::NatsPublish(format!(
                    "Failed to ack job {}: {}",
                    job.job.job_id, e
                ))
            })?;

        Ok(())
    }
}

async fn create_or_get_consumer<T, CreateErr, GetErr, CreateFut, GetFut, CreateFn, GetFn>(
    create: CreateFn,
    get: GetFn,
) -> Result<T>
where
    CreateFn: FnOnce() -> CreateFut,
    GetFn: FnOnce() -> GetFut,
    CreateFut: std::future::Future<Output = std::result::Result<T, CreateErr>>,
    GetFut: std::future::Future<Output = std::result::Result<T, GetErr>>,
    CreateErr: std::fmt::Display,
    GetErr: std::fmt::Display,
{
    match create().await {
        Ok(consumer) => Ok(consumer),
        Err(create_err) => match get().await {
            Ok(consumer) => Ok(consumer),
            Err(get_err) => Err(AlertSchedulerError::Configuration(format!(
                "Failed to create consumer: {create_err}; failed to get existing consumer: {get_err}"
            ))),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::create_or_get_consumer;
    use crate::AlertSchedulerError;
    use std::sync::{
        atomic::{AtomicUsize, Ordering},
        Arc,
    };

    #[tokio::test]
    async fn create_consumer_success_short_circuits_get() {
        let get_calls = Arc::new(AtomicUsize::new(0));
        let get_calls_clone = get_calls.clone();

        let result = create_or_get_consumer(
            || async { Ok::<_, String>("created") },
            move || {
                get_calls_clone.fetch_add(1, Ordering::SeqCst);
                async { Ok::<_, String>("existing") }
            },
        )
        .await;

        assert_eq!(result.unwrap(), "created");
        assert_eq!(get_calls.load(Ordering::SeqCst), 0);
    }

    #[tokio::test]
    async fn create_consumer_falls_back_to_get() {
        let result = create_or_get_consumer(
            || async { Err::<&str, _>("create failed") },
            || async { Ok::<_, &str>("existing") },
        )
        .await;

        assert_eq!(result.unwrap(), "existing");
    }

    #[tokio::test]
    async fn create_consumer_returns_error_when_get_fails() {
        let result = create_or_get_consumer(
            || async { Err::<&str, _>("create failed") },
            || async { Err::<&str, _>("get failed") },
        )
        .await;

        match result {
            Err(AlertSchedulerError::Configuration(message)) => {
                assert!(message.contains("create failed"));
                assert!(message.contains("get failed"));
            }
            other => panic!("unexpected result: {:?}", other),
        }
    }
}

#[async_trait]
impl AlertSchedulerPublisher for NatsClient {
    async fn publish_schedule_request_bytes(
        &self,
        subject: &str,
        msg_id: &str,
        payload: Vec<u8>,
    ) -> Result<()> {
        NatsClient::publish_schedule_request_bytes(self, subject, msg_id, payload).await
    }

    async fn publish_evaluation_job(
        &self,
        job: &AlertEvaluationJobV1,
        priority: &JobPriorityV1,
    ) -> Result<()> {
        NatsClient::publish_evaluation_job(self, job, priority).await
    }
}
