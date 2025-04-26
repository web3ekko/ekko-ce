# Bento Plugins Directory

This directory contains custom Benthos plugins for the Ekko CE project.

## evm_decode_fast

- **File:** `evm_decode_fast.go` (source), `evm_decode_fast.so` (compiled)
- **Purpose:** Fast EVM calldata decoder using selector cache in Valkey (Redis-compatible)
- **Usage:**
  - Build the plugin:
    ```bash
    go build -buildmode=plugin -o evm_decode_fast.so evm_decode_fast.go
    ```
  - The `.so` file is referenced by the Benthos pipeline in `bento/config/evm_decode_pipeline.yaml`.
- **Environment Variables:**
  - `VALKEY_ADDR` (e.g. `valkey:6379`)
  - `CHAIN_ID`
  - `PULSAR_URL`
  - `SNOWTRACE_KEY`

## Directory Structure Example

```
bento/plugins/
  ├── evm_decode_fast.go
  ├── evm_decode_fast.so
  └── README.md
```

See the main project README for how to run the pipeline with this plugin.
