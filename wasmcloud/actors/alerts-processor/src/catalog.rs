use std::collections::HashMap;

use alert_runtime_common::{DatasourceRefV1, EvaluationContextV1};
use chrono::{DateTime, Utc};
use ducklake_common::types::SqlParam;
use serde::Deserialize;
use serde_json::Value;

use crate::runtime::ProcessorError;

#[derive(Debug, Clone, Deserialize)]
pub struct RuntimeCatalogEntryV1 {
    pub catalog_id: String,
    pub r#type: String,
    pub enabled: bool,
    pub description: String,
    pub routing: RuntimeCatalogRoutingV1,
    pub sql: Option<RuntimeCatalogSqlV1>,
    pub params: Vec<RuntimeCatalogParamV1>,
    pub result_schema: RuntimeCatalogResultSchemaV1,
    #[serde(default)]
    pub cache_policy: Value,
    #[serde(default)]
    pub timeouts: Value,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RuntimeCatalogRoutingV1 {
    pub table: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RuntimeCatalogSqlV1 {
    pub dialect: String,
    pub query: String,
    pub param_order: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RuntimeCatalogParamV1 {
    pub name: String,
    pub r#type: String,
    #[serde(default = "default_required")]
    pub required: bool,
}

fn default_required() -> bool {
    true
}

#[derive(Debug, Clone, Deserialize)]
pub struct RuntimeCatalogResultSchemaV1 {
    pub key_columns: Vec<String>,
    pub columns: Vec<RuntimeCatalogResultColumnV1>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RuntimeCatalogResultColumnV1 {
    pub name: String,
    pub r#type: String,
}

pub fn expected_value_columns(entry: &RuntimeCatalogEntryV1) -> Vec<String> {
    let mut keys = entry.result_schema.key_columns.clone();
    keys.sort();
    keys.dedup();

    entry
        .result_schema
        .columns
        .iter()
        .map(|c| c.name.clone())
        .filter(|name| !keys.contains(name))
        .collect()
}

pub fn build_ducklake_subject(
    table: &str,
    network: &str,
    subnet: &str,
) -> Result<String, ProcessorError> {
    let chain = chain_for_network(network)?;
    Ok(format!("ducklake.{}.{}.{}.query", table, chain, subnet))
}

fn chain_for_network(network: &str) -> Result<&'static str, ProcessorError> {
    match network {
        "ETH" => Ok("ethereum"),
        "AVAX" => Ok("avalanche"),
        "SOL" => Ok("solana"),
        "BTC" => Ok("bitcoin"),
        other => Err(ProcessorError::schema(format!(
            "unsupported network '{}'",
            other
        ))),
    }
}

pub fn build_query_params(
    entry: &RuntimeCatalogEntryV1,
    template_ds: &DatasourceRefV1,
    eval_ctx: &EvaluationContextV1,
    now: DateTime<Utc>,
) -> Result<Vec<SqlParam>, ProcessorError> {
    let Some(sql) = entry.sql.as_ref() else {
        return Err(ProcessorError::schema(format!(
            "catalog entry {} missing sql",
            entry.catalog_id
        )));
    };
    let eval_ctx_json = serde_json::to_value(eval_ctx)
        .map_err(|e| ProcessorError::json(format!("eval_ctx json: {e}")))?;

    let param_types: HashMap<String, String> = entry
        .params
        .iter()
        .map(|p| (p.name.clone(), p.r#type.clone()))
        .collect();

    let bindings = template_ds.bindings.as_object();

    let mut params = Vec::with_capacity(sql.param_order.len());
    for name in sql.param_order.iter() {
        let expected_type = param_types
            .get(name)
            .map(|s| s.as_str())
            .unwrap_or("string");

        let binding = bindings.and_then(|b| b.get(name));
        let resolved = resolve_binding_value(name, binding, eval_ctx, &eval_ctx_json, now)?;
        params.push(to_sql_param(expected_type, resolved)?);
    }
    Ok(params)
}

fn resolve_binding_value(
    name: &str,
    binding: Option<&Value>,
    eval_ctx: &EvaluationContextV1,
    eval_ctx_json: &Value,
    now: DateTime<Utc>,
) -> Result<Value, ProcessorError> {
    if let Some(b) = binding {
        return Ok(resolve_binding_expr(b, eval_ctx, eval_ctx_json)?);
    }

    match name {
        "target_keys" => Ok(Value::Array(
            eval_ctx
                .targets
                .keys
                .iter()
                .map(|k| Value::String(k.clone()))
                .collect(),
        )),
        "network" => Ok(Value::String(eval_ctx.partition.network.clone())),
        "subnet" => Ok(Value::String(eval_ctx.partition.subnet.clone())),
        "chain_id" => Ok(Value::Number(eval_ctx.partition.chain_id.into())),
        "as_of" => {
            if let Some(sched) = eval_ctx.schedule.as_ref() {
                Ok(Value::String(sched.effective_as_of.to_rfc3339()))
            } else if let Some(tx) = eval_ctx.tx.as_ref() {
                Ok(Value::String(tx.block_timestamp.to_rfc3339()))
            } else {
                Ok(Value::String(now.to_rfc3339()))
            }
        }
        "scheduled_for" => {
            if let Some(sched) = eval_ctx.schedule.as_ref() {
                Ok(Value::String(sched.scheduled_for.to_rfc3339()))
            } else {
                Ok(Value::String(now.to_rfc3339()))
            }
        }
        other => Err(ProcessorError::schema(format!(
            "missing required datasource binding for '{}'",
            other
        ))),
    }
}

fn resolve_binding_expr(
    expr: &Value,
    eval_ctx: &EvaluationContextV1,
    eval_ctx_json: &Value,
) -> Result<Value, ProcessorError> {
    match expr {
        Value::String(s) => {
            let s = s.trim();
            if let Some(path) = s.strip_prefix("$.") {
                let v = jsonpath_get(eval_ctx_json, path).ok_or_else(|| {
                    ProcessorError::schema(format!("binding JSONPath '{}' not found", s))
                })?;
                return Ok(v.clone());
            }

            if let Some(var) = s.strip_prefix("{{").and_then(|s| s.strip_suffix("}}")) {
                let var = var.trim();
                let vars = eval_ctx.variables.as_object().ok_or_else(|| {
                    ProcessorError::schema(
                        "evaluation_context.variables must be object".to_string(),
                    )
                })?;
                let v = vars.get(var).ok_or_else(|| {
                    ProcessorError::schema(format!("variable '{}' not found for binding", var))
                })?;
                return Ok(v.clone());
            }

            Ok(Value::String(s.to_string()))
        }
        other => Ok(other.clone()),
    }
}

fn jsonpath_get<'a>(root: &'a Value, path: &str) -> Option<&'a Value> {
    // Supported surface is intentionally tiny: dot-separated keys off the EvaluationContext JSON.
    // Path passed in excludes the leading "$.".
    let mut current = root;
    for segment in path.split('.') {
        current = current.get(segment)?;
    }
    Some(current)
}

fn to_sql_param(expected_type: &str, value: Value) -> Result<SqlParam, ProcessorError> {
    match expected_type {
        "string" | "duration" => Ok(SqlParam::String(value_to_string(value))),
        "integer" => Ok(SqlParam::Int64(value_to_i64(value)?)),
        "boolean" => Ok(SqlParam::Bool(value_to_bool(value)?)),
        "decimal" => Ok(SqlParam::Decimal(value_to_string(value))),
        "timestamp" => Ok(SqlParam::Timestamp(value_to_epoch_millis(value)? as u64)),
        // DuckDB (via the duckdb Rust crate) does not support binding LIST parameters safely.
        // We encode target key lists as a single CSV string and split in SQL (string_split + UNNEST).
        "target_keys_csv" => Ok(SqlParam::String(value_to_string_list(value)?.join(","))),
        other => Err(ProcessorError::schema(format!(
            "unsupported param type '{}'",
            other
        ))),
    }
}

fn value_to_string(value: Value) -> String {
    match value {
        Value::String(s) => s,
        Value::Number(n) => n.to_string(),
        Value::Bool(b) => b.to_string(),
        other => other.to_string(),
    }
}

fn value_to_i64(value: Value) -> Result<i64, ProcessorError> {
    match value {
        Value::Number(n) => n
            .as_i64()
            .ok_or_else(|| ProcessorError::schema("invalid integer".to_string())),
        Value::String(s) => s
            .parse::<i64>()
            .map_err(|e| ProcessorError::schema(format!("invalid integer '{}': {}", s, e))),
        other => Err(ProcessorError::schema(format!(
            "invalid integer value {}",
            other
        ))),
    }
}

fn value_to_bool(value: Value) -> Result<bool, ProcessorError> {
    match value {
        Value::Bool(b) => Ok(b),
        Value::String(s) => match s.to_lowercase().as_str() {
            "true" | "1" => Ok(true),
            "false" | "0" => Ok(false),
            _ => Err(ProcessorError::schema(format!("invalid bool '{}'", s))),
        },
        other => Err(ProcessorError::schema(format!("invalid bool {}", other))),
    }
}

fn value_to_epoch_millis(value: Value) -> Result<i64, ProcessorError> {
    match value {
        Value::Number(n) => n
            .as_i64()
            .ok_or_else(|| ProcessorError::schema("invalid timestamp".to_string())),
        Value::String(s) => {
            let dt = DateTime::parse_from_rfc3339(&s).map_err(|e| {
                ProcessorError::schema(format!("invalid rfc3339 timestamp '{}': {}", s, e))
            })?;
            Ok(dt.timestamp_millis())
        }
        other => Err(ProcessorError::schema(format!(
            "invalid timestamp {}",
            other
        ))),
    }
}

fn value_to_string_list(value: Value) -> Result<Vec<String>, ProcessorError> {
    match value {
        Value::Array(arr) => Ok(arr
            .into_iter()
            .map(|v| match v {
                Value::String(s) => s,
                other => other.to_string(),
            })
            .collect()),
        Value::String(s) => Ok(vec![s]),
        other => Err(ProcessorError::schema(format!(
            "invalid list value {}",
            other
        ))),
    }
}
