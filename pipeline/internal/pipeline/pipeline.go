package pipeline

import (
	"context"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/reugn/go-streams"
	"github.com/web3ekko/ekko-ce/pipeline/internal/blockchain"
	"github.com/web3ekko/ekko-ce/pipeline/internal/config"
	"github.com/web3ekko/ekko-ce/pipeline/internal/decoder"
)

// SubnetPipeline represents a pipeline for a single subnet
type SubnetPipeline struct {
	config  config.SubnetConfig
	source  *blockchain.WebSocketSource
	sink    *PulsarSink
	nodeIdx int // Current node index for failover
}

// Pipeline represents the main data processing pipeline
type Pipeline struct {
	subnets   map[string]*SubnetPipeline
	decoder   *decoder.Decoder
	manager   *decoder.TemplateManager
	batchSize int
	workers   int
}

// NewPipeline creates a new pipeline
func NewPipeline(redis *decoder.RedisAdapter, cfg *config.Config) (*Pipeline, error) {
	// Convert subnet configs to subnet pipelines
	subnetPipelines := make(map[string]*SubnetPipeline)
	for _, subnet := range cfg.Subnets {
		subnetPipelines[subnet.Name] = &SubnetPipeline{
			config: subnet,
		}
	}

	return &Pipeline{
		subnets:    subnetPipelines,
		decoder:    decoder.NewDecoder(redis, "default"),
		manager:    decoder.NewTemplateManager(redis),
		batchSize:  100,
		workers:    cfg.DecoderWorkers,
	}, nil
}

// processBlock processes a block and its transactions
func (p *Pipeline) processBlock(ctx context.Context, block *blockchain.Block) error {
	// Start workers
	var wg sync.WaitGroup
	jobs := make(chan int, len(block.Transactions))

	// Start worker goroutines
	for i := 0; i < p.workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for job := range jobs {
				tx := &block.Transactions[job]
				if err := p.decoder.DecodeTransaction(ctx, tx); err != nil {
					log.Printf("Failed to decode transaction %d: %v", job, err)
				}
			}
		}()
	}

	// Send jobs
	for i := range block.Transactions {
		jobs <- i
	}
	close(jobs)

	// Wait for completion
	wg.Wait()

	return nil
}

// Start starts all subnet pipelines
func (p *Pipeline) Start(ctx context.Context) error {
	// Start each subnet pipeline
	for _, subnet := range p.subnets {
		// Determine node URLs for this subnet
		nodeURLs := subnet.config.NodeURLs
		if len(nodeURLs) == 0 {
			// If no specific nodes are configured, use base nodes
			nodeURLs = []string{"https://api.avax.network"} // default node URL
		}

		if len(nodeURLs) == 0 {
			return fmt.Errorf("no nodes available for subnet %s", subnet.config.Name)
		}

		// Create WebSocket source with the first node
		source := blockchain.NewWebSocketSource(
			getWebSocketURL(nodeURLs[0], subnet.config),
			getHTTPURL(nodeURLs[0], subnet.config),
		)

		// Create Pulsar sink
		sink, err := NewPulsarSink("pulsar://localhost:6650", subnet.config.PulsarTopic)
		if err != nil {
			return fmt.Errorf("failed to create sink for subnet %s: %w", subnet.config.Name, err)
		}

		// Store source and sink
		subnet.source = source
		subnet.sink = sink

		// Start processing
		go func(subnet *SubnetPipeline) {
			for {
				select {
				case <-ctx.Done():
					return
				case block := <-subnet.source.Out():
					if err := p.processBlock(ctx, block.(*blockchain.Block)); err != nil {
						log.Printf("Error processing block: %v", err)
						continue
					}
					if err := subnet.sink.Write(ctx, block.(*blockchain.Block)); err != nil {
						log.Printf("Error sending block: %v", err)
					}
				}
			}
		}(subnet)
	}

	<-ctx.Done()
	return ctx.Err()
}

// Stop gracefully stops the pipeline
func (p *Pipeline) Stop() error {
	// Close all subnet sources
	for _, subnet := range p.subnets {
		if subnet.source != nil {
			if err := subnet.source.Close(); err != nil {
				log.Printf("Error closing source for subnet %s: %v", subnet.config.Name, err)
			}
			if err := subnet.sink.Close(); err != nil {
				log.Printf("Error closing sink for subnet %s: %v", subnet.config.Name, err)
			}
		}
	}
	return nil
}

// FailoverSource implements streams.Source with automatic failover
type FailoverSource struct {
	ctx    context.Context
	subnet *SubnetPipeline
	config *config.Config
	outCh  chan any
}

// Out implements streams.Outlet
func (s *FailoverSource) Out() <-chan any {
	if s.outCh == nil {
		s.outCh = make(chan any)
		go s.run()
	}
	return s.outCh
}

// Via implements streams.Source
func (s *FailoverSource) Via(flow streams.Flow) streams.Flow {
	return flow
}

// run processes blocks from nodes with automatic failover
func (s *FailoverSource) run() {
	defer close(s.outCh)

	for {
		select {
		case <-s.ctx.Done():
			return
		default:
			// Try to connect to current node
			nodeURLs := s.subnet.config.NodeURLs
			if len(nodeURLs) == 0 {
				nodeURLs = s.config.BaseNodeURLs
			}

			// Update source with current node
			currentNode := nodeURLs[s.subnet.nodeIdx]
			s.subnet.source = blockchain.NewWebSocketSource(
				getWebSocketURL(currentNode, s.subnet.config),
				getHTTPURL(currentNode, s.subnet.config),
			)



			// Process blocks directly from source
			for block := range s.subnet.source.Out() {
				s.outCh <- block
			}

			// Try next node on error
			s.subnet.nodeIdx = (s.subnet.nodeIdx + 1) % len(nodeURLs)
			time.Sleep(s.config.RetryDelay)
		}
	}
}

// createSourceWithFailover creates a source that automatically fails over to another node
func (p *Pipeline) createSourceWithFailover(subnet *SubnetPipeline) streams.Source {
	// Get node URLs
	nodeURLs := subnet.config.NodeURLs
	if len(nodeURLs) == 0 {
		log.Printf("No nodes configured for subnet %s", subnet.config.Name)
		return nil
	}

	// Create WebSocket source with first node
	baseURL := nodeURLs[0]
	wsURL := getWebSocketURL(baseURL, subnet.config)
	httpURL := baseURL
	source := blockchain.NewWebSocketSource(wsURL, httpURL)

	// Return source
	return source
}

// getWebSocketURL constructs the WebSocket URL for a node
func getWebSocketURL(baseURL string, cfg config.SubnetConfig) string {
	// Remove any trailing slashes
	baseURL = strings.TrimRight(baseURL, "/")
	
	// Add WebSocket path based on VM type
	switch cfg.VMType {
	case "subnet-evm":
		return baseURL + "/ext/bc/" + cfg.ChainID + "/ws"
	default:
		return baseURL + "/ws"
	}
}

// getHTTPURL constructs the HTTP URL for a node
func getHTTPURL(baseURL string, cfg config.SubnetConfig) string {
	// Remove any trailing slashes
	baseURL = strings.TrimRight(baseURL, "/")
	
	// Add HTTP path based on VM type
	switch cfg.VMType {
	case "subnet-evm":
		return baseURL + "/ext/bc/" + cfg.ChainID + "/rpc"
	default:
		return baseURL + "/rpc"
	}
}
