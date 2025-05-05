package pipeline

import (
	"context"
	"fmt"
	"log"
	"os"
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
	pulsarURL string
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
		pulsarURL:  cfg.PulsarURL,
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
				// Log transaction handling
				log.Printf("Processing tx %s from block %s", tx.Hash, block.Hash)
				if err := p.decoder.DecodeTransaction(ctx, tx); err != nil {
					log.Printf("Failed to decode tx %s from block %s: %v", tx.Hash, block.Hash, err)
				} else {
					log.Printf("Decoded tx %s from block %s", tx.Hash, block.Hash)
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
	// Skip pipeline if websocket events are disabled
	if strings.ToLower(os.Getenv("ENABLE_WEBSOCKET_EVENTS")) == "false" {
		log.Println("Websocket events disabled; skipping pipeline execution.")
		<-ctx.Done()
		return ctx.Err()
	}

	// Start each subnet pipeline
	for _, subnet := range p.subnets {
		// Determine WS and HTTP URLs, allow override via config.WebSocketURL/HTTPURL
		var wsURL, httpURL string
		if subnet.config.WebSocketURL != "" && subnet.config.HTTPURL != "" {
			wsURL = subnet.config.WebSocketURL
			httpURL = subnet.config.HTTPURL
		} else {
			nodeURLs := subnet.config.NodeURLs
			if len(nodeURLs) == 0 {
				// fallback to default base node
				nodeURLs = []string{"https://api.avax.network"}
			}
			wsURL = getWebSocketURL(nodeURLs[0], subnet.config)
			httpURL = getHTTPURL(nodeURLs[0], subnet.config)
		}
		source := blockchain.NewWebSocketSource(wsURL, httpURL)
		// Initiate WebSocket connection and subscription
		if err := source.Start(); err != nil {
			return fmt.Errorf("failed to start WebSocket source for subnet %s: %w", subnet.config.Name, err)
		}

		// Create Pulsar sink
		sink, err := NewPulsarSink(p.pulsarURL, subnet.config.PulsarTopic)
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
				case raw := <-subnet.source.Out():
					blk := raw.(*blockchain.Block)
					// Log receipt of block
					log.Printf("Subnet %s: received block %s with %d transactions", subnet.config.Name, blk.Hash, len(blk.Transactions))
					// Process block
					if err := p.processBlock(ctx, blk); err != nil {
						log.Printf("Subnet %s: error processing block %s: %v", subnet.config.Name, blk.Hash, err)
						continue
					}
					// Send to Pulsar
					if err := subnet.sink.Write(ctx, blk); err != nil {
						log.Printf("Subnet %s: error sending block %s: %v", subnet.config.Name, blk.Hash, err)
					} else {
						log.Printf("Subnet %s: sent block %s to topic %s", subnet.config.Name, blk.Hash, subnet.config.PulsarTopic)
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
			// Determine source URL: support per-subnet overrides
			if s.subnet.config.WebSocketURL != "" && s.subnet.config.HTTPURL != "" {
				s.subnet.source = blockchain.NewWebSocketSource(
					s.subnet.config.WebSocketURL,
					s.subnet.config.HTTPURL,
				)
			} else {
				// Fallback to configured nodes or default
				nodeURLs := s.subnet.config.NodeURLs
				if len(nodeURLs) == 0 {
					nodeURLs = []string{"https://api.avax.network"}
				}
				current := nodeURLs[s.subnet.nodeIdx]
				s.subnet.source = blockchain.NewWebSocketSource(
					getWebSocketURL(current, s.subnet.config),
					getHTTPURL(current, s.subnet.config),
				)
			}

			// Process blocks directly from source
			for block := range s.subnet.source.Out() {
				s.outCh <- block
			}

			// If override used, do not retry other nodes
			if !(s.subnet.config.WebSocketURL != "" && s.subnet.config.HTTPURL != "") {
				// Try next node on error
				addrs := s.subnet.config.NodeURLs
				if len(addrs) == 0 {
					addrs = []string{"https://api.avax.network"}
				}
				s.subnet.nodeIdx = (s.subnet.nodeIdx + 1) % len(addrs)
				time.Sleep(s.config.RetryDelay)
			}
		}
	}
}

// createSourceWithFailover creates a source that automatically fails over to another node
func (p *Pipeline) createSourceWithFailover(subnet *SubnetPipeline) streams.Source {
	// If overrides provided, use them
	if subnet.config.WebSocketURL != "" && subnet.config.HTTPURL != "" {
		return blockchain.NewWebSocketSource(subnet.config.WebSocketURL, subnet.config.HTTPURL)
	}
	// Fallback to first node
	nodeURLs := subnet.config.NodeURLs
	if len(nodeURLs) == 0 {
		log.Printf("No nodes configured for subnet %s", subnet.config.Name)
		return nil
	}
	wsURL := getWebSocketURL(nodeURLs[0], subnet.config)
	httpURL := getHTTPURL(nodeURLs[0], subnet.config)
	return blockchain.NewWebSocketSource(wsURL, httpURL)
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
