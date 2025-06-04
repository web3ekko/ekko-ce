package main

import (
	"encoding/json"
	"log"
	"os"
	"time"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	common "github.com/web3ekko/ekko-ce/pipeline/pkg/common"
)

const (
	nodesKVName = "nodes"
)

func main() {
	natsURL := os.Getenv("NATS_URL")
	if natsURL == "" {
		natsURL = nats.DefaultURL
	}

	nc, err := nats.Connect(natsURL, nats.Timeout(10*time.Second))
	if err != nil {
		log.Fatalf("Error connecting to NATS at %s: %v", natsURL, err)
	}
	defer nc.Close()
	log.Printf("Connected to NATS at %s", nc.ConnectedUrl())

	js, err := nc.JetStream()
	if err != nil {
		log.Fatalf("Failed to get JetStream context: %v", err)
	}

	kv, err := js.KeyValue(nodesKVName)
	if err != nil {
		log.Printf("Failed to bind to KV store '%s', attempting to create: %v", nodesKVName, err)
		kv, err = js.CreateKeyValue(&nats.KeyValueConfig{
			Bucket:      nodesKVName,
			Description: "Stores node configurations for Ekko pipelines.",
		})
		if err != nil {
			log.Fatalf("Failed to create KV store '%s': %v", nodesKVName, err)
		}
		log.Printf("Successfully created KV store '%s'", nodesKVName)
	} else {
		log.Printf("Successfully bound to KV store '%s'", nodesKVName)
	}

	// --- Define your Node Configurations Here ---
	nodeConfigs := []common.NodeConfig{
		{
			ID:   uuid.NewString(), // Generates a new unique ID
			Name: "Fuji Test Node 1",
			// GroupID removed, supervisor will group by Network, Subnet, VMType
			Network:   "mainnet",
			Subnet:    "C-Chain", // Or your specific subnet name
			VMType:    "subnet-evm",
			WssURL:    "wss://api.avax-test.network/ext/bc/C/ws", // Public Fuji C-Chain WSS endpoint
			HttpURL:   "https://api.avax-test.network/ext/bc/C/rpc",  // Public Fuji C-Chain HTTP endpoint
			IsEnabled: true,
		},
		// Add more nodes as needed, for the same or different groups
		// Example for a different group or network (if you have one):
		// {
		// 	ID:        uuid.NewString(),
		// 	Name:      "Mainnet Node 1",
		// 	Network:   "mainnet",
		// 	Subnet:    "C-Chain",
		// 	VMType:    "subnet-evm",
		// 	WssURL:    "YOUR_MAINNET_WSS_URL",
		// 	HttpURL:   "YOUR_MAINNET_HTTP_URL",
		// 	IsEnabled: true,
		// },
	}

	for _, nodeCfg := range nodeConfigs {
		key := nodeCfg.ID // Use NodeConfig.ID directly as the key
		jsonData, err := json.Marshal(nodeCfg)
		if err != nil {
			log.Printf("Failed to marshal node config for %s: %v", nodeCfg.Name, err)
			continue
		}

		_, err = kv.Put(key, jsonData)
		if err != nil {
			log.Printf("Failed to put node config for %s (key: %s) into KV store: %v", nodeCfg.Name, key, err)
		} else {
			log.Printf("Successfully stored node config for %s (key: %s)", nodeCfg.Name, key)
		}
	}

	log.Println("Finished populating KV store.")
}
