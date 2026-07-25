# Tutorial 2: Monitoring Avalanche Subnets (L1s) & Custom Chains

Ekko CE is designed Avalanche-first. This tutorial guides you through configuring custom Avalanche Subnets (L1s) or EVM-compatible chains so that Ekko's streaming event pipeline can ingest and evaluate real-time transaction data from your specific network.

---

## Architecture Overview

1. **`newheads-evm` Provider**: Establishes WebSocket connections to the EVM RPC node.
2. **NATS JetStream Subjects**: Publishes block headers onto `newheads.{network}.{subnet}.evm`.
3. **`eth_raw_transactions` Actor**: Subscribes to the raw transaction stream and fetches full block body details for processing.

---

## Step 1: Register the Subnet / Chain in Ekko API

1. Log into the Django Admin at `http://localhost:8000/admin/`.
2. Under **Blockchain**, navigate to **Chains** -> **Add Chain**.
3. Fill in the network details:
   - **Name:** `My Custom Subnet`
   - **Chain ID:** `12345`
   - **Symbol:** `SUBNET`
   - **Is Active:** `True`
4. Under **SubChains**, create a record linking to your parent chain with your WebSocket RPC URL:
   - **RPC WS URL:** `wss://subnets.avax.network/mysubnet/ws`
   - **RPC HTTP URL:** `https://subnets.avax.network/mysubnet/rpc`

---

## Step 2: Configure Provider Environment

Update your `docker-compose.yml` or environment variables for `wasmcloud`:

```yaml
  wasmcloud:
    environment:
      WASMCLOUD_LATTICE_PREFIX: ekko-ce
      CHAIN_12345_WS_ENDPOINT: "wss://subnets.avax.network/mysubnet/ws"
      CHAIN_12345_NETWORK_NAME: "avalanche-custom-subnet"
```

---

## Step 3: Verify NATS Stream Subscriptions

1. Open the NATS monitoring web UI at:
   ```
   http://localhost:8222
   ```
2. Check JetStream stream statistics to ensure subjects are active:
   ```text
   blockchain.avalanche.custom-subnet.transactions.raw
   ```
3. You can also monitor live subjects using `nats-box`:
   ```bash
   docker compose exec nats-setup nats sub "blockchain.avalanche.custom-subnet.>"
   ```

---

## Step 4: Test Alert Matching on Your Subnet

Create an alert targeting a wallet on your custom Subnet ID:
```text
Notify me when wallet 0x1111111111111111111111111111111111111111 performs any contract interaction on My Custom Subnet
```

Ekko will evaluate incoming block transactions on your Subnet and trigger alerts as matching transactions are validated.
