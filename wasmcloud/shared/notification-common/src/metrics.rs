//! Metrics collection and monitoring for notification providers
//!
//! This module provides standardized metrics collection for monitoring
//! notification provider performance and health.

use crate::payloads::DeliveryStatus;
use crate::provider::LegacyProviderError as ProviderError;
use crate::{NotificationChannel, NotificationPriority};
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Arc,
};

/// Comprehensive metrics collector for notification providers
#[derive(Debug)]
pub struct MetricsCollector {
    channel: NotificationChannel,

    // Counters (atomic for thread safety)
    total_sent: AtomicU64,
    successful_deliveries: AtomicU64,
    failed_deliveries: AtomicU64,
    channel_disabled_count: AtomicU64,
    rate_limited_count: AtomicU64,
    quiet_hours_count: AtomicU64,

    // Timing metrics
    total_latency_ms: parking_lot::Mutex<f64>,
    min_latency_ms: parking_lot::Mutex<f64>,
    max_latency_ms: parking_lot::Mutex<f64>,

    // Per-priority metrics
    priority_metrics: DashMap<NotificationPriority, PriorityMetrics>,

    // Error tracking
    error_counts: DashMap<String, AtomicU64>,

    // Time-based metrics
    start_time: DateTime<Utc>,
    last_activity: parking_lot::RwLock<DateTime<Utc>>,

    // Health status
    consecutive_failures: AtomicU64,
    last_health_check: parking_lot::RwLock<DateTime<Utc>>,
    healthy: parking_lot::RwLock<bool>,
}

/// Per-priority metrics breakdown
#[derive(Debug)]
struct PriorityMetrics {
    sent: AtomicU64,
    successful: AtomicU64,
    failed: AtomicU64,
    avg_latency_ms: parking_lot::Mutex<f64>,
}

impl Default for PriorityMetrics {
    fn default() -> Self {
        Self {
            sent: AtomicU64::new(0),
            successful: AtomicU64::new(0),
            failed: AtomicU64::new(0),
            avg_latency_ms: parking_lot::Mutex::new(0.0),
        }
    }
}

/// Aggregated metrics snapshot for reporting
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricsSnapshot {
    pub channel: NotificationChannel,
    pub timestamp: DateTime<Utc>,
    pub uptime_seconds: i64,

    // Delivery metrics
    pub total_sent: u64,
    pub successful_deliveries: u64,
    pub failed_deliveries: u64,
    pub success_rate_percent: f64,
    pub error_rate_percent: f64,

    // Latency metrics
    pub average_latency_ms: f64,
    pub min_latency_ms: f64,
    pub max_latency_ms: f64,

    // Status counts
    pub channel_disabled_count: u64,
    pub rate_limited_count: u64,
    pub quiet_hours_count: u64,

    // Per-priority breakdown
    pub priority_breakdown: std::collections::HashMap<NotificationPriority, PrioritySnapshot>,

    // Error breakdown
    pub error_counts: std::collections::HashMap<String, u64>,

    // Health status
    pub healthy: bool,
    pub consecutive_failures: u64,
    pub last_activity: DateTime<Utc>,
    pub last_health_check: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrioritySnapshot {
    pub sent: u64,
    pub successful: u64,
    pub failed: u64,
    pub success_rate_percent: f64,
    pub avg_latency_ms: f64,
}

impl MetricsCollector {
    /// Create a new metrics collector for a specific channel
    pub fn new(channel: NotificationChannel) -> Self {
        let now = Utc::now();

        Self {
            channel,
            total_sent: AtomicU64::new(0),
            successful_deliveries: AtomicU64::new(0),
            failed_deliveries: AtomicU64::new(0),
            channel_disabled_count: AtomicU64::new(0),
            rate_limited_count: AtomicU64::new(0),
            quiet_hours_count: AtomicU64::new(0),
            total_latency_ms: parking_lot::Mutex::new(0.0),
            min_latency_ms: parking_lot::Mutex::new(f64::MAX),
            max_latency_ms: parking_lot::Mutex::new(0.0),
            priority_metrics: DashMap::new(),
            error_counts: DashMap::new(),
            start_time: now,
            last_activity: parking_lot::RwLock::new(now),
            consecutive_failures: AtomicU64::new(0),
            last_health_check: parking_lot::RwLock::new(now),
            healthy: parking_lot::RwLock::new(true),
        }
    }

    /// Record a delivery attempt with its result
    pub fn record_delivery(
        &self,
        status: &DeliveryStatus,
        priority: NotificationPriority,
        latency_ms: f64,
    ) {
        self.total_sent.fetch_add(1, Ordering::Relaxed);
        *self.last_activity.write() = Utc::now();

        // Update latency metrics
        self.update_latency_metrics(latency_ms);

        // Get or create priority metrics
        let priority_entry = self
            .priority_metrics
            .entry(priority)
            .or_insert_with(Default::default);
        priority_entry.sent.fetch_add(1, Ordering::Relaxed);

        // For now, treat all DeliveryStatus as either success or failure
        // This is a simplified implementation since DeliveryStatus is just a struct
        if status.delivered {
            self.successful_deliveries.fetch_add(1, Ordering::Relaxed);
            priority_entry.successful.fetch_add(1, Ordering::Relaxed);
            self.update_priority_latency(&priority_entry, latency_ms);
            self.consecutive_failures.store(0, Ordering::Relaxed);
        } else {
            self.failed_deliveries.fetch_add(1, Ordering::Relaxed);
            priority_entry.failed.fetch_add(1, Ordering::Relaxed);
            self.consecutive_failures.fetch_add(1, Ordering::Relaxed);

            // Track error types - extract error code from message if possible
            if let Some(error_msg) = &status.error_message {
                // Simple error code extraction - look for uppercase words or use full message
                let error_key = if error_msg.contains("SMTP") {
                    "SMTP_ERROR".to_string()
                } else if error_msg.contains("RATE_LIMIT") {
                    "RATE_LIMIT".to_string()
                } else if error_msg.contains("TIMEOUT") {
                    "TIMEOUT".to_string()
                } else {
                    error_msg.clone()
                };
                let error_entry = self
                    .error_counts
                    .entry(error_key)
                    .or_insert_with(|| AtomicU64::new(0));
                error_entry.fetch_add(1, Ordering::Relaxed);
            }
        }
    }

    /// Record a provider error
    pub fn record_error(&self, error: &ProviderError) {
        self.consecutive_failures.fetch_add(1, Ordering::Relaxed);

        let error_key = error.error_code().to_string();
        let error_entry = self
            .error_counts
            .entry(error_key)
            .or_insert_with(|| AtomicU64::new(0));
        error_entry.fetch_add(1, Ordering::Relaxed);

        // Mark as unhealthy for critical errors
        if !error.is_retryable() {
            self.mark_unhealthy();
        }
    }

    /// Update health status
    pub fn record_health_check(&self, healthy: bool) {
        *self.healthy.write() = healthy;
        *self.last_health_check.write() = Utc::now();

        if healthy {
            self.consecutive_failures.store(0, Ordering::Relaxed);
        } else {
            self.consecutive_failures.fetch_add(1, Ordering::Relaxed);
        }
    }

    /// Mark provider as unhealthy
    pub fn mark_unhealthy(&self) {
        *self.healthy.write() = false;
    }

    /// Get current metrics snapshot
    pub fn get_snapshot(&self) -> MetricsSnapshot {
        let now = Utc::now();
        let total_sent = self.total_sent.load(Ordering::Relaxed);
        let successful = self.successful_deliveries.load(Ordering::Relaxed);
        let failed = self.failed_deliveries.load(Ordering::Relaxed);

        let success_rate = if total_sent > 0 {
            (successful as f64 / total_sent as f64) * 100.0
        } else {
            0.0
        };

        let error_rate = if total_sent > 0 {
            (failed as f64 / total_sent as f64) * 100.0
        } else {
            0.0
        };

        let avg_latency = if successful > 0 {
            *self.total_latency_ms.lock() / successful as f64
        } else {
            0.0
        };

        let min_latency = *self.min_latency_ms.lock();
        let min_latency = if min_latency == f64::MAX {
            0.0
        } else {
            min_latency
        };

        // Collect priority breakdown
        let mut priority_breakdown = std::collections::HashMap::new();
        for entry in self.priority_metrics.iter() {
            let priority = entry.key().clone();
            let metrics = entry.value();

            let priority_sent = metrics.sent.load(Ordering::Relaxed);
            let priority_successful = metrics.successful.load(Ordering::Relaxed);
            let priority_failed = metrics.failed.load(Ordering::Relaxed);

            let priority_success_rate = if priority_sent > 0 {
                (priority_successful as f64 / priority_sent as f64) * 100.0
            } else {
                0.0
            };

            priority_breakdown.insert(
                priority,
                PrioritySnapshot {
                    sent: priority_sent,
                    successful: priority_successful,
                    failed: priority_failed,
                    success_rate_percent: priority_success_rate,
                    avg_latency_ms: *metrics.avg_latency_ms.lock(),
                },
            );
        }

        // Collect error counts
        let mut error_counts = std::collections::HashMap::new();
        for entry in self.error_counts.iter() {
            error_counts.insert(entry.key().clone(), entry.value().load(Ordering::Relaxed));
        }

        MetricsSnapshot {
            channel: self.channel.clone(),
            timestamp: now,
            uptime_seconds: (now - self.start_time).num_seconds(),
            total_sent,
            successful_deliveries: successful,
            failed_deliveries: failed,
            success_rate_percent: success_rate,
            error_rate_percent: error_rate,
            average_latency_ms: avg_latency,
            min_latency_ms: min_latency,
            max_latency_ms: *self.max_latency_ms.lock(),
            channel_disabled_count: self.channel_disabled_count.load(Ordering::Relaxed),
            rate_limited_count: self.rate_limited_count.load(Ordering::Relaxed),
            quiet_hours_count: self.quiet_hours_count.load(Ordering::Relaxed),
            priority_breakdown,
            error_counts,
            healthy: *self.healthy.read(),
            consecutive_failures: self.consecutive_failures.load(Ordering::Relaxed),
            last_activity: *self.last_activity.read(),
            last_health_check: *self.last_health_check.read(),
        }
    }

    /// Get success rate over the last N minutes
    pub fn get_recent_success_rate(&self, _window_minutes: u32) -> f64 {
        // For now, return overall success rate
        // TODO: Implement time-windowed metrics
        let total = self.total_sent.load(Ordering::Relaxed);
        let successful = self.successful_deliveries.load(Ordering::Relaxed);

        if total > 0 {
            (successful as f64 / total as f64) * 100.0
        } else {
            100.0 // No data means we assume healthy
        }
    }

    /// Check if provider should be considered healthy based on metrics
    pub fn is_healthy_by_metrics(&self) -> bool {
        let consecutive_failures = self.consecutive_failures.load(Ordering::Relaxed);
        let health_status = *self.healthy.read();

        // Consider unhealthy if:
        // - Explicitly marked unhealthy
        // - More than 10 consecutive failures
        // - No activity in the last hour (if we've sent messages before)

        if !health_status || consecutive_failures > 10 {
            return false;
        }

        let last_activity = *self.last_activity.read();
        let total_sent = self.total_sent.load(Ordering::Relaxed);

        // If we've sent messages and haven't had activity in an hour, mark unhealthy
        if total_sent > 0 && (Utc::now() - last_activity) > chrono::Duration::hours(1) {
            return false;
        }

        true
    }

    /// Reset all metrics (useful for testing)
    pub fn reset(&self) {
        self.total_sent.store(0, Ordering::Relaxed);
        self.successful_deliveries.store(0, Ordering::Relaxed);
        self.failed_deliveries.store(0, Ordering::Relaxed);
        self.channel_disabled_count.store(0, Ordering::Relaxed);
        self.rate_limited_count.store(0, Ordering::Relaxed);
        self.quiet_hours_count.store(0, Ordering::Relaxed);
        *self.total_latency_ms.lock() = 0.0;
        *self.min_latency_ms.lock() = f64::MAX;
        *self.max_latency_ms.lock() = 0.0;
        self.priority_metrics.clear();
        self.error_counts.clear();
        self.consecutive_failures.store(0, Ordering::Relaxed);
        *self.healthy.write() = true;

        let now = Utc::now();
        *self.last_activity.write() = now;
        *self.last_health_check.write() = now;
    }

    /// Update latency metrics
    fn update_latency_metrics(&self, latency_ms: f64) {
        *self.total_latency_ms.lock() += latency_ms;

        // Update min latency
        {
            let mut min_latency = self.min_latency_ms.lock();
            if latency_ms < *min_latency {
                *min_latency = latency_ms;
            }
        }

        // Update max latency
        {
            let mut max_latency = self.max_latency_ms.lock();
            if latency_ms > *max_latency {
                *max_latency = latency_ms;
            }
        }
    }

    /// Update priority-specific latency
    fn update_priority_latency(&self, priority_metrics: &PriorityMetrics, latency_ms: f64) {
        // Simple running average for now
        let mut avg_latency = priority_metrics.avg_latency_ms.lock();
        let successful_count = priority_metrics.successful.load(Ordering::Relaxed);

        if successful_count == 1 {
            *avg_latency = latency_ms;
        } else {
            let new_avg = (*avg_latency * ((successful_count - 1) as f64) + latency_ms)
                / (successful_count as f64);
            *avg_latency = new_avg;
        }
    }
}

/// Global metrics registry for all providers
#[derive(Debug)]
pub struct MetricsRegistry {
    collectors: DashMap<NotificationChannel, Arc<MetricsCollector>>,
}

impl MetricsRegistry {
    pub fn new() -> Self {
        Self {
            collectors: DashMap::new(),
        }
    }

    /// Get or create metrics collector for a channel
    pub fn get_collector(&self, channel: NotificationChannel) -> Arc<MetricsCollector> {
        self.collectors
            .entry(channel.clone())
            .or_insert_with(|| Arc::new(MetricsCollector::new(channel)))
            .clone()
    }

    /// Get snapshots for all registered channels
    pub fn get_all_snapshots(&self) -> Vec<MetricsSnapshot> {
        self.collectors
            .iter()
            .map(|entry| entry.value().get_snapshot())
            .collect()
    }

    /// Check overall system health
    pub fn is_system_healthy(&self) -> bool {
        if self.collectors.is_empty() {
            return true; // No providers means no problems
        }

        self.collectors
            .iter()
            .all(|entry| entry.value().is_healthy_by_metrics())
    }

    /// Get aggregated system metrics
    pub fn get_system_summary(&self) -> SystemMetricsSummary {
        let snapshots = self.get_all_snapshots();

        let total_sent: u64 = snapshots.iter().map(|s| s.total_sent).sum();
        let total_successful: u64 = snapshots.iter().map(|s| s.successful_deliveries).sum();
        let total_failed: u64 = snapshots.iter().map(|s| s.failed_deliveries).sum();

        let overall_success_rate = if total_sent > 0 {
            (total_successful as f64 / total_sent as f64) * 100.0
        } else {
            100.0
        };

        let healthy_providers = snapshots.iter().filter(|s| s.healthy).count();
        let total_providers = snapshots.len();

        SystemMetricsSummary {
            timestamp: Utc::now(),
            total_providers,
            healthy_providers,
            total_notifications_sent: total_sent,
            overall_success_rate,
            channel_summaries: snapshots
                .into_iter()
                .map(|s| (s.channel.clone(), s))
                .collect(),
        }
    }
}

impl Default for MetricsRegistry {
    fn default() -> Self {
        Self::new()
    }
}

/// System-wide metrics summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemMetricsSummary {
    pub timestamp: DateTime<Utc>,
    pub total_providers: usize,
    pub healthy_providers: usize,
    pub total_notifications_sent: u64,
    pub overall_success_rate: f64,
    pub channel_summaries: std::collections::HashMap<NotificationChannel, MetricsSnapshot>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{DeliveryStatus, NotificationChannel, NotificationPriority};
    use uuid::Uuid;

    #[test]
    fn test_metrics_collector_basic_operations() {
        let collector = MetricsCollector::new(NotificationChannel::Email);

        // Record successful delivery
        let success_status = DeliveryStatus {
            notification_id: Uuid::new_v4(),
            channel: NotificationChannel::Email,
            delivered: true,
            delivered_at: Some(Utc::now()),
            error_message: None,
            provider_message_id: Some("msg-123".to_string()),
            retry_count: 0,
        };

        collector.record_delivery(&success_status, NotificationPriority::High, 150.0);

        let snapshot = collector.get_snapshot();
        assert_eq!(snapshot.total_sent, 1);
        assert_eq!(snapshot.successful_deliveries, 1);
        assert_eq!(snapshot.failed_deliveries, 0);
        assert_eq!(snapshot.success_rate_percent, 100.0);
        assert_eq!(snapshot.average_latency_ms, 150.0);

        // Record failed delivery
        let failed_status = DeliveryStatus {
            notification_id: Uuid::new_v4(),
            channel: NotificationChannel::Email,
            delivered: false,
            delivered_at: None,
            error_message: Some("SMTP server unavailable".to_string()),
            provider_message_id: None,
            retry_count: 1,
        };

        collector.record_delivery(&failed_status, NotificationPriority::Normal, 50.0);

        let snapshot = collector.get_snapshot();
        assert_eq!(snapshot.total_sent, 2);
        assert_eq!(snapshot.successful_deliveries, 1);
        assert_eq!(snapshot.failed_deliveries, 1);
        assert_eq!(snapshot.success_rate_percent, 50.0);
        assert!(snapshot.error_counts.contains_key("SMTP_ERROR"));
        assert_eq!(snapshot.error_counts["SMTP_ERROR"], 1);
    }

    #[test]
    fn test_metrics_registry() {
        let registry = MetricsRegistry::new();

        let email_collector = registry.get_collector(NotificationChannel::Email);
        let slack_collector = registry.get_collector(NotificationChannel::Slack);

        // Record some metrics
        let success_status = DeliveryStatus {
            notification_id: Uuid::new_v4(),
            channel: NotificationChannel::Email,
            delivered: true,
            delivered_at: Some(Utc::now()),
            error_message: None,
            provider_message_id: Some("msg-123".to_string()),
            retry_count: 0,
        };

        email_collector.record_delivery(&success_status, NotificationPriority::High, 100.0);
        slack_collector.record_delivery(&success_status, NotificationPriority::Normal, 200.0);

        let summary = registry.get_system_summary();
        assert_eq!(summary.total_providers, 2);
        assert_eq!(summary.healthy_providers, 2);
        assert_eq!(summary.total_notifications_sent, 2);
        assert_eq!(summary.overall_success_rate, 100.0);
    }

    #[test]
    fn test_priority_breakdown() {
        let collector = MetricsCollector::new(NotificationChannel::Slack);

        let success_status = DeliveryStatus {
            notification_id: Uuid::new_v4(),
            channel: NotificationChannel::Slack,
            delivered: true,
            delivered_at: Some(Utc::now()),
            error_message: None,
            provider_message_id: Some("msg-123".to_string()),
            retry_count: 0,
        };

        // Record deliveries for different priorities
        collector.record_delivery(&success_status, NotificationPriority::Critical, 50.0);
        collector.record_delivery(&success_status, NotificationPriority::High, 100.0);
        collector.record_delivery(&success_status, NotificationPriority::High, 200.0);

        let snapshot = collector.get_snapshot();

        let critical_metrics = &snapshot.priority_breakdown[&NotificationPriority::Critical];
        assert_eq!(critical_metrics.sent, 1);
        assert_eq!(critical_metrics.successful, 1);
        assert_eq!(critical_metrics.avg_latency_ms, 50.0);

        let high_metrics = &snapshot.priority_breakdown[&NotificationPriority::High];
        assert_eq!(high_metrics.sent, 2);
        assert_eq!(high_metrics.successful, 2);
        assert_eq!(high_metrics.avg_latency_ms, 150.0); // (100 + 200) / 2
    }
}
