use crate::nats_client::AlertSchedulerPublisher;
use crate::runtime_store::RuntimeStoreOps;
use crate::{AlertSchedulerConfig, AlertSchedulerError, Result};
use alert_runtime_common::{
    alert_schedule_one_time_schema_version_v1, alert_schedule_periodic_schema_version_v1,
    AlertScheduleOneTimeV1, AlertSchedulePeriodicV1,
};
use chrono::{DateTime, TimeZone, Utc};
use cron::Schedule;
use std::str::FromStr;
use std::sync::Arc;
use tokio::time::Duration;
use tracing::{debug, warn};
use uuid::Uuid;

const PERIODIC_ZSET: &str = "alerts:schedule:periodic";
const ONE_TIME_ZSET: &str = "alerts:schedule:one_time";

const ONE_TIME_FIRED_PREFIX: &str = "alerts:one_time:fired:";

pub struct ScheduleScanner {
    config: AlertSchedulerConfig,
    store: Arc<dyn RuntimeStoreOps>,
    nats: Arc<dyn AlertSchedulerPublisher>,
    scan_cursor: u64,
}

impl ScheduleScanner {
    pub fn new(
        config: AlertSchedulerConfig,
        store: Arc<dyn RuntimeStoreOps>,
        nats: Arc<dyn AlertSchedulerPublisher>,
    ) -> Self {
        Self {
            config,
            store,
            nats,
            scan_cursor: 0,
        }
    }

    pub async fn run_loop(mut self, interval: Duration) {
        let mut ticker = tokio::time::interval(interval);
        loop {
            ticker.tick().await;

            if let Err(err) = self.refresh_schedule_indices().await {
                warn!("schedule index refresh failed: {}", err);
            }
            if let Err(err) = self.publish_due_one_time().await {
                warn!("one_time scan failed: {}", err);
            }
            if let Err(err) = self.publish_due_periodic().await {
                warn!("periodic scan failed: {}", err);
            }
        }
    }

    async fn refresh_schedule_indices(&mut self) -> Result<()> {
        let (next_cursor, keys) = self
            .store
            .scan_instance_keys(self.scan_cursor, self.config.instance_scan_batch_size)
            .await?;
        self.scan_cursor = next_cursor;

        if keys.is_empty() {
            return Ok(());
        }

        let now = Utc::now();
        for key in keys {
            let Some(instance_id) = key.strip_prefix("alerts:instance:") else {
                continue;
            };
            let instance = match self.store.get_instance(instance_id).await {
                Ok(inst) => inst,
                Err(_) => continue,
            };
            if !instance.enabled {
                let _ = self.store.zrem(PERIODIC_ZSET, &instance.instance_id).await;
                let _ = self.store.zrem(ONE_TIME_ZSET, &instance.instance_id).await;
                continue;
            }

            match instance.trigger_type.as_str() {
                "periodic" => {
                    if self
                        .store
                        .zscore(PERIODIC_ZSET, &instance.instance_id)
                        .await?
                        .is_some()
                    {
                        continue;
                    }
                    match next_cron_tick(&instance.trigger_config, now) {
                        Ok(Some(next)) => {
                            self.store
                                .zadd_nx(PERIODIC_ZSET, &instance.instance_id, next.timestamp())
                                .await?;
                        }
                        Ok(None) => {}
                        Err(e) => {
                            // Bad cron data should not break scanning for every other instance.
                            warn!(
                                "skipping periodic instance {} due to invalid trigger_config: {}",
                                instance.instance_id, e
                            );
                            let _ = self.store.zrem(PERIODIC_ZSET, &instance.instance_id).await;
                        }
                    }
                }
                "one_time" => {
                    if self
                        .store
                        .exists(&format!(
                            "{}{}",
                            ONE_TIME_FIRED_PREFIX, instance.instance_id
                        ))
                        .await?
                    {
                        let _ = self.store.zrem(ONE_TIME_ZSET, &instance.instance_id).await;
                        continue;
                    }
                    if self
                        .store
                        .zscore(ONE_TIME_ZSET, &instance.instance_id)
                        .await?
                        .is_some()
                    {
                        continue;
                    }
                    if let Some(run_at) = parse_one_time_run_at(&instance.trigger_config)? {
                        self.store
                            .zadd_nx(ONE_TIME_ZSET, &instance.instance_id, run_at.timestamp())
                            .await?;
                    }
                }
                _ => {
                    // Not a scheduled instance
                }
            }
        }

        Ok(())
    }

    async fn publish_due_one_time(&self) -> Result<()> {
        let now_ts = Utc::now().timestamp();
        let due = self
            .store
            .zrangebyscore_withscores(
                ONE_TIME_ZSET,
                now_ts,
                self.config.schedule_due_batch_size as usize,
            )
            .await?;
        if due.is_empty() {
            return Ok(());
        }

        for (instance_id, scheduled_for_ts) in due {
            let scheduled_for =
                Utc.timestamp_opt(scheduled_for_ts, 0)
                    .single()
                    .ok_or_else(|| {
                        AlertSchedulerError::InvalidAlertData(format!(
                            "invalid scheduled_for timestamp: {}",
                            scheduled_for_ts
                        ))
                    })?;

            // Publish first (at-least-once), then advance/remove indices.
            let request_id = schedule_request_id("one_time", &instance_id, scheduled_for);
            let msg = AlertScheduleOneTimeV1 {
                schema_version: alert_schedule_one_time_schema_version_v1(),
                request_id: request_id.to_string(),
                instance_id: instance_id.clone(),
                scheduled_for,
                requested_at: Utc::now(),
                source: "job_scheduler_scan".to_string(),
            };
            let bytes = serde_json::to_vec(&msg)?;
            self.nats
                .publish_schedule_request_bytes(
                    "alerts.schedule.one_time",
                    &request_id.to_string(),
                    bytes,
                )
                .await?;

            // Remove from schedule set (best-effort). The handler sets the fired marker.
            let _ = self.store.zrem(ONE_TIME_ZSET, &instance_id).await;
        }

        Ok(())
    }

    async fn publish_due_periodic(&self) -> Result<()> {
        let now = Utc::now();
        let now_ts = now.timestamp();

        let due = self
            .store
            .zrangebyscore_withscores(
                PERIODIC_ZSET,
                now_ts,
                self.config.schedule_due_batch_size as usize,
            )
            .await?;
        if due.is_empty() {
            return Ok(());
        }

        for (instance_id, scheduled_for_ts) in due {
            let scheduled_for =
                Utc.timestamp_opt(scheduled_for_ts, 0)
                    .single()
                    .ok_or_else(|| {
                        AlertSchedulerError::InvalidAlertData(format!(
                            "invalid scheduled_for timestamp: {}",
                            scheduled_for_ts
                        ))
                    })?;

            let instance = match self.store.get_instance(&instance_id).await {
                Ok(inst) => inst,
                Err(e) => {
                    warn!(
                        "missing instance {} for periodic schedule: {}",
                        instance_id, e
                    );
                    let _ = self.store.zrem(PERIODIC_ZSET, &instance_id).await;
                    continue;
                }
            };
            if !instance.enabled || instance.trigger_type != "periodic" {
                let _ = self.store.zrem(PERIODIC_ZSET, &instance_id).await;
                continue;
            }

            let mut tick = scheduled_for;
            loop {
                if tick > now {
                    break;
                }

                let request_id = schedule_request_id("periodic", &instance_id, tick);
                let msg = AlertSchedulePeriodicV1 {
                    schema_version: alert_schedule_periodic_schema_version_v1(),
                    request_id: request_id.to_string(),
                    instance_id: instance_id.clone(),
                    scheduled_for: tick,
                    requested_at: Utc::now(),
                    source: "job_scheduler_scan".to_string(),
                };
                let bytes = serde_json::to_vec(&msg)?;
                self.nats
                    .publish_schedule_request_bytes(
                        "alerts.schedule.periodic",
                        &request_id.to_string(),
                        bytes,
                    )
                    .await?;

                let next = match next_cron_tick_after(&instance.trigger_config, tick) {
                    Ok(Some(next)) => next,
                    Ok(None) => {
                        warn!(
                            "no next tick for periodic instance {}, removing from schedule",
                            instance_id
                        );
                        let _ = self.store.zrem(PERIODIC_ZSET, &instance_id).await;
                        break;
                    }
                    Err(e) => {
                        warn!(
                            "invalid cron for periodic instance {}, removing from schedule: {}",
                            instance_id, e
                        );
                        let _ = self.store.zrem(PERIODIC_ZSET, &instance_id).await;
                        break;
                    }
                };

                // Publish first, then advance index. If we crash between, downstream dedupe handles it.
                self.store
                    .zadd_xx(PERIODIC_ZSET, &instance_id, next.timestamp())
                    .await?;
                tick = next;
            }
        }

        Ok(())
    }
}

fn schedule_request_id(
    trigger_type: &str,
    instance_id: &str,
    scheduled_for: DateTime<Utc>,
) -> Uuid {
    let input = format!(
        "{}:{}:{}",
        trigger_type,
        instance_id,
        scheduled_for.to_rfc3339()
    );
    Uuid::new_v5(&Uuid::NAMESPACE_URL, input.as_bytes())
}

fn parse_cron_expr(trigger_config: &serde_json::Value) -> Result<String> {
    if let Some(cron) = trigger_config.get("cron").and_then(|v| v.as_str()) {
        let cron = cron.trim();
        if !cron.is_empty() {
            return Ok(cron.to_string());
        }
    }
    if let Some(cron) = trigger_config
        .get("cron_expression")
        .and_then(|v| v.as_str())
    {
        let cron = cron.trim();
        if !cron.is_empty() {
            return Ok(cron.to_string());
        }
    }
    Err(AlertSchedulerError::InvalidAlertData(
        "missing cron expression".to_string(),
    ))
}

fn next_cron_tick(
    trigger_config: &serde_json::Value,
    now: DateTime<Utc>,
) -> Result<Option<DateTime<Utc>>> {
    let cron_expr = parse_cron_expr(trigger_config)?;
    let schedule = Schedule::from_str(&cron_expr).map_err(|e| {
        AlertSchedulerError::InvalidAlertData(format!("invalid cron '{}': {}", cron_expr, e))
    })?;
    Ok(schedule
        .after(&now)
        .next()
        .map(|dt| dt.with_timezone(&Utc))
        .or_else(|| {
            debug!("no upcoming ticks for cron {}", cron_expr);
            None
        }))
}

fn next_cron_tick_after(
    trigger_config: &serde_json::Value,
    after: DateTime<Utc>,
) -> Result<Option<DateTime<Utc>>> {
    let cron_expr = parse_cron_expr(trigger_config)?;
    let schedule = Schedule::from_str(&cron_expr).map_err(|e| {
        AlertSchedulerError::InvalidAlertData(format!("invalid cron '{}': {}", cron_expr, e))
    })?;
    Ok(schedule
        .after(&after)
        .next()
        .map(|dt| dt.with_timezone(&Utc)))
}

fn parse_one_time_run_at(trigger_config: &serde_json::Value) -> Result<Option<DateTime<Utc>>> {
    let Some(run_at) = trigger_config.get("run_at").and_then(|v| v.as_str()) else {
        return Ok(None);
    };
    let dt = DateTime::parse_from_rfc3339(run_at)
        .map_err(|e| {
            AlertSchedulerError::InvalidAlertData(format!("invalid run_at '{}': {}", run_at, e))
        })?
        .with_timezone(&Utc);
    Ok(Some(dt))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::nats_client::AlertSchedulerPublisher;
    use crate::runtime_store::{InstanceSnapshot, RuntimeStoreOps, TargetSelectorSnapshot};
    use alert_runtime_common::AlertEvaluationJobV1;
    use async_trait::async_trait;
    use serde_json::json;
    use std::collections::{BTreeMap, HashMap};
    use tokio::sync::Mutex;

    #[derive(Default)]
    struct TestState {
        instances: HashMap<String, InstanceSnapshot>,
        zsets: HashMap<String, BTreeMap<String, i64>>,
        strings: HashMap<String, String>,
    }

    #[derive(Clone, Default)]
    struct TestStore {
        state: Arc<Mutex<TestState>>,
    }

    #[async_trait]
    impl RuntimeStoreOps for TestStore {
        async fn get_instance(&self, instance_id: &str) -> Result<InstanceSnapshot> {
            let guard = self.state.lock().await;
            guard
                .instances
                .get(instance_id)
                .cloned()
                .ok_or_else(|| AlertSchedulerError::AlertNotFound(instance_id.to_string()))
        }

        async fn get_template(
            &self,
            _template_id: &str,
            _template_version: i64,
        ) -> Result<alert_runtime_common::AlertTemplateV1> {
            Err(AlertSchedulerError::InvalidAlertData(
                "not used in schedule_scanner tests".to_string(),
            ))
        }

        async fn get_executable(
            &self,
            _template_id: &str,
            _template_version: i64,
        ) -> Result<alert_runtime_common::AlertExecutableV1> {
            Err(AlertSchedulerError::InvalidAlertData(
                "not used in schedule_scanner tests".to_string(),
            ))
        }

        async fn scan_instance_keys(
            &self,
            _cursor: u64,
            _count: u32,
        ) -> Result<(u64, Vec<String>)> {
            let guard = self.state.lock().await;
            let keys = guard
                .instances
                .keys()
                .map(|id| format!("alerts:instance:{}", id))
                .collect();
            Ok((0, keys))
        }

        async fn zrangebyscore_withscores(
            &self,
            key: &str,
            max_score: i64,
            limit: usize,
        ) -> Result<Vec<(String, i64)>> {
            let guard = self.state.lock().await;
            let mut items: Vec<(String, i64)> = guard
                .zsets
                .get(key)
                .into_iter()
                .flat_map(|m| m.iter())
                .filter(|(_member, score)| **score <= max_score)
                .map(|(member, score)| (member.clone(), *score))
                .collect();
            items.sort_by_key(|(member, score)| (*score, member.clone()));
            items.truncate(limit);
            Ok(items)
        }

        async fn zadd_nx(&self, key: &str, member: &str, score: i64) -> Result<()> {
            let mut guard = self.state.lock().await;
            let z = guard.zsets.entry(key.to_string()).or_default();
            z.entry(member.to_string()).or_insert(score);
            Ok(())
        }

        async fn zadd_xx(&self, key: &str, member: &str, score: i64) -> Result<()> {
            let mut guard = self.state.lock().await;
            if let Some(z) = guard.zsets.get_mut(key) {
                if z.contains_key(member) {
                    z.insert(member.to_string(), score);
                }
            }
            Ok(())
        }

        async fn zrem(&self, key: &str, member: &str) -> Result<()> {
            let mut guard = self.state.lock().await;
            if let Some(z) = guard.zsets.get_mut(key) {
                z.remove(member);
            }
            Ok(())
        }

        async fn zscore(&self, key: &str, member: &str) -> Result<Option<i64>> {
            let guard = self.state.lock().await;
            Ok(guard.zsets.get(key).and_then(|z| z.get(member).copied()))
        }

        async fn smembers(&self, _key: &str) -> Result<Vec<String>> {
            Ok(vec![])
        }

        async fn set_nx_ex(&self, key: &str, value: &str, _ttl_secs: usize) -> Result<bool> {
            let mut guard = self.state.lock().await;
            if guard.strings.contains_key(key) {
                return Ok(false);
            }
            guard.strings.insert(key.to_string(), value.to_string());
            Ok(true)
        }

        async fn sscan(
            &self,
            _key: &str,
            _cursor: u64,
            _count: usize,
        ) -> Result<(u64, Vec<String>)> {
            Ok((0, vec![]))
        }

        async fn exists(&self, key: &str) -> Result<bool> {
            let guard = self.state.lock().await;
            Ok(guard.strings.contains_key(key))
        }
    }

    #[derive(Default)]
    struct TestPublisher {
        published: Arc<Mutex<Vec<(String, String, Vec<u8>)>>>,
    }

    #[async_trait]
    impl AlertSchedulerPublisher for TestPublisher {
        async fn publish_schedule_request_bytes(
            &self,
            subject: &str,
            msg_id: &str,
            payload: Vec<u8>,
        ) -> Result<()> {
            self.published
                .lock()
                .await
                .push((subject.to_string(), msg_id.to_string(), payload));
            Ok(())
        }

        async fn publish_evaluation_job(
            &self,
            _job: &AlertEvaluationJobV1,
            _priority: &alert_runtime_common::JobPriorityV1,
        ) -> Result<()> {
            Ok(())
        }
    }

    fn default_config() -> AlertSchedulerConfig {
        AlertSchedulerConfig {
            instance_scan_batch_size: 100,
            schedule_due_batch_size: 50,
            ..Default::default()
        }
    }

    #[tokio::test]
    async fn one_time_seed_and_publish_removes_from_zset() {
        let store = TestStore::default();
        let publisher = Arc::new(TestPublisher::default());

        let instance_id = "inst-1".to_string();
        store.state.lock().await.instances.insert(
            instance_id.clone(),
            InstanceSnapshot {
                instance_id: instance_id.clone(),
                user_id: json!("u1"),
                enabled: true,
                priority: "normal".to_string(),
                template_id: Some("tpl".to_string()),
                template_version: Some(1),
                trigger_type: "one_time".to_string(),
                trigger_config: json!({
                    "run_at": "2026-01-15T12:00:00Z"
                }),
                target_selector: TargetSelectorSnapshot {
                    mode: "keys".to_string(),
                    group_id: None,
                    keys: vec![],
                },
                variable_values: json!({}),
            },
        );

        let mut scanner =
            ScheduleScanner::new(default_config(), Arc::new(store.clone()), publisher.clone());
        scanner.refresh_schedule_indices().await.unwrap();

        let score = store.zscore(ONE_TIME_ZSET, &instance_id).await.unwrap();
        assert!(score.is_some());

        // Force due by setting score <= now
        store
            .zadd_xx(ONE_TIME_ZSET, &instance_id, Utc::now().timestamp() - 1)
            .await
            .unwrap();

        scanner.publish_due_one_time().await.unwrap();

        let after = store.zscore(ONE_TIME_ZSET, &instance_id).await.unwrap();
        assert!(after.is_none());

        let published = publisher.published.lock().await;
        assert_eq!(published.len(), 1);
        assert_eq!(published[0].0, "alerts.schedule.one_time");
    }

    #[tokio::test]
    async fn one_time_fired_marker_prevents_reseeding() {
        let store = TestStore::default();
        let publisher = Arc::new(TestPublisher::default());

        let instance_id = "inst-2".to_string();
        store.state.lock().await.instances.insert(
            instance_id.clone(),
            InstanceSnapshot {
                instance_id: instance_id.clone(),
                user_id: json!("u1"),
                enabled: true,
                priority: "normal".to_string(),
                template_id: Some("tpl".to_string()),
                template_version: Some(1),
                trigger_type: "one_time".to_string(),
                trigger_config: json!({
                    "run_at": "2026-01-15T12:00:00Z"
                }),
                target_selector: TargetSelectorSnapshot {
                    mode: "keys".to_string(),
                    group_id: None,
                    keys: vec![],
                },
                variable_values: json!({}),
            },
        );

        store
            .set_nx_ex(
                &format!("{}{}", ONE_TIME_FIRED_PREFIX, instance_id),
                "1",
                60,
            )
            .await
            .unwrap();

        let mut scanner =
            ScheduleScanner::new(default_config(), Arc::new(store.clone()), publisher);
        scanner.refresh_schedule_indices().await.unwrap();

        let score = store.zscore(ONE_TIME_ZSET, &instance_id).await.unwrap();
        assert!(score.is_none());
    }
}
