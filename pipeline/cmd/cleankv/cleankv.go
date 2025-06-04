package main

import (
	"log"
	"os"

	"github.com/nats-io/nats.go"
)

const (
	natsURLDefault   = nats.DefaultURL // "nats://127.0.0.1:4222"
	nodesKVName      = "nodes"
)

func main() {
	natsURL := os.Getenv("NATS_URL")
	if natsURL == "" {
		natsURL = natsURLDefault
	}

	nc, err := nats.Connect(natsURL)
	if err != nil {
		log.Fatalf("Error connecting to NATS at %s: %v", natsURL, err)
	}
	defer nc.Close()
	log.Printf("Connected to NATS at %s", nc.ConnectedUrl())

	js, err := nc.JetStream()
	if err != nil {
		log.Fatalf("Error getting JetStream context: %v", err)
	}

	kv, err := js.KeyValue(nodesKVName)
	if err != nil {
		log.Fatalf("Error binding to KV store '%s': %v", nodesKVName, err)
	}
	log.Printf("Successfully bound to KV store '%s'", nodesKVName)

	keys, err := kv.Keys()
	if err != nil && err != nats.ErrNoKeysFound {
		log.Fatalf("Error listing keys from KV store '%s': %v", nodesKVName, err)
	}

	if len(keys) == 0 {
		log.Printf("KV store '%s' is already empty.", nodesKVName)
		return
	}

	log.Printf("Found %d keys in KV store '%s'. Deleting them...", len(keys), nodesKVName)
	for _, key := range keys {
		if err := kv.Delete(key); err != nil {
			log.Printf("Error deleting key '%s': %v", key, err)
		} else {
			log.Printf("Successfully deleted key '%s'", key)
		}
	}

	log.Printf("Finished cleaning KV store '%s'.", nodesKVName)
}
