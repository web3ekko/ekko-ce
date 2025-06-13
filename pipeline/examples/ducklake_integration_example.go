package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/internal/config"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	ekkoCommon "github.com/web3ekko/ekko-ce/pipeline/pkg/common"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/persistence"
)

// DuckLakeIntegrationExample demonstrates how to integrate DuckLake writer into the pipeline
func main() {
	log.Println("🚀 DuckLake Integration Example")
	log.Println("==============================")

	// Load configuration
	cfg, err := config.LoadFromEnv()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// Check if DuckLake is enabled
	if !cfg.DuckLakeEnabled {
		log.Println("⚠️  DuckLake is not enabled. Set DUCKLAKE_ENABLED=true to enable.")
		log.Println("Example environment variables:")
		log.Println("  DUCKLAKE_ENABLED=true")
		log.Println("  DUCKLAKE_CATALOG_TYPE=sqlite")
		log.Println("  DUCKLAKE_CATALOG_PATH=/data/ducklake/catalog.sqlite")
		log.Println("  DUCKLAKE_DATA_PATH=s3://ducklake-data/data")
		log.Println("  DUCKLAKE_BUCKET_NAME=ducklake-data")
		return
	}

	// Connect to NATS
	natsConn, err := nats.Connect(cfg.NatsURL)
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}
	defer natsConn.Close()

	// Create DuckLake writer
	duckLakeWriter, err := createDuckLakeWriter(cfg, natsConn)
	if err != nil {
		log.Fatalf("Failed to create DuckLake writer: %v", err)
	}
	defer duckLakeWriter.Close()

	log.Println("✅ DuckLake writer created successfully")

	// Create sample transactions
	sampleTransactions := createSampleTransactions()

	// Process transactions
	ctx := context.Background()
	nodeConfig := ekkoCommon.NodeConfig{
		Network: "Avalanche",
		Subnet:  "Mainnet",
		VMType:  "EVM",
	}

	log.Printf("📝 Processing %d sample transactions...", len(sampleTransactions))

	for i, tx := range sampleTransactions {
		log.Printf("Processing transaction %d/%d: %s", i+1, len(sampleTransactions), tx.Hash)

		// Write transaction to DuckLake
		if err := duckLakeWriter.WriteTransaction(ctx, tx, nodeConfig); err != nil {
			log.Printf("❌ Error writing transaction %s: %v", tx.Hash, err)
		} else {
			log.Printf("✅ Successfully wrote transaction %s", tx.Hash)
		}

		// Small delay to simulate real processing
		time.Sleep(100 * time.Millisecond)
	}

	// Flush all pending data
	log.Println("🔄 Flushing all pending data...")
	if err := duckLakeWriter.FlushAll(ctx); err != nil {
		log.Printf("❌ Error flushing data: %v", err)
	} else {
		log.Println("✅ All data flushed successfully")
	}

	log.Println("🎉 DuckLake integration example completed!")
	log.Println("")
	log.Println("📊 Next steps:")
	log.Println("  1. Check MinIO console: http://localhost:9001")
	log.Println("  2. Verify DuckLake data in bucket: ducklake-data")
	log.Println("  3. Query data using API service")
}

// createDuckLakeWriter creates and initializes a DuckLake writer
func createDuckLakeWriter(cfg *config.Config, natsConn *nats.Conn) (*persistence.DuckLakeWriter, error) {
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

		// MinIO configuration
		MinioEndpoint:  getEnvWithDefault("MINIO_ENDPOINT", "localhost:9000"),
		MinioAccessKey: getEnvWithDefault("MINIO_ACCESS_KEY", "minioadmin"),
		MinioSecretKey: getEnvWithDefault("MINIO_SECRET_KEY", "minioadmin"),
		MinioSecure:    getEnvWithDefault("MINIO_SECURE", "false") == "true",
		MinioRegion:    getEnvWithDefault("MINIO_REGION", "us-east-1"),
	}

	log.Printf("📋 DuckLake Configuration:")
	log.Printf("  Catalog Type: %s", duckLakeConfig.CatalogType)
	log.Printf("  Catalog Path: %s", duckLakeConfig.CatalogPath)
	log.Printf("  Data Path: %s", duckLakeConfig.DataPath)
	log.Printf("  Bucket Name: %s", duckLakeConfig.BucketName)
	log.Printf("  Batch Size: %d", duckLakeConfig.BatchSize)
	log.Printf("  MinIO Endpoint: %s", duckLakeConfig.MinioEndpoint)

	// Create DuckLake writer
	writer, err := persistence.NewDuckLakeWriter(duckLakeConfig, natsConn)
	if err != nil {
		return nil, fmt.Errorf("failed to create DuckLake writer: %w", err)
	}

	return writer, nil
}

// createSampleTransactions creates sample transactions for testing
func createSampleTransactions() []blockchain.Transaction {
	baseTime := time.Now().UTC()

	transactions := []blockchain.Transaction{
		{
			Hash:        "0x1234567890abcdef1234567890abcdef12345678",
			From:        "0xfrom1234567890abcdef1234567890abcdef123456",
			To:          "0xto1234567890abcdef1234567890abcdef1234567",
			Value:       "1000000000000000000", // 1 ETH in wei
			GasPrice:    "20000000000",         // 20 Gwei
			GasLimit:    "21000",
			Nonce:       "42",
			Input:       []byte("0x"),
			BlockNumber: 12345,
			BlockHash:   "0xblock1234567890abcdef1234567890abcdef123456",
			TxIndex:     0,
			BlockTime:   baseTime,
			Success:     true,
		},
		{
			Hash:        "0x2345678901bcdef12345678901bcdef123456789",
			From:        "0xfrom2345678901bcdef12345678901bcdef234567",
			To:          "0xto2345678901bcdef12345678901bcdef2345678",
			Value:       "2000000000000000000", // 2 ETH in wei
			GasPrice:    "25000000000",         // 25 Gwei
			GasLimit:    "21000",
			Nonce:       "43",
			Input:       []byte("0x"),
			BlockNumber: 12345,
			BlockHash:   "0xblock1234567890abcdef1234567890abcdef123456",
			TxIndex:     1,
			BlockTime:   baseTime.Add(1 * time.Second),
			Success:     true,
		},
		{
			Hash:        "0x3456789012cdef123456789012cdef1234567890",
			From:        "0xfrom3456789012cdef123456789012cdef345678",
			To:          "0xto3456789012cdef123456789012cdef3456789",
			Value:       "500000000000000000", // 0.5 ETH in wei
			GasPrice:    "30000000000",        // 30 Gwei
			GasLimit:    "21000",
			Nonce:       "44",
			Input:       []byte("0x"),
			BlockNumber: 12346,
			BlockHash:   "0xblock2345678901bcdef12345678901bcdef234567",
			TxIndex:     0,
			BlockTime:   baseTime.Add(2 * time.Second),
			Success:     false, // Failed transaction
		},
		{
			Hash:        "0x4567890123def1234567890123def12345678901",
			From:        "0xfrom4567890123def1234567890123def456789",
			To:          "0xto4567890123def1234567890123def4567890",
			Value:       "10000000000000000000", // 10 ETH in wei
			GasPrice:    "15000000000",          // 15 Gwei
			GasLimit:    "21000",
			Nonce:       "45",
			Input:       []byte("0x"),
			BlockNumber: 12346,
			BlockHash:   "0xblock2345678901bcdef12345678901bcdef234567",
			TxIndex:     1,
			BlockTime:   baseTime.Add(3 * time.Second),
			Success:     true,
		},
		{
			Hash:        "0x5678901234ef12345678901234ef123456789012",
			From:        "0xfrom5678901234ef12345678901234ef567890",
			To:          "0xto5678901234ef12345678901234ef5678901",
			Value:       "750000000000000000", // 0.75 ETH in wei
			GasPrice:    "22000000000",        // 22 Gwei
			GasLimit:    "21000",
			Nonce:       "46",
			Input:       []byte("0x"),
			BlockNumber: 12347,
			BlockHash:   "0xblock3456789012cdef123456789012cdef345678",
			TxIndex:     0,
			BlockTime:   baseTime.Add(4 * time.Second),
			Success:     true,
		},
	}

	return transactions
}

// Helper function to get environment variable with default
func getEnvWithDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
