//! Simple performance benchmarks for ABI decoder actor

use abi_decoder::{AbiDecoderActor, CacheAbiRequest, DecodeRequest};
use criterion::{black_box, criterion_group, criterion_main, Criterion};

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
    }
]"#;

const TRANSFER_DATA: &str = "0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4d8b60000000000000000000000000000000000000000000000000de0b6b3a7640000";

fn bench_hot_cache_hit(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();

    c.bench_function("hot_cache_hit", |b| {
        // Setup
        let actor = runtime.block_on(async {
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
            actor
        });

        let request = DecodeRequest {
            to_address: "0x0000000000000000000000000000000000000001".to_string(),
            input_data: TRANSFER_DATA.to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0xbench".to_string(),
            request_id: "bench-hot-cache".to_string(),
        };

        // Benchmark
        b.iter(|| {
            runtime.block_on(async {
                let _ = black_box(actor.decode_transaction(request.clone(), |_| None).await);
            })
        });
    });
}

fn bench_cache_miss(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();

    c.bench_function("cache_miss", |b| {
        let actor = AbiDecoderActor::new().unwrap();

        b.iter(|| {
            let request = DecodeRequest {
                to_address: format!("0x{:040x}", rand::random::<u64>()),
                input_data: TRANSFER_DATA.to_string(),
                network: "ethereum".to_string(),
                subnet: "mainnet".to_string(),
                transaction_hash: format!("0x{:064x}", rand::random::<u64>()),
                request_id: format!("bench-miss-{}", rand::random::<u64>()),
            };

            runtime.block_on(async {
                let _ = black_box(actor.decode_transaction(request, |_| None).await);
            })
        });
    });
}

fn bench_native_transfer(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();

    c.bench_function("native_transfer", |b| {
        let actor = AbiDecoderActor::new().unwrap();
        let request = DecodeRequest {
            to_address: "0x742d35cc6634c0532925a3b8d4c9db96c4b4d8b6".to_string(),
            input_data: "0x".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0xnative".to_string(),
            request_id: "bench-native".to_string(),
        };

        b.iter(|| {
            runtime.block_on(async {
                let _ = black_box(actor.decode_transaction(request.clone(), |_| None).await);
            })
        });
    });
}

criterion_group!(
    benches,
    bench_hot_cache_hit,
    bench_cache_miss,
    bench_native_transfer
);
criterion_main!(benches);
