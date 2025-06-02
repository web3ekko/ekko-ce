package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/redis/go-redis/v9"
	"github.com/web3ekko/ekko-ce/pipeline/internal/config"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/supervisor" // Changed to supervisor

	"github.com/nats-io/nats.go"
)

func main() {
	// Load configuration (YAML overrides fall back to env)
	cfg, err := config.Load("config.yaml")
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// Create Redis adapter
	opt, err := redis.ParseURL(cfg.RedisURL)
	if err != nil {
		opt = &redis.Options{
			Addr: cfg.RedisURL,
		}
	}
	redisClient := redis.NewClient(opt)
	redisClientAdapter := decoder.NewRedisClientAdapter(redisClient)
	redisAdapter := decoder.NewRedisAdapter(redisClientAdapter)

	// Connect to NATS
	nc, err := nats.Connect(cfg.NatsURL)
	if err != nil {
		log.Fatalf("Failed to connect to NATS: %v", err)
	}
	defer nc.Close()

	// Get JetStream context
	js, err := nc.JetStream()
	if err != nil {
		log.Fatalf("Failed to get JetStream context: %v", err)
	}

	// Bind to or create the 'nodes' KV store
	kv, err := js.KeyValue("nodes")
	if err != nil {
		log.Printf("Failed to bind to KV store 'nodes', attempting to create: %v", err)
		kv, err = js.CreateKeyValue(&nats.KeyValueConfig{
			Bucket:      "nodes",
			Description: "Stores node configurations for Ekko pipelines.",
			// TTL:         24 * time.Hour, // Example: if you want a TTL for entries
		})
		if err != nil {
			log.Fatalf("Failed to create KV store 'nodes': %v", err)
		}
		log.Println("Successfully created KV store 'nodes'")
	} else {
		log.Println("Successfully bound to KV store 'nodes'")
	}

	// Create PipelineSupervisor
	sup, err := supervisor.NewPipelineSupervisor(nc, kv, redisAdapter)
	if err != nil {
		log.Fatalf("Failed to create PipelineSupervisor: %v", err)
	}

	// Create context with cancellation
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Handle shutdown signals
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		log.Println("Received shutdown signal")
		cancel()
	}()

	// Start PipelineSupervisor
	log.Println("Starting PipelineSupervisor...")
	if err := sup.Run(ctx); err != nil && err != context.Canceled {
		log.Fatalf("PipelineSupervisor error: %v", err)
	}

	log.Println("PipelineSupervisor stopped")
}
