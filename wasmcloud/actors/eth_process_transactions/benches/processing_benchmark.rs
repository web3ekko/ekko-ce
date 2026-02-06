use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use eth_process_transactions::*;

fn create_benchmark_raw_transaction(tx_type: &str, index: usize) -> RawTransaction {
    match tx_type {
        "transfer" => RawTransaction {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            transaction_hash: format!("0x{:064x}", index),
            block_number: 18500000 + index as u64,
            transaction_index: index as u32,
            from_address: format!("0x{:040x}", index),
            to_address: Some(format!("0x{:040x}", index + 1)),
            value: format!("{}", 1000000000000000000u64 * (index as u64 + 1)),
            gas_limit: 21000,
            gas_price: format!("{}", 20000000000u64 + (index as u64 * 1000000000)),
            input_data: "0x".to_string(),
            nonce: index as u64,
            max_fee_per_gas: None,
            max_priority_fee_per_gas: None,
            transaction_type: None,
            processed_at: "2024-01-15T10:30:00Z".to_string(),
            processor_id: "benchmark".to_string(),
        },
        "contract_creation" => RawTransaction {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            transaction_hash: format!("0x{:064x}", index),
            block_number: 18500000 + index as u64,
            transaction_index: index as u32,
            from_address: format!("0x{:040x}", index),
            to_address: None,
            value: "0".to_string(),
            gas_limit: 2100000,
            gas_price: format!("{}", 25000000000u64 + (index as u64 * 1000000000)),
            input_data: format!("0x608060405234801561001057600080fd5b50{:0200x}", index),
            nonce: index as u64,
            max_fee_per_gas: None,
            max_priority_fee_per_gas: None,
            transaction_type: None,
            processed_at: "2024-01-15T10:30:00Z".to_string(),
            processor_id: "benchmark".to_string(),
        },
        "function_call" => RawTransaction {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            transaction_hash: format!("0x{:064x}", index),
            block_number: 18500000 + index as u64,
            transaction_index: index as u32,
            from_address: format!("0x{:040x}", index),
            to_address: Some(format!("0x{:040x}", index + 1000)),
            value: "0".to_string(),
            gas_limit: 100000,
            gas_price: format!("{}", 30000000000u64 + (index as u64 * 1000000000)),
            input_data: format!("0xa9059cbb{:0128x}", index),
            nonce: index as u64,
            max_fee_per_gas: None,
            max_priority_fee_per_gas: None,
            transaction_type: None,
            processed_at: "2024-01-15T10:30:00Z".to_string(),
            processor_id: "benchmark".to_string(),
        },
        _ => panic!("Unknown transaction type"),
    }
}

fn bench_transaction_type_detection(c: &mut Criterion) {
    let mut group = c.benchmark_group("transaction_type_detection");

    for tx_type in ["transfer", "contract_creation", "function_call"].iter() {
        let raw_tx = create_benchmark_raw_transaction(tx_type, 0);

        group.bench_with_input(
            BenchmarkId::new("detect_type", tx_type),
            &raw_tx,
            |b, tx| b.iter(|| detect_transaction_type(black_box(tx))),
        );
    }

    group.finish();
}

fn bench_details_creation(c: &mut Criterion) {
    let mut group = c.benchmark_group("details_creation");

    let transfer_tx = create_benchmark_raw_transaction("transfer", 0);
    group.bench_function("transfer_details", |b| {
        b.iter(|| ProcessedTransaction::create_transfer_details(black_box(&transfer_tx)))
    });

    let creation_tx = create_benchmark_raw_transaction("contract_creation", 0);
    group.bench_function("contract_creation_details", |b| {
        b.iter(|| ProcessedTransaction::create_contract_creation_details(black_box(&creation_tx)))
    });

    let function_tx = create_benchmark_raw_transaction("function_call", 0);
    group.bench_function("function_call_details", |b| {
        b.iter(|| ProcessedTransaction::create_function_call_details(black_box(&function_tx)))
    });

    group.finish();
}

fn bench_single_transaction_processing(c: &mut Criterion) {
    let mut group = c.benchmark_group("single_transaction_processing");

    for tx_type in ["transfer", "contract_creation", "function_call"].iter() {
        let raw_tx = create_benchmark_raw_transaction(tx_type, 0);

        group.bench_with_input(
            BenchmarkId::new("process_single", tx_type),
            &raw_tx,
            |b, tx| b.iter(|| process_single_transaction(black_box(tx.clone()))),
        );
    }

    group.finish();
}

fn bench_batch_processing(c: &mut Criterion) {
    let mut group = c.benchmark_group("batch_processing");

    for batch_size in [10, 100, 1000].iter() {
        let transactions: Vec<RawTransaction> = (0..*batch_size)
            .map(|i| {
                let tx_type = match i % 3 {
                    0 => "transfer",
                    1 => "contract_creation",
                    2 => "function_call",
                    _ => unreachable!(),
                };
                create_benchmark_raw_transaction(tx_type, i)
            })
            .collect();

        group.bench_with_input(
            BenchmarkId::new("batch_process", batch_size),
            &transactions,
            |b, txs| b.iter(|| process_transaction_batch(black_box(txs.clone()))),
        );
    }

    group.finish();
}

fn bench_publishing(c: &mut Criterion) {
    let mut group = c.benchmark_group("publishing");

    // Create mock messaging for benchmarking
    struct BenchmarkMockMessaging;
    impl WasmCloudMessaging for BenchmarkMockMessaging {
        fn publish(&self, _subject: &str, _payload: &[u8]) -> Result<(), String> {
            Ok(()) // No-op for benchmarking
        }
    }

    let messaging = BenchmarkMockMessaging;
    let transactions: Vec<RawTransaction> = (0..100)
        .map(|i| create_benchmark_raw_transaction("transfer", i))
        .collect();

    let batch_result = process_transaction_batch(transactions);

    group.bench_function("publish_results", |b| {
        b.iter(|| {
            publish_processing_results(
                black_box(&batch_result.successful_results),
                black_box(&messaging),
            )
        })
    });

    group.finish();
}

fn bench_complete_pipeline(c: &mut Criterion) {
    let mut group = c.benchmark_group("complete_pipeline");

    struct BenchmarkMockMessaging;
    impl WasmCloudMessaging for BenchmarkMockMessaging {
        fn publish(&self, _subject: &str, _payload: &[u8]) -> Result<(), String> {
            Ok(())
        }
    }

    let messaging = BenchmarkMockMessaging;

    for batch_size in [10, 100].iter() {
        let transactions: Vec<RawTransaction> = (0..*batch_size)
            .map(|i| {
                let tx_type = match i % 3 {
                    0 => "transfer",
                    1 => "contract_creation",
                    2 => "function_call",
                    _ => unreachable!(),
                };
                create_benchmark_raw_transaction(tx_type, i)
            })
            .collect();

        group.bench_with_input(
            BenchmarkId::new("complete_pipeline", batch_size),
            &transactions,
            |b, txs| {
                b.iter(|| {
                    process_and_publish_transactions(black_box(txs.clone()), black_box(&messaging))
                })
            },
        );
    }

    group.finish();
}

criterion_group!(
    benches,
    bench_transaction_type_detection,
    bench_details_creation,
    bench_single_transaction_processing,
    bench_batch_processing,
    bench_publishing,
    bench_complete_pipeline
);
criterion_main!(benches);
