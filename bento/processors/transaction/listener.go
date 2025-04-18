package transaction

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/gorilla/websocket"
)

// WSMessage represents a WebSocket message containing transaction data
type WSMessage struct {
	Chain       string          `json:"chain"`
	Transaction json.RawMessage `json:"transaction"`
}

// Listener handles WebSocket connections and processes incoming transactions
type Listener struct {
	processor *Processor
	wsURL    string
}

// NewListener creates a new WebSocket listener
func NewListener(processor *Processor, wsURL string) *Listener {
	return &Listener{
		processor: processor,
		wsURL:    wsURL,
	}
}

// Start begins listening for transactions
func (l *Listener) Start(ctx context.Context) error {
	// Connect to WebSocket
	c, _, err := websocket.DefaultDialer.Dial(l.wsURL, nil)
	if err != nil {
		return fmt.Errorf("failed to connect to websocket: %w", err)
	}
	defer c.Close()

	// Handle connection closure
	go func() {
		<-ctx.Done()
		c.Close()
	}()

	for {
		select {
		case <-ctx.Done():
			return nil
		default:
			// Read message
			_, message, err := c.ReadMessage()
			if err != nil {
				log.Printf("Error reading websocket: %v", err)
				// Attempt to reconnect
				time.Sleep(5 * time.Second)
				c, _, err = websocket.DefaultDialer.Dial(l.wsURL, nil)
				if err != nil {
					log.Printf("Failed to reconnect: %v", err)
					continue
				}
			}

			// Parse message
			var wsMsg WSMessage
			if err := json.Unmarshal(message, &wsMsg); err != nil {
				log.Printf("Error parsing message: %v", err)
				continue
			}

			// Parse transaction data
			var tx Transaction
			if err := json.Unmarshal(wsMsg.Transaction, &tx); err != nil {
				log.Printf("Error parsing transaction: %v", err)
				continue
			}

			// Set chain and timestamp
			tx.Chain = wsMsg.Chain
			tx.Timestamp = time.Now()

			// Process transaction
			if err := l.processor.ProcessTransaction(ctx, &tx); err != nil {
				log.Printf("Error processing transaction: %v", err)
				continue
			}
		}
	}
}
