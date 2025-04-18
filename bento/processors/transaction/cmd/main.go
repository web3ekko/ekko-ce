package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	txprocessor "github.com/web3ekko/ekko-ce/bento/processors/transaction"
)

func main() {
	// Initialize MinIO client
	minioClient, err := minio.New("localhost:9000", &minio.Options{
		Creds:  credentials.NewStaticV4(os.Getenv("MINIO_ACCESS_KEY"), os.Getenv("MINIO_SECRET_KEY"), ""),
		Secure: false,
	})
	if err != nil {
		log.Fatalf("Failed to create MinIO client: %v", err)
	}

	// Create processor
	processor := txprocessor.NewProcessor(minioClient, "transactions")

	// Create listener
	listener := txprocessor.NewListener(processor, "ws://localhost:8545")

	// Create context that can be cancelled
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Handle graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigChan
		cancel()
	}()

	// Start listening for transactions
	log.Println("Starting transaction processor...")
	if err := listener.Start(ctx); err != nil {
		log.Fatalf("Error in transaction processor: %v", err)
	}
}
