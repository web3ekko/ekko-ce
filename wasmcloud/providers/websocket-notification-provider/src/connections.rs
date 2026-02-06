use crate::types::{
    Connection, ConnectionMetadata, DeviceType, NotificationFilters, ServerMessage,
};
use anyhow::{anyhow, Result};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};
use uuid::Uuid;

/// Connection manager for WebSocket connections
pub struct ConnectionManager {
    connections: Arc<RwLock<HashMap<String, Arc<Connection>>>>,
    user_connections: Arc<RwLock<HashMap<String, Vec<String>>>>,
}

impl ConnectionManager {
    pub fn new() -> Self {
        Self {
            connections: Arc::new(RwLock::new(HashMap::new())),
            user_connections: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Add a new connection
    pub async fn add_connection(&self, connection: Connection) -> Result<()> {
        let connection_id = connection.id.clone();
        let user_id = connection.user_id.clone();

        // Add to connections map
        {
            let mut connections = self.connections.write().await;
            connections.insert(connection_id.clone(), Arc::new(connection));
        }

        // Add to user connections map if authenticated
        if !user_id.is_empty() {
            let mut user_connections = self.user_connections.write().await;
            user_connections
                .entry(user_id.clone())
                .or_insert_with(Vec::new)
                .push(connection_id.clone());
        }

        info!("Added connection: {} for user: {}", connection_id, user_id);
        Ok(())
    }

    /// Remove a connection
    pub async fn remove_connection(&self, connection_id: &str) -> Result<()> {
        // Get connection to find user_id
        let user_id = {
            let connections = self.connections.read().await;
            connections
                .get(connection_id)
                .map(|c| c.user_id.clone())
                .unwrap_or_default()
        };

        // Remove from connections map
        {
            let mut connections = self.connections.write().await;
            connections.remove(connection_id);
        }

        // Remove from user connections map
        if !user_id.is_empty() {
            let mut user_connections = self.user_connections.write().await;
            if let Some(connections) = user_connections.get_mut(&user_id) {
                connections.retain(|id| id != connection_id);
                if connections.is_empty() {
                    user_connections.remove(&user_id);
                }
            }
        }

        info!(
            "Removed connection: {} for user: {}",
            connection_id, user_id
        );
        Ok(())
    }

    /// Get a connection by ID
    pub async fn get_connection(&self, connection_id: &str) -> Option<Arc<Connection>> {
        let connections = self.connections.read().await;
        connections.get(connection_id).cloned()
    }

    /// Get all connections for a user
    pub async fn get_user_connections(&self, user_id: &str) -> Vec<Arc<Connection>> {
        let user_connections = self.user_connections.read().await;
        let connections = self.connections.read().await;

        if let Some(connection_ids) = user_connections.get(user_id) {
            connection_ids
                .iter()
                .filter_map(|id| connections.get(id).cloned())
                .collect()
        } else {
            Vec::new()
        }
    }

    /// Get all active connections
    pub async fn get_all_connections(&self) -> Vec<Arc<Connection>> {
        let connections = self.connections.read().await;
        connections.values().cloned().collect()
    }

    /// Count total connections
    pub async fn count_connections(&self) -> usize {
        let connections = self.connections.read().await;
        connections.len()
    }

    /// Count connections for a user
    pub async fn count_user_connections(&self, user_id: &str) -> usize {
        let user_connections = self.user_connections.read().await;
        user_connections.get(user_id).map(|c| c.len()).unwrap_or(0)
    }

    /// Get connections by device type
    pub async fn get_connections_by_device(&self, device: DeviceType) -> Vec<Arc<Connection>> {
        let connections = self.connections.read().await;
        connections
            .values()
            .filter(|c| c.device == device)
            .cloned()
            .collect()
    }

    /// Update connection filters
    pub async fn update_connection_filters(
        &self,
        connection_id: &str,
        filters: NotificationFilters,
    ) -> Result<()> {
        let connections = self.connections.read().await;

        if let Some(connection) = connections.get(connection_id) {
            // In a real implementation, we'd update the connection's filters
            // For now, we'll just log it
            debug!(
                "Updated filters for connection {}: {:?}",
                connection_id, filters
            );
            Ok(())
        } else {
            Err(anyhow!("Connection not found"))
        }
    }

    /// Clean up stale connections (for testing purposes)
    pub async fn cleanup_stale_connections(&self, timeout_seconds: i64) -> usize {
        use chrono::{Duration, Utc};

        let now = Utc::now();
        let timeout = Duration::seconds(timeout_seconds);
        let mut removed_count = 0;

        let stale_connections: Vec<String> = {
            let connections = self.connections.read().await;
            connections
                .values()
                .filter(|c| now - c.last_ping > timeout)
                .map(|c| c.id.clone())
                .collect()
        };

        for connection_id in stale_connections {
            if self.remove_connection(&connection_id).await.is_ok() {
                removed_count += 1;
                warn!("Removed stale connection: {}", connection_id);
            }
        }

        removed_count
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    async fn create_test_connection(id: &str, user_id: &str, device: DeviceType) -> Connection {
        let mut connection = Connection::new(id.to_string(), "127.0.0.1".to_string());
        connection.user_id = user_id.to_string();
        connection.device = device;
        connection
    }

    #[tokio::test]
    async fn test_add_connection() {
        let manager = ConnectionManager::new();
        let connection = create_test_connection("conn_1", "user_123", DeviceType::Dashboard).await;

        let result = manager.add_connection(connection).await;
        assert!(result.is_ok());

        let count = manager.count_connections().await;
        assert_eq!(count, 1);

        let user_count = manager.count_user_connections("user_123").await;
        assert_eq!(user_count, 1);
    }

    #[tokio::test]
    async fn test_remove_connection() {
        let manager = ConnectionManager::new();
        let connection = create_test_connection("conn_1", "user_123", DeviceType::iOS).await;

        manager.add_connection(connection).await.unwrap();
        assert_eq!(manager.count_connections().await, 1);

        let result = manager.remove_connection("conn_1").await;
        assert!(result.is_ok());
        assert_eq!(manager.count_connections().await, 0);
        assert_eq!(manager.count_user_connections("user_123").await, 0);
    }

    #[tokio::test]
    async fn test_get_connection() {
        let manager = ConnectionManager::new();
        let connection = create_test_connection("conn_1", "user_123", DeviceType::Android).await;

        manager.add_connection(connection).await.unwrap();

        let retrieved = manager.get_connection("conn_1").await;
        assert!(retrieved.is_some());

        let conn = retrieved.unwrap();
        assert_eq!(conn.id, "conn_1");
        assert_eq!(conn.user_id, "user_123");
        assert_eq!(conn.device, DeviceType::Android);
    }

    #[tokio::test]
    async fn test_get_user_connections() {
        let manager = ConnectionManager::new();

        // Add multiple connections for same user
        let conn1 = create_test_connection("conn_1", "user_123", DeviceType::Dashboard).await;
        let conn2 = create_test_connection("conn_2", "user_123", DeviceType::iOS).await;
        let conn3 = create_test_connection("conn_3", "user_456", DeviceType::Android).await;

        manager.add_connection(conn1).await.unwrap();
        manager.add_connection(conn2).await.unwrap();
        manager.add_connection(conn3).await.unwrap();

        let user_connections = manager.get_user_connections("user_123").await;
        assert_eq!(user_connections.len(), 2);

        let user_456_connections = manager.get_user_connections("user_456").await;
        assert_eq!(user_456_connections.len(), 1);
    }

    #[tokio::test]
    async fn test_multi_device() {
        let manager = ConnectionManager::new();

        // Add connections from different devices
        let dashboard = create_test_connection("conn_1", "user_123", DeviceType::Dashboard).await;
        let ios = create_test_connection("conn_2", "user_123", DeviceType::iOS).await;
        let android = create_test_connection("conn_3", "user_123", DeviceType::Android).await;

        manager.add_connection(dashboard).await.unwrap();
        manager.add_connection(ios).await.unwrap();
        manager.add_connection(android).await.unwrap();

        let user_connections = manager.get_user_connections("user_123").await;
        assert_eq!(user_connections.len(), 3);

        // Verify different devices
        let devices: Vec<DeviceType> = user_connections.iter().map(|c| c.device.clone()).collect();

        assert!(devices.contains(&DeviceType::Dashboard));
        assert!(devices.contains(&DeviceType::iOS));
        assert!(devices.contains(&DeviceType::Android));
    }

    #[tokio::test]
    async fn test_get_connections_by_device() {
        let manager = ConnectionManager::new();

        let conn1 = create_test_connection("conn_1", "user_123", DeviceType::iOS).await;
        let conn2 = create_test_connection("conn_2", "user_456", DeviceType::iOS).await;
        let conn3 = create_test_connection("conn_3", "user_789", DeviceType::Dashboard).await;

        manager.add_connection(conn1).await.unwrap();
        manager.add_connection(conn2).await.unwrap();
        manager.add_connection(conn3).await.unwrap();

        let ios_connections = manager.get_connections_by_device(DeviceType::iOS).await;
        assert_eq!(ios_connections.len(), 2);

        let dashboard_connections = manager
            .get_connections_by_device(DeviceType::Dashboard)
            .await;
        assert_eq!(dashboard_connections.len(), 1);

        let android_connections = manager.get_connections_by_device(DeviceType::Android).await;
        assert_eq!(android_connections.len(), 0);
    }

    #[tokio::test]
    async fn test_update_connection_filters() {
        let manager = ConnectionManager::new();
        let connection = create_test_connection("conn_1", "user_123", DeviceType::Dashboard).await;

        manager.add_connection(connection).await.unwrap();

        let filters = NotificationFilters {
            priorities: Some(vec![
                crate::types::NotificationPriority::High,
                crate::types::NotificationPriority::Critical,
            ]),
            alert_ids: Some(vec!["alert_1".to_string(), "alert_2".to_string()]),
            chains: Some(vec!["ethereum".to_string()]),
        };

        let result = manager.update_connection_filters("conn_1", filters).await;
        assert!(result.is_ok());

        // Test with non-existent connection
        let filters2 = NotificationFilters::default();
        let result = manager
            .update_connection_filters("conn_999", filters2)
            .await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_cleanup_stale_connections() {
        let manager = ConnectionManager::new();

        // Create connections with different last_ping times
        let mut conn1 = create_test_connection("conn_1", "user_123", DeviceType::Dashboard).await;
        let mut conn2 = create_test_connection("conn_2", "user_456", DeviceType::iOS).await;

        // Make conn1 stale (last ping 2 hours ago)
        conn1.last_ping = Utc::now() - chrono::Duration::hours(2);

        manager.add_connection(conn1).await.unwrap();
        manager.add_connection(conn2).await.unwrap();

        assert_eq!(manager.count_connections().await, 2);

        // Clean up connections older than 1 hour
        let removed_count = manager.cleanup_stale_connections(3600).await;

        assert_eq!(removed_count, 1);
        assert_eq!(manager.count_connections().await, 1);

        // Verify the correct connection was removed
        let remaining = manager.get_connection("conn_2").await;
        assert!(remaining.is_some());

        let removed = manager.get_connection("conn_1").await;
        assert!(removed.is_none());
    }

    #[tokio::test]
    async fn test_concurrent_operations() {
        let manager = Arc::new(ConnectionManager::new());
        let mut handles = vec![];

        // Spawn multiple tasks adding connections concurrently
        for i in 0..10 {
            let manager_clone = manager.clone();
            let handle = tokio::spawn(async move {
                let connection = create_test_connection(
                    &format!("conn_{}", i),
                    &format!("user_{}", i % 3), // 3 different users
                    match i % 3 {
                        0 => DeviceType::Dashboard,
                        1 => DeviceType::iOS,
                        _ => DeviceType::Android,
                    },
                )
                .await;
                manager_clone.add_connection(connection).await
            });
            handles.push(handle);
        }

        // Wait for all tasks to complete
        for handle in handles {
            handle.await.unwrap().unwrap();
        }

        // Verify all connections were added
        assert_eq!(manager.count_connections().await, 10);

        // Verify user connection counts
        assert!(manager.count_user_connections("user_0").await >= 3);
        assert!(manager.count_user_connections("user_1").await >= 3);
        assert!(manager.count_user_connections("user_2").await >= 3);
    }
}
