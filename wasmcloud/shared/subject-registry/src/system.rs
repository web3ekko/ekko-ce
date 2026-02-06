//! System Subject Patterns
//!
//! Subject hierarchy for system health and status:
//! ```text
//! system.health                             # Health check requests
//! system.status.{component}                 # Component status updates
//! ```

/// System health subject
pub fn health() -> &'static str {
    "system.health"
}

/// Component status subject
///
/// Example: `system.status.alerts-processor`
pub fn status(component: &str) -> String {
    format!("system.status.{}", component)
}

/// Subscription patterns

/// Pattern for all system subjects
pub fn pattern_system_all() -> &'static str {
    "system.>"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_health() {
        assert_eq!(health(), "system.health");
    }

    #[test]
    fn test_status() {
        assert_eq!(status("alerts-processor"), "system.status.alerts-processor");
    }
}
