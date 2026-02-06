use alert_runtime_common::{
    alert_triggered_batch_schema_version_v1, ActionV1, AlertTriggeredBatchV1,
    NotificationTemplateV1,
};
use chrono::{TimeZone, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

#[derive(Debug)]
pub struct RouterError {
    pub code: &'static str,
    pub message: String,
}

impl RouterError {
    pub fn json(message: String) -> Self {
        Self {
            code: "json_error",
            message,
        }
    }

    pub fn schema(message: String) -> Self {
        Self {
            code: "schema_error",
            message,
        }
    }

    pub fn store(message: String) -> Self {
        Self {
            code: "store_error",
            message,
        }
    }

    pub fn render(message: String) -> Self {
        Self {
            code: "render_error",
            message,
        }
    }
}

impl std::fmt::Display for RouterError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for RouterError {}

pub trait RuntimeIO {
    fn kv_get(&self, key: &str) -> Result<Option<Vec<u8>>, RouterError>;
    fn kv_set(&self, key: &str, value: Vec<u8>) -> Result<(), RouterError>;
    fn kv_exists(&self, key: &str) -> Result<bool, RouterError>;
    fn kv_incr(&self, key: &str, delta: u64) -> Result<u64, RouterError>;
    fn nats_publish(&self, subject: &str, body: Vec<u8>) -> Result<(), RouterError>;
    fn now_unix_secs(&self) -> i64;
}

#[derive(Debug, Clone, Deserialize)]
struct InstanceSnapshotV1 {
    instance_id: String,
    #[serde(default)]
    alert_name: String,
    #[serde(default)]
    alert_description: String,
    user_id: Value,
    enabled: bool,
    priority: String,
    #[serde(default)]
    variable_values: Value,
    notification_template: NotificationTemplateV1,
    action: ActionV1,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "lowercase")]
enum WebhookAlertPriority {
    Low,
    Normal,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize)]
struct WebhookNotificationRequestV1 {
    notification_id: String,
    user_id: String,
    alert_id: String,
    alert_name: String,
    priority: WebhookAlertPriority,
    payload: Value,
    timestamp: i64,
}

#[derive(Debug, Clone, Serialize)]
struct WebsocketDeliveryRequestV1 {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub notification_id: Option<String>,
    pub user_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub alert_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subject: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub template: Option<String>,
    #[serde(default)]
    pub variables: HashMap<String, String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub priority: Option<WebhookAlertPriority>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub channel: Option<String>,
    #[serde(default, skip_serializing_if = "HashMap::is_empty")]
    pub channel_config: HashMap<String, String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timestamp: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct TelegramNotificationV1 {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub notification_id: Option<String>,
    pub user_id: String,
    pub alert_id: String,
    pub alert_name: String,
    pub priority: WebhookAlertPriority,
    pub message: String,
    pub chain: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub transaction_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub wallet_address: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub block_number: Option<u64>,
    pub timestamp: String,
}

#[derive(Debug, Clone)]
struct ParsedTargetKey {
    key: String,
    network: String,
    subnet: String,
    address: String,
}

pub fn handle_nats_message(
    io: &dyn RuntimeIO,
    subject: &str,
    body: &[u8],
) -> Result<(), RouterError> {
    if !subject.starts_with("alerts.triggered.") {
        return Ok(());
    }

    let batch: AlertTriggeredBatchV1 = serde_json::from_slice(body)
        .map_err(|e| RouterError::json(format!("invalid triggered batch: {e}")))?;
    if batch.schema_version != alert_triggered_batch_schema_version_v1() {
        return Ok(());
    }

    route_triggered_batch(io, batch)
}

fn route_triggered_batch(
    io: &dyn RuntimeIO,
    batch: AlertTriggeredBatchV1,
) -> Result<(), RouterError> {
    let instance = load_instance_snapshot(io, &batch.instance_id)?;
    if instance.instance_id != batch.instance_id {
        return Err(RouterError::schema(format!(
            "instance snapshot id mismatch (snapshot={}, batch={})",
            instance.instance_id, batch.instance_id
        )));
    }
    if !instance.enabled {
        return Ok(());
    }

    let recipients = load_recipients(io, &batch.instance_id, &instance.user_id)?;

    for m in batch.matches.iter() {
        let target = parse_target_key(&m.target_key)?;

        let render_context = build_render_context(&batch, &instance, &target, &m.match_context)?;

        let title_rendered =
            render_template(&instance.notification_template.title, &render_context)?;
        let body_rendered = render_template(&instance.notification_template.body, &render_context)?;
        let alert_name_raw = if instance.alert_name.trim().is_empty() {
            if title_rendered.trim().is_empty() {
                "Alert triggered".to_string()
            } else {
                title_rendered.clone()
            }
        } else {
            instance.alert_name.clone()
        };
        let title_raw = if title_rendered.trim().is_empty() {
            alert_name_raw.clone()
        } else {
            title_rendered
        };
        let message_raw = if body_rendered.trim().is_empty() {
            alert_name_raw.clone()
        } else {
            body_rendered
        };
        let title = truncate_hex_addresses_in_text(&title_raw);
        let message = truncate_hex_addresses_in_text(&message_raw);
        let alert_name = truncate_hex_addresses_in_text(&alert_name_raw);

        for user_id in recipients.iter() {
            let dedupe_key =
                render_template(&instance.action.dedupe_key_template, &render_context)?;
            if !check_dedupe(io, user_id, &dedupe_key)? {
                continue;
            }

            if instance.action.cooldown_secs > 0 {
                let cooldown_key =
                    render_template(&instance.action.cooldown_key_template, &render_context)?;
                if !check_cooldown(
                    io,
                    user_id,
                    &cooldown_key,
                    instance.action.cooldown_secs,
                    io.now_unix_secs(),
                )? {
                    continue;
                }
            }

            let notification_id = uuid::Uuid::new_v4().to_string();
            publish_notification_content(
                io,
                &instance,
                &batch,
                user_id,
                &target,
                &render_context,
                &alert_name,
                &title,
                &message,
                &notification_id,
            )?;
            publish_webhook(
                io,
                &instance,
                &batch,
                user_id,
                &target.key,
                &notification_id,
                alert_name.clone(),
                title.clone(),
                message.clone(),
                m.match_context.clone(),
            )?;
            publish_websocket(
                io,
                &instance,
                &batch,
                user_id,
                &notification_id,
                title.clone(),
                message.clone(),
                &render_context,
            )?;
            publish_telegram(
                io,
                &instance,
                &batch,
                user_id,
                &target,
                &notification_id,
                alert_name.clone(),
                message.clone(),
            )?;
        }
    }

    Ok(())
}

fn load_instance_snapshot(
    io: &dyn RuntimeIO,
    instance_id: &str,
) -> Result<InstanceSnapshotV1, RouterError> {
    let key = format!("alerts:instance:{}", instance_id);
    let Some(raw) = io.kv_get(&key)? else {
        return Err(RouterError::schema(format!(
            "missing instance snapshot {}",
            instance_id
        )));
    };
    serde_json::from_slice(&raw).map_err(|e| RouterError::json(format!("instance snapshot: {e}")))
}

fn load_recipients(
    io: &dyn RuntimeIO,
    instance_id: &str,
    fallback_user_id: &Value,
) -> Result<Vec<String>, RouterError> {
    let key = format!("alerts:instance:subscribers:{}", instance_id);
    let Some(raw) = io.kv_get(&key)? else {
        return Ok(vec![value_to_user_id(fallback_user_id)?]);
    };

    let parsed: Value =
        serde_json::from_slice(&raw).map_err(|e| RouterError::json(format!("subscribers: {e}")))?;
    let Some(arr) = parsed.as_array() else {
        return Ok(vec![value_to_user_id(fallback_user_id)?]);
    };

    let mut out = Vec::new();
    for v in arr {
        if let Some(s) = v.as_str() {
            let s = s.trim();
            if !s.is_empty() {
                out.push(s.to_string());
            }
        }
    }
    if out.is_empty() {
        out.push(value_to_user_id(fallback_user_id)?);
    }
    Ok(out)
}

fn value_to_user_id(v: &Value) -> Result<String, RouterError> {
    match v {
        Value::String(s) => Ok(s.clone()),
        Value::Number(n) => Ok(n.to_string()),
        other => Err(RouterError::schema(format!(
            "invalid user_id value {}",
            other
        ))),
    }
}

fn parse_target_key(target_key: &str) -> Result<ParsedTargetKey, RouterError> {
    let parts: Vec<&str> = target_key.split(':').collect();
    if parts.len() < 3 {
        return Err(RouterError::schema(format!(
            "invalid target_key '{}'",
            target_key
        )));
    }
    Ok(ParsedTargetKey {
        key: target_key.to_string(),
        network: parts[0].to_string(),
        subnet: parts[1].to_string(),
        address: parts[2].to_string(),
    })
}

fn build_render_context(
    batch: &AlertTriggeredBatchV1,
    instance: &InstanceSnapshotV1,
    target: &ParsedTargetKey,
    match_context: &Value,
) -> Result<Value, RouterError> {
    let mut root = serde_json::Map::new();
    root.insert(
        "instance_id".to_string(),
        Value::String(batch.instance_id.clone()),
    );
    root.insert(
        "alert_name".to_string(),
        Value::String(instance.alert_name.clone()),
    );
    if !instance.alert_description.trim().is_empty() {
        root.insert(
            "alert_description".to_string(),
            Value::String(instance.alert_description.clone()),
        );
    }
    root.insert("run_id".to_string(), Value::String(batch.run_id.clone()));
    root.insert("job_id".to_string(), Value::String(batch.job_id.clone()));

    if let Some(sched) = batch.schedule.as_ref() {
        root.insert(
            "scheduled_for".to_string(),
            Value::String(sched.scheduled_for.to_rfc3339()),
        );
    }

    let mut trigger_map = serde_json::Map::new();
    if let Some(tx) = batch.tx.as_ref() {
        let tx_json =
            serde_json::to_value(tx).map_err(|e| RouterError::json(format!("tx json: {e}")))?;
        root.insert("tx".to_string(), tx_json.clone());
        if let Value::Object(map) = tx_json {
            trigger_map = map;
        }
    }

    let target_short = short_address(&target.address);
    root.insert(
        "target".to_string(),
        serde_json::json!({
            "key": &target.key,
            "network": &target.network,
            "subnet": &target.subnet,
            "address": &target.address,
            "short": target_short,
        }),
    );

    if trigger_map.is_empty() {
        trigger_map = serde_json::Map::new();
    }
    trigger_map.insert(
        "network".to_string(),
        Value::String(batch.partition.network.clone()),
    );
    trigger_map.insert(
        "subnet".to_string(),
        Value::String(batch.partition.subnet.clone()),
    );
    trigger_map.insert(
        "chain_id".to_string(),
        Value::Number(batch.partition.chain_id.into()),
    );
    trigger_map.insert(
        "network_id".to_string(),
        Value::Number(batch.partition.chain_id.into()),
    );
    trigger_map.insert("address".to_string(), Value::String(target.address.clone()));
    trigger_map.insert("key".to_string(), Value::String(target.key.clone()));
    trigger_map.insert("target_key".to_string(), Value::String(target.key.clone()));
    // Backwards-compatible alias for templates that use trigger.* placeholders.
    root.insert("trigger".to_string(), Value::Object(trigger_map));

    // Merge variable values at root level.
    if let Some(vars) = instance.variable_values.as_object() {
        let mut vars_map = serde_json::Map::new();
        for (k, v) in vars {
            root.insert(k.clone(), v.clone());
            vars_map.insert(k.clone(), v.clone());
        }
        if !vars_map.is_empty() {
            // Backwards-compatible alias for templates that use vars.* placeholders.
            root.insert("vars".to_string(), Value::Object(vars_map));
        }
    }

    // Merge match_context at root level (aliases from Polars Eval).
    if let Some(mc) = match_context.as_object() {
        for (k, v) in mc {
            root.insert(k.clone(), v.clone());
        }
    }

    Ok(Value::Object(root))
}

fn short_address(address: &str) -> String {
    let s = address.trim();
    if s.len() <= 12 {
        return s.to_string();
    }
    let start = &s[..6.min(s.len())];
    let end = &s[s.len().saturating_sub(4)..];
    format!("{start}…{end}")
}

fn render_template(template: &str, ctx: &Value) -> Result<String, RouterError> {
    let mut out = String::with_capacity(template.len());
    let bytes = template.as_bytes();
    let mut i = 0usize;

    while i < bytes.len() {
        if i + 1 < bytes.len() && bytes[i] == b'{' && bytes[i + 1] == b'{' {
            let start = i + 2;
            let mut end = None;
            let mut j = start;
            while j + 1 < bytes.len() {
                if bytes[j] == b'}' && bytes[j + 1] == b'}' {
                    end = Some(j);
                    break;
                }
                j += 1;
            }

            let Some(end) = end else {
                return Err(RouterError::render("unclosed {{ placeholder".to_string()));
            };

            let key = template[start..end].trim();
            if key.is_empty() {
                return Err(RouterError::render("empty placeholder".to_string()));
            }
            let val = lookup_path(ctx, key)
                .ok_or_else(|| RouterError::render(format!("missing placeholder '{}'", key)))?;
            out.push_str(&value_to_string(&val));
            i = end + 2;
            continue;
        }

        out.push(bytes[i] as char);
        i += 1;
    }

    Ok(out)
}

fn lookup_path(root: &Value, path: &str) -> Option<Value> {
    let mut current = root;
    for seg in path.split('.') {
        current = current.get(seg)?;
    }
    Some(current.clone())
}

fn value_to_string(v: &Value) -> String {
    match v {
        Value::Null => "".to_string(),
        Value::String(s) => s.clone(),
        Value::Bool(b) => b.to_string(),
        Value::Number(n) => n.to_string(),
        other => other.to_string(),
    }
}

fn check_dedupe(io: &dyn RuntimeIO, user_id: &str, dedupe_key: &str) -> Result<bool, RouterError> {
    let key = format!("alerts:dedupe:{}:{}", user_id, dedupe_key);
    let count = io.kv_incr(&key, 1)?;
    Ok(count == 1)
}

fn check_cooldown(
    io: &dyn RuntimeIO,
    user_id: &str,
    cooldown_key: &str,
    cooldown_secs: i64,
    now: i64,
) -> Result<bool, RouterError> {
    let key = format!("alerts:cooldown:{}:{}", user_id, cooldown_key);
    if let Some(raw) = io.kv_get(&key)? {
        if let Ok(s) = String::from_utf8(raw) {
            if let Ok(last) = s.parse::<i64>() {
                if now - last < cooldown_secs {
                    return Ok(false);
                }
            }
        }
    }

    io.kv_set(&key, now.to_string().into_bytes())?;
    Ok(true)
}

fn publish_webhook(
    io: &dyn RuntimeIO,
    instance: &InstanceSnapshotV1,
    batch: &AlertTriggeredBatchV1,
    user_id: &str,
    target_key: &str,
    notification_id: &str,
    alert_name: String,
    title: String,
    message: String,
    match_context: Value,
) -> Result<(), RouterError> {
    let priority = parse_priority(&instance.priority);

    let payload = serde_json::json!({
        "instance_id": batch.instance_id.clone(),
        "job_id": batch.job_id.clone(),
        "run_id": batch.run_id.clone(),
        "target_key": target_key,
        "partition": batch.partition.clone(),
        "schedule": batch.schedule.clone(),
        "tx": batch.tx.clone(),
        "title": title,
        "body": message,
        "match_context": match_context,
    });

    let req = WebhookNotificationRequestV1 {
        notification_id: notification_id.to_string(),
        user_id: user_id.to_string(),
        alert_id: batch.instance_id.clone(),
        alert_name,
        priority,
        payload,
        timestamp: io.now_unix_secs(),
    };

    let bytes =
        serde_json::to_vec(&req).map_err(|e| RouterError::json(format!("webhook req: {e}")))?;
    io.nats_publish("notifications.send.immediate.webhook", bytes)?;
    Ok(())
}

fn publish_websocket(
    io: &dyn RuntimeIO,
    instance: &InstanceSnapshotV1,
    batch: &AlertTriggeredBatchV1,
    user_id: &str,
    notification_id: &str,
    title: String,
    message: String,
    render_context: &Value,
) -> Result<(), RouterError> {
    let priority = parse_priority(&instance.priority);

    let req = WebsocketDeliveryRequestV1 {
        notification_id: Some(notification_id.to_string()),
        user_id: user_id.to_string(),
        alert_id: Some(batch.instance_id.clone()),
        subject: Some(title),
        message: Some(message),
        template: Some(format!("alert_instance:{}", batch.instance_id)),
        variables: flatten_to_string_map(render_context),
        priority: Some(priority),
        channel: Some("websocket".to_string()),
        channel_config: HashMap::new(),
        timestamp: Some(now_rfc3339(io.now_unix_secs())),
    };

    let bytes =
        serde_json::to_vec(&req).map_err(|e| RouterError::json(format!("websocket req: {e}")))?;
    io.nats_publish("notifications.send.immediate.websocket", bytes)?;
    Ok(())
}

fn publish_telegram(
    io: &dyn RuntimeIO,
    instance: &InstanceSnapshotV1,
    batch: &AlertTriggeredBatchV1,
    user_id: &str,
    target: &ParsedTargetKey,
    notification_id: &str,
    alert_name: String,
    message: String,
) -> Result<(), RouterError> {
    let priority = parse_priority(&instance.priority);
    let (transaction_hash, block_number) = batch
        .tx
        .as_ref()
        .map(|tx| (Some(tx.hash.clone()), Some(tx.block_number)))
        .unwrap_or((None, None));

    let chain = format!(
        "{}.{}",
        chain_for_network(&batch.partition.network),
        batch.partition.subnet
    );

    let req = TelegramNotificationV1 {
        notification_id: Some(notification_id.to_string()),
        user_id: user_id.to_string(),
        alert_id: batch.instance_id.clone(),
        alert_name,
        priority,
        message,
        chain,
        transaction_hash,
        wallet_address: Some(target.address.clone()),
        block_number: block_number.and_then(|n| u64::try_from(n).ok()),
        timestamp: now_rfc3339(io.now_unix_secs()),
    };

    let bytes =
        serde_json::to_vec(&req).map_err(|e| RouterError::json(format!("telegram req: {e}")))?;
    io.nats_publish("notifications.send.immediate.telegram", bytes)?;
    Ok(())
}

fn publish_notification_content(
    io: &dyn RuntimeIO,
    instance: &InstanceSnapshotV1,
    batch: &AlertTriggeredBatchV1,
    user_id: &str,
    target: &ParsedTargetKey,
    render_context: &Value,
    alert_name: &str,
    title: &str,
    message: &str,
    notification_id: &str,
) -> Result<(), RouterError> {
    let now_secs = io.now_unix_secs();
    let now_rfc3339 = now_rfc3339(now_secs);
    let notification_date = Utc
        .timestamp_opt(now_secs, 0)
        .single()
        .unwrap_or_else(|| Utc.timestamp_opt(0, 0).single().unwrap())
        .format("%Y-%m-%d")
        .to_string();

    let chain = "ekko";
    let subnet = "default";
    let subject = format!("ducklake.notification_content.{chain}.{subnet}.write");

    let tx = batch.tx.as_ref();
    let (transaction_hash, from_address, to_address, block_number, value) = if let Some(tx) = tx {
        (
            Some(tx.hash.clone()),
            tx.from.clone(),
            tx.to.clone(),
            Some(tx.block_number),
            tx.value_wei
                .clone()
                .or_else(|| tx.value_native.map(|v| v.to_string())),
        )
    } else {
        (None, None, Some(target.address.clone()), None, None)
    };

    let priority = instance.priority.trim().to_lowercase();
    let alert_name = alert_name.trim();

    let details = serde_json::to_string(render_context)
        .map_err(|e| RouterError::json(format!("details: {e}")))?;
    let template_variables = serde_json::to_string(&instance.variable_values)
        .map_err(|e| RouterError::json(format!("template_variables: {e}")))?;
    let actions = serde_json::to_string(&Vec::<String>::new())
        .map_err(|e| RouterError::json(format!("actions: {e}")))?;
    let target_channels = serde_json::to_string(&vec!["webhook", "websocket", "telegram"])
        .map_err(|e| RouterError::json(format!("target_channels: {e}")))?;

    let payload = serde_json::json!({
        "notification_date": notification_date,
        "notification_id": notification_id,
        "user_id": user_id,
        "alert_id": batch.instance_id,
        "alert_name": alert_name,
        "title": title,
        "message": message,
        "priority": priority,
        "details": details,
        "template_name": format!("alert_instance:{}", batch.instance_id),
        "template_variables": template_variables,
        "actions": actions,
        "transaction_hash": transaction_hash,
        "chain_id": batch.partition.chain_id.to_string(),
        "block_number": block_number,
        "from_address": from_address,
        "to_address": to_address,
        "contract_address": Value::Null,
        "value": value,
        "value_usd": Value::Null,
        "target_channels": target_channels,
        "delivery_status": "pending",
        "channels_delivered": 0,
        "channels_failed": 0,
        "first_delivery_at": Value::Null,
        "all_delivered_at": Value::Null,
        "created_at": now_rfc3339,
    });

    let bytes =
        serde_json::to_vec(&payload).map_err(|e| RouterError::json(format!("content: {e}")))?;
    io.nats_publish(&subject, bytes)?;
    Ok(())
}

fn now_rfc3339(now_unix_secs: i64) -> String {
    Utc.timestamp_opt(now_unix_secs, 0)
        .single()
        .unwrap_or_else(|| Utc.timestamp_opt(0, 0).single().unwrap())
        .to_rfc3339()
}

fn chain_for_network(network: &str) -> &'static str {
    match network {
        "ETH" => "ethereum",
        "AVAX" => "avalanche",
        "SOL" => "solana",
        "BTC" => "bitcoin",
        _ => "unknown",
    }
}

fn flatten_to_string_map(root: &Value) -> HashMap<String, String> {
    let mut out = HashMap::new();
    let Some(obj) = root.as_object() else {
        return out;
    };

    for (k, v) in obj {
        flatten_value(&mut out, k, v);
    }
    out
}

fn flatten_value(out: &mut HashMap<String, String>, prefix: &str, value: &Value) {
    match value {
        Value::Object(map) => {
            for (k, v) in map {
                let next = format!("{}.{}", prefix, k);
                flatten_value(out, &next, v);
            }
        }
        Value::Array(_) => {
            out.insert(prefix.to_string(), value.to_string());
        }
        other => {
            out.insert(prefix.to_string(), value_to_string(other));
        }
    }
}

fn truncate_hex_addresses_in_text(input: &str) -> String {
    let bytes = input.as_bytes();
    let mut out = String::with_capacity(input.len());
    let mut i = 0usize;

    while i < bytes.len() {
        if bytes[i] == b'0' && i + 1 < bytes.len() && bytes[i + 1] == b'x' {
            let start = i;
            let mut j = i + 2;
            let mut count = 0usize;
            while j < bytes.len() && is_hex(bytes[j]) {
                count += 1;
                j += 1;
            }
            if count == 40 {
                let end = start + 2 + count;
                if end <= input.len() {
                    let addr = &input[start..end];
                    out.push_str(&short_address(addr));
                    i = end;
                    continue;
                }
            }
        }

        out.push(bytes[i] as char);
        i += 1;
    }

    out
}

fn is_hex(byte: u8) -> bool {
    matches!(byte, b'0'..=b'9' | b'a'..=b'f' | b'A'..=b'F')
}

fn parse_priority(priority: &str) -> WebhookAlertPriority {
    match priority.trim().to_lowercase().as_str() {
        "critical" => WebhookAlertPriority::Critical,
        "high" => WebhookAlertPriority::High,
        "low" => WebhookAlertPriority::Low,
        _ => WebhookAlertPriority::Normal,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;
    use pretty_assertions::assert_eq;
    use std::collections::HashMap;
    use std::sync::Mutex;

    #[test]
    fn renders_dotted_placeholders() {
        let ctx = serde_json::json!({
            "instance_id": "i1",
            "target": {"key": "ETH:mainnet:0xabc", "short": "0xabc…c"},
            "balance_latest": 0.4
        });

        let out = render_template(
            "Alert {{instance_id}} for {{target.key}} bal={{balance_latest}}",
            &ctx,
        )
        .unwrap();
        assert_eq!(out, "Alert i1 for ETH:mainnet:0xabc bal=0.4");
    }

    #[test]
    fn parses_target_key() {
        let parsed = parse_target_key("ETH:mainnet:0xabc").unwrap();
        assert_eq!(parsed.network, "ETH");
        assert_eq!(parsed.subnet, "mainnet");
        assert_eq!(parsed.address, "0xabc");
    }

    #[test]
    fn render_context_includes_trigger_and_vars_aliases() {
        let batch = AlertTriggeredBatchV1 {
            schema_version: alert_triggered_batch_schema_version_v1(),
            job_id: "job1".to_string(),
            run_id: "run1".to_string(),
            instance_id: "inst1".to_string(),
            partition: alert_runtime_common::PartitionV1 {
                network: "ETH".to_string(),
                subnet: "mainnet".to_string(),
                chain_id: 1,
            },
            schedule: None,
            tx: Some(alert_runtime_common::EvaluationTxV1 {
                kind: alert_runtime_common::TxKindV1::Tx,
                hash: "0xhash".to_string(),
                from: Some("0x111".to_string()),
                to: Some("0x222".to_string()),
                method_selector: None,
                value_wei: None,
                value_native: None,
                log_index: None,
                log_address: None,
                topic0: None,
                topic1: None,
                topic2: None,
                topic3: None,
                data: None,
                block_number: 1,
                block_timestamp: Utc.timestamp_opt(0, 0).unwrap(),
            }),
            matches: vec![],
        };

        let instance: InstanceSnapshotV1 = serde_json::from_value(serde_json::json!({
            "instance_id": "inst1",
            "alert_name": "Balance Alert",
            "user_id": "u1",
            "enabled": true,
            "priority": "normal",
            "variable_values": { "wallet_address": "0x222" },
            "notification_template": { "title": "t", "body": "b" },
            "action": {
                "notification_policy": "per_matched_target",
                "cooldown_secs": 0,
                "cooldown_key_template": "x",
                "dedupe_key_template": "y"
            }
        }))
        .unwrap();

        let target = parse_target_key("ETH:mainnet:0x222").unwrap();
        let ctx = build_render_context(&batch, &instance, &target, &serde_json::json!({})).unwrap();

        assert_eq!(
            lookup_path(&ctx, "vars.wallet_address").unwrap(),
            Value::String("0x222".to_string())
        );
        assert_eq!(
            lookup_path(&ctx, "alert_name").unwrap(),
            Value::String("Balance Alert".to_string())
        );
        assert_eq!(
            lookup_path(&ctx, "trigger.network_id").unwrap(),
            Value::Number(1.into())
        );
        assert_eq!(
            lookup_path(&ctx, "trigger.address").unwrap(),
            Value::String("0x222".to_string())
        );
        assert_eq!(
            lookup_path(&ctx, "trigger.to").unwrap(),
            Value::String("0x222".to_string())
        );
    }

    #[test]
    fn truncates_hex_addresses_only() {
        let addr = "0x1234567890abcdef1234567890abcdef12345678";
        let tx = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd";
        let input = format!("from {} tx {}", addr, tx);
        let output = truncate_hex_addresses_in_text(&input);
        assert!(output.contains("0x1234…5678"));
        assert!(output.contains(tx));
    }

    #[test]
    fn publishes_notification_content_payload() {
        let io = MockRuntime::new(1_700_000_000);
        let instance: InstanceSnapshotV1 = serde_json::from_value(serde_json::json!({
            "instance_id": "inst1",
            "alert_name": "Test Alert",
            "user_id": "u1",
            "enabled": true,
            "priority": "normal",
            "variable_values": { "threshold": 2 },
            "notification_template": { "title": "T", "body": "B" },
            "action": {
                "notification_policy": "per_matched_target",
                "cooldown_secs": 0,
                "cooldown_key_template": "x",
                "dedupe_key_template": "y"
            }
        }))
        .unwrap();

        let batch = AlertTriggeredBatchV1 {
            schema_version: alert_triggered_batch_schema_version_v1(),
            job_id: "job1".to_string(),
            run_id: "run1".to_string(),
            instance_id: "inst1".to_string(),
            partition: alert_runtime_common::PartitionV1 {
                network: "ETH".to_string(),
                subnet: "mainnet".to_string(),
                chain_id: 1,
            },
            schedule: None,
            tx: None,
            matches: vec![],
        };

        let target = parse_target_key("ETH:mainnet:0xabc").unwrap();
        let ctx = serde_json::json!({ "k": "v" });

        publish_notification_content(
            &io,
            &instance,
            &batch,
            "u1",
            &target,
            &ctx,
            "Test Alert",
            "Title",
            "Message",
            "notif-1",
        )
        .unwrap();

        let published = io.published();
        let content = published
            .iter()
            .find(|(subject, _)| subject == "ducklake.notification_content.ekko.default.write")
            .map(|(_, body)| body.clone())
            .expect("notification content not published");

        assert_eq!(content["notification_id"], "notif-1");
        assert_eq!(content["user_id"], "u1");
        assert_eq!(content["alert_name"], "Test Alert");
        assert!(content["details"].is_string());
        assert!(content["template_variables"].is_string());
        assert!(content["target_channels"].is_string());
    }

    struct MockRuntime {
        kv: Mutex<HashMap<String, Vec<u8>>>,
        incr: Mutex<HashMap<String, u64>>,
        published: Mutex<Vec<(String, Vec<u8>)>>,
        now: i64,
    }

    impl MockRuntime {
        fn new(now: i64) -> Self {
            Self {
                kv: Mutex::new(HashMap::new()),
                incr: Mutex::new(HashMap::new()),
                published: Mutex::new(Vec::new()),
                now,
            }
        }

        fn put_json(&self, key: &str, value: serde_json::Value) {
            let bytes = serde_json::to_vec(&value).unwrap();
            self.kv.lock().unwrap().insert(key.to_string(), bytes);
        }

        fn published(&self) -> Vec<(String, serde_json::Value)> {
            self.published
                .lock()
                .unwrap()
                .iter()
                .map(|(subj, body)| (subj.clone(), serde_json::from_slice(body).unwrap()))
                .collect()
        }
    }

    impl RuntimeIO for MockRuntime {
        fn kv_get(&self, key: &str) -> Result<Option<Vec<u8>>, RouterError> {
            Ok(self.kv.lock().unwrap().get(key).cloned())
        }

        fn kv_set(&self, key: &str, value: Vec<u8>) -> Result<(), RouterError> {
            self.kv.lock().unwrap().insert(key.to_string(), value);
            Ok(())
        }

        fn kv_exists(&self, key: &str) -> Result<bool, RouterError> {
            Ok(self.kv.lock().unwrap().contains_key(key))
        }

        fn kv_incr(&self, key: &str, delta: u64) -> Result<u64, RouterError> {
            let mut map = self.incr.lock().unwrap();
            let current = map.entry(key.to_string()).or_insert(0);
            *current += delta;
            Ok(*current)
        }

        fn nats_publish(&self, subject: &str, body: Vec<u8>) -> Result<(), RouterError> {
            self.published
                .lock()
                .unwrap()
                .push((subject.to_string(), body));
            Ok(())
        }

        fn now_unix_secs(&self) -> i64 {
            self.now
        }
    }

    #[test]
    fn routes_matches_and_publishes_per_recipient() {
        let io = MockRuntime::new(1_000);

        io.put_json(
            "alerts:instance:inst1",
            serde_json::json!({
                "instance_id": "inst1",
                "alert_name": "Threshold Alert",
                "user_id": "u1",
                "enabled": true,
                "priority": "high",
                "variable_values": { "threshold": 0.5 },
                "notification_template": { "title": "T {{target.short}}", "body": "B {{balance_latest}} < {{threshold}}" },
                "action": {
                    "notification_policy": "per_matched_target",
                    "cooldown_secs": 0,
                    "cooldown_key_template": "x",
                    "dedupe_key_template": "{{run_id}}:{{target.key}}"
                }
            }),
        );

        io.put_json(
            "alerts:instance:subscribers:inst1",
            serde_json::json!(["u1", "u2"]),
        );

        let batch = AlertTriggeredBatchV1 {
            schema_version: alert_triggered_batch_schema_version_v1(),
            job_id: "job1".to_string(),
            run_id: "run1".to_string(),
            instance_id: "inst1".to_string(),
            partition: alert_runtime_common::PartitionV1 {
                network: "ETH".to_string(),
                subnet: "mainnet".to_string(),
                chain_id: 1,
            },
            schedule: None,
            tx: None,
            matches: vec![alert_runtime_common::AlertTriggeredMatchV1 {
                target_key: "ETH:mainnet:0xabc".to_string(),
                match_context: serde_json::json!({ "balance_latest": 0.4 }),
            }],
        };

        let bytes = serde_json::to_vec(&batch).unwrap();
        handle_nats_message(&io, "alerts.triggered.ETH.mainnet", &bytes).unwrap();

        let published = io.published();
        assert_eq!(published.len(), 8);

        let mut counts = HashMap::new();
        for (subject, v) in published {
            *counts.entry(subject.clone()).or_insert(0usize) += 1;

            if subject == "notifications.send.immediate.webhook" {
                assert_eq!(v["alert_id"], "inst1");
                assert_eq!(v["alert_name"], "Threshold Alert");
                assert_eq!(v["priority"], "high");
                assert_eq!(v["payload"]["title"], "T 0xabc");
                assert_eq!(v["payload"]["body"], "B 0.4 < 0.5");
            } else if subject == "notifications.send.immediate.websocket" {
                assert_eq!(v["alert_id"], "inst1");
                assert_eq!(v["priority"], "high");
                assert_eq!(v["subject"], "T 0xabc");
                assert_eq!(v["message"], "B 0.4 < 0.5");
            } else if subject == "notifications.send.immediate.telegram" {
                assert_eq!(v["alert_id"], "inst1");
                assert_eq!(v["alert_name"], "Threshold Alert");
                assert_eq!(v["priority"], "high");
                assert_eq!(v["message"], "B 0.4 < 0.5");
                assert_eq!(v["chain"], "ethereum.mainnet");
                assert_eq!(v["wallet_address"], "0xabc");
            } else if subject == "ducklake.notification_content.ekko.default.write" {
                assert_eq!(v["alert_id"], "inst1");
                assert_eq!(v["alert_name"], "Threshold Alert");
                assert_eq!(v["priority"], "high");
                assert_eq!(v["title"], "T 0xabc");
                assert_eq!(v["message"], "B 0.4 < 0.5");
            } else {
                panic!("unexpected subject {}", subject);
            }
        }

        assert_eq!(counts.get("notifications.send.immediate.webhook"), Some(&2));
        assert_eq!(
            counts.get("notifications.send.immediate.websocket"),
            Some(&2)
        );
        assert_eq!(
            counts.get("notifications.send.immediate.telegram"),
            Some(&2)
        );
        assert_eq!(
            counts.get("ducklake.notification_content.ekko.default.write"),
            Some(&2)
        );

        // Replaying the same batch should be deduped per subscriber.
        handle_nats_message(&io, "alerts.triggered.ETH.mainnet", &bytes).unwrap();
        assert_eq!(io.published().len(), 8);
    }

    #[test]
    fn falls_back_to_alert_name_when_template_empty() {
        let io = MockRuntime::new(1_000);

        io.put_json(
            "alerts:instance:inst1",
            serde_json::json!({
                "instance_id": "inst1",
                "alert_name": "Alert Name",
                "user_id": "u1",
                "enabled": true,
                "priority": "normal",
                "variable_values": {},
                "notification_template": { "title": "", "body": "" },
                "action": {
                    "notification_policy": "per_matched_target",
                    "cooldown_secs": 0,
                    "cooldown_key_template": "x",
                    "dedupe_key_template": "{{run_id}}:{{target.key}}"
                }
            }),
        );

        io.put_json(
            "alerts:instance:subscribers:inst1",
            serde_json::json!(["u1"]),
        );

        let batch = AlertTriggeredBatchV1 {
            schema_version: alert_triggered_batch_schema_version_v1(),
            job_id: "job1".to_string(),
            run_id: "run1".to_string(),
            instance_id: "inst1".to_string(),
            partition: alert_runtime_common::PartitionV1 {
                network: "ETH".to_string(),
                subnet: "mainnet".to_string(),
                chain_id: 1,
            },
            schedule: None,
            tx: None,
            matches: vec![alert_runtime_common::AlertTriggeredMatchV1 {
                target_key: "ETH:mainnet:0xabc".to_string(),
                match_context: serde_json::json!({}),
            }],
        };

        let bytes = serde_json::to_vec(&batch).unwrap();
        handle_nats_message(&io, "alerts.triggered.ETH.mainnet", &bytes).unwrap();

        let published = io.published();
        let content = published
            .iter()
            .find(|(subject, _)| subject == "ducklake.notification_content.ekko.default.write")
            .map(|(_, body)| body.clone())
            .expect("notification content not published");

        assert_eq!(content["title"], "Alert Name");
        assert_eq!(content["message"], "Alert Name");

        let websocket = published
            .iter()
            .find(|(subject, _)| subject == "notifications.send.immediate.websocket")
            .map(|(_, body)| body.clone())
            .expect("websocket notification not published");

        assert_eq!(websocket["subject"], "Alert Name");
        assert_eq!(websocket["message"], "Alert Name");
    }

    #[test]
    fn cooldown_suppresses_across_runs() {
        let io = MockRuntime::new(1_000);

        io.put_json(
            "alerts:instance:inst1",
            serde_json::json!({
                "instance_id": "inst1",
                "user_id": "u1",
                "enabled": true,
                "priority": "normal",
                "variable_values": {},
                "notification_template": { "title": "T", "body": "B {{x}}" },
                "action": {
                    "notification_policy": "per_matched_target",
                    "cooldown_secs": 60,
                    "cooldown_key_template": "{{instance_id}}:{{target.key}}",
                    "dedupe_key_template": "{{run_id}}:{{instance_id}}:{{target.key}}"
                }
            }),
        );

        let base = AlertTriggeredBatchV1 {
            schema_version: alert_triggered_batch_schema_version_v1(),
            job_id: "job1".to_string(),
            run_id: "run1".to_string(),
            instance_id: "inst1".to_string(),
            partition: alert_runtime_common::PartitionV1 {
                network: "ETH".to_string(),
                subnet: "mainnet".to_string(),
                chain_id: 1,
            },
            schedule: None,
            tx: None,
            matches: vec![alert_runtime_common::AlertTriggeredMatchV1 {
                target_key: "ETH:mainnet:0xabc".to_string(),
                match_context: serde_json::json!({ "x": 1 }),
            }],
        };

        let bytes1 = serde_json::to_vec(&base).unwrap();
        handle_nats_message(&io, "alerts.triggered.ETH.mainnet", &bytes1).unwrap();
        assert_eq!(io.published().len(), 4);

        let bytes2 = serde_json::to_vec(&AlertTriggeredBatchV1 {
            run_id: "run2".to_string(),
            job_id: "job2".to_string(),
            ..base
        })
        .unwrap();
        handle_nats_message(&io, "alerts.triggered.ETH.mainnet", &bytes2).unwrap();
        assert_eq!(io.published().len(), 4);
    }
}
