use std::collections::HashMap;
use std::io::Cursor;
use std::sync::Arc;

use alert_runtime_common::EvaluationTxV1;
use arrow::array::{
    new_null_array, Array, ArrayRef, Float64Array, Int64Array, StringArray, UInt32Array,
    UInt32Builder,
};
use arrow::compute::take;
use arrow::datatypes::{DataType, Field, Schema, SchemaRef};
use arrow::ipc::reader::StreamReader;
use arrow::ipc::writer::StreamWriter;
use arrow::record_batch::RecordBatch;

use crate::runtime::ProcessorError;

pub fn decode_ipc_stream(bytes: &[u8]) -> Result<Vec<RecordBatch>, ProcessorError> {
    let cursor = Cursor::new(bytes);
    let reader = StreamReader::try_new(cursor, None)
        .map_err(|e| ProcessorError::arrow(format!("failed to decode arrow stream: {e}")))?;
    let mut batches = Vec::new();
    for maybe_batch in reader {
        let batch =
            maybe_batch.map_err(|e| ProcessorError::arrow(format!("arrow decode error: {e}")))?;
        batches.push(batch);
    }
    Ok(batches)
}

pub fn encode_ipc_stream(batch: &RecordBatch) -> Result<Vec<u8>, ProcessorError> {
    let mut out = Vec::new();
    {
        let mut writer = StreamWriter::try_new(&mut out, &batch.schema())
            .map_err(|e| ProcessorError::arrow(format!("failed to create arrow writer: {e}")))?;
        writer
            .write(batch)
            .map_err(|e| ProcessorError::arrow(format!("failed to write arrow batch: {e}")))?;
        writer
            .finish()
            .map_err(|e| ProcessorError::arrow(format!("failed to finish arrow stream: {e}")))?;
    }
    Ok(out)
}

pub fn concat_batches(
    schema: &SchemaRef,
    batches: &[RecordBatch],
) -> Result<RecordBatch, ProcessorError> {
    arrow::compute::concat_batches(schema, batches)
        .map_err(|e| ProcessorError::arrow(format!("failed to concat batches: {e}")))
}

pub fn build_base_target_key_column(target_keys: &[String]) -> (Field, ArrayRef) {
    let arr = Arc::new(StringArray::from(target_keys.to_vec())) as ArrayRef;
    (Field::new("target_key", DataType::Utf8, false), arr)
}

pub fn build_tx_columns(tx: Option<&EvaluationTxV1>, rows: usize) -> Vec<(Field, ArrayRef)> {
    let kind = tx.map(|t| match &t.kind {
        alert_runtime_common::TxKindV1::Tx => "tx".to_string(),
        alert_runtime_common::TxKindV1::Log => "log".to_string(),
    });

    let hash = tx.map(|t| t.hash.clone());
    let from = tx.and_then(|t| t.from.clone());
    let to = tx.and_then(|t| t.to.clone());
    let method_selector = tx.and_then(|t| t.method_selector.clone());
    let value_wei = tx.and_then(|t| t.value_wei.clone());
    let value_native = tx.and_then(|t| t.value_native);
    let log_index = tx.and_then(|t| t.log_index);
    let log_address = tx.and_then(|t| t.log_address.clone());
    let topic0 = tx.and_then(|t| t.topic0.clone());
    let topic1 = tx.and_then(|t| t.topic1.clone());
    let topic2 = tx.and_then(|t| t.topic2.clone());
    let topic3 = tx.and_then(|t| t.topic3.clone());
    let data = tx.and_then(|t| t.data.clone());

    let block_number = tx.map(|t| t.block_number);
    let block_timestamp = tx.map(|t| t.block_timestamp.to_rfc3339());

    vec![
        string_column("tx__kind", kind.as_deref(), rows),
        string_column("tx__hash", hash.as_deref(), rows),
        string_column("tx__from", from.as_deref(), rows),
        string_column("tx__to", to.as_deref(), rows),
        string_column("tx__method_selector", method_selector.as_deref(), rows),
        string_column("tx__value_wei", value_wei.as_deref(), rows),
        float_column("tx__value_native", value_native, rows),
        int64_column("tx__log_index", log_index, rows),
        string_column("tx__log_address", log_address.as_deref(), rows),
        string_column("tx__topic0", topic0.as_deref(), rows),
        string_column("tx__topic1", topic1.as_deref(), rows),
        string_column("tx__topic2", topic2.as_deref(), rows),
        string_column("tx__topic3", topic3.as_deref(), rows),
        string_column("tx__data", data.as_deref(), rows),
        int64_column("tx__block_number", block_number, rows),
        string_column("tx__block_timestamp", block_timestamp.as_deref(), rows),
    ]
}

fn string_column(name: &str, value: Option<&str>, rows: usize) -> (Field, ArrayRef) {
    let arr = if let Some(v) = value {
        let values: Vec<Option<String>> = (0..rows).map(|_| Some(v.to_string())).collect();
        Arc::new(StringArray::from(values)) as ArrayRef
    } else {
        new_null_array(&DataType::Utf8, rows)
    };
    (Field::new(name, DataType::Utf8, true), arr)
}

fn float_column(name: &str, value: Option<f64>, rows: usize) -> (Field, ArrayRef) {
    let arr = if let Some(v) = value {
        let values: Vec<Option<f64>> = (0..rows).map(|_| Some(v)).collect();
        Arc::new(Float64Array::from(values)) as ArrayRef
    } else {
        new_null_array(&DataType::Float64, rows)
    };
    (Field::new(name, DataType::Float64, true), arr)
}

fn int64_column(name: &str, value: Option<i64>, rows: usize) -> (Field, ArrayRef) {
    let arr = if let Some(v) = value {
        let values: Vec<Option<i64>> = (0..rows).map(|_| Some(v)).collect();
        Arc::new(Int64Array::from(values)) as ArrayRef
    } else {
        new_null_array(&DataType::Int64, rows)
    };
    (Field::new(name, DataType::Int64, true), arr)
}

pub fn align_datasource_columns(
    datasource_id: &str,
    batch: &RecordBatch,
    target_keys: &[String],
    key_column: &str,
    include_columns: &[String],
) -> Result<Vec<(Field, ArrayRef)>, ProcessorError> {
    let schema = batch.schema();

    let key_idx = schema
        .fields()
        .iter()
        .position(|f| f.name() == key_column)
        .ok_or_else(|| ProcessorError::schema(format!("missing key column '{key_column}'")))?;

    let key_array = batch.column(key_idx);
    let key_strings = key_array
        .as_any()
        .downcast_ref::<StringArray>()
        .ok_or_else(|| ProcessorError::schema("key column must be Utf8".to_string()))?;

    let mut key_to_row: HashMap<String, u32> = HashMap::with_capacity(key_strings.len());
    for row in 0..key_strings.len() {
        if key_strings.is_null(row) {
            continue;
        }
        let key = key_strings.value(row).to_string();
        key_to_row.entry(key).or_insert(row as u32);
    }

    let mut idx_builder = UInt32Builder::with_capacity(target_keys.len());
    for key in target_keys {
        if let Some(idx) = key_to_row.get(key) {
            idx_builder.append_value(*idx);
        } else {
            idx_builder.append_null();
        }
    }
    let indices = UInt32Array::from(idx_builder.finish());

    let mut out = Vec::with_capacity(include_columns.len());
    for col in include_columns {
        let field_idx = schema
            .fields()
            .iter()
            .position(|f| f.name() == col)
            .ok_or_else(|| ProcessorError::schema(format!("missing datasource column '{col}'")))?;
        let field = schema.field(field_idx);
        let taken = take(batch.column(field_idx).as_ref(), &indices, None)
            .map_err(|e| ProcessorError::arrow(format!("take failed for {col}: {e}")))?;

        out.push((
            Field::new(
                &format!("{datasource_id}__{col}"),
                field.data_type().clone(),
                true,
            ),
            taken,
        ));
    }

    Ok(out)
}

pub fn build_joined_record_batch(
    target_keys: &[String],
    tx: Option<&EvaluationTxV1>,
    datasource_columns: Vec<(Field, ArrayRef)>,
) -> Result<RecordBatch, ProcessorError> {
    let mut fields = Vec::new();
    let mut arrays = Vec::new();

    let (tk_field, tk_arr) = build_base_target_key_column(target_keys);
    fields.push(tk_field);
    arrays.push(tk_arr);

    for (field, arr) in build_tx_columns(tx, target_keys.len()) {
        fields.push(field);
        arrays.push(arr);
    }

    for (field, arr) in datasource_columns {
        fields.push(field);
        arrays.push(arr);
    }

    let schema = Arc::new(Schema::new(fields));
    RecordBatch::try_new(schema, arrays)
        .map_err(|e| ProcessorError::arrow(format!("failed to build record batch: {e}")))
}

#[cfg(test)]
mod tests {
    use super::*;
    use arrow::array::Array;
    use arrow::array::Float64Array;
    use arrow::datatypes::Schema;

    #[test]
    fn align_missing_targets_to_nulls() {
        let schema = Arc::new(Schema::new(vec![
            Field::new("target_key", DataType::Utf8, false),
            Field::new("balance_latest", DataType::Float64, true),
        ]));

        let batch = RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(StringArray::from(vec![
                    "ETH:mainnet:0xa".to_string(),
                    "ETH:mainnet:0xc".to_string(),
                ])),
                Arc::new(Float64Array::from(vec![Some(1.0), Some(3.0)])),
            ],
        )
        .unwrap();

        let cols = align_datasource_columns(
            "ds_bal",
            &batch,
            &vec![
                "ETH:mainnet:0xa".to_string(),
                "ETH:mainnet:0xb".to_string(),
                "ETH:mainnet:0xc".to_string(),
            ],
            "target_key",
            &vec!["balance_latest".to_string()],
        )
        .unwrap();

        let joined = build_joined_record_batch(
            &vec![
                "ETH:mainnet:0xa".to_string(),
                "ETH:mainnet:0xb".to_string(),
                "ETH:mainnet:0xc".to_string(),
            ],
            None,
            cols,
        )
        .unwrap();

        let idx = joined
            .schema()
            .fields()
            .iter()
            .position(|f| f.name() == "ds_bal__balance_latest")
            .unwrap();

        let arr = joined
            .column(idx)
            .as_any()
            .downcast_ref::<Float64Array>()
            .unwrap();
        assert_eq!(arr.value(0), 1.0);
        assert!(arr.is_null(1));
        assert_eq!(arr.value(2), 3.0);
    }
}
