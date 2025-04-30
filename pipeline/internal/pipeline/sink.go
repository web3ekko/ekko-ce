package pipeline

import (
	"context"
	"encoding/json"
	"log"

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
