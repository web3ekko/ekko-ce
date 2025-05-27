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
	"github.com/web3ekko/ekko-ce/pipeline/internal/pipeline"
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

	// Create pipeline
	p, err := pipeline.NewPipeline(*cfg, redisAdapter)
	if err != nil {
		log.Fatalf("Failed to create pipeline: %v", err)
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

	// Start pipeline
	log.Println("Starting pipeline...")
	if err := p.Start(ctx); err != nil && err != context.Canceled {
		log.Fatalf("Pipeline error: %v", err)
	}

	log.Println("Pipeline stopped")
}
