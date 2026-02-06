use crate::nats_client::AlertSchedulerPublisher;
use crate::runtime_store::RuntimeStoreOps;
use crate::{AlertSchedulerConfig, AlertSchedulerError, Result};
use alert_runtime_common::{
    alert_evaluation_job_schema_version_v1, evaluation_context_schema_version_v1,
    AlertEvaluationJobV1, AlertExecutableV1, AlertScheduleEventDrivenV1, AlertScheduleOneTimeV1,
    AlertSchedulePeriodicV1, AlertTemplateV1, EvaluationContextInstanceV1, EvaluationContextRunV1,
    EvaluationContextV1, EvaluationTxV1, JobMetaV1, JobPriorityV1, PartitionV1, ScheduleV1,
    TargetModeV1, TargetsV1, TriggerTypeV1, TxKindV1,
};
use chrono::{DateTime, Utc};
use serde_json::Value;
use sha2::Digest;
use std::collections::{BTreeMap, HashMap, HashSet};
use std::sync::Arc;
use tracing::{debug, info, warn};
use uuid::Uuid;

const EVENT_IDX_TARGET_INSTANCES_PREFIX: &str = "alerts:event_idx:target_instances:";
const EVENT_IDX_TARGET_GROUPS_PREFIX: &str = "alerts:event_idx:target_groups:";
const EVENT_IDX_GROUP_INSTANCES_PREFIX: &str = "alerts:event_idx:group_instances:";

const GROUP_PARTITIONS_PREFIX: &str = "alerts:targets:group_partitions:";

const SCHEDULE_DEDUPE_PREFIX: &str = "alerts:schedule:dedupe:";
const ONE_TIME_FIRED_PREFIX: &str = "alerts:one_time:fired:";

pub struct ScheduleRequestHandler {
    config: AlertSchedulerConfig,
    store: Arc<dyn RuntimeStoreOps>,
    nats: Arc<dyn AlertSchedulerPublisher>,
}

impl ScheduleRequestHandler {
    pub fn new(
        config: AlertSchedulerConfig,
        store: Arc<dyn RuntimeStoreOps>,
        nats: Arc<dyn AlertSchedulerPublisher>,
    ) -> Self {
        Self {
            config,
            store,
            nats,
        }
    }

    pub async fn handle_periodic(&self, req: AlertSchedulePeriodicV1) -> Result<u64> {
        let done_key = format!("{}{}", SCHEDULE_DEDUPE_PREFIX, req.request_id);
        if self.store.exists(&done_key).await? {
            debug!("deduped periodic request {}", req.request_id);
            return Ok(0);
        }

        let published = self
            .create_scheduled_jobs(
                req.instance_id,
                TriggerTypeV1::Periodic,
                req.scheduled_for,
                req.request_id.clone(),
            )
            .await?;

        let _ = self
            .store
            .set_nx_ex(&done_key, "1", self.config.schedule_request_dedupe_ttl_secs)
            .await?;

        Ok(published)
    }

    pub async fn handle_one_time(&self, req: AlertScheduleOneTimeV1) -> Result<u64> {
        let done_key = format!("{}{}", SCHEDULE_DEDUPE_PREFIX, req.request_id);
        if self.store.exists(&done_key).await? {
            debug!("deduped one_time request {}", req.request_id);
            return Ok(0);
        }

        let fired_key = format!("{}{}", ONE_TIME_FIRED_PREFIX, req.instance_id);
        if self.store.exists(&fired_key).await? {
            let _ = self
                .store
                .set_nx_ex(&done_key, "1", self.config.schedule_request_dedupe_ttl_secs)
                .await?;
            debug!(
                "one_time instance already fired; request {}",
                req.request_id
            );
            return Ok(0);
        }

        let published = self
            .create_scheduled_jobs(
                req.instance_id.clone(),
                TriggerTypeV1::OneTime,
                req.scheduled_for,
                req.request_id.clone(),
            )
            .await?;

        // Mark the instance fired (best-effort) to short-circuit repeats.
        let _ = self
            .store
            .set_nx_ex(&fired_key, "1", 60 * 60 * 24 * 30)
            .await?;

        let _ = self
            .store
            .set_nx_ex(&done_key, "1", self.config.schedule_request_dedupe_ttl_secs)
            .await?;

        Ok(published)
    }

    pub async fn handle_event_driven(&self, req: AlertScheduleEventDrivenV1) -> Result<u64> {
        let run_id = event_run_id(&req)?;
        let partition = req.partition.clone();

        let instance_to_targets = self.route_event_instances(&req).await?;
        if instance_to_targets.is_empty() {
            return Ok(0);
        }

        let mut jobs_published = 0u64;
        for (instance_id, mut target_keys) in instance_to_targets {
            target_keys.sort();
            target_keys.dedup();

            let instance = match self.store.get_instance(&instance_id).await {
                Ok(inst) => inst,
                Err(_) => continue,
            };
            if !instance.enabled || instance.trigger_type != "event_driven" {
                continue;
            }
            if !instance_network_allows(&instance.trigger_config, &partition) {
                continue;
            }

            let (spec_id, spec_version) = instance_spec_ref(&instance)?;

            // Prefer pruning against the pinned executable (vNext). Fall back to v1 template pruning
            // if the executable is not present in Redis (e.g., stale cache).
            match self.store.get_executable(&spec_id, spec_version).await {
                Ok(executable) => {
                    if !trigger_prunes_executable(&executable, &req) {
                        continue;
                    }
                }
                Err(_) => {
                    let template = self.store.get_template(&spec_id, spec_version).await?;
                    if !trigger_prunes_template(&template, &req) {
                        continue;
                    }
                }
            }

            let priority = parse_priority(&instance.priority);
            let tx = schedule_event_to_eval_tx(&req)?;
            // For event-driven runs we still include a ScheduleV1 so datasources can bind `as_of`
            // deterministically (e.g., window queries) and so the EvaluationContext surface stays stable.
            let (data_lag_secs, effective_as_of) = schedule_effective_as_of_event_driven(
                &instance.trigger_config,
                tx.block_timestamp,
            )?;

            for chunk in target_keys.chunks(self.config.event_job_targets_cap as usize) {
                let job_id = job_id_v5(&run_id, &instance_id, chunk)?;
                let ctx = EvaluationContextV1 {
                    schema_version: evaluation_context_schema_version_v1(),
                    run: EvaluationContextRunV1 {
                        run_id: run_id.to_string(),
                        attempt: 1,
                        trigger_type: TriggerTypeV1::EventDriven,
                        enqueued_at: Utc::now(),
                        started_at: Utc::now(),
                    },
                    instance: EvaluationContextInstanceV1 {
                        instance_id: instance_id.clone(),
                        user_id: instance.user_id.clone(),
                        template_id: spec_id.clone(),
                        template_version: spec_version,
                    },
                    partition: partition.clone(),
                    schedule: Some(ScheduleV1 {
                        scheduled_for: tx.block_timestamp,
                        data_lag_secs,
                        effective_as_of,
                    }),
                    targets: TargetsV1 {
                        mode: TargetModeV1::Keys,
                        group_id: None,
                        keys: chunk.to_vec(),
                    },
                    variables: instance.variable_values.clone(),
                    tx: Some(tx.clone()),
                };

                let job = AlertEvaluationJobV1 {
                    schema_version: alert_evaluation_job_schema_version_v1(),
                    job: JobMetaV1 {
                        job_id: job_id.clone(),
                        priority: priority.clone(),
                        created_at: Utc::now(),
                    },
                    evaluation_context: ctx,
                };

                self.nats.publish_evaluation_job(&job, &priority).await?;
                jobs_published += 1;
            }
        }

        Ok(jobs_published)
    }

    async fn create_scheduled_jobs(
        &self,
        instance_id: String,
        trigger_type: TriggerTypeV1,
        scheduled_for: DateTime<Utc>,
        request_id: String,
    ) -> Result<u64> {
        let instance = self.store.get_instance(&instance_id).await?;
        if !instance.enabled {
            return Ok(0);
        }
        let priority = parse_priority(&instance.priority);
        let (data_lag_secs, effective_as_of) =
            schedule_effective_as_of(&instance.trigger_config, scheduled_for)?;

        let mut published = 0u64;

        match instance.target_selector.mode.as_str() {
            "keys" => {
                let partitions = partition_target_keys(&instance.target_selector.keys)?;
                for ((network, subnet), keys) in partitions {
                    published += self
                        .publish_scheduled_partition_jobs(
                            &instance,
                            trigger_type.clone(),
                            &priority,
                            &network,
                            &subnet,
                            keys,
                            scheduled_for,
                            data_lag_secs,
                            effective_as_of,
                            &request_id,
                            None,
                        )
                        .await?;
                }
            }
            "group" => {
                let group_id = instance.target_selector.group_id.clone().ok_or_else(|| {
                    AlertSchedulerError::InvalidAlertData("missing group_id".to_string())
                })?;

                let partitions_key = format!("{}{}", GROUP_PARTITIONS_PREFIX, group_id);
                let partition_set_keys = self.store.smembers(&partitions_key).await?;
                for partition_set_key in partition_set_keys {
                    let (network, subnet) = parse_group_partition_set_key(&partition_set_key)?;
                    published += self
                        .publish_scheduled_group_partition_jobs(
                            &instance,
                            trigger_type.clone(),
                            &priority,
                            &group_id,
                            &partition_set_key,
                            &network,
                            &subnet,
                            scheduled_for,
                            data_lag_secs,
                            effective_as_of,
                            &request_id,
                        )
                        .await?;
                }
            }
            other => {
                warn!("unknown target_selector.mode={} for {}", other, instance_id);
            }
        }

        info!(
            "created {} jobs for scheduled request {} instance {} ({:?})",
            published, request_id, instance_id, trigger_type
        );
        Ok(published)
    }

    async fn publish_scheduled_group_partition_jobs(
        &self,
        instance: &crate::runtime_store::InstanceSnapshot,
        trigger_type: TriggerTypeV1,
        priority: &JobPriorityV1,
        group_id: &str,
        partition_set_key: &str,
        network: &str,
        subnet: &str,
        scheduled_for: DateTime<Utc>,
        data_lag_secs: i64,
        effective_as_of: DateTime<Utc>,
        request_id: &str,
    ) -> Result<u64> {
        let mut cursor = 0u64;
        let mut batch: Vec<String> =
            Vec::with_capacity(self.config.microbatch_max_targets as usize);
        let mut published = 0u64;

        loop {
            let (next, members) = self
                .store
                .sscan(
                    partition_set_key,
                    cursor,
                    self.config.microbatch_max_targets as usize,
                )
                .await?;
            cursor = next;

            for member in members {
                batch.push(member);
                if batch.len() >= self.config.microbatch_max_targets as usize {
                    published += self
                        .publish_scheduled_partition_jobs(
                            instance,
                            trigger_type.clone(),
                            priority,
                            network,
                            subnet,
                            std::mem::take(&mut batch),
                            scheduled_for,
                            data_lag_secs,
                            effective_as_of,
                            request_id,
                            Some(group_id),
                        )
                        .await?;
                }
            }

            if cursor == 0 {
                break;
            }
        }

        if !batch.is_empty() {
            published += self
                .publish_scheduled_partition_jobs(
                    instance,
                    trigger_type,
                    priority,
                    network,
                    subnet,
                    batch,
                    scheduled_for,
                    data_lag_secs,
                    effective_as_of,
                    request_id,
                    Some(group_id),
                )
                .await?;
        }

        Ok(published)
    }

    async fn publish_scheduled_partition_jobs(
        &self,
        instance: &crate::runtime_store::InstanceSnapshot,
        trigger_type: TriggerTypeV1,
        priority: &JobPriorityV1,
        network: &str,
        subnet: &str,
        keys: Vec<String>,
        scheduled_for: DateTime<Utc>,
        data_lag_secs: i64,
        effective_as_of: DateTime<Utc>,
        request_id: &str,
        group_id: Option<&str>,
    ) -> Result<u64> {
        if keys.is_empty() {
            return Ok(0);
        }

        let (spec_id, spec_version) = instance_spec_ref(instance)?;

        let chain_id = chain_id_for_partition(network, subnet)?;
        let partition = PartitionV1 {
            network: network.to_string(),
            subnet: subnet.to_string(),
            chain_id,
        };

        let run_id = scheduled_run_id(
            &trigger_type,
            &instance.instance_id,
            &partition,
            scheduled_for,
            request_id,
        );

        let mut published = 0u64;
        for chunk in keys.chunks(self.config.microbatch_max_targets as usize) {
            let job_id = job_id_v5(&run_id, &instance.instance_id, chunk)?;
            let ctx = EvaluationContextV1 {
                schema_version: evaluation_context_schema_version_v1(),
                run: EvaluationContextRunV1 {
                    run_id: run_id.to_string(),
                    attempt: 1,
                    trigger_type: trigger_type.clone(),
                    enqueued_at: Utc::now(),
                    started_at: Utc::now(),
                },
                instance: EvaluationContextInstanceV1 {
                    instance_id: instance.instance_id.clone(),
                    user_id: instance.user_id.clone(),
                    template_id: spec_id.clone(),
                    template_version: spec_version,
                },
                partition: partition.clone(),
                schedule: Some(ScheduleV1 {
                    scheduled_for,
                    data_lag_secs,
                    effective_as_of,
                }),
                targets: TargetsV1 {
                    mode: if group_id.is_some() {
                        TargetModeV1::Group
                    } else {
                        TargetModeV1::Keys
                    },
                    group_id: group_id.map(|g| g.to_string()),
                    keys: chunk.to_vec(),
                },
                variables: instance.variable_values.clone(),
                tx: None,
            };

            let job = AlertEvaluationJobV1 {
                schema_version: alert_evaluation_job_schema_version_v1(),
                job: JobMetaV1 {
                    job_id: job_id.clone(),
                    priority: priority.clone(),
                    created_at: Utc::now(),
                },
                evaluation_context: ctx,
            };

            self.nats.publish_evaluation_job(&job, priority).await?;
            published += 1;
        }

        Ok(published)
    }

    async fn route_event_instances(
        &self,
        req: &AlertScheduleEventDrivenV1,
    ) -> Result<HashMap<String, Vec<String>>> {
        let mut instance_to_targets: HashMap<String, Vec<String>> = HashMap::new();
        let candidates: HashSet<String> = req.candidate_target_keys.iter().cloned().collect();

        for target_key in candidates {
            // direct key-mode instances
            let direct_key = format!("{}{}", EVENT_IDX_TARGET_INSTANCES_PREFIX, target_key);
            for instance_id in self.store.smembers(&direct_key).await? {
                instance_to_targets
                    .entry(instance_id)
                    .or_default()
                    .push(target_key.clone());
            }

            // group-mode instances (two-hop)
            let groups_key = format!("{}{}", EVENT_IDX_TARGET_GROUPS_PREFIX, target_key);
            let group_ids = self.store.smembers(&groups_key).await?;
            for group_id in group_ids {
                let group_instances_key =
                    format!("{}{}", EVENT_IDX_GROUP_INSTANCES_PREFIX, group_id);
                for instance_id in self.store.smembers(&group_instances_key).await? {
                    instance_to_targets
                        .entry(instance_id)
                        .or_default()
                        .push(target_key.clone());
                }
            }
        }

        Ok(instance_to_targets)
    }
}

fn parse_priority(priority: &str) -> JobPriorityV1 {
    match priority.to_lowercase().as_str() {
        "critical" => JobPriorityV1::Critical,
        "high" => JobPriorityV1::High,
        "low" => JobPriorityV1::Low,
        _ => JobPriorityV1::Normal,
    }
}

fn chain_id_for_partition(network: &str, subnet: &str) -> Result<i64> {
    match (network, subnet) {
        ("ETH", "mainnet") => Ok(1),
        ("ETH", "sepolia") => Ok(11155111),
        ("AVAX", "mainnet") => Ok(43114),
        ("AVAX", "fuji") => Ok(43113),
        _ => Err(AlertSchedulerError::InvalidAlertData(format!(
            "unsupported partition {network}:{subnet}"
        ))),
    }
}

fn partition_target_keys(keys: &[String]) -> Result<BTreeMap<(String, String), Vec<String>>> {
    let mut map: BTreeMap<(String, String), Vec<String>> = BTreeMap::new();
    for key in keys {
        let (network, subnet) = parse_target_key_partition(key)?;
        map.entry((network, subnet)).or_default().push(key.clone());
    }
    Ok(map)
}

fn parse_target_key_partition(target_key: &str) -> Result<(String, String)> {
    let parts: Vec<&str> = target_key.split(':').collect();
    if parts.len() < 2 {
        return Err(AlertSchedulerError::InvalidAlertData(format!(
            "invalid target_key {}",
            target_key
        )));
    }
    Ok((parts[0].to_string(), parts[1].to_string()))
}

fn parse_group_partition_set_key(key: &str) -> Result<(String, String)> {
    // alerts:targets:group:{group_id}:{NETWORK}:{subnet}
    let parts: Vec<&str> = key.split(':').collect();
    if parts.len() < 6 {
        return Err(AlertSchedulerError::InvalidAlertData(format!(
            "invalid group partition key {}",
            key
        )));
    }
    let network = parts[parts.len() - 2].to_string();
    let subnet = parts[parts.len() - 1].to_string();
    Ok((network, subnet))
}

fn schedule_effective_as_of(
    trigger_config: &Value,
    scheduled_for: DateTime<Utc>,
) -> Result<(i64, DateTime<Utc>)> {
    let data_lag_secs = trigger_config
        .get("data_lag_secs")
        .and_then(|v| v.as_i64())
        .unwrap_or(120);
    let effective_as_of = scheduled_for - chrono::Duration::seconds(data_lag_secs);
    Ok((data_lag_secs, effective_as_of))
}

fn schedule_effective_as_of_event_driven(
    trigger_config: &Value,
    scheduled_for: DateTime<Utc>,
) -> Result<(i64, DateTime<Utc>)> {
    // Unlike periodic runs, event-driven runs should default to querying "as of the triggering tx/log"
    // so the triggering event itself is eligible for window queries unless the user opts into lag.
    let data_lag_secs = trigger_config
        .get("data_lag_secs")
        .and_then(|v| v.as_i64())
        .unwrap_or(0);
    let effective_as_of = scheduled_for - chrono::Duration::seconds(data_lag_secs);
    Ok((data_lag_secs, effective_as_of))
}

fn instance_network_allows(trigger_config: &Value, partition: &PartitionV1) -> bool {
    let Some(networks) = trigger_config.get("networks") else {
        return true;
    };
    let Some(arr) = networks.as_array() else {
        return true;
    };
    let key = format!("{}:{}", partition.network, partition.subnet);
    arr.iter().any(|v| v.as_str() == Some(key.as_str()))
}

fn instance_spec_ref(instance: &crate::runtime_store::InstanceSnapshot) -> Result<(String, i64)> {
    if let (Some(template_id), Some(template_version)) =
        (instance.template_id.as_ref(), instance.template_version)
    {
        return Ok((template_id.clone(), template_version));
    }
    Err(AlertSchedulerError::InvalidAlertData(format!(
        "instance {} missing template reference",
        instance.instance_id
    )))
}

fn trigger_prunes_template(template: &AlertTemplateV1, req: &AlertScheduleEventDrivenV1) -> bool {
    if let Some(chain_id) = template.trigger.chain_id {
        if chain_id != req.partition.chain_id {
            return false;
        }
    }

    match req.event.kind {
        TxKindV1::Tx => {
            if template.trigger.method.required {
                let selector = req
                    .event
                    .evm_tx
                    .as_ref()
                    .and_then(|tx| tx.method_selector.as_deref())
                    .or_else(|| req.event.evm_tx.as_ref().and_then(|tx| tx.input.get(0..10)));
                if selector.is_none() {
                    return false;
                }
                let selector = selector.unwrap();
                if !template.trigger.method.selector_any_of.is_empty()
                    && !template
                        .trigger
                        .method
                        .selector_any_of
                        .iter()
                        .any(|s| s == selector)
                {
                    return false;
                }
            }
        }
        TxKindV1::Log => {
            if let Some(event_filter) = template.trigger.event.as_ref() {
                if event_filter.required {
                    let topic0 = req.event.evm_log.as_ref().map(|l| l.topic0.as_str());
                    if topic0.is_none() {
                        return false;
                    }
                    if !event_filter.topic0_any_of.is_empty()
                        && !event_filter
                            .topic0_any_of
                            .iter()
                            .any(|t| Some(t.as_str()) == topic0)
                    {
                        return false;
                    }
                }
            }
        }
    }

    true
}

fn trigger_prunes_executable(
    executable: &AlertExecutableV1,
    req: &AlertScheduleEventDrivenV1,
) -> bool {
    let evm = &executable.trigger_pruning.evm;

    if !evm.chain_ids.is_empty() && !evm.chain_ids.iter().any(|c| *c == req.partition.chain_id) {
        return false;
    }

    match req.event.kind {
        TxKindV1::Tx => {
            if !evm.to.any_of.is_empty() {
                let to = req.event.evm_tx.as_ref().and_then(|tx| tx.to.as_deref());
                if let Some(to) = to {
                    if !evm.to.any_of.iter().any(|a| a.eq_ignore_ascii_case(to)) {
                        return false;
                    }
                }
            }

            if evm.method.required {
                let selector = req
                    .event
                    .evm_tx
                    .as_ref()
                    .and_then(|tx| tx.method_selector.as_deref())
                    .or_else(|| req.event.evm_tx.as_ref().and_then(|tx| tx.input.get(0..10)));
                if selector.is_none() {
                    return false;
                }
                let selector = selector.unwrap();
                if !evm.method.selector_any_of.is_empty()
                    && !evm.method.selector_any_of.iter().any(|s| s == selector)
                {
                    return false;
                }
            }
        }
        TxKindV1::Log => {
            if !evm.to.any_of.is_empty() {
                let addr = req.event.evm_log.as_ref().map(|l| l.address.as_str());
                if let Some(addr) = addr {
                    if !evm.to.any_of.iter().any(|a| a.eq_ignore_ascii_case(addr)) {
                        return false;
                    }
                }
            }

            if evm.event.required {
                let topic0 = req.event.evm_log.as_ref().map(|l| l.topic0.as_str());
                if topic0.is_none() {
                    return false;
                }
                if !evm.event.topic0_any_of.is_empty()
                    && !evm
                        .event
                        .topic0_any_of
                        .iter()
                        .any(|t| Some(t.as_str()) == topic0)
                {
                    return false;
                }
            }
        }
    }

    true
}

fn schedule_event_to_eval_tx(req: &AlertScheduleEventDrivenV1) -> Result<EvaluationTxV1> {
    match req.event.kind {
        TxKindV1::Tx => {
            let tx = req.event.evm_tx.as_ref().ok_or_else(|| {
                AlertSchedulerError::InvalidAlertData("missing evm_tx".to_string())
            })?;
            Ok(EvaluationTxV1 {
                kind: TxKindV1::Tx,
                hash: tx.hash.clone(),
                from: Some(tx.from.clone()),
                to: tx.to.clone(),
                method_selector: tx
                    .method_selector
                    .clone()
                    .or_else(|| tx.input.get(0..10).map(|s| s.to_string())),
                value_wei: Some(tx.value_wei.clone()),
                value_native: Some(tx.value_native),
                log_index: None,
                log_address: None,
                topic0: None,
                topic1: None,
                topic2: None,
                topic3: None,
                data: None,
                block_number: tx.block_number,
                block_timestamp: tx.block_timestamp,
            })
        }
        TxKindV1::Log => {
            let log = req.event.evm_log.as_ref().ok_or_else(|| {
                AlertSchedulerError::InvalidAlertData("missing evm_log".to_string())
            })?;
            Ok(EvaluationTxV1 {
                kind: TxKindV1::Log,
                hash: log.transaction_hash.clone(),
                from: None,
                to: None,
                method_selector: None,
                value_wei: None,
                value_native: None,
                log_index: Some(log.log_index),
                log_address: Some(log.address.clone()),
                topic0: Some(log.topic0.clone()),
                topic1: log.topic1.clone(),
                topic2: log.topic2.clone(),
                topic3: log.topic3.clone(),
                data: Some(log.data.clone()),
                block_number: log.block_number,
                block_timestamp: log.block_timestamp,
            })
        }
    }
}

fn scheduled_run_id(
    trigger_type: &TriggerTypeV1,
    instance_id: &str,
    partition: &PartitionV1,
    scheduled_for: DateTime<Utc>,
    request_id: &str,
) -> Uuid {
    let input = format!(
        "scheduled:{}:{}:{}:{}:{}:{}",
        trigger_type_str(trigger_type),
        instance_id,
        partition.network,
        partition.subnet,
        scheduled_for.to_rfc3339(),
        request_id
    );
    Uuid::new_v5(&Uuid::NAMESPACE_URL, input.as_bytes())
}

fn trigger_type_str(t: &TriggerTypeV1) -> &'static str {
    match t {
        TriggerTypeV1::EventDriven => "event_driven",
        TriggerTypeV1::Periodic => "periodic",
        TriggerTypeV1::OneTime => "one_time",
    }
}

fn event_run_id(req: &AlertScheduleEventDrivenV1) -> Result<Uuid> {
    let id = match req.event.kind {
        TxKindV1::Tx => {
            let tx = req.event.evm_tx.as_ref().ok_or_else(|| {
                AlertSchedulerError::InvalidAlertData("missing evm_tx".to_string())
            })?;
            format!("evm:tx:{}:{}", req.partition.chain_id, tx.hash)
        }
        TxKindV1::Log => {
            let log = req.event.evm_log.as_ref().ok_or_else(|| {
                AlertSchedulerError::InvalidAlertData("missing evm_log".to_string())
            })?;
            format!(
                "evm:log:{}:{}:{}",
                req.partition.chain_id, log.transaction_hash, log.log_index
            )
        }
    };
    Ok(Uuid::new_v5(&Uuid::NAMESPACE_URL, id.as_bytes()))
}

fn job_id_v5(run_id: &Uuid, instance_id: &str, keys: &[String]) -> Result<String> {
    let mut hasher = sha2::Sha256::new();
    hasher.update(run_id.as_bytes());
    hasher.update(instance_id.as_bytes());
    for k in keys {
        hasher.update(k.as_bytes());
    }
    let digest = hasher.finalize();
    let uuid = Uuid::new_v5(&Uuid::NAMESPACE_URL, &digest[..]);
    Ok(uuid.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::runtime_store::{InstanceSnapshot, TargetSelectorSnapshot};
    use alert_runtime_common::{
        alert_schedule_event_driven_schema_version_v1, alert_schedule_one_time_schema_version_v1,
        alert_schedule_periodic_schema_version_v1, ActionV1, AlertExecutableV1, AlertTemplateV1,
        ConditionSetV1, NotificationTemplateV1, TriggerAddressFilterV1, TriggerMethodFilterV1,
        TriggerV1, VmKindV1,
    };
    use async_trait::async_trait;
    use chrono::TimeZone;
    use serde_json::json;
    use std::collections::{BTreeMap, HashMap};
    use tokio::sync::Mutex;

    #[derive(Default)]
    struct TestState {
        instances: HashMap<String, InstanceSnapshot>,
        templates: HashMap<(String, i64), AlertTemplateV1>,
        sets: HashMap<String, Vec<String>>,
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
            template_id: &str,
            template_version: i64,
        ) -> Result<AlertTemplateV1> {
            let guard = self.state.lock().await;
            guard
                .templates
                .get(&(template_id.to_string(), template_version))
                .cloned()
                .ok_or_else(|| {
                    AlertSchedulerError::InvalidAlertData("template missing".to_string())
                })
        }

        async fn get_executable(
            &self,
            _template_id: &str,
            _template_version: i64,
        ) -> Result<AlertExecutableV1> {
            Err(AlertSchedulerError::InvalidAlertData(
                "executable missing".to_string(),
            ))
        }

        async fn scan_instance_keys(
            &self,
            _cursor: u64,
            _count: u32,
        ) -> Result<(u64, Vec<String>)> {
            Ok((0, vec![]))
        }

        async fn zrangebyscore_withscores(
            &self,
            _key: &str,
            _max_score: i64,
            _limit: usize,
        ) -> Result<Vec<(String, i64)>> {
            Ok(vec![])
        }

        async fn zadd_nx(&self, _key: &str, _member: &str, _score: i64) -> Result<()> {
            Ok(())
        }

        async fn zadd_xx(&self, _key: &str, _member: &str, _score: i64) -> Result<()> {
            Ok(())
        }

        async fn zrem(&self, _key: &str, _member: &str) -> Result<()> {
            Ok(())
        }

        async fn zscore(&self, _key: &str, _member: &str) -> Result<Option<i64>> {
            Ok(None)
        }

        async fn smembers(&self, key: &str) -> Result<Vec<String>> {
            let guard = self.state.lock().await;
            Ok(guard.sets.get(key).cloned().unwrap_or_default())
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
            key: &str,
            _cursor: u64,
            _count: usize,
        ) -> Result<(u64, Vec<String>)> {
            let guard = self.state.lock().await;
            Ok((0, guard.sets.get(key).cloned().unwrap_or_default()))
        }

        async fn exists(&self, key: &str) -> Result<bool> {
            let guard = self.state.lock().await;
            Ok(guard.strings.contains_key(key))
        }
    }

    #[derive(Default)]
    struct TestPublisher {
        jobs: Arc<Mutex<Vec<AlertEvaluationJobV1>>>,
    }

    #[async_trait]
    impl AlertSchedulerPublisher for TestPublisher {
        async fn publish_schedule_request_bytes(
            &self,
            _subject: &str,
            _msg_id: &str,
            _payload: Vec<u8>,
        ) -> Result<()> {
            Ok(())
        }

        async fn publish_evaluation_job(
            &self,
            job: &AlertEvaluationJobV1,
            _priority: &JobPriorityV1,
        ) -> Result<()> {
            self.jobs.lock().await.push(job.clone());
            Ok(())
        }
    }

    fn config_for_tests() -> AlertSchedulerConfig {
        AlertSchedulerConfig {
            microbatch_max_targets: 2,
            event_job_targets_cap: 2,
            schedule_request_dedupe_ttl_secs: 60,
            ..Default::default()
        }
    }

    fn minimal_template_v1(
        chain_id: i64,
        method_required: bool,
        selector_any_of: Vec<String>,
    ) -> AlertTemplateV1 {
        AlertTemplateV1 {
            version: "v1".to_string(),
            name: "t".to_string(),
            description: "d".to_string(),
            alert_type: "wallet".to_string(),
            variables: vec![],
            trigger: TriggerV1 {
                chain_id: Some(chain_id),
                tx_type: "any".to_string(),
                from: TriggerAddressFilterV1 {
                    any_of: vec![],
                    labels: vec![],
                    not: vec![],
                },
                to: TriggerAddressFilterV1 {
                    any_of: vec![],
                    labels: vec![],
                    not: vec![],
                },
                method: TriggerMethodFilterV1 {
                    selector_any_of,
                    name_any_of: vec![],
                    required: method_required,
                },
                event: None,
            },
            datasources: vec![],
            enrichments: vec![],
            conditions: ConditionSetV1 {
                all: vec![],
                any: vec![],
                not: vec![],
            },
            notification_template: NotificationTemplateV1 {
                title: "x".to_string(),
                body: "y".to_string(),
            },
            action: ActionV1 {
                notification_policy: "per_matched_target".to_string(),
                cooldown_secs: 0,
                cooldown_key_template: "{{instance_id}}:{{target.key}}".to_string(),
                dedupe_key_template: "{{run_id}}:{{instance_id}}:{{target.key}}".to_string(),
            },
            performance: json!({}),
            warnings: vec![],
        }
    }

    #[tokio::test]
    async fn periodic_keys_partition_and_microbatch() {
        let store = TestStore::default();
        let publisher = Arc::new(TestPublisher::default());

        store.state.lock().await.instances.insert(
            "inst".to_string(),
            InstanceSnapshot {
                instance_id: "inst".to_string(),
                user_id: json!("u1"),
                enabled: true,
                priority: "normal".to_string(),
                template_id: Some("tpl".to_string()),
                template_version: Some(1),
                trigger_type: "periodic".to_string(),
                trigger_config: json!({ "data_lag_secs": 60 }),
                target_selector: TargetSelectorSnapshot {
                    mode: "keys".to_string(),
                    group_id: None,
                    keys: vec![
                        "ETH:mainnet:0x1".to_string(),
                        "ETH:mainnet:0x2".to_string(),
                        "AVAX:mainnet:0xa".to_string(),
                        "AVAX:mainnet:0xb".to_string(),
                        "AVAX:mainnet:0xc".to_string(),
                    ],
                },
                variable_values: json!({}),
            },
        );

        let handler =
            ScheduleRequestHandler::new(config_for_tests(), Arc::new(store), publisher.clone());
        let scheduled_for = Utc.with_ymd_and_hms(2026, 1, 15, 12, 0, 0).unwrap();
        let req = AlertSchedulePeriodicV1 {
            schema_version: alert_schedule_periodic_schema_version_v1(),
            request_id: "req-1".to_string(),
            instance_id: "inst".to_string(),
            scheduled_for,
            requested_at: scheduled_for,
            source: "test".to_string(),
        };

        let published = handler.handle_periodic(req).await.unwrap();
        assert_eq!(published, 3);

        let jobs = publisher.jobs.lock().await;
        assert_eq!(jobs.len(), 3);

        let mut by_partition: BTreeMap<(String, String), usize> = BTreeMap::new();
        for job in jobs.iter() {
            let part = (
                job.evaluation_context.partition.network.clone(),
                job.evaluation_context.partition.subnet.clone(),
            );
            *by_partition.entry(part).or_default() += 1;
            assert_eq!(
                job.evaluation_context.run.trigger_type,
                TriggerTypeV1::Periodic
            );
            assert!(job.evaluation_context.schedule.is_some());
            assert_eq!(
                job.evaluation_context
                    .schedule
                    .as_ref()
                    .unwrap()
                    .effective_as_of,
                scheduled_for - chrono::Duration::seconds(60)
            );
            assert!(job.evaluation_context.targets.keys.len() <= 2);
        }
        assert_eq!(
            by_partition.get(&("ETH".to_string(), "mainnet".to_string())),
            Some(&1)
        );
        assert_eq!(
            by_partition.get(&("AVAX".to_string(), "mainnet".to_string())),
            Some(&2)
        );
    }

    #[tokio::test]
    async fn periodic_request_done_key_dedupes() {
        let store = TestStore::default();
        let publisher = Arc::new(TestPublisher::default());

        store.state.lock().await.instances.insert(
            "inst".to_string(),
            InstanceSnapshot {
                instance_id: "inst".to_string(),
                user_id: json!("u1"),
                enabled: true,
                priority: "normal".to_string(),
                template_id: Some("tpl".to_string()),
                template_version: Some(1),
                trigger_type: "periodic".to_string(),
                trigger_config: json!({}),
                target_selector: TargetSelectorSnapshot {
                    mode: "keys".to_string(),
                    group_id: None,
                    keys: vec!["ETH:mainnet:0x1".to_string()],
                },
                variable_values: json!({}),
            },
        );

        let handler =
            ScheduleRequestHandler::new(config_for_tests(), Arc::new(store), publisher.clone());
        let scheduled_for = Utc.with_ymd_and_hms(2026, 1, 15, 12, 0, 0).unwrap();

        let req = AlertSchedulePeriodicV1 {
            schema_version: alert_schedule_periodic_schema_version_v1(),
            request_id: "req-dup".to_string(),
            instance_id: "inst".to_string(),
            scheduled_for,
            requested_at: scheduled_for,
            source: "test".to_string(),
        };

        let first = handler.handle_periodic(req.clone()).await.unwrap();
        let second = handler.handle_periodic(req).await.unwrap();

        assert_eq!(first, 1);
        assert_eq!(second, 0);
        assert_eq!(publisher.jobs.lock().await.len(), 1);
    }

    #[tokio::test]
    async fn one_time_sets_fired_marker_and_short_circuits_repeats() {
        let store = TestStore::default();
        let publisher = Arc::new(TestPublisher::default());

        store.state.lock().await.instances.insert(
            "inst".to_string(),
            InstanceSnapshot {
                instance_id: "inst".to_string(),
                user_id: json!("u1"),
                enabled: true,
                priority: "normal".to_string(),
                template_id: Some("tpl".to_string()),
                template_version: Some(1),
                trigger_type: "one_time".to_string(),
                trigger_config: json!({}),
                target_selector: TargetSelectorSnapshot {
                    mode: "keys".to_string(),
                    group_id: None,
                    keys: vec!["ETH:mainnet:0x1".to_string()],
                },
                variable_values: json!({}),
            },
        );

        let store_arc: Arc<dyn RuntimeStoreOps> = Arc::new(store.clone());
        let handler =
            ScheduleRequestHandler::new(config_for_tests(), store_arc.clone(), publisher.clone());

        let scheduled_for = Utc.with_ymd_and_hms(2026, 1, 15, 12, 0, 0).unwrap();
        let req1 = AlertScheduleOneTimeV1 {
            schema_version: alert_schedule_one_time_schema_version_v1(),
            request_id: "req-ot-1".to_string(),
            instance_id: "inst".to_string(),
            scheduled_for,
            requested_at: scheduled_for,
            source: "test".to_string(),
        };

        let first = handler.handle_one_time(req1).await.unwrap();
        assert_eq!(first, 1);

        assert!(store_arc
            .exists("alerts:one_time:fired:inst")
            .await
            .unwrap());

        let req2 = AlertScheduleOneTimeV1 {
            schema_version: alert_schedule_one_time_schema_version_v1(),
            request_id: "req-ot-2".to_string(),
            instance_id: "inst".to_string(),
            scheduled_for,
            requested_at: scheduled_for,
            source: "test".to_string(),
        };

        let second = handler.handle_one_time(req2).await.unwrap();
        assert_eq!(second, 0);
        assert_eq!(publisher.jobs.lock().await.len(), 1);
    }

    #[tokio::test]
    async fn event_driven_routes_and_applies_trigger_pruning() {
        let store = TestStore::default();
        let publisher = Arc::new(TestPublisher::default());

        store.state.lock().await.instances.insert(
            "inst".to_string(),
            InstanceSnapshot {
                instance_id: "inst".to_string(),
                user_id: json!("u1"),
                enabled: true,
                priority: "high".to_string(),
                template_id: Some("tpl".to_string()),
                template_version: Some(1),
                trigger_type: "event_driven".to_string(),
                trigger_config: json!({ "networks": ["ETH:mainnet"] }),
                target_selector: TargetSelectorSnapshot {
                    mode: "keys".to_string(),
                    group_id: None,
                    keys: vec![],
                },
                variable_values: json!({}),
            },
        );

        store.state.lock().await.templates.insert(
            ("tpl".to_string(), 1),
            minimal_template_v1(1, true, vec!["0x12345678".to_string()]),
        );

        store.state.lock().await.sets.insert(
            "alerts:event_idx:target_instances:ETH:mainnet:0xabc".to_string(),
            vec!["inst".to_string()],
        );

        let handler =
            ScheduleRequestHandler::new(config_for_tests(), Arc::new(store), publisher.clone());
        let requested_at = Utc.with_ymd_and_hms(2026, 1, 15, 12, 0, 0).unwrap();
        let req = AlertScheduleEventDrivenV1 {
            schema_version: alert_schedule_event_driven_schema_version_v1(),
            vm: VmKindV1::Evm,
            partition: PartitionV1 {
                network: "ETH".to_string(),
                subnet: "mainnet".to_string(),
                chain_id: 1,
            },
            candidate_target_keys: vec!["ETH:mainnet:0xabc".to_string()],
            event: alert_runtime_common::ScheduleEventV1 {
                kind: TxKindV1::Tx,
                evm_tx: Some(alert_runtime_common::EvmTxV1 {
                    hash: "0xaaa".to_string(),
                    from: "0x111".to_string(),
                    to: Some("0x222".to_string()),
                    input: "0x12345678deadbeef".to_string(),
                    method_selector: Some("0x12345678".to_string()),
                    value_wei: "0".to_string(),
                    value_native: 0.0,
                    block_number: 1,
                    block_timestamp: requested_at,
                }),
                evm_log: None,
            },
            requested_at,
            source: "test".to_string(),
        };

        let published = handler.handle_event_driven(req).await.unwrap();
        assert_eq!(published, 1);

        let jobs = publisher.jobs.lock().await;
        assert_eq!(jobs.len(), 1);
        assert_eq!(
            jobs[0].evaluation_context.run.trigger_type,
            TriggerTypeV1::EventDriven
        );
        assert!(jobs[0].evaluation_context.schedule.is_some());
        assert_eq!(
            jobs[0]
                .evaluation_context
                .schedule
                .as_ref()
                .unwrap()
                .effective_as_of,
            requested_at
        );
        assert!(jobs[0].evaluation_context.tx.is_some());
        assert_eq!(
            jobs[0].evaluation_context.targets.keys,
            vec!["ETH:mainnet:0xabc".to_string()]
        );
    }
}
