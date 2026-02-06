use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::evaluation_context::{EvaluationContextV1, TriggerTypeV1};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum JobPriorityV1 {
    Critical,
    High,
    Normal,
    Low,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobMetaV1 {
    pub job_id: String,
    pub priority: JobPriorityV1,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertEvaluationJobV1 {
    pub schema_version: String,
    pub job: JobMetaV1,
    pub evaluation_context: EvaluationContextV1,
}

pub fn alert_evaluation_job_schema_version_v1() -> String {
    "alert_evaluation_job_v1".to_string()
}

pub fn job_create_subject(trigger_type: TriggerTypeV1, priority: JobPriorityV1) -> String {
    format!(
        "alerts.jobs.create.{}.{}",
        trigger_type_to_str(trigger_type),
        job_priority_to_str(priority)
    )
}

fn trigger_type_to_str(t: TriggerTypeV1) -> &'static str {
    match t {
        TriggerTypeV1::EventDriven => "event_driven",
        TriggerTypeV1::Periodic => "periodic",
        TriggerTypeV1::OneTime => "one_time",
    }
}

fn job_priority_to_str(p: JobPriorityV1) -> &'static str {
    match p {
        JobPriorityV1::Critical => "critical",
        JobPriorityV1::High => "high",
        JobPriorityV1::Normal => "normal",
        JobPriorityV1::Low => "low",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use pretty_assertions::assert_eq;

    #[test]
    fn test_job_subject() {
        assert_eq!(
            job_create_subject(TriggerTypeV1::EventDriven, JobPriorityV1::High),
            "alerts.jobs.create.event_driven.high"
        );
    }
}
