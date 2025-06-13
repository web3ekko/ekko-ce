use anyhow::{Result, Context};
use async_nats::{Client, jetstream::{self, consumer::PullConsumer}};
use deltalake::{DeltaTable, DeltaTableBuilder, DeltaOps};
use deltalake::writer::{DeltaWriter, RecordBatchWriter};
use arrow::array::{StringArray, TimestampMicrosecondArray, Int32Array, UInt64Array, UInt32Array};
use arrow::record_batch::RecordBatch;
use arrow_schema::{Schema, Field, DataType, TimeUnit};
use object_store::aws::AmazonS3Builder;
use futures::StreamExt;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{mpsc, Mutex, RwLock};
use tokio::time::{interval, Duration};
use tracing::{info, warn, error, debug};
use serde_json;

use crate::config::Config;
use crate::event_schema::BlockchainEvent;

/// Delta Writer Service - Direct NATS consumer that writes to Delta Lake
/// Each network/subnet combination gets its own Delta table
pub struct DeltaWriterService {
    config: Config,
    client: Client,
    // Map of "network/subnet" -> DeltaTable
    delta_tables: Arc<RwLock<HashMap<String, DeltaTable>>>,
    event_buffer: Arc<Mutex<Vec<BlockchainEvent>>>,
    write_queue: mpsc::Sender<Vec<BlockchainEvent>>,
}

impl DeltaWriterService {
    /// Create a new Delta Writer Service
    pub async fn new(config: Config) -> Result<Self> {
        info!("🔧 Initializing Delta Writer Service");

        // Connect to NATS
        info!("🔌 Connecting to NATS at: {}", config.nats_url);
        let client = async_nats::connect(&config.nats_url)
            .await
            .context("Failed to connect to NATS")?;
        info!("✅ Connected to NATS");

        // Create write queue
        let (write_tx, write_rx) = mpsc::channel::<Vec<BlockchainEvent>>(100);

        let service = Self {
            config: config.clone(),
            client,
            delta_tables: Arc::new(RwLock::new(HashMap::new())),
            event_buffer: Arc::new(Mutex::new(Vec::new())),
            write_queue: write_tx,
        };

        // Start background writer
        service.start_background_writer(write_rx).await;

        info!("✅ Delta Writer Service initialized");
        Ok(service)
    }

    /// Get or create a Delta table for a specific network/subnet
    async fn get_or_create_delta_table(&self, network: &str, subnet: &str) -> Result<DeltaTable> {
        let table_key = format!("{}/{}", network.to_lowercase(), subnet.to_lowercase());

        // Check if table already exists in cache
        {
            let tables = self.delta_tables.read().await;
            if let Some(table) = tables.get(&table_key) {
                return Ok(table.clone());
            }
        }

        info!("🦆 Initializing Delta table for {}/{}", network, subnet);

        let table_uri = self.config.delta_table_uri(network, subnet);
        info!("📍 Table URI: {}", table_uri);

        // Configure S3 object store
        let s3_store = AmazonS3Builder::new()
            .with_endpoint(&self.config.s3_endpoint_url())
            .with_access_key_id(&self.config.s3_access_key)
            .with_secret_access_key(&self.config.s3_secret_key)
            .with_region(&self.config.s3_region)
            .with_bucket_name(&self.config.s3_bucket)
            .with_allow_http(!self.config.s3_use_ssl)
            .build()
            .context("Failed to build S3 store")?;

        // Try to load existing table or create new one
        let delta_table = match DeltaTableBuilder::from_uri(&table_uri)
            .with_object_store(Arc::new(s3_store.clone()))
            .load()
            .await
        {
            Ok(table) => {
                info!("📖 Loaded existing Delta table for {}/{}", network, subnet);
                table
            }
            Err(_) => {
                info!("🆕 Creating new Delta table for {}/{}", network, subnet);
                self.create_delta_table_for_network_subnet(&table_uri, s3_store).await?
            }
        };

        // Cache the table
        {
            let mut tables = self.delta_tables.write().await;
            tables.insert(table_key, delta_table.clone());
        }

        info!("✅ Delta table ready for {}/{}", network, subnet);
        Ok(delta_table)
    }

    /// Create a new Delta table with the events schema for a specific network/subnet
    async fn create_delta_table_for_network_subnet(
        &self,
        table_uri: &str,
        s3_store: AmazonS3Builder
    ) -> Result<DeltaTable> {
        let schema = Self::get_events_schema();

        let table = DeltaOps::try_from_uri(table_uri)
            .context("Failed to create Delta ops")?
            .with_object_store(Arc::new(s3_store.build()?))
            .create()
            .with_columns(schema.fields().iter().cloned())
            .with_partition_columns(vec!["event_type", "year", "month", "day"])
            .await
            .context("Failed to create Delta table")?;

        info!("✅ Created new Delta table with events schema at: {}", table_uri);
        Ok(table)
    }

    /// Get the Arrow schema for events
    fn get_events_schema() -> Schema {
        Schema::new(vec![
            // Event identification
            Field::new("event_type", DataType::Utf8, false),
            Field::new("tx_hash", DataType::Utf8, false),
            Field::new("timestamp", DataType::Timestamp(TimeUnit::Microsecond, Some("UTC".into())), false),
            
            // Entity information
            Field::new("entity_type", DataType::Utf8, false),
            Field::new("chain", DataType::Utf8, false),
            Field::new("entity_address", DataType::Utf8, false),
            Field::new("entity_name", DataType::Utf8, true),
            Field::new("entity_symbol", DataType::Utf8, true),
            
            // Metadata
            Field::new("network", DataType::Utf8, false),
            Field::new("subnet", DataType::Utf8, false),
            Field::new("vm_type", DataType::Utf8, false),
            Field::new("block_number", DataType::UInt64, false),
            Field::new("block_hash", DataType::Utf8, false),
            Field::new("tx_index", DataType::UInt32, false),
            
            // Time partitioning
            Field::new("year", DataType::Int32, false),
            Field::new("month", DataType::Int32, false),
            Field::new("day", DataType::Int32, false),
            Field::new("hour", DataType::Int32, false),
            
            // Flexible details as JSON string
            Field::new("details", DataType::Utf8, false),
        ])
    }

    /// Add an event to the buffer
    pub async fn add_event(&self, event: BlockchainEvent) -> Result<()> {
        let mut buffer = self.event_buffer.lock().await;
        buffer.push(event);
        
        // Check if we should flush
        if buffer.len() >= self.config.batch_size {
            let events_to_write = buffer.drain(..).collect();
            drop(buffer); // Release lock early
            
            if let Err(e) = self.write_queue.send(events_to_write).await {
                error!("Failed to queue events for writing: {}", e);
                return Err(anyhow::anyhow!("Write queue full"));
            }
        }
        
        Ok(())
    }

    /// Start the background writer task
    async fn start_background_writer(&self, mut write_rx: mpsc::Receiver<Vec<BlockchainEvent>>) {
        let delta_tables = self.delta_tables.clone();
        let config = self.config.clone();
        let service_ref = Arc::new(self);

        tokio::spawn(async move {
            let mut flush_interval = interval(Duration::from_secs(config.flush_interval_seconds));

            loop {
                tokio::select! {
                    // Handle incoming write batches
                    Some(events) = write_rx.recv() => {
                        if let Err(e) = Self::write_events_to_delta_by_network(&service_ref, events).await {
                            error!("Failed to write events to Delta: {}", e);
                        }
                    }

                    // Periodic flush
                    _ = flush_interval.tick() => {
                        debug!("Periodic flush triggered");
                        // This would flush any remaining buffered events
                        // Implementation depends on your buffering strategy
                    }

                    else => break,
                }
            }

            info!("Background writer task stopped");
        });
    }

    /// Write events to Delta tables, grouped by network/subnet
    async fn write_events_to_delta_by_network(
        service: &Arc<&DeltaWriterService>,
        events: Vec<BlockchainEvent>,
    ) -> Result<()> {
        if events.is_empty() {
            return Ok(());
        }

        info!("📝 Writing {} events to Delta tables", events.len());

        // Group events by network/subnet
        let mut events_by_network: HashMap<String, Vec<BlockchainEvent>> = HashMap::new();

        for event in events {
            let key = format!("{}/{}", event.metadata.network, event.metadata.subnet);
            events_by_network.entry(key).or_insert_with(Vec::new).push(event);
        }

        // Write each group to its respective table
        for (network_subnet, events_group) in events_by_network {
            let parts: Vec<&str> = network_subnet.split('/').collect();
            if parts.len() != 2 {
                error!("Invalid network/subnet format: {}", network_subnet);
                continue;
            }

            let network = parts[0];
            let subnet = parts[1];

            match service.get_or_create_delta_table(network, subnet).await {
                Ok(table) => {
                    if let Err(e) = Self::write_events_to_table(&table, events_group).await {
                        error!("Failed to write events to {}/{} table: {}", network, subnet, e);
                    }
                }
                Err(e) => {
                    error!("Failed to get/create table for {}/{}: {}", network, subnet, e);
                }
            }
        }

        Ok(())
    }

    /// Write events to a specific Delta table
    async fn write_events_to_table(
        table: &DeltaTable,
        events: Vec<BlockchainEvent>,
    ) -> Result<()> {
        if events.is_empty() {
            return Ok(());
        }

        info!("📝 Writing {} events to Delta table", events.len());

        // Convert events to Arrow RecordBatch
        let record_batch = Self::events_to_record_batch(events)?;

        // Write to table
        let mut writer = RecordBatchWriter::for_table(table)?;
        writer.write(record_batch).await?;
        writer.flush_and_commit().await?;

        info!("✅ Successfully wrote events to Delta table");
        Ok(())
    }

    /// Convert events to Arrow RecordBatch
    fn events_to_record_batch(events: Vec<BlockchainEvent>) -> Result<RecordBatch> {
        let len = events.len();
        
        // Extract data into vectors
        let mut event_types = Vec::with_capacity(len);
        let mut tx_hashes = Vec::with_capacity(len);
        let mut timestamps = Vec::with_capacity(len);
        let mut entity_types = Vec::with_capacity(len);
        let mut chains = Vec::with_capacity(len);
        let mut entity_addresses = Vec::with_capacity(len);
        let mut entity_names = Vec::with_capacity(len);
        let mut entity_symbols = Vec::with_capacity(len);
        let mut networks = Vec::with_capacity(len);
        let mut subnets = Vec::with_capacity(len);
        let mut vm_types = Vec::with_capacity(len);
        let mut block_numbers = Vec::with_capacity(len);
        let mut block_hashes = Vec::with_capacity(len);
        let mut tx_indices = Vec::with_capacity(len);
        let mut years = Vec::with_capacity(len);
        let mut months = Vec::with_capacity(len);
        let mut days = Vec::with_capacity(len);
        let mut hours = Vec::with_capacity(len);
        let mut details = Vec::with_capacity(len);

        for event in events {
            event_types.push(serde_json::to_string(&event.event_type)?);
            tx_hashes.push(event.tx_hash);
            timestamps.push(event.timestamp.timestamp_micros());
            entity_types.push(serde_json::to_string(&event.entity.r#type)?);
            chains.push(event.entity.chain);
            entity_addresses.push(event.entity.address);
            entity_names.push(event.entity.name);
            entity_symbols.push(event.entity.symbol);
            networks.push(event.metadata.network);
            subnets.push(event.metadata.subnet);
            vm_types.push(event.metadata.vm_type);
            block_numbers.push(event.metadata.block_number);
            block_hashes.push(event.metadata.block_hash);
            tx_indices.push(event.metadata.tx_index);
            years.push(event.metadata.year);
            months.push(event.metadata.month);
            days.push(event.metadata.day);
            hours.push(event.metadata.hour);
            details.push(event.details.to_string());
        }

        // Create Arrow arrays
        let schema = Self::get_events_schema();
        let record_batch = RecordBatch::try_new(
            Arc::new(schema),
            vec![
                Arc::new(StringArray::from(event_types)),
                Arc::new(StringArray::from(tx_hashes)),
                Arc::new(TimestampMicrosecondArray::from(timestamps)),
                Arc::new(StringArray::from(entity_types)),
                Arc::new(StringArray::from(chains)),
                Arc::new(StringArray::from(entity_addresses)),
                Arc::new(StringArray::from(entity_names)),
                Arc::new(StringArray::from(entity_symbols)),
                Arc::new(StringArray::from(networks)),
                Arc::new(StringArray::from(subnets)),
                Arc::new(StringArray::from(vm_types)),
                Arc::new(arrow::array::UInt64Array::from(block_numbers)),
                Arc::new(StringArray::from(block_hashes)),
                Arc::new(arrow::array::UInt32Array::from(tx_indices)),
                Arc::new(Int32Array::from(years)),
                Arc::new(Int32Array::from(months)),
                Arc::new(Int32Array::from(days)),
                Arc::new(Int32Array::from(hours)),
                Arc::new(StringArray::from(details)),
            ],
        )?;

        Ok(record_batch)
    }

    /// Start the service - begins consuming from NATS
    pub async fn start(&self) -> Result<()> {
        info!("🚀 Starting Delta Writer Service");

        // Start NATS consumer
        self.start_nats_consumer().await?;

        Ok(())
    }

    /// Start NATS consumer to process transaction messages
    async fn start_nats_consumer(&self) -> Result<()> {
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

        // Try to get existing stream
        match jetstream.get_stream(stream_name).await {
            Ok(stream) => {
                info!("📖 Using existing stream: {}", stream_name);
                Ok(stream)
            }
            Err(_) => {
                info!("🆕 Creating new stream: {}", stream_name);

                let stream = jetstream
                    .create_stream(jetstream::stream::Config {
                        name: stream_name.clone(),
                        subjects: vec![self.config.nats_subject.clone()],
                        retention: jetstream::stream::RetentionPolicy::Limits,
                        max_messages: 10_000_000,
                        max_bytes: 10_000_000_000, // 10GB
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

    /// Process a single message from NATS
    async fn process_single_message(
        &self,
        message: jetstream::Message,
    ) -> Result<()> {
        let subject = message.subject.clone();
        debug!("📨 Processing message from subject: {}", subject);

        // Parse network/subnet from subject
        let (network, subnet) = self.parse_subject(&subject)?;
        debug!("🏷️  Parsed subject - Network: {}, Subnet: {}", network, subnet);

        // Parse the message payload
        let payload = std::str::from_utf8(&message.payload)
            .context("Invalid UTF-8 in message payload")?;

        // Try to parse as blockchain event or raw transaction
        let event = match serde_json::from_str::<BlockchainEvent>(payload) {
            Ok(event) => event,
            Err(_) => {
                // If it's not a BlockchainEvent, try to convert raw transaction data
                debug!("Converting raw transaction data to BlockchainEvent");
                self.convert_raw_transaction_to_event(payload, &network, &subnet).await?
            }
        };

        // Add event to buffer for writing
        if let Err(e) = self.add_event(event).await {
            error!("Failed to add event to buffer: {}", e);
            return Err(e);
        }

        // Acknowledge the message
        if let Err(e) = message.ack().await {
            error!("Failed to acknowledge message: {}", e);
            return Err(anyhow::anyhow!("Failed to ack message"));
        }

        debug!("✅ Successfully processed message from: {}", subject);
        Ok(())
    }

    /// Parse network and subnet from NATS subject
    /// Subject format: transactions.{vmtype}.{network}.{subnet}
    /// Example: transactions.subnet-evm.avalanche.mainnet
    fn parse_subject(&self, subject: &str) -> Result<(String, String)> {
        let parts: Vec<&str> = subject.split('.').collect();

        if parts.len() >= 4 && parts[0] == "transactions" {
            let network = parts[2].to_string();
            let subnet = parts[3].to_string();
            Ok((network, subnet))
        } else {
            // Fallback for other subject formats
            warn!("Unknown subject format: {}, using defaults", subject);
            Ok(("unknown".to_string(), "mainnet".to_string()))
        }
    }

    /// Convert raw transaction data to BlockchainEvent
    async fn convert_raw_transaction_to_event(
        &self,
        payload: &str,
        network: &str,
        subnet: &str,
    ) -> Result<BlockchainEvent> {
        // Parse raw transaction JSON
        let raw_tx: serde_json::Value = serde_json::from_str(payload)
            .context("Failed to parse raw transaction JSON")?;

        // Extract basic transaction info
        let tx_hash = raw_tx.get("hash")
            .and_then(|h| h.as_str())
            .unwrap_or("unknown")
            .to_string();

        let from_address = raw_tx.get("from")
            .and_then(|f| f.as_str())
            .unwrap_or("unknown")
            .to_string();

        let block_number = raw_tx.get("blockNumber")
            .and_then(|b| b.as_u64())
            .unwrap_or(0);

        let now = chrono::Utc::now();

        // Create BlockchainEvent
        let event = BlockchainEvent {
            event_type: crate::event_schema::EventType::WalletTx,
            entity: crate::event_schema::Entity {
                r#type: crate::event_schema::EntityType::Wallet,
                chain: network.to_string(),
                address: from_address,
                name: None,
                symbol: None,
            },
            timestamp: now,
            tx_hash,
            details: raw_tx,
            metadata: crate::event_schema::Metadata {
                network: network.to_string(),
                subnet: subnet.to_string(),
                vm_type: "evm".to_string(),
                block_number,
                block_hash: "unknown".to_string(),
                tx_index: 0,
                year: now.year(),
                month: now.month() as i32,
                day: now.day() as i32,
                hour: now.hour() as i32,
            },
        };

        Ok(event)
    }

    /// Shutdown the service gracefully
    pub async fn shutdown(&self) -> Result<()> {
        info!("🛑 Shutting down Delta Writer Service");
        
        // Flush any remaining events
        let buffer = self.event_buffer.lock().await;
        if !buffer.is_empty() {
            warn!("Flushing {} remaining events during shutdown", buffer.len());
            // Implementation would flush remaining events
        }
        
        info!("✅ Delta Writer Service shutdown complete");
        Ok(())
    }
}
