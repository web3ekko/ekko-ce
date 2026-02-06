use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::evaluation_context::EvaluationContextV1;
use crate::executable::AlertExecutableV1;
use crate::template::AlertTemplateV1;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArrowFrameV1 {
    pub format: String,
    pub data: String,
}

pub fn arrow_ipc_stream_base64_format_v1() -> String {
    "arrow_ipc_stream_base64".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutputFieldV1 {
    pub r#ref: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub alias: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolarsEvalRequestV1 {
    pub schema_version: String,
    pub request_id: String,
    pub job_id: String,
    pub run_id: String,
    pub template: AlertTemplateV1,
    pub evaluation_context: EvaluationContextV1,
    pub frame: ArrowFrameV1,
    pub output_fields: Vec<OutputFieldV1>,
}

pub fn polars_eval_request_schema_version_v1() -> String {
    "polars_eval_request_v1".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolarsEvalRequestV2 {
    pub schema_version: String,
    pub request_id: String,
    pub job_id: String,
    pub run_id: String,
    pub executable: AlertExecutableV1,
    pub evaluation_context: EvaluationContextV1,
    pub frame: ArrowFrameV1,
    pub output_fields: Vec<OutputFieldV1>,
}

pub fn polars_eval_request_schema_version_v2() -> String {
    "polars_eval_request_v2".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolarsEvalMatchV1 {
    pub target_key: String,
    pub match_context: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolarsEvalErrorV1 {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolarsEvalTimingsV1 {
    pub total: u64,
    pub enrichments: u64,
    pub conditions: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolarsEvalResponseV1 {
    pub schema_version: String,
    pub request_id: String,
    pub job_id: String,
    pub run_id: String,
    pub instance_id: String,
    pub partition: crate::evaluation_context::PartitionV1,
    pub rows_evaluated: i64,
    #[serde(default)]
    pub matched: Vec<PolarsEvalMatchV1>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<PolarsEvalErrorV1>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timings_ms: Option<PolarsEvalTimingsV1>,
}

pub fn polars_eval_response_schema_version_v1() -> String {
    "polars_eval_response_v1".to_string()
}
