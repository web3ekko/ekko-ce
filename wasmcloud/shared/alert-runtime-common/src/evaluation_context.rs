use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TriggerTypeV1 {
    EventDriven,
    Periodic,
    OneTime,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvaluationContextRunV1 {
    pub run_id: String,
    pub attempt: u32,
    pub trigger_type: TriggerTypeV1,
    pub enqueued_at: DateTime<Utc>,
    pub started_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvaluationContextInstanceV1 {
    pub instance_id: String,
    pub user_id: Value,
    pub template_id: String,
    pub template_version: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PartitionV1 {
    pub network: String,
    pub subnet: String,
    pub chain_id: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScheduleV1 {
    pub scheduled_for: DateTime<Utc>,
    pub data_lag_secs: i64,
    pub effective_as_of: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TargetModeV1 {
    Keys,
    Group,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TargetsV1 {
    pub mode: TargetModeV1,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub group_id: Option<String>,
    pub keys: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TxKindV1 {
    Tx,
    Log,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvaluationTxV1 {
    pub kind: TxKindV1,
    pub hash: String,

    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub from: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub to: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub method_selector: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub value_wei: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub value_native: Option<f64>,

    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub log_index: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub log_address: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub topic0: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub topic1: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub topic2: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub topic3: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub data: Option<String>,

    pub block_number: i64,
    pub block_timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvaluationContextV1 {
    pub schema_version: String,
    pub run: EvaluationContextRunV1,
    pub instance: EvaluationContextInstanceV1,
    pub partition: PartitionV1,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub schedule: Option<ScheduleV1>,
    pub targets: TargetsV1,
    pub variables: Value,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tx: Option<EvaluationTxV1>,
}

pub fn evaluation_context_schema_version_v1() -> String {
    "evaluation_context_v1".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use pretty_assertions::assert_eq;

    #[test]
    fn test_roundtrip_minimal_scheduled_context() {
        let now = Utc::now();
        let ctx = EvaluationContextV1 {
            schema_version: evaluation_context_schema_version_v1(),
            run: EvaluationContextRunV1 {
                run_id: "run".to_string(),
                attempt: 1,
                trigger_type: TriggerTypeV1::Periodic,
                enqueued_at: now,
                started_at: now,
            },
            instance: EvaluationContextInstanceV1 {
                instance_id: "inst".to_string(),
                user_id: Value::String("123".to_string()),
                template_id: "tpl".to_string(),
                template_version: 1,
            },
            partition: PartitionV1 {
                network: "ETH".to_string(),
                subnet: "mainnet".to_string(),
                chain_id: 1,
            },
            schedule: Some(ScheduleV1 {
                scheduled_for: now,
                data_lag_secs: 120,
                effective_as_of: now,
            }),
            targets: TargetsV1 {
                mode: TargetModeV1::Keys,
                group_id: None,
                keys: vec!["ETH:mainnet:0xabc".to_string()],
            },
            variables: Value::Object(Default::default()),
            tx: None,
        };

        let json = serde_json::to_value(&ctx).unwrap();
        let decoded: EvaluationContextV1 = serde_json::from_value(json).unwrap();
        assert_eq!(decoded.schema_version, "evaluation_context_v1");
        assert_eq!(decoded.partition.network, "ETH");
        assert_eq!(decoded.targets.keys[0], "ETH:mainnet:0xabc");
    }
}
