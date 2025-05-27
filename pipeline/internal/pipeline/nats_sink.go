package pipeline

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
)

// NATSSink implements a NATS JetStream sink for blockchain data
type NATSSink struct {
	conn      *nats.Conn
	js        nats.JetStreamContext
	stream    string
	subject   string
	connected bool
}

// NewNATSSink creates a new NATS JetStream sink
func NewNATSSink(url, stream, subject string) (*NATSSink, error) {
	// Set default URL if not provided
	if url == "" {
		url = nats.DefaultURL
	}

	// Connect to NATS
	conn, err := nats.Connect(url, nats.RetryOnFailedConnect(true), nats.MaxReconnects(-1))
	if err != nil {
		return nil, fmt.Errorf("failed to connect to NATS: %w", err)
	}

	// Create JetStream context
	js, err := conn.JetStream()
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to create JetStream context: %w", err)
	}

	// Create or get the stream
	_, err = js.StreamInfo(stream)
	if err != nil {
		// Stream doesn't exist, create it
		log.Printf("Creating stream %s for subject %s", stream, subject)
		
		// Configure stream with reasonable defaults
		streamConfig := &nats.StreamConfig{
			Name:      stream,
			Subjects:  []string{subject},
			Retention: nats.InterestPolicy,
			Storage:   nats.FileStorage,
			MaxAge:    24 * time.Hour, // Default retention of 24 hours
			Replicas:  1,              // Single replica for development
		}
		
		_, err = js.AddStream(streamConfig)
		if err != nil {
			conn.Close()
			return nil, fmt.Errorf("failed to create stream: %w", err)
		}
	}

	return &NATSSink{
		conn:      conn,
		js:        js,
		stream:    stream,
		subject:   subject,
		connected: true,
	}, nil
}

// Write sends a block to NATS JetStream
func (s *NATSSink) Write(ctx context.Context, block *blockchain.Block) error {
	if !s.connected {
		return fmt.Errorf("NATS connection is closed")
	}

	// Convert block to JSON
	data, err := json.Marshal(block)
	if err != nil {
		return fmt.Errorf("failed to marshal block: %w", err)
	}

	// Publish to JetStream
	_, err = s.js.Publish(s.subject, data)
	if err != nil {
		return fmt.Errorf("failed to publish to NATS: %w", err)
	}

	return nil
}

// Close closes the NATS connection
func (s *NATSSink) Close() error {
	if s.conn != nil {
		s.connected = false
		s.conn.Close()
	}
	return nil
}
