//! Performance benchmarks for ABI decoder actor

use abi_decoder::{AbiDecoderActor, BatchDecodeRequest, CacheAbiRequest, DecodeRequest};
use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use std::time::Duration;

// Mock data for benchmarks
const ERC20_ABI: &str = r#"[
    {
        "type": "function",
        "name": "transfer",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"}
        ],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable"
    },
    {
        "type": "function",
        "name": "approve",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable"
    }
]"#;

const TRANSFER_DATA: &str = "0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4d8b60000000000000000000000000000000000000000000000000de0b6b3a7640000";
const APPROVE_DATA: &str = "0x095ea7b3000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4d8b60000000000000000000000000000000000000000000000000de0b6b3a7640000";

fn create_decode_request(index: usize, input_data: &str) -> DecodeRequest {
    DecodeRequest {
        to_address: format!("0x{:040x}", index),
        input_data: input_data.to_string(),
        network: "ethereum".to_string(),
        subnet: "mainnet".to_string(),
        transaction_hash: format!("0x{:064x}", index),
        request_id: format!("bench-{}", index),
    }
}

fn bench_hot_cache_hit(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();

    c.bench_function("hot_cache_hit", |b| {
        b.to_async(&runtime)
            .iter_with_setup(|| async {
                let actor = AbiDecoderActor::new().unwrap();

                // Pre-cache an ABI
                let cache_request = CacheAbiRequest {
                    network: "ethereum".to_string(),
                    contract_address: "0x0000000000000000000000000000000000000001".to_string(),
                    abi_json: ERC20_ABI.to_string(),
                    source: "benchmark".to_string(),
                    verified: true,
                };
                actor.cache_abi(cache_request).await.unwrap();

                let request = DecodeRequest {
                    to_address: "0x0000000000000000000000000000000000000001".to_string(),
                    input_data: TRANSFER_DATA.to_string(),
                    network: "ethereum".to_string(),
                    subnet: "mainnet".to_string(),
                    transaction_hash: "0xbench".to_string(),
                    request_id: "bench-hot-cache".to_string(),
                };

                (actor, request)
            })
            .iter(|(actor, request)| async {
                let _ = black_box(actor.decode_transaction(request.clone(), |_| None).await);
            });
    });
}

fn bench_cache_miss(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();

    c.bench_function("cache_miss", |b| {
        b.to_async(&runtime)
            .iter_with_setup(|| async {
                let actor = AbiDecoderActor::new().unwrap();
                let request = DecodeRequest {
                    to_address: format!("0x{:040x}", rand::random::<u64>()),
                    input_data: TRANSFER_DATA.to_string(),
                    network: "ethereum".to_string(),
                    subnet: "mainnet".to_string(),
                    transaction_hash: format!("0x{:064x}", rand::random::<u64>()),
                    request_id: format!("bench-miss-{}", rand::random::<u64>()),
                };
                (actor, request)
            })
            .iter(|(actor, request)| async {
                let _ = black_box(actor.decode_transaction(request.clone(), |_| None).await);
            });
    });
}

fn bench_batch_decode(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();

    let batch_sizes = vec![10, 50, 100, 500];

    for size in batch_sizes {
        c.bench_with_input(BenchmarkId::new("batch_decode", size), &size, |b, &size| {
            b.to_async(&runtime)
                .iter_with_setup(|| async {
                    let actor = AbiDecoderActor::new().unwrap();

                    // Pre-cache some ABIs
                    for i in 0..10 {
                        let cache_request = CacheAbiRequest {
                            network: "ethereum".to_string(),
                            contract_address: format!("0x{:040x}", i),
                            abi_json: ERC20_ABI.to_string(),
                            source: "benchmark".to_string(),
                            verified: true,
                        };
                        actor.cache_abi(cache_request).await.unwrap();
                    }

                    // Create batch request
                    let requests: Vec<DecodeRequest> = (0..size)
                        .map(|i| {
                            let input_data = if i % 2 == 0 {
                                TRANSFER_DATA
                            } else {
                                APPROVE_DATA
                            };
                            create_decode_request(i % 10, input_data)
                        })
                        .collect();

                    let batch = BatchDecodeRequest {
                        requests,
                        batch_id: format!("bench-batch-{}", size),
                    };

                    (actor, batch)
                })
                .iter(|(actor, batch)| async {
                    let _ = black_box(actor.decode_batch(batch.clone(), |_| None).await);
                });
        });
    }
}

fn bench_concurrent_requests(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();

    let concurrency_levels = vec![10, 50, 100];

    for level in concurrency_levels {
        c.bench_with_input(
            BenchmarkId::new("concurrent_decode", level),
            &level,
            |b, &level| {
                b.to_async(&runtime)
                    .iter_with_setup(|| async {
                        let actor = AbiDecoderActor::new().unwrap();

                        // Pre-cache an ABI
                        let cache_request = CacheAbiRequest {
                            network: "ethereum".to_string(),
                            contract_address: "0x0000000000000000000000000000000000000001"
                                .to_string(),
                            abi_json: ERC20_ABI.to_string(),
                            source: "benchmark".to_string(),
                            verified: true,
                        };
                        actor.cache_abi(cache_request).await.unwrap();

                        actor
                    })
                    .iter(|actor| async {
                        let mut tasks = vec![];

                        for i in 0..level {
                            let actor_clone = actor.clone();
                            let request = DecodeRequest {
                                to_address: "0x0000000000000000000000000000000000000001"
                                    .to_string(),
                                input_data: if i % 2 == 0 {
                                    TRANSFER_DATA
                                } else {
                                    APPROVE_DATA
                                }
                                .to_string(),
                                network: "ethereum".to_string(),
                                subnet: "mainnet".to_string(),
                                transaction_hash: format!("0x{:064x}", i),
                                request_id: format!("bench-concurrent-{}", i),
                            };

                            let task = tokio::spawn(async move {
                                actor_clone.decode_transaction(request, |_| None).await
                            });
                            tasks.push(task);
                        }

                        let results = futures::future::join_all(tasks).await;
                        black_box(results);
                    });
            },
        );
    }
}

fn bench_cache_operations(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();

    c.bench_function("cache_abi", |b| {
        b.to_async(&runtime)
            .iter_with_setup(|| async {
                let actor = AbiDecoderActor::new().unwrap();
                actor
            })
            .iter(|actor| async {
                let cache_request = CacheAbiRequest {
                    network: "ethereum".to_string(),
                    contract_address: format!("0x{:040x}", rand::random::<u64>()),
                    abi_json: ERC20_ABI.to_string(),
                    source: "benchmark".to_string(),
                    verified: true,
                };
                let _ = black_box(actor.cache_abi(cache_request).await);
            });
    });
}

fn bench_different_transaction_types(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();

    let mut group = c.benchmark_group("transaction_types");

    // Native transfer
    group.bench_function("native_transfer", |b| {
        b.to_async(&runtime)
            .iter_with_setup(|| async {
                let actor = AbiDecoderActor::new().unwrap();
                let request = DecodeRequest {
                    to_address: "0x742d35cc6634c0532925a3b8d4c9db96c4b4d8b6".to_string(),
                    input_data: "0x".to_string(),
                    network: "ethereum".to_string(),
                    subnet: "mainnet".to_string(),
                    transaction_hash: "0xnative".to_string(),
                    request_id: "bench-native".to_string(),
                };
                (actor, request)
            })
            .iter(|(actor, request)| async {
                let _ = black_box(actor.decode_transaction(request.clone(), |_| None).await);
            });
    });

    // Contract creation
    group.bench_function("contract_creation", |b| {
        b.to_async(&runtime)
            .iter_with_setup(|| async {
                let actor = AbiDecoderActor::new().unwrap();
                let request = DecodeRequest {
                    to_address: "".to_string(),
                    input_data: "0x608060405234801561001057600080fd5b50".to_string(),
                    network: "ethereum".to_string(),
                    subnet: "mainnet".to_string(),
                    transaction_hash: "0xcreation".to_string(),
                    request_id: "bench-creation".to_string(),
                };
                (actor, request)
            })
            .iter(|(actor, request)| async {
                let _ = black_box(actor.decode_transaction(request.clone(), |_| None).await);
            });
    });

    // Function call with cached ABI
    group.bench_function("function_call_cached", |b| {
        b.to_async(&runtime)
            .iter_with_setup(|| async {
                let actor = AbiDecoderActor::new().unwrap();

                // Pre-cache ABI
                let cache_request = CacheAbiRequest {
                    network: "ethereum".to_string(),
                    contract_address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48".to_string(),
                    abi_json: ERC20_ABI.to_string(),
                    source: "benchmark".to_string(),
                    verified: true,
                };
                actor.cache_abi(cache_request).await.unwrap();

                let request = DecodeRequest {
                    to_address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48".to_string(),
                    input_data: TRANSFER_DATA.to_string(),
                    network: "ethereum".to_string(),
                    subnet: "mainnet".to_string(),
                    transaction_hash: "0xfunction".to_string(),
                    request_id: "bench-function".to_string(),
                };
                (actor, request)
            })
            .iter(|(actor, request)| async {
                let _ = black_box(actor.decode_transaction(request.clone(), |_| None).await);
            });
    });

    group.finish();
}

fn configure_criterion() -> Criterion {
    Criterion::default()
        .measurement_time(Duration::from_secs(10))
        .sample_size(100)
        .warm_up_time(Duration::from_secs(3))
}

criterion_group! {
    name = benches;
    config = configure_criterion();
    targets =
        bench_hot_cache_hit,
        bench_cache_miss,
        bench_batch_decode,
        bench_concurrent_requests,
        bench_cache_operations,
        bench_different_transaction_types
}

criterion_main!(benches);
