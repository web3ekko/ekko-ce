use polars_eval_provider::{
    DataSchema, PolarsEvalProvider, TransactionData, ValidationResult,
};

#[tokio::test]
async fn test_provider_lifecycle() {
    // Create provider
    let provider = PolarsEvalProvider::new();

    // Validate expression
    let schema = DataSchema::default_transaction_schema();
    let validation = provider
        .validate("value_usd > 1000", &schema)
        .expect("Validation failed");

    assert!(validation.valid, "Expression should be valid");

    // Compile expression
    let expr_id = provider
        .compile("value_usd > 1000", &schema)
        .expect("Compilation failed");

    // Create test transaction
    let tx = TransactionData {
        tx_hash: "0x123".to_string(),
        chain: "ethereum".to_string(),
        block_number: 100,
        timestamp: 1234567890,
        from_address: "0xabc".to_string(),
        to_address: Some("0xdef".to_string()),
        value: "1000000000000000000".to_string(),
        value_usd: Some(2000.0),
        gas_used: Some(21000),
        gas_price: Some("50000000000".to_string()),
        tx_type: "transfer".to_string(),
        contract_address: None,
        method_signature: None,
        token_address: None,
        token_symbol: None,
        token_amount: None,
        status: "success".to_string(),
        input_data: None,
        logs_bloom: None,
    };

    // Evaluate using compiled expression
    let result = provider
        .evaluate_compiled(&expr_id, &tx)
        .expect("Evaluation failed");

    assert!(result, "Transaction should match filter");

    // Get cache stats
    let stats = provider.get_cache_stats();
    assert_eq!(stats.total_entries, 1, "Should have 1 cached expression");
    assert!(stats.hit_rate > 0.0, "Should have cache hits");

    // Clear cache
    provider.clear_cache().await;
    let stats = provider.get_cache_stats();
    assert_eq!(stats.total_entries, 0, "Cache should be empty");
}

#[tokio::test]
async fn test_high_throughput_evaluation() {
    let provider = PolarsEvalProvider::with_capacity(100);
    let schema = DataSchema::default_transaction_schema();

    // Compile 10 different expressions
    let expressions = vec![
        "value_usd > 1000",
        "value_usd > 2000",
        "gas_used > 21000",
        "status == 'success'",
        "tx_type == 'transfer'",
        "value_usd > 1000 && status == 'success'",
        "value_usd > 2000 || gas_used < 25000",
        "block_number > 50",
        "timestamp > 1000000000",
        "chain == 'ethereum'",
    ];

    let mut compiled_exprs = Vec::new();
    for expr in &expressions {
        let expr_id = provider.compile(expr, &schema).expect("Compilation failed");
        compiled_exprs.push(expr_id);
    }

    // Create 1000 test transactions
    let transactions: Vec<TransactionData> = (0..1000)
        .map(|i| TransactionData {
            tx_hash: format!("0x{:x}", i),
            chain: "ethereum".to_string(),
            block_number: 100 + i,
            timestamp: 1234567890 + i,
            from_address: format!("0x{:x}", i),
            to_address: Some(format!("0x{:x}", i + 1)),
            value: "1000000000000000000".to_string(),
            value_usd: Some(1000.0 + i as f64),
            gas_used: Some(21000 + i),
            gas_price: Some("50000000000".to_string()),
            tx_type: "transfer".to_string(),
            contract_address: None,
            method_signature: None,
            token_address: None,
            token_symbol: None,
            token_amount: None,
            status: if i % 10 == 0 { "failed" } else { "success" }.to_string(),
            input_data: None,
            logs_bloom: None,
        })
        .collect();

    // Evaluate each transaction against each expression
    let mut total_matches = 0;
    for tx in &transactions {
        for expr_id in &compiled_exprs {
            if let Ok(result) = provider.evaluate_compiled(expr_id, tx) {
                if result {
                    total_matches += 1;
                }
            }
        }
    }

    println!("Total matches: {} out of 10000 evaluations", total_matches);

    // Check cache stats
    let stats = provider.get_cache_stats();
    assert_eq!(stats.total_entries, 10, "Should have 10 cached expressions");

    // Cache hit rate should be very high (>99%)
    // First 10 evals are misses, then 9990 are hits
    let expected_hit_rate = 9990.0 / 10000.0;
    assert!(
        (stats.hit_rate - expected_hit_rate).abs() < 0.01,
        "Cache hit rate should be ~{}, got {}",
        expected_hit_rate,
        stats.hit_rate
    );
}

#[tokio::test]
async fn test_concurrent_evaluation() {
    use std::sync::Arc;
    use tokio::task;

    let provider = Arc::new(PolarsEvalProvider::with_capacity(100));
    let schema = DataSchema::default_transaction_schema();

    // Compile expression
    let expr_id = Arc::new(
        provider
            .compile("value_usd > 1000", &schema)
            .expect("Compilation failed"),
    );

    // Spawn 100 concurrent evaluation tasks
    let mut handles = Vec::new();
    for i in 0..100 {
        let provider = Arc::clone(&provider);
        let expr_id = Arc::clone(&expr_id);

        let handle = task::spawn(async move {
            let tx = TransactionData {
                tx_hash: format!("0x{:x}", i),
                chain: "ethereum".to_string(),
                block_number: 100 + i,
                timestamp: 1234567890 + i,
                from_address: format!("0x{:x}", i),
                to_address: Some(format!("0x{:x}", i + 1)),
                value: "1000000000000000000".to_string(),
                value_usd: Some(900.0 + i as f64 * 30.0), // Some will be >1000, some <1000
                gas_used: Some(21000),
                gas_price: Some("50000000000".to_string()),
                tx_type: "transfer".to_string(),
                contract_address: None,
                method_signature: None,
                token_address: None,
                token_symbol: None,
                token_amount: None,
                status: "success".to_string(),
                input_data: None,
                logs_bloom: None,
            };

            provider
                .evaluate_compiled(&expr_id, &tx)
                .expect("Evaluation failed")
        });

        handles.push(handle);
    }

    // Wait for all tasks to complete
    let results = futures::future::join_all(handles).await;

    // Count successful evaluations
    let successes = results
        .into_iter()
        .filter(|r| r.is_ok() && r.as_ref().unwrap() == &true)
        .count();

    println!("Concurrent evaluations: {} matches out of 100", successes);

    // Should have some matches (value_usd > 1000)
    assert!(successes > 0, "Should have some matching transactions");
    assert!(successes < 100, "Not all transactions should match");
}

#[tokio::test]
async fn test_error_handling() {
    let provider = PolarsEvalProvider::new();
    let tx = TransactionData {
        tx_hash: "0x123".to_string(),
        chain: "ethereum".to_string(),
        block_number: 100,
        timestamp: 1234567890,
        from_address: "0xabc".to_string(),
        to_address: Some("0xdef".to_string()),
        value: "1000000000000000000".to_string(),
        value_usd: Some(2000.0),
        gas_used: Some(21000),
        gas_price: Some("50000000000".to_string()),
        tx_type: "transfer".to_string(),
        contract_address: None,
        method_signature: None,
        token_address: None,
        token_symbol: None,
        token_amount: None,
        status: "success".to_string(),
        input_data: None,
        logs_bloom: None,
    };

    // Invalid syntax
    let result = provider.evaluate("invalid >>> syntax", &tx);
    assert!(result.is_err(), "Should fail on invalid syntax");

    // Non-existent column
    let result = provider.evaluate("nonexistent_column > 1000", &tx);
    assert!(result.is_err(), "Should fail on non-existent column");

    // Empty expression
    let result = provider.evaluate("", &tx);
    assert!(result.is_err(), "Should fail on empty expression");
}

#[tokio::test]
async fn test_validation_edge_cases() {
    let provider = PolarsEvalProvider::new();
    let schema = DataSchema::default_transaction_schema();

    // Valid expression
    let result = provider.validate("value_usd > 1000", &schema);
    assert!(result.is_ok());
    let validation = result.unwrap();
    assert!(validation.valid);

    // Invalid syntax
    let result = provider.validate("invalid >>> syntax", &schema);
    assert!(result.is_ok());
    let validation = result.unwrap();
    assert!(!validation.valid);
    assert!(!validation.errors.is_empty());

    // Empty expression
    let result = provider.validate("", &schema);
    assert!(result.is_ok());
    let validation = result.unwrap();
    assert!(!validation.valid);
}
