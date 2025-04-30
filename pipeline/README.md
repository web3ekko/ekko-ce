# Ekko Pipeline

A high-performance data pipeline for processing Avalanche blockchain data. The pipeline connects to Avalanche nodes via WebSocket, processes blocks and transactions, and forwards the data to Apache Pulsar.

## Features

- Multi-subnet support
- Automatic node failover
- Parallel transaction decoding
- Configurable caching (Redis/Memory)
- Robust error handling and retries

## Configuration

The pipeline is configured via a `.env` file. Copy the example configuration file and modify as needed:

```bash
cp .env.example .env
```

Configuration options in `.env`:

```env
# Infrastructure
PULSAR_HOST=pulsar              # Pulsar host
PULSAR_PORT=6650               # Pulsar port
REDIS_HOST=redis               # Redis host (if using Redis cache)
REDIS_PORT=6379               # Redis port
METRICS_PORT=9090             # Metrics endpoint port

# Pipeline Configuration
DECODER_WORKERS=4              # Number of parallel transaction decoders
MAX_RETRIES=3                 # Max retries for operations
RETRY_DELAY=5s                # Delay between retries
CACHE_TYPE=memory             # Cache type: redis or memory

# Avalanche Subnets
AVAX_SUBNETS=subnet1,subnet2   # Comma-separated list of subnet names

# Per-subnet Configuration
SUBNET1_NODE_URLS=http://node1:9650,http://node2:9650
SUBNET1_CHAIN_ID=2q9e4r
SUBNET1_VM_TYPE=subnet-evm
SUBNET1_PULSAR_TOPIC=blocks-subnet1
```

## Building

```bash
go build -o pipeline ./cmd/pipeline
```

## Running

```bash
./pipeline
```

## Docker

Build the image:
```bash
docker build -t ekko-pipeline .
```

Run with Docker:
```bash
docker run -d \
  --name ekko-pipeline \
  --env-file .env \
  ekko-pipeline
```

## Architecture

1. **WebSocket Source**: Connects to Avalanche nodes and subscribes to new blocks
2. **Decoder**: Decodes transactions in parallel using a worker pool
3. **Cache**: Caches decoded transactions using Redis or in-memory storage
4. **Pulsar Sink**: Forwards processed blocks to Apache Pulsar

The pipeline automatically handles node failover and includes retry mechanisms for resilience.
