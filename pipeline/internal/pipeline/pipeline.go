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

// SubnetPipeline represents a pipeline for a single Avalanche subnet
type SubnetPipeline struct {
	config   config.SubnetConfig
	source   *blockchain.WebSocketSource
	decoder  *decoder.Decoder
	sink     *PulsarSink
	flow     streams.Flow
	nodeIdx  int // Current node index for failover
}

// Pipeline represents the main data processing pipeline
type Pipeline struct {
	config   *config.Config
	subnets  []*SubnetPipeline
	cache    decoder.Cache
	workers  int
}

// NewPipeline creates a new processing pipeline
func NewPipeline(cfg *config.Config) (*Pipeline, error) {
	// Create cache based on configuration
	var cache decoder.Cache
	if cfg.CacheType == "redis" {
		cache = decoder.NewRedisCache(cfg.RedisURL)
	} else {
		cache = decoder.NewMemoryCache()
	}

	// Create subnet pipelines
	subnets := make([]*SubnetPipeline, 0, len(cfg.Subnets))
	for _, subnetCfg := range cfg.Subnets {
		// Determine node URLs for this subnet
		nodeURLs := subnetCfg.NodeURLs
		if len(nodeURLs) == 0 {
			// Use base nodes if no subnet-specific nodes are configured
			nodeURLs = cfg.BaseNodeURLs
		}

		if len(nodeURLs) == 0 {
			return nil, fmt.Errorf("no nodes available for subnet %s", subnetCfg.Name)
		}

		// Create WebSocket source with the first node
		source := blockchain.NewWebSocketSource(
			getWebSocketURL(nodeURLs[0], subnetCfg),
			getHTTPURL(nodeURLs[0], subnetCfg),
		)

		// Create decoder
		dec := decoder.NewDecoder(cache, subnetCfg.ChainID)

		// Create Pulsar sink
		sink, err := NewPulsarSink(cfg.PulsarURL, subnetCfg.PulsarTopic)
		if err != nil {
			return nil, fmt.Errorf("failed to create sink for subnet %s: %w", subnetCfg.Name, err)
		}

		subnets = append(subnets, &SubnetPipeline{
			config:  subnetCfg,
			source:  source,
			decoder: dec,
			sink:    sink,
			nodeIdx: 0,
		})
	}

	return &Pipeline{
		config:  cfg,
		subnets: subnets,
		cache:   cache,
		workers: cfg.DecoderWorkers,
	}, nil
}

// decodeTransactionsParallel decodes transactions in parallel using a worker pool
func (p *Pipeline) decodeTransactionsParallel(ctx context.Context, block *blockchain.Block, dec *decoder.Decoder) {
	if len(block.Transactions) == 0 {
		return
	}

	// Create work channels
	jobs := make(chan int, len(block.Transactions))
	wg := sync.WaitGroup{}

	// Start workers
	for i := 0; i < p.workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for idx := range jobs {
				if err := dec.DecodeTransaction(ctx, &block.Transactions[idx]); err != nil {
					// Log error but continue processing
					continue
				}
			}
		}()
	}

	// Send jobs to workers
	for i := range block.Transactions {
		jobs <- i
	}
	close(jobs)

	// Wait for all workers to finish
	wg.Wait()
}

// Start starts all subnet pipelines
func (p *Pipeline) Start(ctx context.Context) error {
	// Start each subnet pipeline
	for _, subnet := range p.subnets {
		// Create source with retry and failover
		source := p.createSourceWithFailover(subnet)

		// Store source for cleanup
		subnet.source = source.(*blockchain.WebSocketSource)

		// Start the source
		if err := subnet.source.Start(); err != nil {
			return fmt.Errorf("failed to start source for subnet %s: %v", subnet.config.Name, err)
		}

		// Start processing blocks
		go func() {
			for item := range source.Out() {
				// Decode transactions
				block := item.(*blockchain.Block)
				p.decodeTransactionsParallel(ctx, block, subnet.decoder)

				// Send to Pulsar with retry
				for attempt := 0; attempt <= p.config.MaxRetries; attempt++ {
					if err := subnet.sink.Write(ctx, block); err == nil {
						break
					}
					if attempt < p.config.MaxRetries {
						time.Sleep(p.config.RetryDelay)
					}
				}
			}
		}()


	}

	// Wait for context cancellation
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
