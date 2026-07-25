# Tutorial 4: Writing a Custom wasmCloud Actor in Rust

Ekko CE executes real-time evaluation logic inside sandboxed WebAssembly (WASM) actors running on **wasmCloud** hosts linked via NATS JetStream.

In this tutorial, you will build a custom Rust WASM actor that listens to raw transaction streams, filters for specialized contract events, and emits alert signals.

---

## Prerequisites

- Rust toolchain installed (`rustup`).
- WebAssembly compilation target added:
  ```bash
  rustup target add wasm32-wasip1
  ```
- `wash` CLI installed (optional, but helpful for testing).

---

## Step 1: Create a New Actor Project

Navigate to `wasmcloud/actors/` and generate a new library crate:

```bash
cd wasmcloud/actors
cargo new --lib my_custom_actor
```

Add dependencies to `Cargo.toml`:

```toml
[package]
name = "my_custom_actor"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib", "rlib"]

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
wasmcloud-actor-core = "0.4"
```

---

## Step 2: Implement Event Handler Logic

In `src/lib.rs`, implement the stream message handler:

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct TransactionData {
    pub hash: String,
    pub from: String,
    pub to: Option<String>,
    pub value: String,
}

#[derive(Debug, Serialize)]
pub struct AlertSignal {
    pub alert_id: String,
    pub tx_hash: String,
    pub matched_address: String,
    pub reason: String,
}

pub fn process_transaction(raw_json: &str) -> Option<String> {
    let tx: TransactionData = serde_json::from_str(raw_json).ok()?;
    
    // Example custom logic: flag high-value zero-address interactions
    if tx.to.is_none() && tx.value != "0" {
        let signal = AlertSignal {
            alert_id: "custom_contract_creation_alert".to_string(),
            tx_hash: tx.hash,
            matched_address: tx.from,
            reason: "High-value contract creation detected".to_string(),
        };
        return serde_json::to_string(&signal).ok();
    }
    
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_process_transaction() {
        let sample = r#"{
            "hash": "0xabc",
            "from": "0x123",
            "to": null,
            "value": "1000000000000000000"
        }"#;
        let result = process_transaction(sample);
        assert!(result.is_some());
    }
}
```

---

## Step 3: Compile the Actor Target

Build the WebAssembly module:

```bash
cargo build --target wasm32-wasip1 --release
```

The compiled WASM binary will be generated at:
`target/wasm32-wasip1/release/my_custom_actor.wasm`

---

## Step 4: Register in Deployment Manifest

Add your new actor to `wasmcloud/manifests/ekko-actors.yaml`:

```yaml
components:
  - name: my-custom-actor
    type: component
    properties:
      image: localhost:5001/my_custom_actor:v0.1.0
    traits:
      - type: link
        properties:
          target: nats-messaging
          namespace: wasmcloud
          package: messaging
          interfaces: [consumer]
          target_config:
            subscriptions:
              - "blockchain.avalanche.>.transactions.raw"
```

Re-deploy the manifests with `./wasmcloud/deploy-operator.sh` or Docker Compose to start low-latency execution!
