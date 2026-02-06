use crate::{AlertSchedulerError, RedisManager, Result};
use async_trait::async_trait;
use redis::AsyncCommands;
use serde::Deserialize;
use serde_json::Value;
use std::sync::Arc;

use alert_runtime_common::{AlertExecutableV1, AlertTemplateV1};

#[derive(Debug, Clone, Deserialize)]
pub struct TargetSelectorSnapshot {
    pub mode: String,
    #[serde(default)]
    pub group_id: Option<String>,
    #[serde(default)]
    pub keys: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct InstanceSnapshot {
    pub instance_id: String,
    pub user_id: Value,
    pub enabled: bool,
    pub priority: String,
    #[serde(default)]
    pub template_id: Option<String>,
    #[serde(default)]
    pub template_version: Option<i64>,
    pub trigger_type: String,
    #[serde(default)]
    pub trigger_config: Value,
    pub target_selector: TargetSelectorSnapshot,
    #[serde(default)]
    pub variable_values: Value,
}

pub struct RuntimeStore {
    redis: Arc<RedisManager>,
}

#[async_trait]
pub trait RuntimeStoreOps: Send + Sync {
    async fn get_instance(&self, instance_id: &str) -> Result<InstanceSnapshot>;
    async fn get_template(
        &self,
        template_id: &str,
        template_version: i64,
    ) -> Result<AlertTemplateV1>;
    async fn get_executable(
        &self,
        template_id: &str,
        template_version: i64,
    ) -> Result<AlertExecutableV1>;
    async fn scan_instance_keys(&self, cursor: u64, count: u32) -> Result<(u64, Vec<String>)>;
    async fn zrangebyscore_withscores(
        &self,
        key: &str,
        max_score: i64,
        limit: usize,
    ) -> Result<Vec<(String, i64)>>;
    async fn zadd_nx(&self, key: &str, member: &str, score: i64) -> Result<()>;
    async fn zadd_xx(&self, key: &str, member: &str, score: i64) -> Result<()>;
    async fn zrem(&self, key: &str, member: &str) -> Result<()>;
    async fn zscore(&self, key: &str, member: &str) -> Result<Option<i64>>;
    async fn smembers(&self, key: &str) -> Result<Vec<String>>;
    async fn set_nx_ex(&self, key: &str, value: &str, ttl_secs: usize) -> Result<bool>;
    async fn sscan(&self, key: &str, cursor: u64, count: usize) -> Result<(u64, Vec<String>)>;
    async fn exists(&self, key: &str) -> Result<bool>;
}

impl RuntimeStore {
    pub fn new(redis: Arc<RedisManager>) -> Self {
        Self { redis }
    }

    pub async fn get_instance(&self, instance_id: &str) -> Result<InstanceSnapshot> {
        let mut conn = self.redis.get_connection().await?;
        let key = format!("alerts:instance:{}", instance_id);
        let raw: Option<String> = conn
            .get(&key)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        let Some(raw) = raw else {
            return Err(AlertSchedulerError::AlertNotFound(instance_id.to_string()));
        };

        let instance: InstanceSnapshot = serde_json::from_str(&raw)?;
        Ok(instance)
    }

    pub async fn get_template(
        &self,
        template_id: &str,
        template_version: i64,
    ) -> Result<AlertTemplateV1> {
        let mut conn = self.redis.get_connection().await?;
        let key = format!("alerts:template:{}:{}", template_id, template_version);
        let raw: Option<String> = conn
            .get(&key)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        let Some(raw) = raw else {
            return Err(AlertSchedulerError::InvalidAlertData(format!(
                "template spec missing in redis for {}:{}",
                template_id, template_version
            )));
        };

        let template: AlertTemplateV1 = serde_json::from_str(&raw)?;
        Ok(template)
    }

    pub async fn get_executable(
        &self,
        template_id: &str,
        template_version: i64,
    ) -> Result<AlertExecutableV1> {
        let mut conn = self.redis.get_connection().await?;
        let key = format!("alerts:executable:{}:{}", template_id, template_version);
        let raw: Option<String> = conn
            .get(&key)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        let Some(raw) = raw else {
            return Err(AlertSchedulerError::InvalidAlertData(format!(
                "executable missing in redis for {}:{}",
                template_id, template_version
            )));
        };

        let executable: AlertExecutableV1 = serde_json::from_str(&raw)?;
        Ok(executable)
    }

    pub async fn scan_instance_keys(&self, cursor: u64, count: u32) -> Result<(u64, Vec<String>)> {
        let mut conn = self.redis.get_connection().await?;
        let mut cmd = redis::cmd("SCAN");
        cmd.arg(cursor)
            .arg("MATCH")
            .arg("alerts:instance:*")
            .arg("COUNT")
            .arg(count);
        let (next, keys): (u64, Vec<String>) = cmd
            .query_async(&mut conn)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok((next, keys))
    }

    pub async fn zrangebyscore_withscores(
        &self,
        key: &str,
        max_score: i64,
        limit: usize,
    ) -> Result<Vec<(String, i64)>> {
        let mut conn = self.redis.get_connection().await?;
        let mut cmd = redis::cmd("ZRANGEBYSCORE");
        cmd.arg(key)
            .arg("-inf")
            .arg(max_score)
            .arg("WITHSCORES")
            .arg("LIMIT")
            .arg(0)
            .arg(limit);
        let raw: Vec<(String, f64)> = cmd
            .query_async(&mut conn)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok(raw
            .into_iter()
            .map(|(member, score)| (member, score as i64))
            .collect())
    }

    pub async fn zadd_nx(&self, key: &str, member: &str, score: i64) -> Result<()> {
        let mut conn = self.redis.get_connection().await?;
        let mut cmd = redis::cmd("ZADD");
        cmd.arg(key).arg("NX").arg(score).arg(member);
        cmd.query_async::<_, ()>(&mut conn)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok(())
    }

    pub async fn zadd_xx(&self, key: &str, member: &str, score: i64) -> Result<()> {
        let mut conn = self.redis.get_connection().await?;
        let mut cmd = redis::cmd("ZADD");
        cmd.arg(key).arg("XX").arg(score).arg(member);
        cmd.query_async::<_, ()>(&mut conn)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok(())
    }

    pub async fn zrem(&self, key: &str, member: &str) -> Result<()> {
        let mut conn = self.redis.get_connection().await?;
        let _: i64 = conn
            .zrem(key, member)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok(())
    }

    pub async fn zscore(&self, key: &str, member: &str) -> Result<Option<i64>> {
        let mut conn = self.redis.get_connection().await?;
        let score: Option<f64> = conn
            .zscore(key, member)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok(score.map(|s| s as i64))
    }

    pub async fn smembers(&self, key: &str) -> Result<Vec<String>> {
        let mut conn = self.redis.get_connection().await?;
        let members: Vec<String> = conn
            .smembers(key)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok(members)
    }

    pub async fn set_nx_ex(&self, key: &str, value: &str, ttl_secs: usize) -> Result<bool> {
        let mut conn = self.redis.get_connection().await?;
        let mut cmd = redis::cmd("SET");
        cmd.arg(key).arg(value).arg("NX").arg("EX").arg(ttl_secs);
        let result: Option<String> = cmd
            .query_async(&mut conn)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok(result.is_some())
    }

    pub async fn sadd(&self, key: &str, member: &str) -> Result<()> {
        let mut conn = self.redis.get_connection().await?;
        let _: i64 = conn
            .sadd(key, member)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok(())
    }

    pub async fn sscan(&self, key: &str, cursor: u64, count: usize) -> Result<(u64, Vec<String>)> {
        let mut conn = self.redis.get_connection().await?;
        let mut cmd = redis::cmd("SSCAN");
        cmd.arg(key).arg(cursor).arg("COUNT").arg(count);
        let (next, members): (u64, Vec<String>) = cmd
            .query_async(&mut conn)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok((next, members))
    }

    pub async fn exists(&self, key: &str) -> Result<bool> {
        let mut conn = self.redis.get_connection().await?;
        let exists: i64 = conn
            .exists(key)
            .await
            .map_err(AlertSchedulerError::RedisConnection)?;
        Ok(exists > 0)
    }
}

#[async_trait]
impl RuntimeStoreOps for RuntimeStore {
    async fn get_instance(&self, instance_id: &str) -> Result<InstanceSnapshot> {
        RuntimeStore::get_instance(self, instance_id).await
    }

    async fn get_template(
        &self,
        template_id: &str,
        template_version: i64,
    ) -> Result<AlertTemplateV1> {
        RuntimeStore::get_template(self, template_id, template_version).await
    }

    async fn get_executable(
        &self,
        template_id: &str,
        template_version: i64,
    ) -> Result<AlertExecutableV1> {
        RuntimeStore::get_executable(self, template_id, template_version).await
    }

    async fn scan_instance_keys(&self, cursor: u64, count: u32) -> Result<(u64, Vec<String>)> {
        RuntimeStore::scan_instance_keys(self, cursor, count).await
    }

    async fn zrangebyscore_withscores(
        &self,
        key: &str,
        max_score: i64,
        limit: usize,
    ) -> Result<Vec<(String, i64)>> {
        RuntimeStore::zrangebyscore_withscores(self, key, max_score, limit).await
    }

    async fn zadd_nx(&self, key: &str, member: &str, score: i64) -> Result<()> {
        RuntimeStore::zadd_nx(self, key, member, score).await
    }

    async fn zadd_xx(&self, key: &str, member: &str, score: i64) -> Result<()> {
        RuntimeStore::zadd_xx(self, key, member, score).await
    }

    async fn zrem(&self, key: &str, member: &str) -> Result<()> {
        RuntimeStore::zrem(self, key, member).await
    }

    async fn zscore(&self, key: &str, member: &str) -> Result<Option<i64>> {
        RuntimeStore::zscore(self, key, member).await
    }

    async fn smembers(&self, key: &str) -> Result<Vec<String>> {
        RuntimeStore::smembers(self, key).await
    }

    async fn set_nx_ex(&self, key: &str, value: &str, ttl_secs: usize) -> Result<bool> {
        RuntimeStore::set_nx_ex(self, key, value, ttl_secs).await
    }

    async fn sscan(&self, key: &str, cursor: u64, count: usize) -> Result<(u64, Vec<String>)> {
        RuntimeStore::sscan(self, key, cursor, count).await
    }

    async fn exists(&self, key: &str) -> Result<bool> {
        RuntimeStore::exists(self, key).await
    }
}
