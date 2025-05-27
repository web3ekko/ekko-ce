package listeners

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/gorilla/websocket"
	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/common"
)

// NewHeadListener listens for new block headers from a WebSocket endpoint
// and publishes them to a NATS subject.
type NewHeadListener struct {
	nodeCfg  common.NodeConfig
	natsConn *nats.Conn
	// logger   *log.Logger // Or use the global log package
}

// NewNewHeadListener creates a new instance of NewHeadListener.
func NewNewHeadListener(cfg common.NodeConfig, nc *nats.Conn) *NewHeadListener {
	return &NewHeadListener{
		nodeCfg:  cfg,
		natsConn: nc,
	}
}

// Run starts the listener. It connects to the WebSocket, subscribes to new heads,
// and publishes received headers to NATS. It will attempt to reconnect on errors.
func (l *NewHeadListener) Run(ctx context.Context) error {
	log.Printf("NewHeadListener: Starting for node %s (ID: %s, WSS: %s)", l.nodeCfg.Name, l.nodeCfg.ID, l.nodeCfg.WssURL)
	defer log.Printf("NewHeadListener: Stopped for node %s (ID: %s)", l.nodeCfg.Name, l.nodeCfg.ID)

	if l.nodeCfg.WssURL == "" {
		return fmt.Errorf("NewHeadListener: WSS URL is empty for node %s (ID: %s)", l.nodeCfg.Name, l.nodeCfg.ID)
	}

	// NATS subject to publish new head information
	natsSubject := fmt.Sprintf("ekko.heads.%s.%s.%s", l.nodeCfg.VMType, l.nodeCfg.Network, l.nodeCfg.ID)

	for {
		select {
		case <-ctx.Done():
			log.Printf("NewHeadListener: Context cancelled for node %s. Exiting Run loop.", l.nodeCfg.Name)
			return nil // Graceful shutdown
		default:
			// Attempt to connect and listen
			err := l.connectAndListen(ctx, natsSubject)
			if err != nil {
				if ctx.Err() == context.Canceled { // Check if context was cancelled during connectAndListen
					return nil
				}
				log.Printf("NewHeadListener: Error for node %s: %v. Retrying in 15 seconds...", l.nodeCfg.Name, err)
				// Wait before retrying, unless context is cancelled
				select {
				case <-time.After(15 * time.Second):
				case <-ctx.Done():
					return nil // Exit if context cancelled during wait
				}
			}
		}
	}
}

// connectAndListen handles the WebSocket connection, subscription, and message reading loop.
func (l *NewHeadListener) connectAndListen(ctx context.Context, natsSubject string) error {
	log.Printf("NewHeadListener: Attempting to connect to %s for node %s", l.nodeCfg.WssURL, l.nodeCfg.Name)
	conn, _, err := websocket.DefaultDialer.DialContext(ctx, l.nodeCfg.WssURL, nil)
	if err != nil {
		return fmt.Errorf("failed to dial WebSocket: %w", err)
	}
	defer conn.Close()
	log.Printf("NewHeadListener: Successfully connected to %s for node %s", l.nodeCfg.WssURL, l.nodeCfg.Name)

	if l.nodeCfg.VMType == "evm" {
		subscriptionMsg := `{"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["newHeads"]}`
		if err := conn.WriteMessage(websocket.TextMessage, []byte(subscriptionMsg)); err != nil {
			return fmt.Errorf("failed to send subscription message: %w", err)
		}
		log.Printf("NewHeadListener: Subscribed to newHeads for node %s", l.nodeCfg.Name)
	} else {
		log.Printf("NewHeadListener: Skipping subscription for non-EVM node %s (VMType: %s)", l.nodeCfg.Name, l.nodeCfg.VMType)
	}

	// Read messages
	for {
		select {
		case <-ctx.Done():
			log.Printf("NewHeadListener: connectAndListen context cancelled for node %s.", l.nodeCfg.Name)
			_ = conn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""))
			return nil // Graceful shutdown
		default:
			conn.SetReadDeadline(time.Now().Add(30 * time.Second))
			_, message, err := conn.ReadMessage()
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure, websocket.CloseNormalClosure) {
					log.Printf("NewHeadListener: Read error for node %s: %v", l.nodeCfg.Name, err)
					return fmt.Errorf("read error: %w", err)
				}
				// If it's another type of error (e.g. timeout), log it but continue loop to check ctx.Done()
				// log.Printf("NewHeadListener: ReadMessage error/timeout for node %s: %v", l.nodeCfg.Name, err)
				continue 
			}

			log.Printf("NewHeadListener: Received message for node %s: %s", l.nodeCfg.Name, string(message))

			if err := l.natsConn.Publish(natsSubject, message); err != nil {
				log.Printf("NewHeadListener: Failed to publish message to NATS subject %s for node %s: %v", natsSubject, l.nodeCfg.Name, err)
			} else {
				log.Printf("NewHeadListener: Published message to NATS subject %s for node %s", natsSubject, l.nodeCfg.Name)
			}
		}
	}
}
