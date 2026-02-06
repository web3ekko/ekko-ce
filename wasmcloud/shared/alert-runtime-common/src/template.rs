use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertTemplateV1 {
    pub version: String,
    pub name: String,
    pub description: String,
    pub alert_type: String,
    #[serde(default)]
    pub variables: Vec<AlertVariableV1>,
    pub trigger: TriggerV1,
    #[serde(default)]
    pub datasources: Vec<DatasourceRefV1>,
    #[serde(default)]
    pub enrichments: Vec<EnrichmentV1>,
    pub conditions: ConditionSetV1,
    pub notification_template: NotificationTemplateV1,
    pub action: ActionV1,
    pub performance: Value,
    #[serde(default)]
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertVariableV1 {
    pub id: String,
    #[serde(rename = "type")]
    pub var_type: String,
    pub label: String,
    #[serde(default)]
    pub description: String,
    pub required: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub validation: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ui: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerAddressFilterV1 {
    #[serde(default)]
    pub any_of: Vec<String>,
    #[serde(default)]
    pub labels: Vec<String>,
    #[serde(default)]
    pub not: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerMethodFilterV1 {
    #[serde(default)]
    pub selector_any_of: Vec<String>,
    #[serde(default)]
    pub name_any_of: Vec<String>,
    pub required: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerEventFilterV1 {
    #[serde(default)]
    pub topic0_any_of: Vec<String>,
    #[serde(default)]
    pub name_any_of: Vec<String>,
    pub required: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerV1 {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub chain_id: Option<i64>,
    pub tx_type: String,
    pub from: TriggerAddressFilterV1,
    pub to: TriggerAddressFilterV1,
    pub method: TriggerMethodFilterV1,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub event: Option<TriggerEventFilterV1>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatasourceRefV1 {
    pub id: String,
    pub catalog_id: String,
    pub bindings: Value,
    pub cache_ttl_secs: i64,
    pub timeout_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnrichmentV1 {
    pub id: String,
    pub expr: ExprV1,
    pub output: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConditionSetV1 {
    #[serde(default)]
    pub all: Vec<ExprV1>,
    #[serde(default)]
    pub any: Vec<ExprV1>,
    #[serde(default)]
    pub not: Vec<ExprV1>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ExprOpV1 {
    Add,
    Sub,
    Mul,
    Div,
    Gt,
    Gte,
    Lt,
    Lte,
    Eq,
    Neq,
    And,
    Or,
    Not,
    Coalesce,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ExprOperandV1 {
    Expr(Box<ExprV1>),
    Literal(Value),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExprV1 {
    pub op: ExprOpV1,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub left: Option<ExprOperandV1>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub right: Option<ExprOperandV1>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub values: Option<Vec<ExprOperandV1>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationTemplateV1 {
    pub title: String,
    pub body: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionV1 {
    pub notification_policy: String,
    pub cooldown_secs: i64,
    pub cooldown_key_template: String,
    pub dedupe_key_template: String,
}
