# Polars Eval Provider

wasmCloud capability provider for high-performance Polars DataFrame expression evaluation.

## Overview

The Polars Eval Provider enables wasmCloud actors to evaluate complex filtering expressions against transaction data using the Polars DataFrame library. It provides:

- **High Performance**: <10ms p95 latency for complex expressions
- **Expression Caching**: 95%+ cache hit rate for repeated expressions
- **Type Safety**: Schema validation before evaluation
- **Declarative Filtering**: SQL-like expression syntax

## Features

### Expression Evaluation

Evaluate Polars expressions against transaction data:

```rust
let evaluator = PolarsEvalProvider::new();

let tx = TransactionData {
    value_usd: Some(2000.0),
    status: "success".to_string(),
    // ... other fields
};

// Simple comparison
let result = evaluator.evaluate("value_usd > 1000", &tx)?;
assert!(result); // true

// Logical operations
let result = evaluator.evaluate("value_usd > 1000 && status == 'success'", &tx)?;
assert!(result); // true
```

### Supported Operators

#### Comparison Operators
- `>` - Greater than
- `<` - Less than
- `>=` - Greater than or equal
- `<=` - Less than or equal
- `==` - Equal

#### Logical Operators
- `&&` or `&` - Logical AND
- `||` or `|` - Logical OR

### Expression Validation

Validate expressions before use:

```rust
let schema = DataSchema::default_transaction_schema();
let validation = evaluator.validate("value_usd > 1000", &schema)?;

if validation.valid {
    println!("Expression is valid!");
} else {
    println!("Errors: {:?}", validation.errors);
}
```

### Expression Compilation

Pre-compile expressions for repeated use:

```rust
// Compile once
let expr_id = evaluator.compile("value_usd > 1000 && status == 'success'", &schema)?;

// Evaluate many times
for tx in transactions {
    let result = evaluator.evaluate_compiled(&expr_id, &tx)?;
    if result {
        // Transaction matches filter
    }
}
```

### Cache Management

```rust
// Get cache statistics
let stats = evaluator.get_cache_stats();
println!("Hit rate: {:.2}%", stats.hit_rate * 100.0);
println!("Total entries: {}", stats.total_entries);

// Clear cache
evaluator.clear_cache().await;
```

## Performance

### Benchmarks

```bash
cargo bench
```

Expected performance (on modern hardware):

| Operation | Latency (p95) | Throughput |
|-----------|---------------|------------|
| Simple comparison | <2ms | >10K ops/sec |
| Logical AND/OR | <5ms | >5K ops/sec |
| Complex expression | <10ms | >2K ops/sec |
| Cache hit | <1ms | >50K ops/sec |

### Cache Performance

- **Hit Rate**: 95%+ for typical workloads
- **Capacity**: 1000 expressions (default)
- **Eviction**: LRU (Least Recently Used)

## Testing

### Unit Tests

```bash
cargo test --lib
```

### Integration Tests

```bash
cargo test --test '*'
```

### Coverage

```bash
cargo tarpaulin --out Html
```

Target: >80% code coverage

## Expression Examples

### Simple Filters

```rust
// Value threshold
"value_usd > 1000"

// Status check
"status == 'success'"

// Gas limit
"gas_used < 50000"
```

### Complex Filters

```rust
// High-value successful transactions
"value_usd > 1000 && status == 'success'"

// Failed or high-gas transactions
"status == 'failed' || gas_used > 100000"

// Multi-condition filter
"value_usd > 1000 && status == 'success' && gas_used < 50000"
```

### Transaction Data Fields

Available fields for filtering:

- `tx_hash` (string)
- `chain` (string)
- `block_number` (u64)
- `timestamp` (u64)
- `from_address` (string)
- `to_address` (string)
- `value` (f64) - converted from Wei string
- `value_usd` (f64)
- `gas_used` (u64)
- `tx_type` (string)
- `status` (string)

## Metrics

Prometheus metrics exposed:

- `polars_eval_latency_seconds` - Evaluation latency histogram
- `polars_validate_latency_seconds` - Validation latency histogram
- `polars_compile_latency_seconds` - Compilation latency histogram
- `polars_eval_total` - Total evaluations counter
- `polars_eval_success` - Successful evaluations counter
- `polars_eval_errors` - Failed evaluations counter
- `polars_cache_hits` - Cache hits counter
- `polars_cache_misses` - Cache misses counter
- `polars_cache_size` - Current cache size gauge
- `polars_parse_errors` - Parse errors counter
- `polars_execution_errors` - Execution errors counter

## Error Handling

```rust
use polars_eval_provider::EvalError;

match evaluator.evaluate(expression, &tx) {
    Ok(result) => println!("Match: {}", result),
    Err(EvalError::ParseError(msg)) => eprintln!("Parse error: {}", msg),
    Err(EvalError::ExecutionError(msg)) => eprintln!("Execution error: {}", msg),
    Err(EvalError::InvalidData(msg)) => eprintln!("Invalid data: {}", msg),
    Err(e) => eprintln!("Other error: {}", e),
}
```

## wasmCloud Integration

### WIT Interface

See `wit/polars-eval.wit` for the complete interface definition.

### Provider Configuration

```yaml
# wasmcloud.toml
[provider]
name = "polars-eval-provider"
vendor = "ekko"
version = "0.1.0"

[provider.config]
cache_capacity = 1000
max_expression_length = 1024
evaluation_timeout_ms = 5000
```

### Link Configuration

No link-specific configuration required. Provider is stateless and can be shared across actors.

## Development

### Build

```bash
cargo build --release
```

### Run Tests

```bash
# All tests
cargo test

# Unit tests only
cargo test --lib

# Integration tests only
cargo test --test '*'

# With output
cargo test -- --nocapture
```

### Benchmarks

```bash
cargo bench

# Specific benchmark
cargo bench simple_comparison
```

## Future Enhancements

- [ ] Support for more Polars operations (is_in, contains, etc.)
- [ ] Custom function support
- [ ] Expression optimization
- [ ] Distributed caching (Redis)
- [ ] SQL expression parsing
- [ ] JIT compilation for hot paths

## License

Copyright Ekko Team
