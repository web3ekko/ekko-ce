//! Alert Subject Patterns
//!
//! Subject hierarchy for alert job processing (from PRD-NATS-Task-Queue-System-USDT.md §B.2):
//! ```text
//! alerts.jobs.create.{trigger_type}.{priority}  # Job creation requests
//! alerts.jobs.result.{alert_instance_id}        # Job execution results
//! alerts.jobs.retry.{job_id}                    # Failed job retry requests
//! alerts.scheduler.scan.{trigger_type}          # Scheduler coordination
//! alerts.triggered.{user_id}                    # Alert trigger events
//! ```

/// Job creation subject - from scheduler to job queue
///
/// Example: `alerts.jobs.create.event_driven.critical`
pub fn job_create(trigger_type: &str, priority: &str) -> String {
    format!("alerts.jobs.create.{}.{}", trigger_type, priority)
}

/// Job result subject - execution results
///
/// Example: `alerts.jobs.result.uuid-12345`
pub fn job_result(alert_instance_id: &str) -> String {
    format!("alerts.jobs.result.{}", alert_instance_id)
}

/// Job retry subject - failed job retry requests
///
/// Example: `alerts.jobs.retry.job-uuid-12345`
pub fn job_retry(job_id: &str) -> String {
    format!("alerts.jobs.retry.{}", job_id)
}

/// Scheduler scan subject - coordination messages
///
/// Example: `alerts.scheduler.scan.periodic`
pub fn scheduler_scan(trigger_type: &str) -> String {
    format!("alerts.scheduler.scan.{}", trigger_type)
}

/// Alert triggered subject - for notification routing
///
/// Example: `alerts.triggered.user-uuid-12345`
pub fn triggered(user_id: &str) -> String {
    format!("alerts.triggered.{}", user_id)
}

/// Subscription patterns for handlers

/// Pattern for all job creation requests
pub fn pattern_jobs_create_all() -> &'static str {
    "alerts.jobs.create.>"
}

/// Pattern for all job results
pub fn pattern_jobs_result_all() -> &'static str {
    "alerts.jobs.result.>"
}

/// Pattern for all triggered alerts
pub fn pattern_triggered_all() -> &'static str {
    "alerts.triggered.>"
}

/// Pattern for all alerts subjects (use with caution)
pub fn pattern_alerts_all() -> &'static str {
    "alerts.>"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_job_create() {
        assert_eq!(
            job_create("event_driven", "critical"),
            "alerts.jobs.create.event_driven.critical"
        );
        assert_eq!(
            job_create("periodic", "normal"),
            "alerts.jobs.create.periodic.normal"
        );
    }

    #[test]
    fn test_job_result() {
        assert_eq!(job_result("uuid-12345"), "alerts.jobs.result.uuid-12345");
    }

    #[test]
    fn test_triggered() {
        assert_eq!(triggered("user-uuid-123"), "alerts.triggered.user-uuid-123");
    }
}
