use chrono::{Duration, Utc};
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{self, Duration as TokioDuration};

/// Heartbeat manager for WebSocket connections
pub struct HeartbeatManager {
    interval_seconds: u64,
    timeout_seconds: u64,
    last_pings: Arc<RwLock<std::collections::HashMap<String, chrono::DateTime<Utc>>>>,
}

impl HeartbeatManager {
    pub fn new(interval_seconds: u64, timeout_seconds: u64) -> Self {
        Self {
            interval_seconds,
            timeout_seconds,
            last_pings: Arc::new(RwLock::new(std::collections::HashMap::new())),
        }
    }

    /// Record a ping from a connection
    pub async fn record_ping(&self, connection_id: &str) {
        let mut pings = self.last_pings.write().await;
        pings.insert(connection_id.to_string(), Utc::now());
    }

    /// Check if a connection is alive
    pub async fn is_connection_alive(&self, connection_id: &str) -> bool {
        let pings = self.last_pings.read().await;
        if let Some(last_ping) = pings.get(connection_id) {
            let elapsed = Utc::now() - *last_ping;
            elapsed.num_seconds() < self.timeout_seconds as i64
        } else {
            false
        }
    }

    /// Get stale connections
    pub async fn get_stale_connections(&self) -> Vec<String> {
        let pings = self.last_pings.read().await;
        let now = Utc::now();
        let timeout = Duration::seconds(self.timeout_seconds as i64);

        pings
            .iter()
            .filter(|(_, last_ping)| now - **last_ping > timeout)
            .map(|(id, _)| id.clone())
            .collect()
    }

    /// Remove connection from tracking
    pub async fn remove_connection(&self, connection_id: &str) {
        let mut pings = self.last_pings.write().await;
        pings.remove(connection_id);
    }
}

/// Reconnection manager with exponential backoff
pub struct ReconnectionManager {
    max_attempts: u32,
    base_delay_ms: u64,
    max_delay_ms: u64,
}

impl ReconnectionManager {
    pub fn new(max_attempts: u32, base_delay_ms: u64, max_delay_ms: u64) -> Self {
        Self {
            max_attempts,
            base_delay_ms,
            max_delay_ms,
        }
    }

    /// Calculate delay for nth attempt using exponential backoff
    pub fn calculate_delay(&self, attempt: u32) -> u64 {
        if attempt >= self.max_attempts {
            return 0; // No more retries
        }

        let delay = self.base_delay_ms * 2_u64.pow(attempt);
        delay.min(self.max_delay_ms)
    }

    /// Should retry based on attempt number
    pub fn should_retry(&self, attempt: u32) -> bool {
        attempt < self.max_attempts
    }

    /// Get reconnection window duration
    pub fn get_reconnection_window(&self) -> Duration {
        // Calculate total time for all attempts
        let mut total_ms = 0u64;
        for i in 0..self.max_attempts {
            total_ms += self.calculate_delay(i);
        }
        Duration::milliseconds(total_ms as i64)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_ping_pong() {
        let heartbeat = HeartbeatManager::new(30, 60);
        
        // Record ping
        heartbeat.record_ping("conn_1").await;
        
        // Check if alive immediately
        assert!(heartbeat.is_connection_alive("conn_1").await);
        
        // Check non-existent connection
        assert!(!heartbeat.is_connection_alive("conn_999").await);
    }

    #[tokio::test]
    async fn test_stale_connection_detection() {
        let heartbeat = HeartbeatManager::new(30, 60);
        
        // Add connections with different ping times
        heartbeat.record_ping("conn_1").await;
        
        // Manually set an old ping time for testing
        {
            let mut pings = heartbeat.last_pings.write().await;
            pings.insert(
                "conn_2".to_string(),
                Utc::now() - Duration::seconds(120), // 2 minutes ago
            );
        }
        
        // Check stale connections
        let stale = heartbeat.get_stale_connections().await;
        assert_eq!(stale.len(), 1);
        assert!(stale.contains(&"conn_2".to_string()));
        assert!(!stale.contains(&"conn_1".to_string()));
    }

    #[tokio::test]
    async fn test_heartbeat_timeout() {
        let heartbeat = HeartbeatManager::new(30, 2); // 2 second timeout for testing
        
        heartbeat.record_ping("conn_1").await;
        assert!(heartbeat.is_connection_alive("conn_1").await);
        
        // Wait for timeout
        tokio::time::sleep(TokioDuration::from_secs(3)).await;
        
        assert!(!heartbeat.is_connection_alive("conn_1").await);
    }

    #[tokio::test]
    async fn test_remove_connection() {
        let heartbeat = HeartbeatManager::new(30, 60);
        
        heartbeat.record_ping("conn_1").await;
        assert!(heartbeat.is_connection_alive("conn_1").await);
        
        heartbeat.remove_connection("conn_1").await;
        assert!(!heartbeat.is_connection_alive("conn_1").await);
    }

    #[test]
    fn test_backoff() {
        let reconnect = ReconnectionManager::new(5, 1000, 30000);
        
        // Test exponential backoff
        assert_eq!(reconnect.calculate_delay(0), 1000);  // 1s
        assert_eq!(reconnect.calculate_delay(1), 2000);  // 2s
        assert_eq!(reconnect.calculate_delay(2), 4000);  // 4s
        assert_eq!(reconnect.calculate_delay(3), 8000);  // 8s
        assert_eq!(reconnect.calculate_delay(4), 16000); // 16s
        
        // Max delay cap
        assert_eq!(reconnect.calculate_delay(10), 0); // Beyond max attempts
    }

    #[test]
    fn test_max_delay_cap() {
        let reconnect = ReconnectionManager::new(10, 1000, 5000);
        
        // Should cap at max_delay_ms
        assert_eq!(reconnect.calculate_delay(0), 1000);
        assert_eq!(reconnect.calculate_delay(1), 2000);
        assert_eq!(reconnect.calculate_delay(2), 4000);
        assert_eq!(reconnect.calculate_delay(3), 5000); // Capped at 5000
        assert_eq!(reconnect.calculate_delay(4), 5000); // Still capped
    }

    #[test]
    fn test_should_retry() {
        let reconnect = ReconnectionManager::new(3, 1000, 30000);
        
        assert!(reconnect.should_retry(0));
        assert!(reconnect.should_retry(1));
        assert!(reconnect.should_retry(2));
        assert!(!reconnect.should_retry(3)); // Max attempts reached
        assert!(!reconnect.should_retry(4));
    }

    #[test]
    fn test_reconnection_window() {
        let reconnect = ReconnectionManager::new(3, 1000, 30000);
        
        let window = reconnect.get_reconnection_window();
        // 1000 + 2000 + 4000 = 7000ms = 7 seconds
        assert_eq!(window.num_seconds(), 7);
    }

    #[tokio::test]
    async fn test_concurrent_ping_updates() {
        let heartbeat = Arc::new(HeartbeatManager::new(30, 60));
        let mut handles = vec![];
        
        // Spawn multiple tasks updating pings concurrently
        for i in 0..10 {
            let hb = heartbeat.clone();
            let handle = tokio::spawn(async move {
                let conn_id = format!("conn_{}", i);
                for _ in 0..5 {
                    hb.record_ping(&conn_id).await;
                    tokio::time::sleep(TokioDuration::from_millis(10)).await;
                }
            });
            handles.push(handle);
        }
        
        // Wait for all tasks
        for handle in handles {
            handle.await.unwrap();
        }
        
        // Verify all connections are alive
        for i in 0..10 {
            let conn_id = format!("conn_{}", i);
            assert!(heartbeat.is_connection_alive(&conn_id).await);
        }
    }

    #[tokio::test]
    async fn test_heartbeat_cleanup() {
        let heartbeat = HeartbeatManager::new(30, 1); // 1 second timeout
        
        // Add multiple connections
        for i in 0..5 {
            heartbeat.record_ping(&format!("conn_{}", i)).await;
        }
        
        // Update only some connections
        tokio::time::sleep(TokioDuration::from_secs(2)).await;
        heartbeat.record_ping("conn_0").await;
        heartbeat.record_ping("conn_2").await;
        
        // Check stale connections
        let stale = heartbeat.get_stale_connections().await;
        assert_eq!(stale.len(), 3);
        assert!(stale.contains(&"conn_1".to_string()));
        assert!(stale.contains(&"conn_3".to_string()));
        assert!(stale.contains(&"conn_4".to_string()));
        
        // Clean up stale connections
        for conn_id in stale {
            heartbeat.remove_connection(&conn_id).await;
        }
        
        // Verify only active connections remain
        assert!(heartbeat.is_connection_alive("conn_0").await);
        assert!(!heartbeat.is_connection_alive("conn_1").await);
        assert!(heartbeat.is_connection_alive("conn_2").await);
        assert!(!heartbeat.is_connection_alive("conn_3").await);
    }
}