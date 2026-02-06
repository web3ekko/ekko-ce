use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::template::{
    ActionV1, AlertVariableV1, ConditionSetV1, DatasourceRefV1, EnrichmentV1,
    TriggerAddressFilterV1, TriggerEventFilterV1, TriggerMethodFilterV1,
};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutableTemplateRefV1 {
    pub schema_version: String,
    #[serde(alias = "plan_id")]
    pub template_id: String,
    pub fingerprint: String,
    pub version: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegistrySnapshotV1 {
    pub kind: String,
    pub version: String,
    pub hash: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvmTriggerPruningV1 {
    pub chain_ids: Vec<i64>,
    pub tx_type: String,
    pub from: TriggerAddressFilterV1,
    pub to: TriggerAddressFilterV1,
    pub method: TriggerMethodFilterV1,
    pub event: TriggerEventFilterV1,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerPruningV1 {
    pub evm: EvmTriggerPruningV1,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertExecutableV1 {
    pub schema_version: String,
    pub executable_id: String,
    #[serde(alias = "plan")]
    pub template: ExecutableTemplateRefV1,
    pub registry_snapshot: RegistrySnapshotV1,
    pub target_kind: String,
    #[serde(default)]
    pub variables: Vec<AlertVariableV1>,
    pub trigger_pruning: TriggerPruningV1,
    #[serde(default)]
    pub datasources: Vec<DatasourceRefV1>,
    #[serde(default)]
    pub enrichments: Vec<EnrichmentV1>,
    pub conditions: ConditionSetV1,
    pub notification_template: crate::template::NotificationTemplateV1,
    pub action: ActionV1,
    pub performance: Value,
    #[serde(default)]
    pub warnings: Vec<String>,
}

pub fn alert_executable_schema_version_v1() -> String {
    "alert_executable_v1".to_string()
}
