package persistence

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"sync"
	"time"

	_ "github.com/marcboeker/go-duckdb" // DuckDB driver
	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	ekkoCommon "github.com/web3ekko/ekko-ce/pipeline/pkg/common"
)

// DuckLakeWriterConfig holds configuration for the DuckLake writer
type DuckLakeWriterConfig struct {
	CatalogType   string        // Catalog type: sqlite, duckdb, postgres, mysql
	CatalogPath   string        // Path to catalog database (SQLite file, DuckDB file, etc.)
	DataPath      string        // S3 path to DuckLake data directory
	BucketName    string        // MinIO bucket name for DuckLake data
	BatchSize     int           // Number of transactions to batch before writing
	FlushInterval time.Duration // Maximum time to wait before flushing
	MaxRetries    int           // Maximum number of retry attempts
	RetryDelay    time.Duration // Delay between retry attempts

	// MinIO connection settings
	MinioEndpoint  string
	MinioAccessKey string
	MinioSecretKey string
	MinioSecure    bool
	MinioRegion    string
}

// DuckLakeWriter handles buffering transactions and writing them to DuckLake format
type DuckLakeWriter struct {
	config         DuckLakeWriterConfig
	natsConn       *nats.Conn
	db             *sql.DB
	mutex          sync.Mutex
	transactions   map[string][]TransactionRecord   // Network-subnet-vmType -> transactions
	networkConfigs map[string]ekkoCommon.NodeConfig // Network-subnet-vmType -> config
	lastFlush      map[string]time.Time             // Network-subnet-vmType -> last flush time
	shutdownCh     chan struct{}
	isInitialized  bool
}

// NewDuckLakeWriter creates a new DuckLake writer instance
func NewDuckLakeWriter(config DuckLakeWriterConfig, natsConn *nats.Conn) (*DuckLakeWriter, error) {
	writer := &DuckLakeWriter{
		config:         config,
		natsConn:       natsConn,
		transactions:   make(map[string][]TransactionRecord),
		networkConfigs: make(map[string]ekkoCommon.NodeConfig),
		lastFlush:      make(map[string]time.Time),
		shutdownCh:     make(chan struct{}),
	}

	if err := writer.initialize(); err != nil {
		return nil, fmt.Errorf("failed to initialize DuckLake writer: %w", err)
	}

	return writer, nil
}

// initialize sets up the DuckDB connection and DuckLake database
func (dw *DuckLakeWriter) initialize() error {
	// Open DuckDB connection (in-memory for DuckLake with MinIO backend)
	db, err := sql.Open("duckdb", "")
	if err != nil {
		return fmt.Errorf("failed to open DuckDB connection: %w", err)
	}
	dw.db = db

	// Install and load DuckLake extension
	if err := dw.setupDuckLake(); err != nil {
		return fmt.Errorf("failed to setup DuckLake: %w", err)
	}

	dw.isInitialized = true
	log.Printf("DuckLake writer initialized successfully")
	return nil
}

// setupDuckLake installs DuckLake extension and creates/attaches the database
func (dw *DuckLakeWriter) setupDuckLake() error {
	// Install DuckLake extension
	if _, err := dw.db.Exec("INSTALL ducklake;"); err != nil {
		return fmt.Errorf("failed to install ducklake extension: %w", err)
	}

	// Load DuckLake extension
	if _, err := dw.db.Exec("LOAD ducklake;"); err != nil {
		return fmt.Errorf("failed to load ducklake extension: %w", err)
	}

	// Install and load httpfs for S3/MinIO support
	if _, err := dw.db.Exec("INSTALL httpfs;"); err != nil {
		return fmt.Errorf("failed to install httpfs extension: %w", err)
	}
	if _, err := dw.db.Exec("LOAD httpfs;"); err != nil {
		return fmt.Errorf("failed to load httpfs extension: %w", err)
	}

	// Configure S3/MinIO settings
	if err := dw.configureMinIO(); err != nil {
		return fmt.Errorf("failed to configure MinIO: %w", err)
	}

	// Attach DuckLake database with SQLite catalog and MinIO storage
	var attachSQL string
	switch dw.config.CatalogType {
	case "sqlite":
		attachSQL = fmt.Sprintf(
			"ATTACH 'ducklake:sqlite:%s' AS blockchain (DATA_PATH '%s');",
			dw.config.CatalogPath,
			dw.config.DataPath,
		)
	case "duckdb":
		attachSQL = fmt.Sprintf(
			"ATTACH 'ducklake:%s' AS blockchain (DATA_PATH '%s');",
			dw.config.CatalogPath,
			dw.config.DataPath,
		)
	default:
		return fmt.Errorf("unsupported catalog type: %s", dw.config.CatalogType)
	}

	if _, err := dw.db.Exec(attachSQL); err != nil {
		return fmt.Errorf("failed to attach DuckLake database: %w", err)
	}

	// Create transactions table if it doesn't exist
	if err := dw.createTransactionsTable(); err != nil {
		return fmt.Errorf("failed to create transactions table: %w", err)
	}

	log.Printf("DuckLake database attached and transactions table ready")
	return nil
}

// configureMinIO sets up S3/MinIO connection settings for DuckDB
func (dw *DuckLakeWriter) configureMinIO() error {
	// Set S3/MinIO configuration
	configs := []struct {
		setting string
		value   string
	}{
		{"s3_endpoint", dw.config.MinioEndpoint},
		{"s3_access_key_id", dw.config.MinioAccessKey},
		{"s3_secret_access_key", dw.config.MinioSecretKey},
		{"s3_region", dw.config.MinioRegion},
		{"s3_use_ssl", fmt.Sprintf("%t", dw.config.MinioSecure)},
	}

	for _, config := range configs {
		sql := fmt.Sprintf("SET %s='%s';", config.setting, config.value)
		if _, err := dw.db.Exec(sql); err != nil {
			return fmt.Errorf("failed to set %s: %w", config.setting, err)
		}
	}

	log.Printf("MinIO configuration applied: endpoint=%s, region=%s, secure=%t",
		dw.config.MinioEndpoint, dw.config.MinioRegion, dw.config.MinioSecure)
	return nil
}

// createTransactionsTable creates the transactions table in DuckLake
func (dw *DuckLakeWriter) createTransactionsTable() error {
	createTableSQL := `
		CREATE TABLE IF NOT EXISTS blockchain.transactions (
			-- Partition columns
			network VARCHAR NOT NULL,
			subnet VARCHAR NOT NULL,
			vm_type VARCHAR NOT NULL,
			
			-- Time fields
			block_time TIMESTAMP WITH TIME ZONE NOT NULL,
			year INTEGER NOT NULL,
			month INTEGER NOT NULL,
			day INTEGER NOT NULL,
			hour INTEGER NOT NULL,
			
			-- Block information
			block_hash VARCHAR NOT NULL,
			block_number BIGINT NOT NULL,
			
			-- Transaction data
			tx_hash VARCHAR PRIMARY KEY,
			tx_index INTEGER NOT NULL,
			from_address VARCHAR NOT NULL,
			to_address VARCHAR,
			value VARCHAR NOT NULL,
			gas_price VARCHAR NOT NULL,
			gas_limit VARCHAR NOT NULL,
			nonce VARCHAR NOT NULL,
			input_data BLOB,
			
			-- Derived fields
			success BOOLEAN NOT NULL DEFAULT true,
			
			-- Metadata
			ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
		);
	`

	if _, err := dw.db.Exec(createTableSQL); err != nil {
		return fmt.Errorf("failed to create transactions table: %w", err)
	}

	return nil
}

// WriteTransaction adds a transaction to the buffer for writing to DuckLake
func (dw *DuckLakeWriter) WriteTransaction(ctx context.Context, tx blockchain.Transaction, nodeConfig ekkoCommon.NodeConfig) error {
	if !dw.isInitialized {
		return fmt.Errorf("DuckLake writer not initialized")
	}

	network := nodeConfig.Network
	subnet := nodeConfig.Subnet
	vmType := nodeConfig.VMType

	// Convert to TransactionRecord - use current time if block time is not available
	txRecord := FromBlockchainTransaction(tx, network, subnet, vmType, time.Now())

	// Add to buffer
	dw.mutex.Lock()
	defer dw.mutex.Unlock()

	networkKey := fmt.Sprintf("%s:%s:%s", network, subnet, vmType)
	dw.networkConfigs[networkKey] = nodeConfig
	dw.transactions[networkKey] = append(dw.transactions[networkKey], txRecord)

	// Check if we need to flush
	if len(dw.transactions[networkKey]) >= dw.config.BatchSize {
		if err := dw.flushBatchLocked(ctx, networkKey); err != nil {
			log.Printf("Error flushing batch for %s: %v", networkKey, err)
		}
	}

	return nil
}

// flushBatchLocked writes a batch of transactions to DuckLake (assumes mutex is held)
func (dw *DuckLakeWriter) flushBatchLocked(ctx context.Context, networkKey string) error {
	transactions := dw.transactions[networkKey]
	if len(transactions) == 0 {
		return nil
	}

	log.Printf("Flushing %d transactions for %s to DuckLake", len(transactions), networkKey)

	// Prepare batch insert statement
	insertSQL := `
		INSERT INTO blockchain.transactions (
			network, subnet, vm_type, block_time, year, month, day, hour,
			block_hash, block_number, tx_hash, tx_index, from_address, to_address,
			value, gas_price, gas_limit, nonce, input_data, success, ingested_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	// Begin transaction
	tx, err := dw.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Prepare statement
	stmt, err := tx.PrepareContext(ctx, insertSQL)
	if err != nil {
		return fmt.Errorf("failed to prepare statement: %w", err)
	}
	defer stmt.Close()

	// Insert each transaction
	for _, txRecord := range transactions {
		_, err := stmt.ExecContext(ctx,
			txRecord.Network, txRecord.Subnet, txRecord.VMType,
			txRecord.BlockTime, txRecord.Year, txRecord.Month, txRecord.Day, txRecord.Hour,
			txRecord.BlockHash, txRecord.BlockNumber, txRecord.TxHash, txRecord.TxIndex,
			txRecord.From, txRecord.To, txRecord.Value, txRecord.GasPrice, txRecord.GasLimit,
			txRecord.Nonce, txRecord.InputData, txRecord.Success, time.Now(),
		)
		if err != nil {
			return fmt.Errorf("failed to insert transaction %s: %w", txRecord.TxHash, err)
		}
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	// Clear the buffer and update last flush time
	dw.transactions[networkKey] = nil
	dw.lastFlush[networkKey] = time.Now()

	log.Printf("Successfully flushed %d transactions for %s to DuckLake", len(transactions), networkKey)
	return nil
}

// StartPeriodicFlush starts a goroutine that periodically flushes buffered transactions
func (dw *DuckLakeWriter) StartPeriodicFlush(ctx context.Context) {
	go func() {
		ticker := time.NewTicker(dw.config.FlushInterval)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-dw.shutdownCh:
				return
			case <-ticker.C:
				dw.flushAll(ctx)
			}
		}
	}()
}

// flushAll flushes all buffered transactions
func (dw *DuckLakeWriter) flushAll(ctx context.Context) {
	dw.mutex.Lock()
	defer dw.mutex.Unlock()

	for networkKey := range dw.transactions {
		if len(dw.transactions[networkKey]) > 0 {
			if err := dw.flushBatchLocked(ctx, networkKey); err != nil {
				log.Printf("Error flushing batch for %s: %v", networkKey, err)
			}
		}
	}
}

// Close gracefully shuts down the DuckLake writer
func (dw *DuckLakeWriter) Close() error {
	close(dw.shutdownCh)

	// Flush any remaining transactions
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	dw.flushAll(ctx)

	// Close database connection
	if dw.db != nil {
		return dw.db.Close()
	}

	return nil
}
