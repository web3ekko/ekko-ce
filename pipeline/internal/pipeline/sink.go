package pipeline

import (
	"context"

	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
)

// Sink defines the interface for message sinks in the pipeline
// This interface is implemented by NATSSink (in nats_sink.go)
type Sink interface {
	// Write sends a block to the sink
	Write(ctx context.Context, block *blockchain.Block) error
	// Close closes the sink connection
	Close() error
}
