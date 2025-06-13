package supervisor

import (
	"context"
	"fmt"
	"log"
	"os"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/internal/config"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	ekkoCommon "github.com/web3ekko/ekko-ce/pipeline/pkg/common"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/persistence"
)

// ManagedPipelineWithDuckLake extends the managed pipeline to include DuckLake writer
type ManagedPipelineWithDuckLake struct {
	// Core pipeline components
	network     string
	subnet      string
	vmType      string
	nodes       []ekkoCommon.NodeConfig
	natsConn    *nats.Conn
	redisClient decoder.RedisClient

	// Writers
	arrowWriter    *persistence.ArrowWriter
	duckLakeWriter *persistence.DuckLakeWriter

	// Processing context
	ctx    context.Context
	cancel context.CancelFunc

	// Synchronization
	mutex   sync.RWMutex
	running bool

	// Callback for status updates (simplified)
	statusCallback func(nodeID string, status string) error
}

// NewManagedPipelineWithDuckLake creates a new managed pipeline with both Arrow and DuckLake writers
func NewManagedPipelineWithDuckLake(
	parentCtx context.Context,
	network, subnet, vmType string,
	nodes []ekkoCommon.NodeConfig,
	natsConn *nats.Conn,
	redisClient decoder.RedisClient,
	statusCallback func(string, string) error,
) (*ManagedPipelineWithDuckLake, error) {

	// Load configuration
	cfg, err := config.LoadFromEnv()
	if err != nil {
		return nil, fmt.Errorf("failed to load config: %w", err)
	}

	// Create child context
	ctx, cancel := context.WithCancel(parentCtx)

	pipeline := &ManagedPipelineWithDuckLake{
		network:        network,
		subnet:         subnet,
		vmType:         vmType,
		nodes:          nodes,
		natsConn:       natsConn,
		redisClient:    redisClient,
		ctx:            ctx,
		cancel:         cancel,
		statusCallback: statusCallback,
	}

	// Initialize Arrow writer (existing functionality)
	if err := pipeline.initializeArrowWriter(cfg); err != nil {
		cancel()
		return nil, fmt.Errorf("failed to initialize Arrow writer: %w", err)
	}

	// Initialize DuckLake writer (new functionality)
	if cfg.DuckLakeEnabled {
		if err := pipeline.initializeDuckLakeWriter(cfg); err != nil {
			cancel()
			return nil, fmt.Errorf("failed to initialize DuckLake writer: %w", err)
		}
		log.Printf("DuckLake writer enabled for %s-%s-%s", network, subnet, vmType)
	} else {
		log.Printf("DuckLake writer disabled for %s-%s-%s", network, subnet, vmType)
	}

	// Note: Block fetcher initialization removed for simplicity
	// In a full implementation, you would initialize the block fetcher here

	return pipeline, nil
}

// initializeArrowWriter sets up the Arrow writer
func (mp *ManagedPipelineWithDuckLake) initializeArrowWriter(cfg *config.Config) error {
	// Create Arrow writer config
	arrowConfig := persistence.ArrowWriterConfig{
		BatchSize:          cfg.BatchSize,
		FlushInterval:      30 * time.Second,
		NatsURL:            cfg.NatsURL,
		NatsSubjectPattern: "ekko.*.*.*.persistence",
		MinioConfig: persistence.MinioConfig{
			Endpoint:   getEnvWithDefault("MINIO_ENDPOINT", "localhost:9000"),
			AccessKey:  getEnvWithDefault("MINIO_ACCESS_KEY", "minioadmin"),
			SecretKey:  getEnvWithDefault("MINIO_SECRET_KEY", "minioadmin"),
			BucketName: getEnvWithDefault("MINIO_BUCKET_NAME", "blockchain-data"),
			BasePath:   "arrow-data",
			UseSSL:     getEnvWithDefault("MINIO_SECURE", "false") == "true",
		},
	}

	// Create Arrow writer
	writer, err := persistence.NewArrowWriter(arrowConfig)
	if err != nil {
		return fmt.Errorf("failed to create Arrow writer: %w", err)
	}

	mp.arrowWriter = writer
	return nil
}

// initializeDuckLakeWriter sets up the DuckLake writer
func (mp *ManagedPipelineWithDuckLake) initializeDuckLakeWriter(cfg *config.Config) error {
	// Create DuckLake writer config
	duckLakeConfig := persistence.DuckLakeWriterConfig{
		CatalogType:   cfg.DuckLakeCatalogType,
		CatalogPath:   cfg.DuckLakeCatalogPath,
		DataPath:      cfg.DuckLakeDataPath,
		BucketName:    cfg.DuckLakeBucketName,
		BatchSize:     cfg.DuckLakeBatchSize,
		FlushInterval: cfg.DuckLakeFlushInterval,
		MaxRetries:    cfg.MaxRetries,
		RetryDelay:    cfg.RetryDelay,

		// MinIO configuration - get from environment or config
		MinioEndpoint:  getEnvWithDefault("MINIO_ENDPOINT", "localhost:9000"),
		MinioAccessKey: getEnvWithDefault("MINIO_ACCESS_KEY", "minioadmin"),
		MinioSecretKey: getEnvWithDefault("MINIO_SECRET_KEY", "minioadmin"),
		MinioSecure:    getEnvWithDefault("MINIO_SECURE", "false") == "true",
		MinioRegion:    getEnvWithDefault("MINIO_REGION", "us-east-1"),
	}

	// Create DuckLake writer
	writer, err := persistence.NewDuckLakeWriter(duckLakeConfig, mp.natsConn)
	if err != nil {
		return fmt.Errorf("failed to create DuckLake writer: %w", err)
	}

	mp.duckLakeWriter = writer
	return nil
}

// Note: Block fetcher functionality removed for simplification
// In a full implementation, you would implement block fetching here

// Run starts the managed pipeline
func (mp *ManagedPipelineWithDuckLake) Run() {
	mp.mutex.Lock()
	if mp.running {
		mp.mutex.Unlock()
		return
	}
	mp.running = true
	mp.mutex.Unlock()

	log.Printf("Starting managed pipeline for %s-%s-%s with %d nodes",
		mp.network, mp.subnet, mp.vmType, len(mp.nodes))

	// Start periodic flushing for writers
	go mp.periodicFlush()

	// Start block processing
	go mp.processBlocks()

	// Wait for context cancellation
	<-mp.ctx.Done()

	// Cleanup
	mp.shutdown()
}

// processBlocks handles the main block processing loop
func (mp *ManagedPipelineWithDuckLake) processBlocks() {
	ticker := time.NewTicker(1 * time.Second) // Poll for new blocks every second
	defer ticker.Stop()

	for {
		select {
		case <-mp.ctx.Done():
			return
		case <-ticker.C:
			if err := mp.fetchAndProcessLatestBlock(); err != nil {
				log.Printf("Error processing block for %s-%s-%s: %v",
					mp.network, mp.subnet, mp.vmType, err)
			}
		}
	}
}

// processTransaction processes a single transaction through both writers
func (mp *ManagedPipelineWithDuckLake) processTransaction(tx blockchain.Transaction) error {
	nodeConfig := ekkoCommon.NodeConfig{
		Network: mp.network,
		Subnet:  mp.subnet,
		VMType:  mp.vmType,
	}

	// Write to DuckLake writer (new functionality)
	if mp.duckLakeWriter != nil {
		if err := mp.duckLakeWriter.WriteTransaction(mp.ctx, tx, nodeConfig); err != nil {
			log.Printf("Error writing transaction %s to DuckLake: %v", tx.Hash, err)
			return err
		}
	}

	log.Printf("Successfully processed transaction %s for %s-%s-%s",
		tx.Hash, mp.network, mp.subnet, mp.vmType)

	return nil
}

// periodicFlush handles periodic flushing of buffered data
func (mp *ManagedPipelineWithDuckLake) periodicFlush() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-mp.ctx.Done():
			return
		case <-ticker.C:
			// Flush Arrow writer
			if mp.arrowWriter != nil {
				if err := mp.arrowWriter.FlushAll(mp.ctx); err != nil {
					log.Printf("Error flushing Arrow writer: %v", err)
				}
			}

			// Flush DuckLake writer
			if mp.duckLakeWriter != nil {
				if err := mp.duckLakeWriter.FlushAll(mp.ctx); err != nil {
					log.Printf("Error flushing DuckLake writer: %v", err)
				}
			}
		}
	}
}

// UpdateNodeConfigs updates the node configurations
func (mp *ManagedPipelineWithDuckLake) UpdateNodeConfigs(nodes []ekkoCommon.NodeConfig) error {
	mp.mutex.Lock()
	defer mp.mutex.Unlock()

	mp.nodes = nodes

	// Update block fetcher with new nodes if needed
	if len(nodes) > 0 && mp.fetcher != nil {
		// For now, just use the first node
		// In a more sophisticated implementation, you might implement failover
		firstNode := nodes[0]
		if err := mp.fetcher.UpdateNodeConfig(firstNode); err != nil {
			log.Printf("Error updating block fetcher config: %v", err)
		}
	}

	log.Printf("Updated node configs for %s-%s-%s: %d nodes",
		mp.network, mp.subnet, mp.vmType, len(nodes))

	return nil
}

// shutdown gracefully shuts down the pipeline
func (mp *ManagedPipelineWithDuckLake) shutdown() {
	mp.mutex.Lock()
	defer mp.mutex.Unlock()

	if !mp.running {
		return
	}

	log.Printf("Shutting down managed pipeline for %s-%s-%s", mp.network, mp.subnet, mp.vmType)

	// Final flush of all writers
	if mp.arrowWriter != nil {
		if err := mp.arrowWriter.FlushAll(context.Background()); err != nil {
			log.Printf("Error during final Arrow flush: %v", err)
		}
		mp.arrowWriter.Close()
	}

	if mp.duckLakeWriter != nil {
		if err := mp.duckLakeWriter.FlushAll(context.Background()); err != nil {
			log.Printf("Error during final DuckLake flush: %v", err)
		}
		mp.duckLakeWriter.Close()
	}

	mp.running = false
	log.Printf("Managed pipeline for %s-%s-%s shut down complete", mp.network, mp.subnet, mp.vmType)
}

// Helper function to get environment variable with default
func getEnvWithDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
