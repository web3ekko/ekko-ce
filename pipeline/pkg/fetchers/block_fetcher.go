package fetchers

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain" // For blockchain.Block
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"    // For decoder.RedisClient, decoder.Decoder
	"github.com/web3ekko/ekko-ce/pipeline/pkg/common"        // For common.NodeConfig
)

// EVMNewHeadResult is a simplified struct to parse the "result" field from an EVM newHeads subscription event.
// We only care about the block number or hash to fetch the full block.
type EVMNewHeadResult struct {
	Hash   string `json:"hash"`
	Number string `json:"number"`
	// Add other fields if necessary, but hash or number is primary for fetching.
}

// EVMSubscriptionMessage is a struct to parse the overall message from an EVM newHeads subscription.
type EVMSubscriptionMessage struct {
	Params struct {
		Subscription string           `json:"subscription"`
		Result       EVMNewHeadResult `json:"result"`
	} `json:"params"`
}

// BlockFetcher subscribes to new head events from NATS, fetches the full block,
// decodes transactions (if applicable), and publishes the processed block.
type BlockFetcher struct {
	vmType      string
	network     string
	natsConn    *nats.Conn
	kvStore     nats.KeyValue
	redisClient decoder.RedisClient // Needed to initialize the EVM decoder
	evmDecoder  *decoder.Decoder    // Instance of EVM decoder, nil if not EVM
}

// NewBlockFetcher creates a new BlockFetcher instance.
func NewBlockFetcher(vmType, network string, nc *nats.Conn, kv nats.KeyValue, rc decoder.RedisClient) (*BlockFetcher, error) {
	fetcher := &BlockFetcher{
		vmType:      vmType,
		network:     network,
		natsConn:    nc,
		kvStore:     kv,
		redisClient: rc,
	}

	if strings.ToLower(vmType) == "evm" {
		if rc == nil {
			return nil, fmt.Errorf("RedisClient is required for EVM BlockFetcher (%s-%s)", vmType, network)
		}
		// The actual EVM decoder initialization needs to be aligned with how `decoder.New`
		// and `decoder.NewTemplateManager` are used in your existing `pipeline/pipeline.go`.
		// For now, this is a placeholder. The MEMORY indicates we need to reuse existing logic.
		// This will likely involve passing the redisClient to a NewTemplateManager,
		// and then that manager to NewDecoder.
		templateManager := decoder.NewTemplateManager(rc)
		fetcher.evmDecoder = decoder.NewDecoder(templateManager, fetcher.network) // Pass any required ABIs if necessary, or load them in the decoder
		log.Printf("BlockFetcher for %s-%s: EVM decoder initialized.", vmType, network)
	}

	return fetcher, nil
}

// Run starts the BlockFetcher's main loop.
func (bf *BlockFetcher) Run(ctx context.Context) error {
	log.Printf("BlockFetcher: Starting for VMType: %s, Network: %s", bf.vmType, bf.network)
	defer log.Printf("BlockFetcher: Stopped for VMType: %s, Network: %s", bf.vmType, bf.network)

	natsSubscriptionSubject := fmt.Sprintf("ekko.heads.%s.%s.*", bf.vmType, bf.network)

	msgChan := make(chan *nats.Msg, 64) // Buffer for incoming messages

	sub, err := bf.natsConn.ChanSubscribe(natsSubscriptionSubject, msgChan)
	if err != nil {
		return fmt.Errorf("BlockFetcher (%s-%s): Failed to subscribe to NATS subject %s: %w", bf.vmType, bf.network, natsSubscriptionSubject, err)
	}
	log.Printf("BlockFetcher (%s-%s): Subscribed to %s", bf.vmType, bf.network, natsSubscriptionSubject)

	for {
		select {
		case <-ctx.Done():
			log.Printf("BlockFetcher (%s-%s): Context cancelled. Unsubscribing and shutting down.", bf.vmType, bf.network)
			if err := sub.Unsubscribe(); err != nil {
				log.Printf("BlockFetcher (%s-%s): Error unsubscribing from NATS: %v", bf.vmType, bf.network, err)
			}
			close(msgChan)
			return nil
		case msg := <-msgChan:
			bf.processMessage(ctx, msg)
		}
	}
}

func (bf *BlockFetcher) processMessage(ctx context.Context, msg *nats.Msg) {
	tokens := strings.Split(msg.Subject, ".")
	if len(tokens) < 5 { // ekko.heads.vmType.network.nodeID
		log.Printf("BlockFetcher (%s-%s): Received message on unexpected subject format: %s", bf.vmType, bf.network, msg.Subject)
		return
	}
	nodeID := tokens[4]

	log.Printf("BlockFetcher (%s-%s): Received new head event from node %s on subject %s", bf.vmType, bf.network, nodeID, msg.Subject)

	entry, err := bf.kvStore.Get(nodeID)
	if err != nil {
		log.Printf("BlockFetcher (%s-%s): Failed to get NodeConfig for ID %s from KV store: %v", bf.vmType, bf.network, nodeID, err)
		return
	}
	var nodeCfg common.NodeConfig
	if err := json.Unmarshal(entry.Value(), &nodeCfg); err != nil {
		log.Printf("BlockFetcher (%s-%s): Failed to unmarshal NodeConfig for ID %s: %v", bf.vmType, bf.network, nodeID, err)
		return
	}

	if nodeCfg.HttpURL == "" {
		log.Printf("BlockFetcher (%s-%s): HttpURL is empty for node %s. Cannot fetch block.", bf.vmType, bf.network, nodeID)
		return
	}

	var blockIdentifier string
	if strings.ToLower(bf.vmType) == "evm" {
		var evmMsg EVMSubscriptionMessage
		if err := json.Unmarshal(msg.Data, &evmMsg); err != nil {
			log.Printf("BlockFetcher (%s-%s): Failed to unmarshal EVM new head message from node %s: %v. Data: %s", bf.vmType, bf.network, nodeID, err, string(msg.Data))
			return
		}
		if evmMsg.Params.Result.Hash != "" {
			blockIdentifier = evmMsg.Params.Result.Hash
		} else if evmMsg.Params.Result.Number != "" {
			blockIdentifier = evmMsg.Params.Result.Number
		} else {
			log.Printf("BlockFetcher (%s-%s): EVM new head message from node %s lacks block hash or number.", bf.vmType, bf.network, nodeID)
			return
		}
	} else {
		blockIdentifier = string(msg.Data) // Assuming non-EVM message data is the block identifier
		log.Printf("BlockFetcher (%s-%s): Assuming non-EVM new head message from node %s is block identifier: %s", bf.vmType, bf.network, nodeID, blockIdentifier)
	}

	log.Printf("BlockFetcher (%s-%s): Attempting to fetch block %s from node %s (URL: %s)", bf.vmType, bf.network, blockIdentifier, nodeID, nodeCfg.HttpURL)

	// Fetch the full block
	fullBlock, err := bf.fetchFullBlock(ctx, nodeCfg.HttpURL, blockIdentifier)
	if err != nil {
		log.Printf("BlockFetcher (%s-%s): Failed to fetch full block %s from node %s: %v", bf.vmType, bf.network, blockIdentifier, nodeID, err)
		return
	}
	if fullBlock == nil {
		log.Printf("BlockFetcher (%s-%s): Fetched nil block for %s from node %s", bf.vmType, bf.network, blockIdentifier, nodeID)
		return
	}

	log.Printf("BlockFetcher (%s-%s): Successfully fetched block %s from node %s. Tx count: %d", bf.vmType, bf.network, fullBlock.Hash, nodeID, len(fullBlock.Transactions))

	// Process transactions: Decode if EVM
	if bf.evmDecoder != nil && fullBlock.Transactions != nil {
		for i := range fullBlock.Transactions {
			if err := bf.evmDecoder.DecodeTransaction(ctx, &fullBlock.Transactions[i]); err != nil { 
				log.Printf("BlockFetcher (%s-%s): Failed to decode tx %s (block %s, node %s): %v", bf.vmType, bf.network, fullBlock.Transactions[i].Hash, fullBlock.Hash, nodeID, err)
			}
		}
	}

	// Publish processed block
	outputSubject := fmt.Sprintf("ekko.processed_blocks.%s.%s.%s", bf.vmType, bf.network, nodeID)
	outputPayload, err := json.Marshal(fullBlock)
	if err != nil {
		log.Printf("BlockFetcher (%s-%s): Failed to marshal processed block %s for publishing: %v", bf.vmType, bf.network, fullBlock.Hash, err)
		return
	}
	if err := bf.natsConn.Publish(outputSubject, outputPayload); err != nil {
		log.Printf("BlockFetcher (%s-%s): Failed to publish processed block %s to NATS subject %s: %v", bf.vmType, bf.network, fullBlock.Hash, outputSubject, err)
	} else {
		log.Printf("BlockFetcher (%s-%s): Published processed block %s (Tx count: %d) to %s", bf.vmType, bf.network, fullBlock.Hash, len(fullBlock.Transactions), outputSubject)
	}
}

// fetchFullBlock fetches full block details via HTTP RPC.
func (bf *BlockFetcher) fetchFullBlock(ctx context.Context, httpURL string, blockIdentifier string) (*blockchain.Block, error) {
	if strings.ToLower(bf.vmType) != "evm" {
		log.Printf("BlockFetcher: fetchFullBlock not implemented for VMType: %s. Returning nil.", bf.vmType)
		// For non-EVM types, we might return an error or a specific kind of empty/stub block.
		// For now, returning an error to make it explicit that it's not handled.
		return nil, fmt.Errorf("fetchFullBlock not implemented for VMType: %s", bf.vmType)
	}

	if httpURL == "" {
		return nil, fmt.Errorf("HTTP RPC URL is empty for %s-%s", bf.vmType, bf.network)
	}

	client := &http.Client{Timeout: 15 * time.Second}

	var method string
	var params []interface{}

	// EVM specific logic: eth_getBlockByHash or eth_getBlockByNumber
	// blockIdentifier is expected to be a hash (0x-prefixed, 66 chars) or a hex block number (0x-prefixed)
	if len(blockIdentifier) == 66 && strings.HasPrefix(strings.ToLower(blockIdentifier), "0x") {
		method = "eth_getBlockByHash"
		params = []interface{}{blockIdentifier, true} // true for full transaction objects
	} else if strings.HasPrefix(strings.ToLower(blockIdentifier), "0x") {
		method = "eth_getBlockByNumber"
		params = []interface{}{blockIdentifier, true} // true for full transaction objects
	} else {
		return nil, fmt.Errorf("invalid EVM blockIdentifier format: %s", blockIdentifier)
	}

	rpcReq := blockchain.JSONRPCRequest{
		JSONRPC: "2.0",
		Method:  method,
		Params:  params,
		ID:      1, // Static ID for simplicity
	}

	reqBytes, err := json.Marshal(rpcReq)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal JSON-RPC request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", httpURL, bytes.NewBuffer(reqBytes))
	if err != nil {
		return nil, fmt.Errorf("failed to create HTTP request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	log.Printf("BlockFetcher (%s-%s): Sending RPC request to %s: Method=%s, Params=%v", bf.vmType, bf.network, httpURL, method, params)

	httpResp, err := client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to execute HTTP request to %s: %w", httpURL, err)
	}
	defer httpResp.Body.Close()

	if httpResp.StatusCode != http.StatusOK {
		// Try to read body for more details, but don't fail if read fails
		bodyBytes, _ := io.ReadAll(httpResp.Body)
		return nil, fmt.Errorf("HTTP request to %s failed with status %s; Body: %s", httpURL, httpResp.Status, string(bodyBytes))
	}

	var rpcResp blockchain.JSONRPCResponse
	if err := json.NewDecoder(httpResp.Body).Decode(&rpcResp); err != nil {
		return nil, fmt.Errorf("failed to decode JSON-RPC response from %s: %w", httpURL, err)
	}

	if rpcResp.Error != nil {
		return nil, fmt.Errorf("JSON-RPC error from %s: %s (code: %d)", httpURL, rpcResp.Error.Message, rpcResp.Error.Code)
	}

	if rpcResp.Result == nil {
		// This can happen if a block is not found (e.g., eth_getBlockByHash for a pending block's hash, or non-existent block)
		log.Printf("BlockFetcher (%s-%s): RPC result is null for block %s from %s. This might indicate the block is not yet available or does not exist.", bf.vmType, bf.network, blockIdentifier, httpURL)
		return nil, nil // Return nil, nil to indicate block not found, not necessarily an error for the fetcher to retry immediately.
	}

	// The rpcResp.Result is an interface{}. Marshal it to JSON and then Unmarshal into our blockchain.Block struct.
	resultBytes, err := json.Marshal(rpcResp.Result)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal rpcResp.Result for block %s from %s: %w", blockIdentifier, httpURL, err)
	}

	var block blockchain.Block
	if err := json.Unmarshal(resultBytes, &block); err != nil {
		return nil, fmt.Errorf("failed to unmarshal block data for %s from %s (JSON: %s): %w", blockIdentifier, httpURL, string(resultBytes), err)
	}

	// Ensure essential fields are present, e.g. Hash. The actual block hash might differ from blockIdentifier if it was a number.
	if block.Hash == "" {
		log.Printf("BlockFetcher (%s-%s): Fetched block from %s using identifier %s has an empty hash. Raw result: %s", bf.vmType, bf.network, httpURL, blockIdentifier, string(resultBytes))
		// Depending on strictness, this could be an error or handled as a block with missing data.
		// For now, let it pass, but it's a point of concern.
	}

	log.Printf("BlockFetcher (%s-%s): Successfully parsed block %s from %s", bf.vmType, bf.network, block.Hash, httpURL)
	return &block, nil
}
