use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use polars_eval_provider::{PolarsEvalProvider, TransactionData};

fn create_test_transaction() -> TransactionData {
    TransactionData {
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
    }
}

fn bench_simple_comparison(c: &mut Criterion) {
    let evaluator = PolarsEvalProvider::new();
    let tx = create_test_transaction();

    c.bench_function("simple_comparison", |b| {
        b.iter(|| evaluator.evaluate(black_box("value_usd > 1000"), black_box(&tx)))
    });
}

fn bench_logical_and(c: &mut Criterion) {
    let evaluator = PolarsEvalProvider::new();
    let tx = create_test_transaction();

    c.bench_function("logical_and", |b| {
        b.iter(|| {
            evaluator.evaluate(
                black_box("value_usd > 1000 && status == 'success'"),
                black_box(&tx),
            )
        })
    });
}

fn bench_complex_expression(c: &mut Criterion) {
    let evaluator = PolarsEvalProvider::new();
    let tx = create_test_transaction();

    c.bench_function("complex_expression", |b| {
        b.iter(|| {
            evaluator.evaluate(
                black_box("value_usd > 1000 && status == 'success' || gas_used < 30000"),
                black_box(&tx),
            )
        })
    });
}

fn bench_cache_hit(c: &mut Criterion) {
    let evaluator = PolarsEvalProvider::new();
    let tx = create_test_transaction();
    let expr = "value_usd > 1000";

    // Prime the cache
    evaluator.evaluate(expr, &tx).unwrap();

    c.bench_function("cache_hit", |b| {
        b.iter(|| evaluator.evaluate(black_box(expr), black_box(&tx)))
    });
}

fn bench_cache_miss(c: &mut Criterion) {
    let evaluator = PolarsEvalProvider::new();
    let tx = create_test_transaction();

    let mut group = c.benchmark_group("cache_miss");
    for i in 0..5 {
        let expr = format!("value_usd > {}", 1000 + i * 100);
        group.bench_with_input(BenchmarkId::from_parameter(i), &expr, |b, expr| {
            b.iter(|| evaluator.evaluate(black_box(expr), black_box(&tx)))
        });
    }
    group.finish();
}

fn bench_throughput(c: &mut Criterion) {
    let evaluator = PolarsEvalProvider::new();
    let tx = create_test_transaction();
    let expr = "value_usd > 1000 && status == 'success'";

    let mut group = c.benchmark_group("throughput");
    group.throughput(criterion::Throughput::Elements(1));

    group.bench_function("single_eval", |b| {
        b.iter(|| evaluator.evaluate(black_box(expr), black_box(&tx)))
    });

    group.finish();
}

criterion_group!(
    benches,
    bench_simple_comparison,
    bench_logical_and,
    bench_complex_expression,
    bench_cache_hit,
    bench_cache_miss,
    bench_throughput
);

criterion_main!(benches);
