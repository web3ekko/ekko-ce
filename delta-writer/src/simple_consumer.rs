use anyhow::{Result, Context};
use async_nats::{Client, jetstream::{self, consumer::PullConsumer}};
use futures::{StreamExt, TryStreamExt};
use std::sync::Arc;
use std::collections::HashMap;
use tokio::sync::Mutex;
use tokio::time::Duration;
use tracing::{info, warn, error, debug};
use serde_json;

use crate::config::Config;
use crate::event_schema::BlockchainEvent;

/// Simple NATS Consumer with in-memory storage and subject parsing
pub struct SimpleNatsConsumer {
    config: Config,
    client: Client,
    event_storage: Arc<Mutex<HashMap<String, Vec<BlockchainEvent>>>>,
}

impl SimpleNatsConsumer {
    /// Create a new simple NATS consumer with in-memory storage
    pub async fn new(config: Config) -> Result<Self> {
        info!("🔌 Connecting to NATS at: {}", config.nats_url);

        let client = async_nats::connect(&config.nats_url)
            .await
            .context("Failed to connect to NATS")?;

        info!("✅ Connected to NATS");

        Ok(Self {
            config,
            client,
            event_storage: Arc::new(Mutex::new(HashMap::new())),
        })
    }

    /// Start consuming messages
    pub async fn start(&self) -> Result<()> {
        info!("🎯 Starting NATS consumer for subject: {}", self.config.nats_subject);

        // Get JetStream context
        let jetstream = jetstream::new(self.client.clone());

        // Create or get stream
        let stream = self.ensure_stream(&jetstream).await?;
        info!("📡 Stream '{}' ready", self.config.nats_stream_name);

        // Create or get consumer
        let consumer = self.ensure_consumer(&stream).await?;
        info!("👂 Consumer '{}' ready", self.config.nats_consumer_name);

        // Start message processing loop
        self.process_messages(consumer).await?;

        Ok(())
    }

    /// Ensure the stream exists
    async fn ensure_stream(
        &self,
        jetstream: &jetstream::Context,
    ) -> Result<jetstream::stream::Stream> {
        let stream_name = &self.config.nats_stream_name;

        // Try to get existing stream first
        match jetstream.get_stream(stream_name).await {
            Ok(stream) => {
                info!("📖 Using existing stream: {}", stream_name);
                Ok(stream)
            }
            Err(_) => {
                // Try to find any existing stream that covers our subject
                info!("🔍 Looking for existing streams that cover subject: {}", self.config.nats_subject);

                let mut streams = jetstream.streams();
                while let Ok(Some(stream_info)) = streams.try_next().await {
                    // Check if any subject in the stream covers our subject pattern
                    for subject in &stream_info.config.subjects {
                        if subject == "transactions.>" || subject.contains("transactions.") {
                            info!("📖 Found existing stream '{}' with subject '{}'", stream_info.config.name, subject);
                            // Get the actual stream object
                            let stream = jetstream.get_stream(&stream_info.config.name).await?;
                            return Ok(stream);
                        }
                    }
                }

                // Create a new stream with smaller limits
                info!("🆕 Creating new stream: {}", stream_name);
                let stream = jetstream
                    .create_stream(jetstream::stream::Config {
                        name: stream_name.clone(),
                        subjects: vec![self.config.nats_subject.clone()],
                        retention: jetstream::stream::RetentionPolicy::Limits,
                        max_messages: 100_000,
                        max_bytes: 100_000_000, // 100MB
                        storage: jetstream::stream::StorageType::File,
                        discard: jetstream::stream::DiscardPolicy::Old,
                        ..Default::default()
                    })
                    .await
                    .context("Failed to create stream")?;

                info!("✅ Created stream: {}", stream_name);
                Ok(stream)
            }
        }
    }

    /// Ensure the consumer exists
    async fn ensure_consumer(
        &self,
        stream: &jetstream::stream::Stream,
    ) -> Result<PullConsumer> {
        let consumer_name = &self.config.nats_consumer_name;

        // Try to get existing consumer
        match stream.get_consumer(consumer_name).await {
            Ok(consumer) => {
                info!("📖 Using existing consumer: {}", consumer_name);
                Ok(consumer)
            }
            Err(_) => {
                info!("🆕 Creating new consumer: {}", consumer_name);
                
                let consumer = stream
                    .create_consumer(jetstream::consumer::pull::Config {
                        durable_name: Some(consumer_name.clone()),
                        filter_subject: self.config.nats_subject.clone(),
                        ack_policy: jetstream::consumer::AckPolicy::Explicit,
                        max_deliver: 3,
                        ack_wait: Duration::from_secs(30),
                        ..Default::default()
                    })
                    .await
                    .context("Failed to create consumer")?;

                info!("✅ Created consumer: {}", consumer_name);
                Ok(consumer)
            }
        }
    }

    /// Process messages from the consumer
    async fn process_messages(&self, consumer: PullConsumer) -> Result<()> {
        info!("🔄 Starting message processing loop");

        let mut messages = consumer.messages().await?;

        while let Some(message) = messages.next().await {
            match message {
                Ok(msg) => {
                    if let Err(e) = self.process_single_message(msg).await {
                        error!("Failed to process message: {}", e);
                        // Continue processing other messages
                    }
                }
                Err(e) => {
                    error!("Error receiving message: {}", e);
                    // Add backoff/retry logic here if needed
                    tokio::time::sleep(Duration::from_millis(1000)).await;
                }
            }
        }

        warn!("Message stream ended");
        Ok(())
    }

    /// Process a single message
    async fn process_single_message(
        &self,
        message: jetstream::Message,
    ) -> Result<()> {
        let subject = message.subject.clone();
        debug!("📨 Processing message from subject: {}", subject);

        // Parse the message payload
        let payload = std::str::from_utf8(&message.payload)
            .context("Invalid UTF-8 in message payload")?;

        // Try to parse as blockchain event
        let event = match serde_json::from_str::<BlockchainEvent>(payload) {
            Ok(event) => event,
            Err(e) => {
                warn!("Failed to parse as BlockchainEvent: {}, treating as raw transaction", e);
                // For now, just acknowledge and skip
                if let Err(ack_err) = message.ack().await {
                    error!("Failed to ack unparseable message: {}", ack_err);
                }
                return Ok(());
            }
        };

        // Parse network/subnet from subject
        let (network, subnet) = self.parse_subject(&subject)?;
        info!("🏷️  Parsed subject - Network: {}, Subnet: {}", network, subnet);

        // Store the event in memory
        let storage_key = format!("{}/{}", network, subnet);
        {
            let mut storage = self.event_storage.lock().await;
            storage.entry(storage_key.clone()).or_insert_with(Vec::new).push(event);
        }
        info!("✅ Stored event for {}", storage_key);

        // Acknowledge the message
        if let Err(e) = message.ack().await {
            error!("Failed to acknowledge message: {}", e);
            return Err(anyhow::anyhow!("Failed to ack message"));
        }

        debug!("✅ Successfully processed message from: {}", subject);
        Ok(())
    }

    /// Parse network and subnet from NATS subject
    /// Subject formats:
    /// - Production: transactions.{vmtype}.{network}.{subnet}
    /// - Test: transactions.test.{vmtype}.{network}.{subnet}
    /// Examples:
    /// - transactions.subnet-evm.avalanche.mainnet
    /// - transactions.test.subnet-evm.avalanche.mainnet
    fn parse_subject(&self, subject: &str) -> Result<(String, String)> {
        let parts: Vec<&str> = subject.split('.').collect();

        if parts.len() >= 4 && parts[0] == "transactions" {
            if parts[1] == "test" && parts.len() >= 5 {
                // Test format: transactions.test.{vmtype}.{network}.{subnet}
                let network = parts[3].to_string();
                let subnet = parts[4].to_string();
                Ok((network, subnet))
            } else {
                // Production format: transactions.{vmtype}.{network}.{subnet}
                let network = parts[2].to_string();
                let subnet = parts[3].to_string();
                Ok((network, subnet))
            }
        } else {
            // Fallback for other subject formats
            warn!("Unknown subject format: {}, using defaults", subject);
            Ok(("unknown".to_string(), "mainnet".to_string()))
        }
    }

    /// Get stored events for debugging
    pub async fn get_stored_events(&self) -> HashMap<String, Vec<BlockchainEvent>> {
        let storage = self.event_storage.lock().await;
        storage.clone()
    }
}
