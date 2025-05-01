package pipeline

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/apache/pulsar-client-go/pulsar"
	"github.com/web3ekko/ekko-ce/pipeline/internal/blockchain"
)

// PulsarSink implements a Pulsar sink for blockchain data
type PulsarSink struct {
	client  pulsar.Client
	producer pulsar.Producer
	topic    string
}

// NewPulsarSink creates a new Pulsar sink
func NewPulsarSink(url, topic string) (*PulsarSink, error) {
	// Ensure topic exists via Pulsar admin
	adminURL := os.Getenv("PULSAR_ADMIN_URL")
	if adminURL == "" {
		adminURL = "http://pulsar:8080"
	}
	// Attempt to create non-partitioned topic
	req, err := http.NewRequest("PUT", fmt.Sprintf("%s/admin/v2/persistent/public/default/%s", adminURL, topic), nil)
	if err != nil {
		return nil, fmt.Errorf("failed to build topic creation request: %w", err)
	}
	clientHTTP := &http.Client{Timeout: 5 * time.Second}
	resp, err := clientHTTP.Do(req)
	if err != nil {
		return nil, fmt.Errorf("topic creation request failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusNoContent && resp.StatusCode != http.StatusOK {
		if resp.StatusCode != http.StatusConflict {
			body, _ := io.ReadAll(resp.Body)
			return nil, fmt.Errorf("failed to create topic %s: %s", topic, string(body))
		}
	}
	// Create Pulsar client
	client, err := pulsar.NewClient(pulsar.ClientOptions{
		URL: url,
	})
	if err != nil {
		return nil, err
	}

	// Create producer
	producer, err := client.CreateProducer(pulsar.ProducerOptions{
		Topic: topic,
	})
	if err != nil {
		client.Close()
		return nil, err
	}

	return &PulsarSink{
		client:   client,
		producer: producer,
		topic:    topic,
	}, nil
}

// Write sends a block to Pulsar
func (s *PulsarSink) Write(ctx context.Context, block *blockchain.Block) error {
	// Convert block to JSON
	data, err := json.Marshal(block)
	if err != nil {
		return err
	}

	// Send message
	_, err = s.producer.Send(ctx, &pulsar.ProducerMessage{
		Payload: data,
		Key:     block.Hash,
	})
	if err != nil {
		log.Printf("Failed to send message: %v", err)
		return err
	}

	return nil
}

// Close closes the Pulsar connection
func (s *PulsarSink) Close() error {
	s.producer.Close()
	s.client.Close()
	return nil
}
