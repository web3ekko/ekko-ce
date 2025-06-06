package persistence

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	// arrow is used indirectly via record.Schema() from ipc package
	_ "github.com/apache/arrow/go/v15/arrow"
	"github.com/apache/arrow/go/v15/arrow/ipc"
	"github.com/apache/arrow/go/v15/arrow/memory"
	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/common"
)

// ArrowWriterConfig contains configuration for the ArrowWriter
type ArrowWriterConfig struct {
	BatchSize          int           // Number of transactions in a batch before flushing
	FlushInterval      time.Duration // Maximum time to wait before flushing a batch
	MinioConfig        MinioConfig   // Configuration for MinIO connection
	NatsURL            string        // NATS server URL for subscribing to events
	NatsSubjectPattern string        // Pattern like "ekko.%s.%s.%s.persistence"
}

// ArrowWriter handles buffering transactions and writing them to Arrow format
type ArrowWriter struct {
	config         ArrowWriterConfig
	natsConn       *nats.Conn
	minioStorage   *MinioStorage
	mutex          sync.Mutex
	transactions   map[string][]TransactionRecord // Network-subnet-vmType -> transactions
	networkConfigs map[string]common.NodeConfig   // Network-subnet-vmType -> config
	lastFlush      map[string]time.Time           // Network-subnet-vmType -> last flush time
	shutdownCh     chan struct{}
	allocator      memory.Allocator // Arrow memory allocator
}

// NewArrowWriter creates a new ArrowWriter
func NewArrowWriter(config ArrowWriterConfig) (*ArrowWriter, error) {
	// Create MinIO storage client
	minioStorage, err := NewMinioStorage(config.MinioConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create MinIO storage client: %w", err)
	}

	// Connect to NATS
	natsConn, err := nats.Connect(config.NatsURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to NATS: %w", err)
	}

	// Use default memory allocator for Arrow operations
	alloc := memory.NewGoAllocator()

	return &ArrowWriter{
		config:         config,
		natsConn:       natsConn,
		minioStorage:   minioStorage,
		transactions:   make(map[string][]TransactionRecord),
		networkConfigs: make(map[string]common.NodeConfig),
		lastFlush:      make(map[string]time.Time),
		shutdownCh:     make(chan struct{}),
		allocator:      alloc,
	}, nil
}

// Start begins listening for transactions and periodically flushing batches
func (aw *ArrowWriter) Start(ctx context.Context) error {
	log.Println("Starting ArrowWriter service")

	// Subscribe to persistence events from all networks
	sub, err := aw.natsConn.Subscribe(aw.config.NatsSubjectPattern, func(msg *nats.Msg) {
		if err := aw.handleNatsMessage(ctx, msg); err != nil {
			log.Printf("Error handling NATS message: %v", err)
		}
	})
	if err != nil {
		return fmt.Errorf("failed to subscribe to NATS: %w", err)
	}
	defer sub.Unsubscribe()

	// Start periodic flusher
	ticker := time.NewTicker(10 * time.Second) // Check every 10 seconds if any batches need flushing
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			if err := aw.checkAndFlushBatches(ctx); err != nil {
				log.Printf("Error flushing batches: %v", err)
			}
		case <-ctx.Done():
			log.Println("Context cancelled, stopping ArrowWriter")
			return nil
		case <-aw.shutdownCh:
			log.Println("Shutdown signal received, stopping ArrowWriter")
			return aw.flushAllBatches(ctx)
		}
	}
}

// Stop gracefully stops the ArrowWriter
func (aw *ArrowWriter) Stop(ctx context.Context) error {
	log.Println("Stopping ArrowWriter service")
	close(aw.shutdownCh)
	return nil
}

// handleNatsMessage processes incoming NATS transaction messages
func (aw *ArrowWriter) handleNatsMessage(ctx context.Context, msg *nats.Msg) error {
	log.Printf("DEBUG: Received NATS message on subject: %s", msg.Subject)
	
	var tx blockchain.Transaction
	if err := json.Unmarshal(msg.Data, &tx); err != nil {
		return fmt.Errorf("failed to unmarshal transaction: %w", err)
	}
	log.Printf("DEBUG: Unmarshalled transaction hash: %s", tx.Hash)

	// Extract network info from NATS subject
	// Example: "ekko.ethereum.mainnet.evm.persistence"
	parts := strings.Split(msg.Subject, ".")
	if len(parts) < 5 {
		return fmt.Errorf("invalid NATS subject format: %s", msg.Subject)
	}

	network := parts[1]
	subnet := parts[2]
	vmType := parts[3]
	
	// Create node config if it doesn't exist
	nodeConfig := common.NodeConfig{
		Network: network,
		Subnet:  subnet,
		VMType:  vmType,
	}

	// Convert to TransactionRecord - use current time if block time is not available
	txRecord := FromBlockchainTransaction(tx, network, subnet, vmType, time.Now())

	// Add to buffer
	aw.mutex.Lock()
	defer aw.mutex.Unlock()

	networkKey := fmt.Sprintf("%s:%s:%s", network, subnet, vmType)
	aw.networkConfigs[networkKey] = nodeConfig
	aw.transactions[networkKey] = append(aw.transactions[networkKey], txRecord)

	// Check if we need to flush
	if len(aw.transactions[networkKey]) >= aw.config.BatchSize {
		if err := aw.flushBatchLocked(ctx, networkKey); err != nil {
			log.Printf("Error flushing batch for %s: %v", networkKey, err)
		}
	}

	return nil
}

// checkAndFlushBatches checks if any batches need to be flushed based on time
func (aw *ArrowWriter) checkAndFlushBatches(ctx context.Context) error {
	aw.mutex.Lock()
	defer aw.mutex.Unlock()

	now := time.Now()
	var errors []error

	for networkKey, lastFlushTime := range aw.lastFlush {
		// If we have transactions and it's been longer than the flush interval since the last flush
		if len(aw.transactions[networkKey]) > 0 && now.Sub(lastFlushTime) >= aw.config.FlushInterval {
			if err := aw.flushBatchLocked(ctx, networkKey); err != nil {
				errors = append(errors, fmt.Errorf("failed to flush batch for %s: %w", networkKey, err))
			}
		}
	}

	if len(errors) > 0 {
		return fmt.Errorf("errors flushing batches: %v", errors)
	}

	return nil
}

// flushBatch flushes a batch of transactions for the given network key
func (aw *ArrowWriter) flushBatch(ctx context.Context, networkKey string) error {
	aw.mutex.Lock()
	defer aw.mutex.Unlock()
	return aw.flushBatchLocked(ctx, networkKey)
}

// flushBatchLocked flushes a batch of transactions without acquiring the lock
// Caller must hold the mutex
func (aw *ArrowWriter) flushBatchLocked(ctx context.Context, networkKey string) error {
	transactions := aw.transactions[networkKey]
	if len(transactions) == 0 {
		return nil
	}
	
	log.Printf("DEBUG: Flushing batch of %d transactions for network key: %s", len(transactions), networkKey)
	
	nodeConfig := aw.networkConfigs[networkKey]
	
	// Find min/max blocks and times
	var minBlock, maxBlock uint64 = ^uint64(0), 0
	var minTime, maxTime time.Time = time.Now(), time.Time{}
	
	for _, tx := range transactions {
		if tx.BlockNumber < minBlock {
			minBlock = tx.BlockNumber
		}
		if tx.BlockNumber > maxBlock {
			maxBlock = tx.BlockNumber
		}
		if tx.BlockTime.Before(minTime) {
			minTime = tx.BlockTime
		}
		if tx.BlockTime.After(maxTime) {
			maxTime = tx.BlockTime
		}
	}
	
	// Generate filename with UUID for uniqueness
	now := time.Now()
	uid := uuid.New().String()
	filename := fmt.Sprintf("transactions_%s_%s.arrow", 
		now.Format("20060102T150405"), 
		uid[:8])
	
	// Build object path using Hive-style partitioning
	objectPath := aw.minioStorage.BuildObjectPath(
		nodeConfig.Network, 
		nodeConfig.Subnet, 
		nodeConfig.VMType, 
		minBlock, 
		maxBlock, 
		minTime.Format(time.RFC3339), 
		maxTime.Format(time.RFC3339),
		now.Format(time.RFC3339),
		filename,
	)
	
	// Create a temporary file for the Arrow data
	tmpFile, err := os.CreateTemp("", "transactions_*.arrow")
	if err != nil {
		return fmt.Errorf("failed to create temp file: %w", err)
	}
	defer os.Remove(tmpFile.Name())
	defer tmpFile.Close()
	
	// Create Arrow record from transactions
	record := CreateArrowRecord(transactions, aw.allocator)
	if record == nil {
		return fmt.Errorf("failed to create Arrow record from transactions")
	}
	defer record.Release()
	
	// Create Arrow file writer
	writer, err := ipc.NewFileWriter(tmpFile, ipc.WithSchema(record.Schema()))
	if err != nil {
		return fmt.Errorf("failed to create Arrow file writer: %w", err)
	}
	
	// Write record to file
	if err := writer.Write(record); err != nil {
		return fmt.Errorf("failed to write record: %w", err)
	}
	
	// Close the writer to finalize the file
	if err := writer.Close(); err != nil {
		return fmt.Errorf("failed to close Arrow file writer: %w", err)
	}
	
	// Rewind file for reading
	if _, err := tmpFile.Seek(0, io.SeekStart); err != nil {
		return fmt.Errorf("failed to seek temp file: %w", err)
	}
	
	// Get file size
	fileInfo, err := tmpFile.Stat()
	if err != nil {
		return fmt.Errorf("failed to get file size: %w", err)
	}
	
	// Upload to MinIO
	info, err := aw.minioStorage.Upload(ctx, objectPath, tmpFile, fileInfo.Size(), "application/octet-stream")
	if err != nil {
		return fmt.Errorf("failed to upload to MinIO: %w", err)
	}
	
	log.Printf("Successfully wrote %d transactions to %s (size: %d bytes)", len(transactions), objectPath, info.Size)
	
	// Create metadata for this batch
	metadata := BatchMetadata{
		Network:    nodeConfig.Network,
		Subnet:     nodeConfig.Subnet,
		VMType:     nodeConfig.VMType,
		StartBlock: minBlock,
		EndBlock:   maxBlock,
		StartTime:  minTime,
		EndTime:    maxTime,
		TxCount:    len(transactions),
		FilePath:   objectPath,
		FileSize:   info.Size,
		CreatedAt:  now,
	}
	
	// Write metadata to MinIO
	metadataJson, err := json.Marshal(metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}
	
	metadataPath := objectPath + ".metadata.json"
	_, err = aw.minioStorage.Upload(
		ctx, 
		metadataPath, 
		bytes.NewReader(metadataJson), 
		int64(len(metadataJson)), 
		"application/json",
	)
	if err != nil {
		log.Printf("Warning: failed to write metadata: %v", err)
	}
	
	// Clear batch
	aw.transactions[networkKey] = nil
	aw.lastFlush[networkKey] = now
	
	return nil
}

// flushAllBatches flushes all batches
func (aw *ArrowWriter) flushAllBatches(ctx context.Context) error {
	aw.mutex.Lock()
	defer aw.mutex.Unlock()
	
	var errors []error
	
	for networkKey := range aw.transactions {
		if len(aw.transactions[networkKey]) > 0 {
			if err := aw.flushBatchLocked(ctx, networkKey); err != nil {
				errors = append(errors, fmt.Errorf("failed to flush batch for %s: %w", networkKey, err))
			}
		}
	}
	
	if len(errors) > 0 {
		return fmt.Errorf("errors flushing batches: %v", errors)
	}
	
	return nil
}
