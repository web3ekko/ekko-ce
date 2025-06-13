package storage

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	_ "github.com/marcboeker/go-duckdb"
)

// DuckDBStorage handles blockchain transaction storage using DuckDB with MinIO backend
type DuckDBStorage struct {
	db       *sql.DB
	s3Config S3Config
}

// S3Config holds MinIO/S3 configuration
type S3Config struct {
	Endpoint     string
	AccessKey    string
	SecretKey    string
	UseSSL       bool
	Region       string
	BucketPrefix string // Prefix for bucket names (e.g., "blockchain")
}

// Transaction represents a blockchain transaction
type Transaction struct {
	// Partitioning columns (for Hive format)
	Network   string    `json:"network"`
	Subnet    string    `json:"subnet"`
	VMType    string    `json:"vm_type"`
	BlockTime time.Time `json:"block_time"`
	Year      int       `json:"year"`
	Month     int       `json:"month"`
	Day       int       `json:"day"`
	Hour      int       `json:"hour"`

	// Block information
	BlockHash   string `json:"block_hash"`
	BlockNumber int64  `json:"block_number"`

	// Transaction information
	TxHash      string  `json:"tx_hash"`
	TxIndex     int     `json:"tx_index"`
	FromAddress string  `json:"from_address"`
	ToAddress   *string `json:"to_address,omitempty"`
	Value       string  `json:"value"`
	GasPrice    *string `json:"gas_price,omitempty"`
	GasLimit    *string `json:"gas_limit,omitempty"`
	Nonce       *string `json:"nonce,omitempty"`
	InputData   []byte  `json:"input_data,omitempty"`
	Success     bool    `json:"success"`
}

// NewDuckDBStorage creates a new DuckDB storage instance
func NewDuckDBStorage(s3Config S3Config) (*DuckDBStorage, error) {
	// Open DuckDB connection
	db, err := sql.Open("duckdb", "")
	if err != nil {
		return nil, fmt.Errorf("failed to open DuckDB: %w", err)
	}

	storage := &DuckDBStorage{
		db:       db,
		s3Config: s3Config,
	}

	// Initialize the storage
	if err := storage.initialize(); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to initialize storage: %w", err)
	}

	return storage, nil
}

// initialize sets up DuckDB with S3/MinIO configuration and creates necessary tables
func (s *DuckDBStorage) initialize() error {
	log.Println("🔧 Initializing DuckDB storage with MinIO backend...")

	// Install and load required extensions
	extensions := []string{"aws", "parquet"}
	for _, ext := range extensions {
		if err := s.installExtension(ext); err != nil {
			return fmt.Errorf("failed to install %s extension: %w", ext, err)
		}
	}

	// Configure S3/MinIO settings
	if err := s.configureS3(); err != nil {
		return fmt.Errorf("failed to configure S3: %w", err)
	}

	// Create the main transactions table
	if err := s.createTransactionsTable(); err != nil {
		return fmt.Errorf("failed to create transactions table: %w", err)
	}

	log.Println("✅ DuckDB storage initialized successfully")
	return nil
}

// installExtension installs and loads a DuckDB extension
func (s *DuckDBStorage) installExtension(name string) error {
	log.Printf("📦 Installing %s extension...", name)

	// Install extension
	if _, err := s.db.Exec(fmt.Sprintf("INSTALL %s", name)); err != nil {
		return fmt.Errorf("failed to install %s: %w", name, err)
	}

	// Load extension
	if _, err := s.db.Exec(fmt.Sprintf("LOAD %s", name)); err != nil {
		return fmt.Errorf("failed to load %s: %w", name, err)
	}

	log.Printf("✅ %s extension loaded successfully", name)
	return nil
}

// configureS3 sets up S3/MinIO configuration in DuckDB
func (s *DuckDBStorage) configureS3() error {
	log.Printf("🔗 Configuring S3 for endpoint: %s", s.s3Config.Endpoint)

	queries := []string{
		fmt.Sprintf("SET s3_endpoint='%s'", s.s3Config.Endpoint),
		fmt.Sprintf("SET s3_access_key_id='%s'", s.s3Config.AccessKey),
		fmt.Sprintf("SET s3_secret_access_key='%s'", s.s3Config.SecretKey),
		fmt.Sprintf("SET s3_use_ssl=%t", s.s3Config.UseSSL),
		fmt.Sprintf("SET s3_region='%s'", s.s3Config.Region),
	}

	for _, query := range queries {
		if _, err := s.db.Exec(query); err != nil {
			return fmt.Errorf("failed to execute %s: %w", query, err)
		}
	}

	log.Println("✅ S3/MinIO configuration completed")
	return nil
}

// createTransactionsTable creates the main transactions table
func (s *DuckDBStorage) createTransactionsTable() error {
	log.Println("🗃️ Creating transactions table...")

	query := `
		CREATE TABLE IF NOT EXISTS transactions (
			-- Partitioning columns (for Hive format)
			network VARCHAR NOT NULL,
			subnet VARCHAR NOT NULL,
			vm_type VARCHAR NOT NULL,
			block_time TIMESTAMP WITH TIME ZONE NOT NULL,
			year INTEGER NOT NULL,
			month INTEGER NOT NULL,
			day INTEGER NOT NULL,
			hour INTEGER NOT NULL,
			
			-- Block information
			block_hash VARCHAR NOT NULL,
			block_number BIGINT NOT NULL,
			
			-- Transaction information
			tx_hash VARCHAR PRIMARY KEY,
			tx_index INTEGER NOT NULL,
			from_address VARCHAR NOT NULL,
			to_address VARCHAR,
			value VARCHAR NOT NULL,
			gas_price VARCHAR,
			gas_limit VARCHAR,
			nonce VARCHAR,
			input_data BLOB,
			success BOOLEAN NOT NULL DEFAULT true
		)
	`

	if _, err := s.db.Exec(query); err != nil {
		return fmt.Errorf("failed to create transactions table: %w", err)
	}

	log.Println("✅ Transactions table created successfully")
	return nil
}

// getBucketName generates bucket name for network-subnet combination
func (s *DuckDBStorage) getBucketName(network, subnet string) string {
	// Convert to lowercase and replace spaces/special chars with hyphens
	networkClean := strings.ToLower(strings.ReplaceAll(network, " ", "-"))
	subnetClean := strings.ToLower(strings.ReplaceAll(subnet, " ", "-"))

	// Format: {prefix}-{network}-{subnet}
	return fmt.Sprintf("%s-%s-%s", s.s3Config.BucketPrefix, networkClean, subnetClean)
}

// StoreTransaction stores a single transaction
func (s *DuckDBStorage) StoreTransaction(tx Transaction) error {
	// Set partitioning fields based on block time
	tx.Year = tx.BlockTime.Year()
	tx.Month = int(tx.BlockTime.Month())
	tx.Day = tx.BlockTime.Day()
	tx.Hour = tx.BlockTime.Hour()

	query := `
		INSERT INTO transactions (
			network, subnet, vm_type, block_time, year, month, day, hour,
			block_hash, block_number, tx_hash, tx_index, from_address, to_address,
			value, gas_price, gas_limit, nonce, input_data, success
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err := s.db.Exec(query,
		tx.Network, tx.Subnet, tx.VMType, tx.BlockTime, tx.Year, tx.Month, tx.Day, tx.Hour,
		tx.BlockHash, tx.BlockNumber, tx.TxHash, tx.TxIndex, tx.FromAddress, tx.ToAddress,
		tx.Value, tx.GasPrice, tx.GasLimit, tx.Nonce, tx.InputData, tx.Success,
	)

	if err != nil {
		return fmt.Errorf("failed to store transaction %s: %w", tx.TxHash, err)
	}

	return nil
}

// StoreTransactionBatch stores multiple transactions efficiently
func (s *DuckDBStorage) StoreTransactionBatch(transactions []Transaction) error {
	if len(transactions) == 0 {
		return nil
	}

	log.Printf("💾 Storing batch of %d transactions...", len(transactions))

	// Begin transaction for batch insert
	tx, err := s.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Prepare statement
	stmt, err := tx.Prepare(`
		INSERT INTO transactions (
			network, subnet, vm_type, block_time, year, month, day, hour,
			block_hash, block_number, tx_hash, tx_index, from_address, to_address,
			value, gas_price, gas_limit, nonce, input_data, success
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return fmt.Errorf("failed to prepare statement: %w", err)
	}
	defer stmt.Close()

	// Insert all transactions
	for _, transaction := range transactions {
		// Set partitioning fields
		transaction.Year = transaction.BlockTime.Year()
		transaction.Month = int(transaction.BlockTime.Month())
		transaction.Day = transaction.BlockTime.Day()
		transaction.Hour = transaction.BlockTime.Hour()

		_, err := stmt.Exec(
			transaction.Network, transaction.Subnet, transaction.VMType, transaction.BlockTime,
			transaction.Year, transaction.Month, transaction.Day, transaction.Hour,
			transaction.BlockHash, transaction.BlockNumber, transaction.TxHash, transaction.TxIndex,
			transaction.FromAddress, transaction.ToAddress, transaction.Value, transaction.GasPrice,
			transaction.GasLimit, transaction.Nonce, transaction.InputData, transaction.Success,
		)
		if err != nil {
			return fmt.Errorf("failed to insert transaction %s: %w", transaction.TxHash, err)
		}
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit batch: %w", err)
	}

	log.Printf("✅ Successfully stored %d transactions", len(transactions))
	return nil
}

// ExportToParquet exports transactions to MinIO in Hive-partitioned Parquet format
// Each network-subnet combination gets its own bucket
func (s *DuckDBStorage) ExportToParquet(network, subnet, vmType string, startTime, endTime time.Time) error {
	bucketName := s.getBucketName(network, subnet)
	log.Printf("📤 Exporting transactions to Parquet (Hive format) for %s/%s/%s to bucket: %s",
		network, subnet, vmType, bucketName)

	// Create S3 path: s3://bucket-network-subnet/vm_type=X/year=YYYY/month=MM/day=DD/
	s3Path := fmt.Sprintf("s3://%s", bucketName)

	// Export query with Hive partitioning by vm_type, year, month, day
	query := fmt.Sprintf(`
		COPY (
			SELECT
				block_time, block_hash, block_number,
				tx_hash, tx_index, from_address, to_address,
				value, gas_price, gas_limit, nonce, input_data, success,
				vm_type, year, month, day, hour
			FROM transactions
			WHERE network = ?
			AND subnet = ?
			AND vm_type = ?
			AND block_time >= ?
			AND block_time < ?
		) TO '%s' (
			FORMAT PARQUET,
			PARTITION_BY (vm_type, year, month, day),
			OVERWRITE_OR_IGNORE true
		)
	`, s3Path)

	_, err := s.db.Exec(query, network, subnet, vmType, startTime, endTime)
	if err != nil {
		return fmt.Errorf("failed to export to Parquet: %w", err)
	}

	log.Printf("✅ Successfully exported transactions to %s", s3Path)
	return nil
}

// ExportAllToParquet exports all transactions to MinIO, creating separate buckets per network-subnet
func (s *DuckDBStorage) ExportAllToParquet() error {
	log.Println("📤 Exporting all transactions to Parquet (Hive format) with separate buckets per network-subnet...")

	// Get all unique network-subnet combinations
	rows, err := s.db.Query("SELECT DISTINCT network, subnet FROM transactions ORDER BY network, subnet")
	if err != nil {
		return fmt.Errorf("failed to get network-subnet combinations: %w", err)
	}
	defer rows.Close()

	var combinations []struct {
		Network string
		Subnet  string
	}

	for rows.Next() {
		var network, subnet string
		if err := rows.Scan(&network, &subnet); err != nil {
			return fmt.Errorf("failed to scan network-subnet: %w", err)
		}
		combinations = append(combinations, struct {
			Network string
			Subnet  string
		}{Network: network, Subnet: subnet})
	}

	// Export each network-subnet combination to its own bucket
	for _, combo := range combinations {
		bucketName := s.getBucketName(combo.Network, combo.Subnet)
		s3Path := fmt.Sprintf("s3://%s", bucketName)

		log.Printf("📤 Exporting %s/%s to bucket: %s", combo.Network, combo.Subnet, bucketName)

		query := fmt.Sprintf(`
			COPY (
				SELECT
					block_time, block_hash, block_number,
					tx_hash, tx_index, from_address, to_address,
					value, gas_price, gas_limit, nonce, input_data, success,
					vm_type, year, month, day, hour
				FROM transactions
				WHERE network = ? AND subnet = ?
				ORDER BY vm_type, year, month, day, hour, block_time
			) TO '%s' (
				FORMAT PARQUET,
				PARTITION_BY (vm_type, year, month, day),
				OVERWRITE_OR_IGNORE true
			)
		`, s3Path)

		_, err := s.db.Exec(query, combo.Network, combo.Subnet)
		if err != nil {
			return fmt.Errorf("failed to export %s/%s to Parquet: %w", combo.Network, combo.Subnet, err)
		}

		log.Printf("✅ Successfully exported %s/%s to %s", combo.Network, combo.Subnet, s3Path)
	}

	log.Printf("✅ Successfully exported all transactions to %d buckets", len(combinations))
	return nil
}

// QueryFromParquet queries transactions directly from Parquet files in MinIO
func (s *DuckDBStorage) QueryFromParquet(network, subnet, vmType string, startTime, endTime time.Time) ([]Transaction, error) {
	bucketName := s.getBucketName(network, subnet)
	log.Printf("🔍 Querying transactions from Parquet for %s/%s/%s from bucket: %s",
		network, subnet, vmType, bucketName)

	// Construct S3 path for the specific network-subnet bucket
	s3Path := fmt.Sprintf("s3://%s", bucketName)

	// Use Hive partitioning for efficient querying
	query := fmt.Sprintf(`
		SELECT
			'%s' as network, '%s' as subnet, vm_type,
			block_time, year, month, day, hour,
			block_hash, block_number, tx_hash, tx_index, from_address, to_address,
			value, gas_price, gas_limit, nonce, input_data, success
		FROM read_parquet('%s/**/*.parquet', hive_partitioning=true)
		WHERE vm_type = ?
		AND block_time >= ?
		AND block_time < ?
		ORDER BY block_time, tx_index
	`, network, subnet, s3Path)

	rows, err := s.db.Query(query, vmType, startTime, endTime)
	if err != nil {
		return nil, fmt.Errorf("failed to query from Parquet: %w", err)
	}
	defer rows.Close()

	var transactions []Transaction
	for rows.Next() {
		var tx Transaction
		err := rows.Scan(
			&tx.Network, &tx.Subnet, &tx.VMType, &tx.BlockTime, &tx.Year, &tx.Month, &tx.Day, &tx.Hour,
			&tx.BlockHash, &tx.BlockNumber, &tx.TxHash, &tx.TxIndex, &tx.FromAddress, &tx.ToAddress,
			&tx.Value, &tx.GasPrice, &tx.GasLimit, &tx.Nonce, &tx.InputData, &tx.Success,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan transaction: %w", err)
		}
		transactions = append(transactions, tx)
	}

	log.Printf("✅ Found %d transactions", len(transactions))
	return transactions, nil
}

// GetTransactionStats returns statistics about stored transactions
func (s *DuckDBStorage) GetTransactionStats() (map[string]interface{}, error) {
	log.Println("📊 Getting transaction statistics...")

	stats := make(map[string]interface{})

	// Total count
	var totalCount int64
	err := s.db.QueryRow("SELECT COUNT(*) FROM transactions").Scan(&totalCount)
	if err != nil {
		return nil, fmt.Errorf("failed to get total count: %w", err)
	}
	stats["total_transactions"] = totalCount

	// Count by network-subnet-vmtype with bucket names
	rows, err := s.db.Query(`
		SELECT network, subnet, vm_type, COUNT(*) as count
		FROM transactions
		GROUP BY network, subnet, vm_type
		ORDER BY count DESC
	`)
	if err != nil {
		return nil, fmt.Errorf("failed to get network stats: %w", err)
	}
	defer rows.Close()

	networkStats := make(map[string]map[string]interface{})
	for rows.Next() {
		var network, subnet, vmType string
		var count int64
		if err := rows.Scan(&network, &subnet, &vmType, &count); err != nil {
			return nil, fmt.Errorf("failed to scan network stats: %w", err)
		}

		key := fmt.Sprintf("%s/%s", network, subnet)
		if networkStats[key] == nil {
			networkStats[key] = map[string]interface{}{
				"bucket_name": s.getBucketName(network, subnet),
				"vm_types":    make(map[string]int64),
				"total":       int64(0),
			}
		}

		networkStats[key]["vm_types"].(map[string]int64)[vmType] = count
		networkStats[key]["total"] = networkStats[key]["total"].(int64) + count
	}
	stats["by_network_subnet"] = networkStats

	// Date range
	var minTime, maxTime time.Time
	err = s.db.QueryRow("SELECT MIN(block_time), MAX(block_time) FROM transactions").Scan(&minTime, &maxTime)
	if err != nil {
		return nil, fmt.Errorf("failed to get date range: %w", err)
	}
	stats["earliest_transaction"] = minTime
	stats["latest_transaction"] = maxTime

	log.Printf("✅ Statistics: %d total transactions across %d network-subnet combinations",
		totalCount, len(networkStats))
	return stats, nil
}

// Close closes the DuckDB connection
func (s *DuckDBStorage) Close() error {
	if s.db != nil {
		return s.db.Close()
	}
	return nil
}

// NewS3ConfigFromEnv creates S3Config from environment variables
func NewS3ConfigFromEnv() S3Config {
	return S3Config{
		Endpoint:     getEnvOrDefault("MINIO_ENDPOINT", "localhost:9000"),
		AccessKey:    getEnvOrDefault("MINIO_ACCESS_KEY", "minioadmin"),
		SecretKey:    getEnvOrDefault("MINIO_SECRET_KEY", "minioadmin"),
		UseSSL:       getEnvOrDefault("MINIO_USE_SSL", "false") == "true",
		Region:       getEnvOrDefault("MINIO_REGION", "us-east-1"),
		BucketPrefix: getEnvOrDefault("MINIO_BUCKET_PREFIX", "blockchain"),
	}
}

// getEnvOrDefault gets environment variable or returns default value
func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
