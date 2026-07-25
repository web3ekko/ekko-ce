# Ekko CE Tutorials & Guides

Welcome to the Ekko Community Edition (CE) tutorial series. These step-by-step guides cover everything from basic natural-language alert creation to extending the low-latency wasmCloud event runtime with custom Rust actors.

---

## Available Tutorials

### 1. 🚀 [Quickstart: Natural Language Alerts & Webhooks](./01-quickstart-natural-language-alerts.md)
Learn how to get Ekko CE running locally via Docker Compose, parse natural language monitoring requests, create alert instances, and receive real-time webhook notifications.

### 2. 🔺 [Monitoring Avalanche Subnets (L1s) & Custom Chains](./02-monitoring-avalanche-subnets.md)
Discover how to point Ekko's block ingestion pipeline to your custom Avalanche Subnet or EVM chain RPC endpoints and subscribe to live transaction streams.

### 3. 📋 [Building Custom Alert Templates & Parameter Schemas](./03-creating-alert-templates.md)
Master the creation of reusable alert templates with parametric variables (e.g. `{{wallet}}`, `{{threshold}}`, `{{token}}`) and organize them into team Alert Groups.

### 4. 🦀 [Extending Ekko: Writing a Custom wasmCloud Actor in Rust](./04-writing-wasmcloud-actors.md)
Deep dive into Ekko's event-driven runtime architecture. Learn how to write, compile, and deploy a WASM actor in Rust to evaluate custom smart contract events over NATS JetStream.

---

## System Requirements

- **Docker & Docker Compose** (for running PostgreSQL, Redis, NATS, MinIO, API, and Dashboard)
- **Node.js 18+ & npm** (if building or customizing the React dashboard locally)
- **Python 3.10+ & pip** (if developing on the Django API backend)
- **Rust toolchain & `wasm32-wasip1` target** (if building custom wasmCloud actors)
