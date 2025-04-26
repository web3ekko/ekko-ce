# Bento: Multi-Chain Transaction Decoder

Bento is a modular, chain-agnostic transaction decoding engine. Each Bento instance processes a single chain (e.g., Avalanche C-Chain, Ethereum mainnet), decodes transactions, and renders human-readable descriptions using cached ABIs and templates. ABI fetching and template generation are globally controlled with a single environment flag.

## Architecture Diagram

```
                                             ◀───────── global switch ────────▶
                                             FETCH_ABI_ENABLED = true | false


 ╭──────────────────────────╮                                           ╭──────────────────────────╮
 │  Avalanche  C‑Chain RPC  │                                           │     Ethereum  mainnet    │
 │ wss://avax…/ext/bc/C/ws  │                                           │  wss://eth‑ws.alchemy…   │
 ╰─────────────┬────────────╯                                           ╰─────────────┬────────────╯
               │ raw‑tx JSON                                                         │
               ▼                                                                     ▼
 ╭──────────────────────────────────────────────────────────────────────────────────────────────────╮
 │                             one container **per chain**: Bento‑${CHAIN}                          │
 │                             (env: CHAIN=avax | eth | …)                                          │
 │                                                                                                  │
 │   ╭────────────╮ ① “simple transfer?”                                                           |
 │   │decode_tx   │━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮ │
 │   │plugin      │                                                                               │ │
 │   ╰────────────╯                                                                               │ │
 │        │ len(input)==0?                                                                        │ │
 │        ├─ yes ─► render “Transfer X <symbol> from A → B” ─► PUBLISH to                         │ │
 │        │                                                   Valkey channel                       │ │
 │        │                                                   tx_plain_english:${CHAIN}           │ │
 │        └─ no                                                                                   │ │
 │             │                                                                                  │ │
 │             ▼ ② lookup Valkey key  ${CHAIN}:abi:${addr}                                         │ │
 │          hit?                                                                                  │ │
 │             ├─ yes ─► decode + render NL ─► PUBLISH                                             │ │
 │             └─ no                                                                               │ │
 │                  │                                                                              │ │
 │                  ▼ ③ FETCH_ABI_ENABLED == "true"?                                              │ │
 │                  ├─ no ─► render “Called <sig> args… (ABI unavailable)” ─► PUBLISH              │ │
 │                  └─ yes                                                                         │ │
 │                        │ ④ set metadata abi_miss=true                                          │ │
 │                        ▼                                                                        │ │
 │                branch pushes addr to Valkey Stream                                               │ │
 │                - VALKEY_URL=valkey://valkey:6379${CHAIN}                                                            │ │
 ╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
                                   ▲                                           ▲                      
                                   │ Valkey Stream per‑chain                    │
                                   │                                           │
                                   ▼                                           ▼
                        ╭────────────────────────────╮             (same worker code,
                        │  ABI‑Fetcher worker pool   │             different consumer groups)
                        ╰─────────────┬──────────────╯
                                      │ ⑤ call Snowtrace / Etherscan for ABI
                                      │
                                      ├─ store ABI  → HSET  ${CHAIN}:abi:${addr}
                                      │
                                      ├─ publish ABI file → Pulsar topic
                                      │   (topic: ${PULSAR_TOPIC})
                                      │
                                      ├─ generate template map
                                      │   HSET  ${CHAIN}:tmpl:${addr}
                                      │   + publish to Pulsar topic (abi-templates)
                                      │
                                      ╰─ (next time the Bento instance
                                         processes a tx for this contract,
                                         step ② hits the fresh cache ✅)
```

## Quick Start

1. Set environment variables in `.env`:

```bash
PULSAR_URL=pulsar://pulsar:6650
PULSAR_TOPIC=transactions
#SNOWTRACE_API_KEY=your_api_key
# Set to 'true' to enable ABI fetching, defaults to 'false' if unset
FETCH_ABI_ENABLED=false
# Pulsar configuration
PULSAR_URL=pulsar://pulsar:6650
PULSAR_TOPIC=transactions
```

2. Start the services:

```bash
make compose-up
```

3. Watch the logs:

```bash
docker compose logs -f benthos-tx-processor
```

## Chain-Specific Decode Processors

Each chain (e.g., Avalanche, Ethereum) has its own `decode_tx` processor under `processors/<chain>/decode_tx/`.

## Metrics & Monitoring

- Prometheus metrics at:
  - Transaction Processor: http://localhost:4195/metrics
  - ABI Fetcher: http://localhost:4196/metrics

- Grafana Dashboard:
  1. Add Prometheus datasource: http://localhost:9090
  2. Import dashboard from `dashboards/tx_processor.json`

## Development

```bash
# Build all services
make build

# Run linters
make lint

# Start services
make compose-up

# Stop services
make compose-down
```
