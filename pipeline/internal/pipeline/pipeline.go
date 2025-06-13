package pipeline

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/reugn/go-streams"
	"github.com/web3ekko/ekko-ce/pipeline/internal/config"
	"github.com/web3ekko/ekko-ce/pipeline/internal/storage"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
)

// SubnetPipeline represents a pipeline for a single subnet
type SubnetPipeline struct {
	config  config.SubnetConfig
	source  *blockchain.WebSocketSource
	sink    *NATSSink
	nodeIdx int // Current node index for failover
}

// Pipeline represents the main data pipeline
type Pipeline struct {
	subnets     map[string]*SubnetPipeline
	config      config.Config
	redis       decoder.RedisClient
	manager     *decoder.TemplateManager
	duckStorage *storage.DuckDBStorage
	batchSize   int
	workers     int
	natsURL     string
}

// NewPipeline creates a new pipeline
func NewPipeline(cfg config.Config, redis decoder.RedisClient) (*Pipeline, error) {
	// Initialize DuckDB storage
	s3Config := storage.NewS3ConfigFromEnv()
	duckStorage, err := storage.NewDuckDBStorage(s3Config)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize DuckDB storage: %w", err)
	}

	return &Pipeline{
		subnets:     make(map[string]*SubnetPipeline),
		config:      cfg,
		redis:       redis,
		manager:     decoder.NewTemplateManager(redis),
		duckStorage: duckStorage,
		batchSize:   100,
		workers:     cfg.DecoderWorkers,
		natsURL:     cfg.NatsURL,
	}, nil
}

// processBlock processes a block and its transactions
func (p *Pipeline) processBlock(block *blockchain.Block, network, subnet, vmType string) error {
	// Convert blockchain transactions to storage format
	var transactions []storage.Transaction

	for i, tx := range block.Transactions {
		storageTransaction := storage.Transaction{
			Network:     network,
			Subnet:      subnet,
			VMType:      vmType,
			BlockTime:   time.Now(), // TODO: Use actual block timestamp when available
			BlockHash:   block.Hash,
			BlockNumber: int64(block.Number),
			TxHash:      tx.Hash,
			TxIndex:     i,
			FromAddress: tx.From,
			ToAddress:   &tx.To,
			Value:       tx.Value,
			GasPrice:    &tx.GasPrice,
			GasLimit:    &tx.Gas,
			Nonce:       &tx.Nonce,
			InputData:   []byte(tx.Data),
			Success:     true, // TODO: Determine success from receipt
		}
		transactions = append(transactions, storageTransaction)
	}

	// Store transactions in DuckDB
	if len(transactions) > 0 {
		if err := p.duckStorage.StoreTransactionBatch(transactions); err != nil {
			log.Printf("Error storing transactions in DuckDB: %v", err)
			return fmt.Errorf("failed to store transactions: %w", err)
		}
		log.Printf("Successfully stored %d transactions from block %s in DuckDB", len(transactions), block.Hash)
	}

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

		// Create NATS JetStream sink
		sink, err := NewNATSSink(p.natsURL, subnet.config.StreamName, subnet.config.Subject)
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
					// Process block with network/subnet/vmtype info
					if err := p.processBlock(blk, subnet.config.Network, subnet.config.Name, subnet.config.VMType); err != nil {
						log.Printf("Subnet %s: error processing block %s: %v", subnet.config.Name, blk.Hash, err)
						continue
					}
					// Send to NATS JetStream
					err = subnet.sink.Write(ctx, blk)
					if err != nil {
						log.Printf("Subnet %s: error sending block to NATS: %v", subnet.config.Name, err)
					} else {
						log.Printf("Subnet %s: sent block %s to subject %s", subnet.config.Name, blk.Hash, subnet.config.Subject)
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

	// Close DuckDB storage
	if p.duckStorage != nil {
		if err := p.duckStorage.Close(); err != nil {
			log.Printf("Error closing DuckDB storage: %v", err)
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
