use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::evaluation_context::{EvaluationTxV1, PartitionV1, ScheduleV1};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertTriggeredMatchV1 {
    pub target_key: String,
    pub match_context: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertTriggeredBatchV1 {
    pub schema_version: String,
    pub job_id: String,
    pub run_id: String,
    pub instance_id: String,
    pub partition: PartitionV1,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub schedule: Option<ScheduleV1>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tx: Option<EvaluationTxV1>,
    pub matches: Vec<AlertTriggeredMatchV1>,
}

pub fn alert_triggered_batch_schema_version_v1() -> String {
    "alert_triggered_batch_v1".to_string()
}
