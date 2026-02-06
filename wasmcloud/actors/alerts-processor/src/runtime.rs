use std::collections::HashMap;
use std::sync::Arc;

use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine as _;
use chrono::{DateTime, Utc};
use regex::Regex;
use serde::Deserialize;

use alert_runtime_common::{
    alert_triggered_batch_schema_version_v1, arrow_ipc_stream_base64_format_v1,
    polars_eval_request_schema_version_v1, polars_eval_request_schema_version_v2,
    AlertEvaluationJobV1, AlertExecutableV1, AlertTemplateV1, AlertTriggeredBatchV1,
    AlertTriggeredMatchV1, AlertVariableV1, ArrowFrameV1, DatasourceRefV1, EnrichmentV1,
    OutputFieldV1, PolarsEvalRequestV1, PolarsEvalRequestV2, PolarsEvalResponseV1,
};
use ducklake_common::types::QueryRequest;

use crate::arrow_frame::{
    align_datasource_columns, build_joined_record_batch, concat_batches, decode_ipc_stream,
    encode_ipc_stream,
};
use crate::catalog::{
    build_ducklake_subject, build_query_params, expected_value_columns, RuntimeCatalogEntryV1,
};

#[derive(Debug)]
pub struct ProcessorError {
    pub code: &'static str,
    pub message: String,
}

impl ProcessorError {
    pub fn json(message: String) -> Self {
        Self {
            code: "json_error",
            message,
        }
    }

    pub fn schema(message: String) -> Self {
        Self {
            code: "schema_error",
            message,
        }
    }

    pub fn arrow(message: String) -> Self {
        Self {
            code: "arrow_error",
            message,
        }
    }

    pub fn nats(message: String) -> Self {
        Self {
            code: "nats_error",
            message,
        }
    }
}

impl std::fmt::Display for ProcessorError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for ProcessorError {}

pub trait RuntimeIO {
    fn kv_get(&self, key: &str) -> Result<Option<Vec<u8>>, ProcessorError>;
    fn nats_request(
        &self,
        subject: &str,
        body: Vec<u8>,
        timeout_ms: u32,
    ) -> Result<Vec<u8>, ProcessorError>;
    fn nats_publish(&self, subject: &str, body: Vec<u8>) -> Result<(), ProcessorError>;
    fn now(&self) -> DateTime<Utc>;
}

#[derive(Debug, Clone, Deserialize)]
struct InstanceSnapshotV1 {
    instance_id: String,
    enabled: bool,
    #[serde(default)]
    template_id: Option<String>,
    #[serde(default)]
    template_version: Option<i64>,
}

#[derive(Debug, Clone)]
enum LoadedSpecV1 {
    Template(AlertTemplateV1),
    Executable(AlertExecutableV1),
}

trait SpecLikeV1 {
    fn variables(&self) -> &[AlertVariableV1];
    fn notification_template(&self) -> &alert_runtime_common::NotificationTemplateV1;
    fn datasources(&self) -> &[DatasourceRefV1];
    fn enrichments(&self) -> &[EnrichmentV1];
}

impl SpecLikeV1 for AlertTemplateV1 {
    fn variables(&self) -> &[AlertVariableV1] {
        self.variables.as_slice()
    }

    fn notification_template(&self) -> &alert_runtime_common::NotificationTemplateV1 {
        &self.notification_template
    }

    fn datasources(&self) -> &[DatasourceRefV1] {
        self.datasources.as_slice()
    }

    fn enrichments(&self) -> &[EnrichmentV1] {
        self.enrichments.as_slice()
    }
}

impl SpecLikeV1 for AlertExecutableV1 {
    fn variables(&self) -> &[AlertVariableV1] {
        self.variables.as_slice()
    }

    fn notification_template(&self) -> &alert_runtime_common::NotificationTemplateV1 {
        &self.notification_template
    }

    fn datasources(&self) -> &[DatasourceRefV1] {
        self.datasources.as_slice()
    }

    fn enrichments(&self) -> &[EnrichmentV1] {
        self.enrichments.as_slice()
    }
}

impl SpecLikeV1 for LoadedSpecV1 {
    fn variables(&self) -> &[AlertVariableV1] {
        match self {
            Self::Template(t) => t.variables(),
            Self::Executable(e) => e.variables(),
        }
    }

    fn notification_template(&self) -> &alert_runtime_common::NotificationTemplateV1 {
        match self {
            Self::Template(t) => t.notification_template(),
            Self::Executable(e) => e.notification_template(),
        }
    }

    fn datasources(&self) -> &[DatasourceRefV1] {
        match self {
            Self::Template(t) => t.datasources(),
            Self::Executable(e) => e.datasources(),
        }
    }

    fn enrichments(&self) -> &[EnrichmentV1] {
        match self {
            Self::Template(t) => t.enrichments(),
            Self::Executable(e) => e.enrichments(),
        }
    }
}

pub fn handle_nats_message(
    io: &dyn RuntimeIO,
    subject: &str,
    body: &[u8],
) -> Result<(), ProcessorError> {
    if !subject.starts_with("alerts.jobs.create.") {
        return Ok(());
    }

    let job: AlertEvaluationJobV1 = serde_json::from_slice(body)
        .map_err(|e| ProcessorError::json(format!("invalid AlertEvaluationJobV1: {e}")))?;
    process_job(io, job)
}

fn process_job(io: &dyn RuntimeIO, mut job: AlertEvaluationJobV1) -> Result<(), ProcessorError> {
    let now = io.now();

    job.evaluation_context.run.started_at = now;

    let instance_id = job.evaluation_context.instance.instance_id.clone();
    let instance = load_instance(io, &instance_id)?;
    if !instance.enabled {
        return Ok(());
    }

    let (pinned_id, pinned_ver) = resolve_pinned_spec_ref(&instance)?;
    if pinned_id != job.evaluation_context.instance.template_id
        || pinned_ver != job.evaluation_context.instance.template_version
    {
        return Err(ProcessorError::schema(format!(
            "job references template {}:{} but instance pinned to {}:{}",
            job.evaluation_context.instance.template_id,
            job.evaluation_context.instance.template_version,
            pinned_id,
            pinned_ver
        )));
    }

    let spec = if let (Some(template_id), Some(template_version)) =
        (instance.template_id.as_deref(), instance.template_version)
    {
        // Prefer the pinned executable (vNext). Fall back to v1 template for stale caches.
        match load_executable(io, template_id, template_version) {
            Ok(exec) => LoadedSpecV1::Executable(exec),
            Err(_) => LoadedSpecV1::Template(load_template(io, template_id, template_version)?),
        }
    } else {
        return Err(ProcessorError::schema(format!(
            "instance {} missing template reference",
            instance.instance_id
        )));
    };

    let datasource_columns =
        fetch_and_align_datasources(io, spec.datasources(), &job.evaluation_context, now)?;

    let joined = build_joined_record_batch(
        &job.evaluation_context.targets.keys,
        job.evaluation_context.tx.as_ref(),
        datasource_columns,
    )?;
    let joined_ipc = encode_ipc_stream(&joined)?;
    let joined_b64 = BASE64.encode(joined_ipc);

    let output_fields = compute_output_fields(&spec, io)?;

    let frame = ArrowFrameV1 {
        format: arrow_ipc_stream_base64_format_v1(),
        data: joined_b64,
    };

    let request_id = job.job.job_id.clone();
    let eval_subject = format!("alerts.eval.request.{}", request_id);

    let eval_bytes = build_polars_eval_request_bytes(&job, &spec, frame, output_fields)?;

    let eval_response_bytes = io.nats_request(&eval_subject, eval_bytes, 5000)?;
    let eval_resp: PolarsEvalResponseV1 = serde_json::from_slice(&eval_response_bytes)
        .map_err(|e| ProcessorError::json(format!("polars resp: {e}")))?;

    if let Some(err) = eval_resp.error {
        return Err(ProcessorError {
            code: "polars_eval_failed",
            message: format!("{}: {}", err.code, err.message),
        });
    }

    if eval_resp.matched.is_empty() {
        return Ok(());
    }

    publish_triggered(io, &job, eval_resp.matched)?;
    Ok(())
}

fn build_polars_eval_request_bytes(
    job: &AlertEvaluationJobV1,
    spec: &LoadedSpecV1,
    frame: ArrowFrameV1,
    output_fields: Vec<OutputFieldV1>,
) -> Result<Vec<u8>, ProcessorError> {
    let request_id = job.job.job_id.clone();

    match spec {
        LoadedSpecV1::Template(template) => {
            let req = PolarsEvalRequestV1 {
                schema_version: polars_eval_request_schema_version_v1(),
                request_id: request_id.clone(),
                job_id: job.job.job_id.clone(),
                run_id: job.evaluation_context.run.run_id.clone(),
                template: template.clone(),
                evaluation_context: job.evaluation_context.clone(),
                frame,
                output_fields,
            };
            serde_json::to_vec(&req).map_err(|e| ProcessorError::json(format!("polars req: {e}")))
        }
        LoadedSpecV1::Executable(executable) => {
            let req = PolarsEvalRequestV2 {
                schema_version: polars_eval_request_schema_version_v2(),
                request_id: request_id.clone(),
                job_id: job.job.job_id.clone(),
                run_id: job.evaluation_context.run.run_id.clone(),
                executable: executable.clone(),
                evaluation_context: job.evaluation_context.clone(),
                frame,
                output_fields,
            };
            serde_json::to_vec(&req).map_err(|e| ProcessorError::json(format!("polars req: {e}")))
        }
    }
}

fn load_instance(
    io: &dyn RuntimeIO,
    instance_id: &str,
) -> Result<InstanceSnapshotV1, ProcessorError> {
    let key = format!("alerts:instance:{}", instance_id);
    let Some(raw) = io.kv_get(&key)? else {
        return Err(ProcessorError::schema(format!(
            "missing instance snapshot {}",
            instance_id
        )));
    };
    serde_json::from_slice(&raw)
        .map_err(|e| ProcessorError::json(format!("instance snapshot: {e}")))
}

fn resolve_pinned_spec_ref(instance: &InstanceSnapshotV1) -> Result<(String, i64), ProcessorError> {
    if let (Some(template_id), Some(template_version)) =
        (instance.template_id.as_ref(), instance.template_version)
    {
        return Ok((template_id.clone(), template_version));
    }
    Err(ProcessorError::schema(format!(
        "instance {} missing template reference",
        instance.instance_id
    )))
}

fn load_template(
    io: &dyn RuntimeIO,
    template_id: &str,
    template_version: i64,
) -> Result<AlertTemplateV1, ProcessorError> {
    let key = format!("alerts:template:{}:{}", template_id, template_version);
    let Some(raw) = io.kv_get(&key)? else {
        return Err(ProcessorError::schema(format!(
            "missing template {}:{}",
            template_id, template_version
        )));
    };
    serde_json::from_slice(&raw).map_err(|e| ProcessorError::json(format!("template spec: {e}")))
}

fn load_executable(
    io: &dyn RuntimeIO,
    template_id: &str,
    template_version: i64,
) -> Result<AlertExecutableV1, ProcessorError> {
    let key = format!("alerts:executable:{}:{}", template_id, template_version);
    let Some(raw) = io.kv_get(&key)? else {
        return Err(ProcessorError::schema(format!(
            "missing executable {}:{}",
            template_id, template_version
        )));
    };
    serde_json::from_slice(&raw).map_err(|e| ProcessorError::json(format!("executable spec: {e}")))
}

fn load_catalog_entry(
    io: &dyn RuntimeIO,
    catalog_id: &str,
) -> Result<RuntimeCatalogEntryV1, ProcessorError> {
    let key = format!("datasource_catalog:{}", catalog_id);
    let Some(raw) = io.kv_get(&key)? else {
        return Err(ProcessorError::schema(format!(
            "missing datasource_catalog:{}",
            catalog_id
        )));
    };
    serde_json::from_slice(&raw).map_err(|e| ProcessorError::json(format!("catalog entry: {e}")))
}

fn fetch_and_align_datasources(
    io: &dyn RuntimeIO,
    datasources: &[DatasourceRefV1],
    eval_ctx: &alert_runtime_common::EvaluationContextV1,
    now: DateTime<Utc>,
) -> Result<Vec<(arrow::datatypes::Field, arrow::array::ArrayRef)>, ProcessorError> {
    let mut out = Vec::new();

    for ds in datasources.iter() {
        let entry = load_catalog_entry(io, &ds.catalog_id)?;
        if !entry.enabled {
            return Err(ProcessorError::schema(format!(
                "datasource {} disabled",
                entry.catalog_id
            )));
        }
        let sql = entry.sql.as_ref().ok_or_else(|| {
            ProcessorError::schema(format!("catalog {} missing sql", entry.catalog_id))
        })?;

        let params = build_query_params(&entry, ds, eval_ctx, now)?;

        let subject = build_ducklake_subject(
            &entry.routing.table,
            &eval_ctx.partition.network,
            &eval_ctx.partition.subnet,
        )?;
        let req = QueryRequest {
            query: sql.query.clone(),
            limit: None,
            timeout_seconds: Some(((ds.timeout_ms.max(1000) as f64) / 1000.0).ceil() as u32),
            parameters: Some(params),
        };

        let req_bytes = serde_json::to_vec(&req)
            .map_err(|e| ProcessorError::json(format!("ducklake req: {e}")))?;
        let resp_bytes = io.nats_request(&subject, req_bytes, ds.timeout_ms as u32)?;

        let batches = decode_ipc_stream(&resp_bytes)?;
        let schema = if let Some(first) = batches.first() {
            first.schema()
        } else {
            Arc::new(arrow::datatypes::Schema::empty())
        };
        let batch = concat_batches(&schema, &batches)?;

        let key_column = entry
            .result_schema
            .key_columns
            .get(0)
            .cloned()
            .unwrap_or_else(|| "target_key".to_string());
        let include_columns = expected_value_columns(&entry);
        let aligned = align_datasource_columns(
            &ds.id,
            &batch,
            &eval_ctx.targets.keys,
            &key_column,
            &include_columns,
        )?;
        out.extend(aligned);
    }

    Ok(out)
}

fn compute_output_fields(
    spec: &impl SpecLikeV1,
    io: &dyn RuntimeIO,
) -> Result<Vec<OutputFieldV1>, ProcessorError> {
    // v1: derive output_fields from notification template placeholders.
    let nt = spec.notification_template();
    let placeholders = extract_placeholders(&nt.title)?
        .into_iter()
        .chain(extract_placeholders(&nt.body)?.into_iter())
        .collect::<Vec<_>>();

    let variable_ids: Vec<String> = spec.variables().iter().map(|v| v.id.clone()).collect();

    let mut alias_to_ref: HashMap<String, String> = HashMap::new();

    // Enrichments (leaf-only)
    for enrich in spec.enrichments().iter() {
        let leaf = enrich
            .output
            .rsplit('.')
            .next()
            .unwrap_or(enrich.output.as_str())
            .to_string();
        if !leaf.is_empty() {
            alias_to_ref.insert(leaf.clone(), enrich.output.clone());
        }
    }

    // Datasource columns from catalog result_schema
    for ds in spec.datasources().iter() {
        let entry = load_catalog_entry(io, &ds.catalog_id)?;
        for col in expected_value_columns(&entry) {
            let key = col.clone();
            let r = format!("$.datasources.{}.{}", ds.id, col);
            alias_to_ref.entry(key).or_insert(r);
        }
    }

    let mut output_fields = Vec::new();
    for placeholder in placeholders {
        if placeholder.contains('.') {
            continue;
        }
        if variable_ids.iter().any(|v| v == &placeholder) {
            continue;
        }
        if let Some(r) = alias_to_ref.get(&placeholder) {
            output_fields.push(OutputFieldV1 {
                r#ref: r.clone(),
                alias: Some(placeholder.clone()),
            });
        }
    }

    Ok(output_fields)
}

fn extract_placeholders(text: &str) -> Result<Vec<String>, ProcessorError> {
    let re = Regex::new(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
        .map_err(|e| ProcessorError::schema(format!("invalid placeholder regex: {e}")))?;
    Ok(re
        .captures_iter(text)
        .filter_map(|cap| cap.get(1).map(|m| m.as_str().to_string()))
        .collect())
}

fn publish_triggered(
    io: &dyn RuntimeIO,
    job: &AlertEvaluationJobV1,
    matched: Vec<alert_runtime_common::PolarsEvalMatchV1>,
) -> Result<(), ProcessorError> {
    let instance_id = job.evaluation_context.instance.instance_id.clone();
    let subject = format!("alerts.triggered.{}", instance_id);

    // Chunk for safety (still one message per job in the common case).
    let chunk_size = 1000usize;

    for chunk in matched.chunks(chunk_size) {
        let batch = AlertTriggeredBatchV1 {
            schema_version: alert_triggered_batch_schema_version_v1(),
            job_id: job.job.job_id.clone(),
            run_id: job.evaluation_context.run.run_id.clone(),
            instance_id: job.evaluation_context.instance.instance_id.clone(),
            partition: job.evaluation_context.partition.clone(),
            schedule: job.evaluation_context.schedule.clone(),
            tx: job.evaluation_context.tx.clone(),
            matches: chunk
                .iter()
                .map(|m| AlertTriggeredMatchV1 {
                    target_key: m.target_key.clone(),
                    match_context: m.match_context.clone(),
                })
                .collect(),
        };

        let bytes = serde_json::to_vec(&batch)
            .map_err(|e| ProcessorError::json(format!("triggered: {e}")))?;
        io.nats_publish(&subject, bytes)?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use alert_runtime_common::{
        alert_evaluation_job_schema_version_v1, alert_executable_schema_version_v1,
        arrow_ipc_stream_base64_format_v1, evaluation_context_schema_version_v1,
        EvaluationContextInstanceV1, EvaluationContextRunV1, EvaluationContextV1, JobMetaV1,
        JobPriorityV1, PartitionV1, TargetModeV1, TargetsV1, TriggerTypeV1,
    };
    use chrono::Utc;
    use std::collections::BTreeMap;

    struct MockIO {
        kv: BTreeMap<String, Vec<u8>>,
    }

    impl RuntimeIO for MockIO {
        fn kv_get(&self, key: &str) -> Result<Option<Vec<u8>>, ProcessorError> {
            Ok(self.kv.get(key).cloned())
        }

        fn nats_request(
            &self,
            _subject: &str,
            _body: Vec<u8>,
            _timeout_ms: u32,
        ) -> Result<Vec<u8>, ProcessorError> {
            Err(ProcessorError::nats(
                "not implemented in unit test".to_string(),
            ))
        }

        fn nats_publish(&self, _subject: &str, _body: Vec<u8>) -> Result<(), ProcessorError> {
            Ok(())
        }

        fn now(&self) -> DateTime<Utc> {
            Utc::now()
        }
    }

    #[test]
    fn placeholder_extraction_filters_dotted_paths() {
        let tpl: AlertTemplateV1 = serde_json::from_value(serde_json::json!({
            "version": "v1",
            "name": "t",
            "description": "d",
            "alert_type": "wallet",
            "variables": [{"id":"threshold","type":"number","label":"Threshold","required":true}],
            "trigger": {
              "chain_id": 1,
              "tx_type": "any",
              "from": {"any_of": [], "labels": [], "not": []},
              "to": {"any_of": [], "labels": [], "not": []},
              "method": {"selector_any_of": [], "name_any_of": [], "required": false}
            },
            "datasources": [{"id":"ds_balance","catalog_id":"ducklake.wallet_balance_latest","bindings":{},"cache_ttl_secs":30,"timeout_ms":1500}],
            "enrichments": [],
            "conditions": {"all": [], "any": [], "not": []},
            "notification_template": {"title": "Balance {{balance_latest}} for {{target.key}}", "body": "th={{threshold}}"},
            "action": {"notification_policy": "per_matched_target", "cooldown_secs": 0, "cooldown_key_template": "x", "dedupe_key_template": "y"},
            "performance": {},
            "warnings": []
        })).unwrap();

        let catalog_entry = serde_json::json!({
          "catalog_id": "ducklake.wallet_balance_latest",
          "type": "ducklake_query",
          "enabled": true,
          "description": "x",
          "routing": {"table": "wallet_balance_latest"},
          "sql": {"dialect":"duckdb","query":"SELECT 1","param_order":[]},
          "params": [],
          "result_schema": {"key_columns":["target_key"],"columns":[{"name":"target_key","type":"string"},{"name":"balance_latest","type":"decimal"}]},
          "cache_policy": {},
          "timeouts": {}
        });

        let mut kv = BTreeMap::new();
        kv.insert(
            "datasource_catalog:ducklake.wallet_balance_latest".to_string(),
            serde_json::to_vec(&catalog_entry).unwrap(),
        );

        let io = MockIO { kv };

        let fields = compute_output_fields(&tpl, &io).unwrap();
        assert_eq!(fields.len(), 1);
        assert_eq!(fields[0].alias.as_deref(), Some("balance_latest"));
    }

    #[test]
    fn polars_eval_request_schema_version_v2_for_executable() {
        let now = Utc::now();
        let job = AlertEvaluationJobV1 {
            schema_version: alert_evaluation_job_schema_version_v1(),
            job: JobMetaV1 {
                job_id: "job_1".to_string(),
                priority: JobPriorityV1::Normal,
                created_at: now,
            },
            evaluation_context: EvaluationContextV1 {
                schema_version: evaluation_context_schema_version_v1(),
                run: EvaluationContextRunV1 {
                    run_id: "run_1".to_string(),
                    attempt: 1,
                    trigger_type: TriggerTypeV1::Periodic,
                    enqueued_at: now,
                    started_at: now,
                },
                instance: EvaluationContextInstanceV1 {
                    instance_id: "inst_1".to_string(),
                    user_id: serde_json::json!("u1"),
                    template_id: "tpl_1".to_string(),
                    template_version: 1,
                },
                partition: PartitionV1 {
                    network: "ETH".to_string(),
                    subnet: "mainnet".to_string(),
                    chain_id: 1,
                },
                schedule: None,
                targets: TargetsV1 {
                    mode: TargetModeV1::Keys,
                    group_id: None,
                    keys: vec!["ETH:mainnet:0xa".to_string()],
                },
                variables: serde_json::json!({}),
                tx: None,
            },
        };

        let frame = ArrowFrameV1 {
            format: arrow_ipc_stream_base64_format_v1(),
            data: "ignored".to_string(),
        };

        let exe: AlertExecutableV1 = serde_json::from_value(serde_json::json!({
            "schema_version": alert_executable_schema_version_v1(),
            "executable_id": "exe_1",
            "template": {"schema_version": "alert_template_v2", "template_id": "tpl_1", "fingerprint": "fp", "version": 1},
            "registry_snapshot": {"kind": "internal", "version": "v1", "hash": "h"},
            "target_kind": "wallet",
            "variables": [],
            "trigger_pruning": {"evm": {
                "chain_ids": [1],
                "tx_type": "any",
                "from": {"any_of": [], "labels": [], "not": []},
                "to": {"any_of": [], "labels": [], "not": []},
                "method": {"selector_any_of": [], "name_any_of": [], "required": false},
                "event": {"topic0_any_of": [], "name_any_of": [], "required": false}
            }},
            "datasources": [],
            "enrichments": [],
            "conditions": {"all": [], "any": [], "not": []},
            "notification_template": {"title":"t","body":"b"},
            "action": {"notification_policy":"per_matched_target","cooldown_secs":0,"cooldown_key_template":"x","dedupe_key_template":"y"},
            "performance": {},
            "warnings": []
        }))
        .unwrap();

        let bytes =
            build_polars_eval_request_bytes(&job, &LoadedSpecV1::Executable(exe), frame, vec![])
                .unwrap();
        let v: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(
            v["schema_version"],
            serde_json::json!("polars_eval_request_v2")
        );
        assert!(v.get("executable").is_some());
        assert!(v.get("template").is_none());
    }

    #[test]
    fn polars_eval_request_schema_version_v1_for_template() {
        let now = Utc::now();
        let job = AlertEvaluationJobV1 {
            schema_version: alert_evaluation_job_schema_version_v1(),
            job: JobMetaV1 {
                job_id: "job_1".to_string(),
                priority: JobPriorityV1::Normal,
                created_at: now,
            },
            evaluation_context: EvaluationContextV1 {
                schema_version: evaluation_context_schema_version_v1(),
                run: EvaluationContextRunV1 {
                    run_id: "run_1".to_string(),
                    attempt: 1,
                    trigger_type: TriggerTypeV1::Periodic,
                    enqueued_at: now,
                    started_at: now,
                },
                instance: EvaluationContextInstanceV1 {
                    instance_id: "inst_1".to_string(),
                    user_id: serde_json::json!("u1"),
                    template_id: "tpl_1".to_string(),
                    template_version: 1,
                },
                partition: PartitionV1 {
                    network: "ETH".to_string(),
                    subnet: "mainnet".to_string(),
                    chain_id: 1,
                },
                schedule: None,
                targets: TargetsV1 {
                    mode: TargetModeV1::Keys,
                    group_id: None,
                    keys: vec!["ETH:mainnet:0xa".to_string()],
                },
                variables: serde_json::json!({}),
                tx: None,
            },
        };

        let frame = ArrowFrameV1 {
            format: arrow_ipc_stream_base64_format_v1(),
            data: "ignored".to_string(),
        };

        let tpl: AlertTemplateV1 = serde_json::from_value(serde_json::json!({
            "version": "v1",
            "name": "t",
            "description": "d",
            "alert_type": "wallet",
            "variables": [],
            "trigger": {"tx_type":"any","from":{"any_of":[],"labels":[],"not":[]},"to":{"any_of":[],"labels":[],"not":[]},"method":{"selector_any_of":[],"name_any_of":[],"required":false}},
            "datasources": [],
            "enrichments": [],
            "conditions": {"all": [], "any": [], "not": []},
            "notification_template": {"title":"t","body":"b"},
            "action": {"notification_policy":"per_matched_target","cooldown_secs":0,"cooldown_key_template":"x","dedupe_key_template":"y"},
            "performance": {},
            "warnings": []
        }))
        .unwrap();

        let bytes =
            build_polars_eval_request_bytes(&job, &LoadedSpecV1::Template(tpl), frame, vec![])
                .unwrap();
        let v: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(
            v["schema_version"],
            serde_json::json!("polars_eval_request_v1")
        );
        assert!(v.get("template").is_some());
        assert!(v.get("executable").is_none());
    }
}
