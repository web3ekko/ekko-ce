package fetchers

import (
	"context"
	"encoding/json" // Added back for processMessage
	"fmt"
	"log"
	"math/big"
	"strings"

	"github.com/ethereum/go-ethereum"
	gethcommon "github.com/ethereum/go-ethereum/common" // Aliased
	"github.com/ethereum/go-ethereum/common/hexutil"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/ethclient"
	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	ekkoCommon "github.com/web3ekko/ekko-ce/pipeline/pkg/common" // Aliased
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
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
	subnet      string // Added subnet
	natsConn    *nats.Conn
	kvStore     nats.KeyValue
	redisClient decoder.RedisClient // Needed to initialize the EVM decoder
	evmDecoder  *decoder.Decoder    // Instance of EVM decoder, nil if not EVM
	ethClient   *ethclient.Client      // EVM client for fetching blocks
	nodeConfig  ekkoCommon.NodeConfig // Node configuration for this fetcher
}

// NewBlockFetcher creates a new BlockFetcher instance.
func NewBlockFetcher(nodeConfig ekkoCommon.NodeConfig, nc *nats.Conn, kv nats.KeyValue, rc decoder.RedisClient) (*BlockFetcher, error) {
	fetcher := &BlockFetcher{
		vmType:      nodeConfig.VMType,
		network:     nodeConfig.Network,
		subnet:      nodeConfig.Subnet,
		natsConn:    nc,
		kvStore:     kv,
		redisClient: rc,
		nodeConfig:  nodeConfig,
	}

	if strings.ToLower(fetcher.vmType) == "evm" {
		if fetcher.nodeConfig.HttpURL == "" {
			return nil, fmt.Errorf("HttpURL is required for EVM BlockFetcher (%s-%s) but was empty", fetcher.vmType, fetcher.network)
		}
		if rc == nil {
			return nil, fmt.Errorf("RedisClient is required for EVM BlockFetcher (%s-%s)", fetcher.vmType, fetcher.network)
		}
		client, err := ethclient.DialContext(context.Background(), fetcher.nodeConfig.HttpURL) // Use a background context for dialing initially
		if err != nil {
			return nil, fmt.Errorf("failed to connect to EVM node %s for BlockFetcher (%s-%s): %w", fetcher.nodeConfig.HttpURL, fetcher.vmType, fetcher.network, err)
		}
		fetcher.ethClient = client
		// The actual EVM decoder initialization needs to be aligned with how `decoder.New`
		// and `decoder.NewTemplateManager` are used in your existing `pipeline/pipeline.go`.
		// For now, this is a placeholder. The MEMORY indicates we need to reuse existing logic.
		// This will likely involve passing the redisClient to a NewTemplateManager,
		// and then that manager to NewDecoder.
		templateManager := decoder.NewTemplateManager(rc)
		fetcher.evmDecoder = decoder.NewDecoder(templateManager, fetcher.network) // Pass any required ABIs if necessary, or load them in the decoder
		log.Printf("BlockFetcher for %s-%s: EVM decoder and ethClient initialized for %s.", fetcher.vmType, fetcher.network, fetcher.nodeConfig.HttpURL)
	}

	return fetcher, nil
}

// Run starts the BlockFetcher's main loop.
func (bf *BlockFetcher) Run(ctx context.Context) error {
	log.Printf("BlockFetcher: Starting for VMType: %s, Network: %s, Subnet: %s", bf.vmType, bf.network, bf.subnet)
	defer log.Printf("BlockFetcher: Stopped for VMType: %s, Network: %s, Subnet: %s", bf.vmType, bf.network, bf.subnet)

	natsSubscriptionSubject := fmt.Sprintf("%s.%s.%s.newheads",
		strings.ToLower(bf.network),
		strings.ToLower(bf.subnet),
		strings.ToLower(bf.vmType))

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
	var nodeCfg ekkoCommon.NodeConfig
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
	fullBlock, err := bf.fetchFullBlock(ctx, blockIdentifier)
	if err != nil {
		log.Printf("BlockFetcher (%s-%s): Failed to fetch full block %s from node %s: %v", bf.vmType, bf.network, blockIdentifier, nodeID, err)
		return
	}
	if fullBlock == nil {
		log.Printf("BlockFetcher (%s-%s): Block %s not found or not ready, skipping.", bf.vmType, bf.network, blockIdentifier)
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

// fetchFullBlock fetches full block details using ethClient.
func (bf *BlockFetcher) fetchFullBlock(ctx context.Context, blockIdentifier string) (*blockchain.Block, error) {
	if strings.ToLower(bf.vmType) != "evm" || bf.ethClient == nil {
		log.Printf("BlockFetcher (%s-%s): fetchFullBlock called for non-EVM type or nil ethClient.", bf.vmType, bf.network)
		return nil, fmt.Errorf("fetchFullBlock: not an EVM fetcher or ethClient not initialized for %s-%s", bf.vmType, bf.network)
	}

	var gethBlock *types.Block
	var err error

	if len(blockIdentifier) == 66 && strings.HasPrefix(strings.ToLower(blockIdentifier), "0x") {
		blockHash := gethcommon.HexToHash(blockIdentifier)
		gethBlock, err = bf.ethClient.BlockByHash(ctx, blockHash)
	} else if strings.HasPrefix(strings.ToLower(blockIdentifier), "0x") {
		blockNumber := new(big.Int)
		_, success := blockNumber.SetString(strings.TrimPrefix(blockIdentifier, "0x"), 16)
		if !success {
			return nil, fmt.Errorf("invalid block number format: %s", blockIdentifier)
		}
		gethBlock, err = bf.ethClient.BlockByNumber(ctx, blockNumber)
	} else {
		return nil, fmt.Errorf("invalid blockIdentifier format: '%s'. Expected 0x-prefixed hash or number", blockIdentifier)
	}

	if err != nil {
		if err == ethereum.NotFound {
			log.Printf("BlockFetcher (%s-%s): Block %s not found.", bf.vmType, bf.network, blockIdentifier)
			return nil, nil // Block not found, not an error for the fetcher to retry immediately.
		}
		return nil, fmt.Errorf("failed to fetch block %s: %w", blockIdentifier, err)
	}

	if gethBlock == nil { // Should be covered by ethereum.NotFound, but as a safeguard.
		log.Printf("BlockFetcher (%s-%s): Block %s not found (gethBlock is nil after fetch attempt).", bf.vmType, bf.network, blockIdentifier)
		return nil, nil
	}

	internalBlock, err := convertGethBlockToInternalBlock(gethBlock)
	if err != nil {
		return nil, fmt.Errorf("failed to convert fetched Geth block %s to internal representation: %w", gethBlock.Hash().Hex(), err)
	}

	log.Printf("BlockFetcher (%s-%s): Successfully fetched and converted block %s (Number: %s)", bf.vmType, bf.network, internalBlock.Hash, internalBlock.Number)
	return internalBlock, nil
}

// convertGethBlockToInternalBlock converts a go-ethereum types.Block to blockchain.Block.
// convertGethBlockToInternalBlock converts a go-ethereum types.Block to blockchain.Block.
func convertGethBlockToInternalBlock(gethBlock *types.Block) (*blockchain.Block, error) {
	if gethBlock == nil {
		return nil, fmt.Errorf("cannot convert nil gethBlock")
	}

	header := gethBlock.Header()
	if header == nil {
		return nil, fmt.Errorf("gethBlock has nil header")
	}

	internalTxs := make([]blockchain.Transaction, len(gethBlock.Transactions()))
	for i, gethTx := range gethBlock.Transactions() {
		internalTx, err := convertGethTxToInternalTx(gethTx, gethBlock.Hash(), gethBlock.Number(), uint(i), gethBlock.BaseFee()) // Pass BaseFee
		if err != nil {
			return nil, fmt.Errorf("failed to convert transaction %s at index %d: %w", gethTx.Hash().Hex(), i, err)
		}
		if internalTx != nil { // Ensure internalTx is not nil before dereferencing
		    internalTxs[i] = *internalTx
		}
	}

	block := &blockchain.Block{
		Hash:         gethBlock.Hash().Hex(),
		Number:       hexutil.EncodeBig(gethBlock.Number()),
		Timestamp:    hexutil.EncodeUint64(gethBlock.Time()),
		ParentHash:   gethBlock.ParentHash().Hex(),
		Transactions: internalTxs,
		// Fields like GasLimit, GasUsed, Miner, Difficulty, Size, ExtraData, Sha3Uncles, ReceiptsRoot, StateRoot, BaseFeePerGas
		// are commented out in blockchain.Block definition (types.go) and thus removed here.
		// TODO: If these fields are needed, they must be uncommented/added in pipeline/pkg/blockchain/types.go first.
	}

	// BaseFee handling removed as BaseFeePerGas is not in blockchain.Block struct

	return block, nil
}

// convertGethTxToInternalTx converts a go-ethereum types.Transaction to blockchain.Transaction.
func convertGethTxToInternalTx(gethTx *types.Transaction, blockHash gethcommon.Hash, blockNumber *big.Int, txIndex uint, baseFee *big.Int) (*blockchain.Transaction, error) {
	if gethTx == nil {
		return nil, fmt.Errorf("cannot convert nil gethTx")
	}

	signer := types.LatestSignerForChainID(gethTx.ChainId())
	from, err := types.Sender(signer, gethTx)
	if err != nil {
		// For pre-EIP155 transactions or certain scenarios, Sender might fail if chain ID is ambiguous.
		// Try with a more general signer if specific one fails and chain ID is nil.
		if gethTx.ChainId() == nil {
			signer = types.HomesteadSigner{}
			from, err = types.Sender(signer, gethTx)
		}
		if err != nil {
			return nil, fmt.Errorf("failed to derive sender for transaction %s: %w", gethTx.Hash().Hex(), err)
		}
	}

	var toAddrStrP *string
	if to := gethTx.To(); to != nil {
		s := to.Hex()
		toAddrStrP = &s
	}

	_, _, _ = gethTx.RawSignatureValues() // V, R, S are not used in the internal transaction struct

	txTypeHex := hexutil.EncodeUint64(uint64(gethTx.Type()))
	blockHashHex := blockHash.Hex()
	blockNumberHex := hexutil.EncodeBig(blockNumber)
	txIndexHex := hexutil.EncodeUint64(uint64(txIndex))

	internalTx := &blockchain.Transaction{
		Type:        &txTypeHex,
		Hash:        gethTx.Hash().Hex(),
		From:        from.Hex(),
		To:          toAddrStrP,
		Value:       hexutil.EncodeBig(gethTx.Value()),
		Gas:         hexutil.EncodeUint64(gethTx.Gas()),
		Data:        hexutil.Encode(gethTx.Data()), 
		Nonce:       hexutil.EncodeUint64(gethTx.Nonce()),
		BlockHash:   &blockHashHex,
		BlockNumber: &blockNumberHex,
		TransactionIndex: &txIndexHex, 
		// ChainID, MaxPriorityFeePerGas, MaxFeePerGas are commented out in blockchain.Transaction (types.go)
		// and thus removed here.
		// V, R, S are also not part of the struct definition.
		// TODO: If these fields are needed, they must be uncommented/added in pipeline/pkg/blockchain/types.go first.
	}

	// ChainID handling removed

	switch gethTx.Type() {
	case types.LegacyTxType:
		internalTx.GasPrice = hexutil.EncodeBig(gethTx.GasPrice())
	case types.AccessListTxType:
		internalTx.GasPrice = hexutil.EncodeBig(gethTx.GasPrice())
		// TODO: Handle AccessList if needed in blockchain.Transaction
	case types.DynamicFeeTxType: // EIP-1559
		// MaxPriorityFeePerGas and MaxFeePerGas handling removed
		// TODO: Handle AccessList if needed in blockchain.Transaction
	}

	return internalTx, nil
}
