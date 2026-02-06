use crate::auth::AuthService;
use crate::connections::ConnectionManager;
use crate::nats_handler::MessageSender;
use crate::provider::ProviderConfig;
use crate::types::{ClientMessage, DeviceType, ServerMessage};
use anyhow::{anyhow, Context, Result};
use futures_util::{SinkExt, StreamExt};
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::mpsc;
use tokio::time::{self, interval};
use tokio_tungstenite::{accept_async, tungstenite::Message, WebSocketStream};
use tracing::{debug, error, info, warn};
use uuid::Uuid;

/// WebSocket server for handling client connections
pub struct WebSocketServer {
    config: ProviderConfig,
    auth_service: Arc<AuthService>,
    connection_manager: Arc<ConnectionManager>,
    message_sender: Arc<WebSocketMessageSenderImpl>,
}

impl WebSocketServer {
    pub fn new(
        config: ProviderConfig,
        auth_service: Arc<AuthService>,
        connection_manager: Arc<ConnectionManager>,
        message_sender: Arc<WebSocketMessageSenderImpl>,
    ) -> Self {
        Self {
            config,
            auth_service,
            connection_manager,
            message_sender,
        }
    }

    /// Start the WebSocket server
    pub async fn start(&self) -> Result<()> {
        let addr: SocketAddr = format!("0.0.0.0:{}", self.config.websocket_port)
            .parse()
            .context("Failed to parse WebSocket listen address")?;
        let listener = TcpListener::bind(&addr)
            .await
            .with_context(|| format!("Failed to bind WebSocket server on {}", addr))?;
        info!("WebSocket server listening on {}", addr);

        loop {
            match listener.accept().await {
                Ok((stream, peer_addr)) => {
                    self.handle_connection(stream, peer_addr).await;
                }
                Err(e) => {
                    error!("WebSocket accept error: {}", e);
                    break;
                }
            }
        }

        Ok(())
    }

    /// Handle a new WebSocket connection
    async fn handle_connection(&self, stream: TcpStream, peer_addr: SocketAddr) {
        let ws_stream = match accept_async(stream).await {
            Ok(ws) => ws,
            Err(e) => {
                error!(
                    "Failed to accept WebSocket connection from {}: {}",
                    peer_addr, e
                );
                return;
            }
        };

        info!("New WebSocket connection from {}", peer_addr);

        let connection_id = Uuid::new_v4().to_string();
        let auth_service = self.auth_service.clone();
        let connection_manager = self.connection_manager.clone();
        let message_sender = self.message_sender.clone();
        let config = self.config.clone();

        tokio::spawn(async move {
            if let Err(e) = handle_client(
                ws_stream,
                connection_id.clone(),
                peer_addr,
                auth_service,
                connection_manager,
                message_sender.clone(),
                config,
            )
            .await
            {
                error!("Error handling client connection: {}", e);
            }
            // Ensure sender is unregistered on exit
            message_sender.unregister_sender(&connection_id).await;
        });
    }
}

/// Handle a single client connection
async fn handle_client(
    ws_stream: WebSocketStream<TcpStream>,
    connection_id: String,
    peer_addr: SocketAddr,
    auth_service: Arc<AuthService>,
    connection_manager: Arc<ConnectionManager>,
    message_sender: Arc<WebSocketMessageSenderImpl>,
    config: ProviderConfig,
) -> Result<()> {
    let (mut ws_sender, mut ws_receiver) = ws_stream.split();
    let (tx, mut rx) = mpsc::channel::<ServerMessage>(100);

    // Register the sender so NATS handler can send notifications to this connection
    message_sender
        .register_sender(connection_id.clone(), tx.clone())
        .await;
    info!("Registered sender for connection {}", connection_id);

    // Create connection state
    let mut connection_state = ConnectionState {
        id: connection_id.clone(),
        authenticated: false,
        user_id: None,
        device: DeviceType::Dashboard,
        peer_addr,
    };

    // Start heartbeat timer
    let mut heartbeat_interval = interval(Duration::from_secs(config.heartbeat_interval_secs));
    let mut last_pong = std::time::Instant::now();

    // Main connection loop
    loop {
        tokio::select! {
            // Handle incoming WebSocket messages
            msg = ws_receiver.next() => {
                match msg {
                    Some(Ok(Message::Text(text))) => {
                        if let Ok(client_msg) = serde_json::from_str::<ClientMessage>(&text) {
                            if let Err(e) = handle_client_message(
                                client_msg,
                                &mut connection_state,
                                &auth_service,
                                &connection_manager,
                                &tx,
                                &config,
                            ).await {
                                error!("Error handling client message: {}", e);
                                tx.send(ServerMessage::Error { message: e.to_string() }).await?;
                            }
                        }
                    }
                    Some(Ok(Message::Binary(bin))) => {
                        if let Ok(client_msg) = serde_json::from_slice::<ClientMessage>(&bin) {
                            if let Err(e) = handle_client_message(
                                client_msg,
                                &mut connection_state,
                                &auth_service,
                                &connection_manager,
                                &tx,
                                &config,
                            ).await {
                                error!("Error handling client message: {}", e);
                                tx.send(ServerMessage::Error { message: e.to_string() }).await?;
                            }
                        }
                    }
                    Some(Ok(Message::Ping(data))) => {
                        ws_sender.send(Message::Pong(data)).await?;
                    }
                    Some(Ok(Message::Pong(_))) => {
                        last_pong = std::time::Instant::now();
                        debug!("Received pong from connection {}", connection_id);
                    }
                    Some(Ok(Message::Close(_))) => {
                        info!("Connection {} closed by client", connection_id);
                        break;
                    }
                    Some(Err(e)) => {
                        error!("WebSocket error for connection {}: {}", connection_id, e);
                        break;
                    }
                    None => {
                        info!("Connection {} closed", connection_id);
                        break;
                    }
                    _ => {}
                }
            }

            // Handle outgoing messages
            msg = rx.recv() => {
                if let Some(server_msg) = msg {
                    let json = serde_json::to_string(&server_msg)?;
                    if let Err(e) = ws_sender.send(Message::Text(json)).await {
                        error!("Failed to send message to connection {}: {}", connection_id, e);
                        break;
                    }
                }
            }

            // Send heartbeat ping
            _ = heartbeat_interval.tick() => {
                if last_pong.elapsed() > Duration::from_secs(config.connection_timeout_secs) {
                    warn!("Connection {} timed out (no pong received)", connection_id);
                    break;
                }

                if let Err(e) = ws_sender.send(Message::Ping(vec![])).await {
                    error!("Failed to send ping to connection {}: {}", connection_id, e);
                    break;
                }
            }
        }
    }

    // Clean up connection
    // Unregister sender first so no more notifications can be sent
    message_sender.unregister_sender(&connection_id).await;
    info!("Unregistered sender for connection {}", connection_id);

    if let Some(user_id) = &connection_state.user_id {
        if let Err(e) = auth_service.disconnect(&connection_id, user_id).await {
            error!("Failed to disconnect {}: {}", connection_id, e);
        }

        connection_manager.remove_connection(&connection_id).await;
        info!(
            "Cleaned up connection {} for user {}",
            connection_id, user_id
        );
    }

    Ok(())
}

/// Handle a client message
async fn handle_client_message(
    message: ClientMessage,
    state: &mut ConnectionState,
    auth_service: &Arc<AuthService>,
    connection_manager: &Arc<ConnectionManager>,
    tx: &mpsc::Sender<ServerMessage>,
    _config: &ProviderConfig,
) -> Result<()> {
    match message {
        ClientMessage::Authenticate { token, device } => {
            if state.authenticated {
                return Err(anyhow!("Already authenticated"));
            }

            // Authenticate with Knox token
            let mut connection = crate::types::Connection {
                id: state.id.clone(),
                user_id: String::new(), // Will be set by auth
                device: device.clone(),
                connected_at: chrono::Utc::now(),
                last_ping: chrono::Utc::now(),
                filters: Default::default(),
            };

            match auth_service
                .authenticate(&mut connection, &token, device.clone())
                .await
            {
                Ok(()) => {
                    state.authenticated = true;
                    state.user_id = Some(connection.user_id.clone());
                    state.device = device;

                    // Add to connection manager
                    connection_manager.add_connection(connection.clone()).await;

                    // Send success response
                    tx.send(ServerMessage::Authenticated {
                        connection_id: state.id.clone(),
                        user_id: connection.user_id.clone(),
                        device: state.device.clone(),
                    })
                    .await?;

                    info!(
                        "Connection {} authenticated as user {} on {}",
                        state.id, connection.user_id, state.device
                    );
                }
                Err(e) => {
                    warn!("Authentication failed for connection {}: {}", state.id, e);
                    tx.send(ServerMessage::Error {
                        message: format!("Authentication failed: {}", e),
                    })
                    .await?;
                }
            }
        }
        ClientMessage::Subscribe { filters } => {
            if !state.authenticated {
                return Err(anyhow!("Not authenticated"));
            }

            // Update connection filters
            connection_manager
                .update_connection_filters(&state.id, filters.clone())
                .await?;

            tx.send(ServerMessage::Subscribed {
                filters: filters.clone(),
            })
            .await?;

            debug!("Connection {} updated filters: {:?}", state.id, filters);
        }
        ClientMessage::Ping => {
            tx.send(ServerMessage::Pong {
                timestamp: chrono::Utc::now(),
            })
            .await?;
        }
        ClientMessage::GetStatus => {
            if !state.authenticated {
                return Err(anyhow!("Not authenticated"));
            }

            if let Some(connection) = connection_manager.get_connection(&state.id).await {
                tx.send(ServerMessage::Status {
                    connected: true,
                    authenticated: true,
                    connection_id: state.id.clone(),
                    user_id: connection.user_id.clone(),
                    device: connection.device.clone(),
                    connected_at: connection.connected_at,
                    filters: connection.filters.clone(),
                })
                .await?;
            }
        }
    }

    Ok(())
}

/// Connection state for a WebSocket client
struct ConnectionState {
    id: String,
    authenticated: bool,
    user_id: Option<String>,
    device: DeviceType,
    peer_addr: SocketAddr,
}

/// WebSocket message sender implementation for NATS handler
pub struct WebSocketMessageSenderImpl {
    connection_manager: Arc<ConnectionManager>,
    tx_map:
        Arc<tokio::sync::RwLock<std::collections::HashMap<String, mpsc::Sender<ServerMessage>>>>,
}

impl WebSocketMessageSenderImpl {
    pub fn new(connection_manager: Arc<ConnectionManager>) -> Self {
        Self {
            connection_manager,
            tx_map: Arc::new(tokio::sync::RwLock::new(std::collections::HashMap::new())),
        }
    }

    pub async fn register_sender(&self, connection_id: String, tx: mpsc::Sender<ServerMessage>) {
        let mut map = self.tx_map.write().await;
        map.insert(connection_id, tx);
    }

    pub async fn unregister_sender(&self, connection_id: &str) {
        let mut map = self.tx_map.write().await;
        map.remove(connection_id);
    }
}

#[async_trait::async_trait]
impl MessageSender for WebSocketMessageSenderImpl {
    async fn send_to_connection(&self, connection_id: &str, message: ServerMessage) -> Result<()> {
        let map = self.tx_map.read().await;
        if let Some(tx) = map.get(connection_id) {
            tx.send(message).await?;
            Ok(())
        } else {
            Err(anyhow!("Connection {} not found", connection_id))
        }
    }

    async fn send_to_user(&self, user_id: &str, message: ServerMessage) -> Result<usize> {
        let connections = self.connection_manager.get_user_connections(user_id).await;
        let map = self.tx_map.read().await;
        let mut sent_count = 0;

        for connection in connections {
            if let Some(tx) = map.get(&connection.id) {
                if tx.send(message.clone()).await.is_ok() {
                    sent_count += 1;
                }
            }
        }

        Ok(sent_count)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_connection_state_creation() {
        let state = ConnectionState {
            id: "test_id".to_string(),
            authenticated: false,
            user_id: None,
            device: DeviceType::Dashboard,
            peer_addr: "127.0.0.1:8080".parse().unwrap(),
        };

        assert_eq!(state.id, "test_id");
        assert!(!state.authenticated);
        assert!(state.user_id.is_none());
    }
}
