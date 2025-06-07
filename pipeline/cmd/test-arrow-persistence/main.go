package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/persistence"
)

const (
	natsSubject    = "ekko.ethereum.sepolia.evm.persistence"
	bucketName     = "test-transactions"
	transactionNum = 5
	flushInterval  = 3 * time.Second  // How often the Arrow writer flushes batches
	batchSize      = 2                // Flush after this many transactions
)

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	
	// Connect to NATS
	natsURL := os.Getenv("NATS_URL")
	if natsURL == "" {
		natsURL = "nats://localhost:4222"
	}
	
	nc, err := nats.Connect(natsURL)
	if err != nil {
		log.Fatalf("Failed to connect to NATS at %s: %v", natsURL, err)
	}
	defer nc.Close()
	log.Printf("Connected to NATS at %s", nc.ConnectedUrl())
	
	// Connect to MinIO
	minioEndpoint := "localhost:9000"
	minioClient, err := minio.New(minioEndpoint, &minio.Options{
		Creds:  credentials.NewStaticV4("minioadmin", "minioadmin", ""),
		Secure: false,
	})
	if err != nil {
		log.Fatalf("Failed to connect to MinIO: %v", err)
	}
	log.Printf("Connected to MinIO at %s", minioEndpoint)
	
	// Check if the bucket exists
	exists, err := minioClient.BucketExists(ctx, bucketName)
	if err != nil {
		log.Fatalf("Failed to check if bucket exists: %v", err)
	}
	if !exists {
		log.Fatalf("Bucket %s does not exist", bucketName)
	}
	log.Printf("Bucket %s exists", bucketName)
	
	// Start the Arrow writer service
	log.Println("Starting ArrowWriter...")
	arrowWriterConfig := persistence.ArrowWriterConfig{
		BatchSize:          batchSize,
		FlushInterval:      flushInterval,
		MinioConfig: persistence.MinioConfig{
			Endpoint:  minioEndpoint,
			AccessKey: "minioadmin",
			SecretKey: "minioadmin",
			UseSSL:    false,
			BucketName: bucketName,
			BasePath:   "transactions", // Base path in the bucket
		},
		NatsURL:            natsURL,
		NatsSubjectPattern: "ekko.*.*.*.persistence", // This will match all network.subnet.vmtype combinations
	}
	
	arrowWriter, err := persistence.NewArrowWriter(arrowWriterConfig)
	if err != nil {
		log.Fatalf("Failed to create ArrowWriter: %v", err)
	}
	
	// Run the ArrowWriter in a separate goroutine
	go func() {
		if err := arrowWriter.Start(ctx); err != nil && err != context.Canceled {
			log.Printf("ArrowWriter stopped with error: %v", err)
		}
	}()
	
	// Give the ArrowWriter time to initialize and start listening for messages
	log.Println("Waiting for ArrowWriter to initialize...")
	time.Sleep(1 * time.Second)
	
	// Generate mock transactions
	log.Printf("Generating and publishing %d mock transactions", transactionNum)
	for i := 0; i < transactionNum; i++ {
		// Create mock transaction data using the correct Transaction structure
		blockHash := fmt.Sprintf("0x%064d", 12345)
		blockNumber := "0x1000"
		txIndex := "0x0"
		txType := "0x0"
		toAddr := fmt.Sprintf("0x%040d", i*2)
		
		tx := blockchain.Transaction{
			Hash:             fmt.Sprintf("0x%064d", i),
			From:             fmt.Sprintf("0x%040d", i),
			To:               &toAddr,
			Value:            "0x0",
			Gas:              "0x1000",
			GasPrice:         "0x100000",
			Nonce:            "0x1",
			Data:             fmt.Sprintf("0x%040d", i*2+1),
			BlockHash:        &blockHash,
			BlockNumber:      &blockNumber,
			TransactionIndex: &txIndex,
			Type:             &txType,
		}
		
		// Marshal to JSON
		txData, err := json.Marshal(tx)
		if err != nil {
			log.Printf("Failed to marshal transaction: %v", err)
			continue
		}
		
		// Create a message with network metadata in the subject
		// The subject format is important for the Arrow Writer to extract network/subnet/vm_type
		subject := natsSubject
		
		// Publish with retry
		for retries := 0; retries < 3; retries++ {
			err = nc.Publish(subject, txData)
			if err == nil {
				break
			}
			time.Sleep(50 * time.Millisecond)
		}
		if err != nil {
			log.Printf("Failed to publish transaction after retries: %v", err)
			continue
		}
		
		log.Printf("Published transaction %d: %s", i+1, tx.Hash)
	}
	
	// Flush to ensure all messages are delivered
	log.Printf("Flushing NATS messages...")
	for i := 0; i < 3; i++ {
		err := nc.Flush()
		if err != nil {
			log.Printf("Warning: NATS flush failed (attempt %d): %v", i+1, err)
		}
		time.Sleep(100 * time.Millisecond)
	}
	
	log.Printf("Waiting for arrow batch flush... (Interval: %v, BatchSize: %d)", flushInterval, batchSize)
	// Wait for the ArrowWriter to process and flush the transactions
	// - Either waiting for batch size to be reached (5 transactions > batch size of 2)
	// - Or waiting for the flush interval to trigger
	waitTime := flushInterval + (2 * time.Second) // Add buffer time
	log.Printf("Waiting %v for batch flush", waitTime)
	time.Sleep(waitTime)
	
	// List objects in the bucket to check for Arrow files
	log.Printf("Checking for Arrow files in MinIO bucket %s", bucketName)
	prefix := "transactions/transactions/network=ethereum/subnet=sepolia/vm_type=evm/"
	
	// Poll until we find Arrow files or timeout
	found := false
	maxAttempts := 5
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		log.Printf("Polling attempt %d of %d...", attempt, maxAttempts)
		
		// List all objects in bucket for debugging
		allObjects := listAllObjectsInBucket(ctx, minioClient, bucketName)
		log.Printf("Total objects in bucket: %d", len(allObjects))
		for _, obj := range allObjects {
			log.Printf("Found in bucket: '%s' (size: %d, last-modified: %s)",
				obj.Key, obj.Size, obj.LastModified)
		}
		
		// List objects with our specific prefix
		arrowFiles := listObjectsWithPrefix(ctx, minioClient, bucketName, prefix)
		log.Printf("Found %d objects with prefix '%s'", len(arrowFiles), prefix)
		for _, obj := range arrowFiles {
			log.Printf("Found with prefix '%s': '%s' (size: %d)",
				prefix, obj.Key, obj.Size)
		}
		
		// Check for .arrow files specifically
		arrowCount := 0
		for _, obj := range arrowFiles {
			if len(obj.Key) > 6 && obj.Key[len(obj.Key)-6:] == ".arrow" {
				log.Printf("Found Arrow file: %s (size: %d bytes)",
					obj.Key, obj.Size)
				arrowCount++
			}
		}
		
		if arrowCount > 0 {
			log.Printf("✅ Success! Found %d Arrow files in MinIO", arrowCount)
			found = true
			break
		}
		
		log.Printf("No Arrow files found yet, waiting before next attempt...")
		time.Sleep(time.Duration(attempt) * time.Second)
	}
	
	if !found {
		log.Printf("❌ Failed to find any Arrow files after %d attempts", maxAttempts)
	}
	
	// Stop the ArrowWriter
	log.Println("Stopping ArrowWriter...")
	cancel() // Cancel the context to signal stop
	
	// Give the ArrowWriter time to clean up and flush any remaining data
	time.Sleep(1 * time.Second)
}

// listAllObjectsInBucket lists all objects in the MinIO bucket
func listAllObjectsInBucket(ctx context.Context, minioClient *minio.Client, bucketName string) []minio.ObjectInfo {
	objectsCh := minioClient.ListObjects(ctx, bucketName, minio.ListObjectsOptions{
		Recursive: true,
	})
	
	var allObjects []minio.ObjectInfo
	for obj := range objectsCh {
		if obj.Err != nil {
			log.Printf("ERROR: Failed to list object: %v", obj.Err)
			continue
		}
		allObjects = append(allObjects, obj)
	}
	return allObjects
}

// listObjectsWithPrefix lists objects in the MinIO bucket with the specified prefix
func listObjectsWithPrefix(ctx context.Context, minioClient *minio.Client, bucketName, prefix string) []minio.ObjectInfo {
	objectsCh := minioClient.ListObjects(ctx, bucketName, minio.ListObjectsOptions{
		Prefix:    prefix,
		Recursive: true,
	})
	
	var objects []minio.ObjectInfo
	for obj := range objectsCh {
		if obj.Err != nil {
			log.Printf("ERROR: Failed to list object: %v", obj.Err)
			continue
		}
		objects = append(objects, obj)
	}
	return objects
}
