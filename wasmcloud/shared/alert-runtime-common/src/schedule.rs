use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::evaluation_context::{PartitionV1, TxKindV1};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum VmKindV1 {
    Evm,
    Svm,
    Utxo,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvmTxV1 {
    pub hash: String,
    pub from: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub to: Option<String>,
    pub input: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub method_selector: Option<String>,
    pub value_wei: String,
    pub value_native: f64,
    pub block_number: i64,
    pub block_timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvmLogV1 {
    pub transaction_hash: String,
    pub log_index: i64,
    pub address: String,
    pub topic0: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub topic1: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub topic2: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub topic3: Option<String>,
    pub data: String,
    pub block_number: i64,
    pub block_timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScheduleEventV1 {
    pub kind: TxKindV1,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub evm_tx: Option<EvmTxV1>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub evm_log: Option<EvmLogV1>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertScheduleEventDrivenV1 {
    pub schema_version: String,
    pub vm: VmKindV1,
    pub partition: PartitionV1,
    pub candidate_target_keys: Vec<String>,
    pub event: ScheduleEventV1,
    pub requested_at: DateTime<Utc>,
    pub source: String,
}

pub fn alert_schedule_event_driven_schema_version_v1() -> String {
    "alert_schedule_event_driven_v1".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertSchedulePeriodicV1 {
    pub schema_version: String,
    pub request_id: String,
    pub instance_id: String,
    pub scheduled_for: DateTime<Utc>,
    pub requested_at: DateTime<Utc>,
    pub source: String,
}

pub fn alert_schedule_periodic_schema_version_v1() -> String {
    "alert_schedule_periodic_v1".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertScheduleOneTimeV1 {
    pub schema_version: String,
    pub request_id: String,
    pub instance_id: String,
    pub scheduled_for: DateTime<Utc>,
    pub requested_at: DateTime<Utc>,
    pub source: String,
}

pub fn alert_schedule_one_time_schema_version_v1() -> String {
    "alert_schedule_one_time_v1".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use pretty_assertions::assert_eq;

    #[test]
    fn test_event_driven_schema_version() {
        assert_eq!(
            alert_schedule_event_driven_schema_version_v1(),
            "alert_schedule_event_driven_v1"
        );
    }
}
