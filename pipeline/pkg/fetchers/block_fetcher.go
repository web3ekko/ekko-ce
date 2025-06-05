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
	vmType               string
	network              string
	subnet               string // Added subnet
	natsConn             *nats.Conn
	kvStore              nats.KeyValue
	redisClient          decoder.RedisClient // Needed to initialize the EVM decoder
	evmDecoder           *decoder.Decoder    // Instance of EVM decoder, nil if not EVM
	ethClient            *ethclient.Client      // EVM client for fetching blocks
	nodeConfig           ekkoCommon.NodeConfig // Node configuration for this fetcher
	filterWalletsEnabled bool                  // New: Flag to enable/disable wallet address filtering
}

// NewBlockFetcher creates a new BlockFetcher instance.
func NewBlockFetcher(nodeConfig ekkoCommon.NodeConfig, nc *nats.Conn, kv nats.KeyValue, rc decoder.RedisClient, filterWalletsEnabled bool) (*BlockFetcher, error) {
	fetcher := &BlockFetcher{
		vmType:               nodeConfig.VMType,
		network:              nodeConfig.Network,
		subnet:               nodeConfig.Subnet,
		natsConn:             nc,
		kvStore:              kv,
		redisClient:          rc,
		nodeConfig:           nodeConfig,
		filterWalletsEnabled: filterWalletsEnabled, // New
	}

	if strings.Contains(strings.ToLower(fetcher.nodeConfig.VMType), "evm") {
		if fetcher.nodeConfig.HttpURL == "" {
			return nil, fmt.Errorf("HttpURL is required for EVM BlockFetcher (%s-%s-%s) but was empty", fetcher.nodeConfig.Network, fetcher.nodeConfig.Subnet, fetcher.nodeConfig.VMType)
		}
		if rc == nil {
			return nil, fmt.Errorf("RedisClient is required for EVM BlockFetcher (%s-%s-%s)", fetcher.nodeConfig.Network, fetcher.nodeConfig.Subnet, fetcher.nodeConfig.VMType)
		}
		client, err := ethclient.DialContext(context.Background(), fetcher.nodeConfig.HttpURL) // Use a background context for dialing initially
		if err != nil {
			return nil, fmt.Errorf("failed to connect to EVM node %s for BlockFetcher (%s-%s-%s): %w", fetcher.nodeConfig.HttpURL, fetcher.nodeConfig.Network, fetcher.nodeConfig.Subnet, fetcher.nodeConfig.VMType, err)
		}
		fetcher.ethClient = client
		// The actual EVM decoder initialization needs to be aligned with how `decoder.New`
		// and `decoder.NewTemplateManager` are used in your existing `pipeline/pipeline.go`.
		// For now, this is a placeholder. The MEMORY indicates we need to reuse existing logic.
		// This will likely involve passing the redisClient to a NewTemplateManager,
		// and then that manager to NewDecoder.
		templateManager := decoder.NewTemplateManager(rc)
		fetcher.evmDecoder = decoder.NewDecoder(templateManager, fetcher.nodeConfig.Network) // Pass any required ABIs if necessary, or load them in the decoder
		log.Printf("BlockFetcher for %s-%s-%s: EVM decoder and ethClient initialized for %s.", fetcher.nodeConfig.Network, fetcher.nodeConfig.Subnet, fetcher.nodeConfig.VMType, fetcher.nodeConfig.HttpURL)
	}

	return fetcher, nil
}

// NodeConfig returns the NodeConfig associated with this BlockFetcher.
func (bf *BlockFetcher) NodeConfig() ekkoCommon.NodeConfig {
	return bf.nodeConfig
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
	// DEBUG logs as requested by user. Using bf.nodeConfig fields for consistency.
	log.Printf("BlockFetcher (%s-%s-%s): DEBUG: Received NATS message. Subject: '%s'", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, msg.Subject)
	log.Printf("BlockFetcher (%s-%s-%s): DEBUG: Raw Data: '%s'", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, string(msg.Data))

	// Expected subject: <network>.<subnet>.<vmType>.newheads (4 parts)
	tokens := strings.Split(msg.Subject, ".")
	log.Printf("BlockFetcher (%s-%s-%s): DEBUG: Parsed Subject Tokens (length %d): %v", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, len(tokens), tokens)

	if len(tokens) < 4 { // Validate subject structure matches <network>.<subnet>.<vmType>.newheads
		log.Printf("BlockFetcher (%s-%s-%s): Received message on unexpected subject format (expected 4 parts, got %d): %s. Discarding.", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, len(tokens), msg.Subject)
		return
	}

	var newHeadEvent ekkoCommon.NewHeadEvent
	if err := json.Unmarshal(msg.Data, &newHeadEvent); err != nil {
		log.Printf("BlockFetcher (%s-%s-%s): Failed to unmarshal NewHeadEvent from NATS message on subject %s: %v. Data: %s. Discarding.", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, msg.Subject, err, string(msg.Data))
		return
	}

	// Critical: Ensure this BlockFetcher instance is responsible for the NodeID in the event.
	// The NATS subject (network.subnet.vmtype.newheads) can be generic.
	if newHeadEvent.NodeID == "" {
		log.Printf("BlockFetcher (%s-%s-%s): Received NewHeadEvent with empty NodeID on subject %s. Discarding. Event Data: %+v", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, msg.Subject, newHeadEvent)
		return
	}
	if newHeadEvent.NodeID != bf.nodeConfig.ID {
		// This is not an error, just this fetcher instance isn't supposed to handle this specific node's event.
		// Another BlockFetcher instance (if one exists for newHeadEvent.NodeID) will pick it up.
		log.Printf("BlockFetcher (%s-%s-%s): DEBUG: Skipping NewHeadEvent for NodeID %s as this fetcher is for NodeID %s. Subject: %s.", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, newHeadEvent.NodeID, bf.nodeConfig.ID, msg.Subject)
		return
	}

	log.Printf("BlockFetcher (%s-%s-%s): Processing NewHeadEvent for its NodeID %s (Hash: %s, Number: %d) from subject %s", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, newHeadEvent.NodeID, newHeadEvent.Hash, newHeadEvent.Number, msg.Subject)

	if bf.nodeConfig.HttpURL == "" {
		log.Printf("BlockFetcher (%s-%s-%s): HttpURL is empty for this fetcher's node %s. Cannot fetch block.", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, bf.nodeConfig.ID)
		return
	}

	var blockIdentifier string
	if newHeadEvent.Hash != "" {
		blockIdentifier = newHeadEvent.Hash
	} else if newHeadEvent.Number != 0 { // Assuming 0 is not a valid block number to fetch by; ethclient.BlockByNumber uses *big.Int
		blockIdentifier = hexutil.EncodeUint64(newHeadEvent.Number) // ethclient methods expect hex string for number if not using big.Int directly
	} else {
		log.Printf("BlockFetcher (%s-%s-%s): NewHeadEvent from NodeID %s (Subject: %s) lacks both block hash and number. Discarding.", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, newHeadEvent.NodeID, msg.Subject)
		return
	}

	log.Printf("BlockFetcher (%s-%s-%s): Attempting to fetch block %s for node %s (URL: %s)", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, blockIdentifier, bf.nodeConfig.ID, bf.nodeConfig.HttpURL)

	// Fetch the full block using the BlockFetcher's configured ethClient (which uses bf.nodeConfig.HttpURL)
	fullBlock, err := bf.fetchFullBlock(ctx, blockIdentifier)
	if err != nil {
		log.Printf("BlockFetcher (%s-%s-%s): Failed to fetch full block %s for node %s: %v", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, blockIdentifier, bf.nodeConfig.ID, err)
		return
	}
	if fullBlock == nil { // fetchFullBlock should log if not found, this is an additional guard.
		log.Printf("BlockFetcher (%s-%s-%s): Block %s not found or not ready for node %s, skipping.", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, blockIdentifier, bf.nodeConfig.ID)
		return
	}

	log.Printf("BlockFetcher (%s-%s-%s): Successfully fetched block %s (Number: %v) for node %s. Tx count: %d", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, fullBlock.Hash, fullBlock.Number, bf.nodeConfig.ID, len(fullBlock.Transactions))

	// Process transactions: Decode if EVM and decoder is available
	if bf.evmDecoder != nil && len(fullBlock.Transactions) > 0 {
		log.Printf("BlockFetcher (%s-%s-%s): Decoding %d transactions for block %s (node %s)...", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, len(fullBlock.Transactions), fullBlock.Hash, bf.nodeConfig.ID)
		for i := range fullBlock.Transactions {
			tx := &fullBlock.Transactions[i] // Get a pointer to the transaction for modification
			if err := bf.evmDecoder.DecodeTransaction(ctx, tx); err != nil {
				log.Printf("BlockFetcher (%s-%s-%s): Failed to decode tx %s (block %s, node %s): %v", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, tx.Hash, fullBlock.Hash, bf.nodeConfig.ID, err)
			}
		}
	}

	// Publish processed block to a subject specific to this node
	publishSubject := fmt.Sprintf("%s.%s.%s.blocks", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType)
	blockData, err := json.Marshal(fullBlock)
	if err != nil {
		log.Printf("BlockFetcher (%s-%s-%s): Failed to marshal processed block %s for publishing: %v", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, fullBlock.Hash, err)
		// Continue to attempt publishing individual transactions even if block publish fails for some reason
	}
	if err := bf.natsConn.Publish(publishSubject, blockData); err != nil {
		log.Printf("BlockFetcher (%s-%s-%s): Failed to publish block %s to NATS subject %s: %v", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, fullBlock.Hash, publishSubject, err)
		// Continue to attempt publishing individual transactions even if block publish fails for some reason
	} else {
		log.Printf("BlockFetcher (%s-%s-%s): Successfully published block %s to NATS subject %s", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, fullBlock.Hash, publishSubject)
	}

	// Publish successfully decoded individual transactions
	for _, tx := range fullBlock.Transactions {
		if tx.DecodedCall != nil && tx.DecodedCall.Function != "" && tx.DecodedCall.Function != "UnknownContractCall" && tx.DecodedCall.Function != "UnknownTransactionType" {
			decodedTxData, err := json.Marshal(tx) // Marshal the whole transaction
			if err != nil {
				log.Printf("BlockFetcher (%s-%s-%s): Failed to marshal successfully decoded transaction %s (block %s): %v", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, tx.Hash, fullBlock.Hash, err)
				continue // Skip this transaction
			}

			txPublishSubject := fmt.Sprintf("transactions.%s.%s.%s", bf.nodeConfig.VMType, bf.nodeConfig.Network, bf.nodeConfig.Subnet)
			if err := bf.natsConn.Publish(txPublishSubject, decodedTxData); err != nil {
				log.Printf("BlockFetcher (%s-%s-%s): Failed to publish decoded transaction %s to subject %s: %v", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, tx.Hash, txPublishSubject, err)
			} else {
				log.Printf("BlockFetcher (%s-%s-%s): Successfully published decoded transaction %s (Function: %s) to subject %s", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, tx.Hash, tx.DecodedCall.Function, txPublishSubject)
			}
		}
	}
}

// fetchFullBlock fetches full block details using ethClient.
func (bf *BlockFetcher) fetchFullBlock(ctx context.Context, blockIdentifier string) (*blockchain.Block, error) {
if !strings.Contains(strings.ToLower(bf.nodeConfig.VMType), "evm") || bf.ethClient == nil {
		log.Printf("BlockFetcher (%s-%s-%s): fetchFullBlock called for non-EVM type or nil ethClient.", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType)
		return nil, fmt.Errorf("fetchFullBlock: not an EVM fetcher or ethClient not initialized for %s-%s-%s", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType)
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
			log.Printf("BlockFetcher (%s-%s-%s): Block %s not found.", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, blockIdentifier)
			return nil, nil // Block not found, not an error for the fetcher to retry immediately.
		}
		return nil, fmt.Errorf("failed to fetch block %s: %w", blockIdentifier, err)
	}

	if gethBlock == nil { // Should be covered by ethereum.NotFound, but as a safeguard.
		log.Printf("BlockFetcher (%s-%s-%s): Block %s not found (gethBlock is nil after fetch attempt).", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, blockIdentifier)
		return nil, nil
	}

	internalBlock, err := convertGethBlockToInternalBlock(gethBlock)
	if err != nil {
		return nil, fmt.Errorf("failed to convert fetched Geth block %s to internal representation: %w", gethBlock.Hash().Hex(), err)
	}

	log.Printf("BlockFetcher (%s-%s-%s): Successfully fetched and converted block %s (Number: %v)", bf.nodeConfig.Network, bf.nodeConfig.Subnet, bf.nodeConfig.VMType, internalBlock.Hash, internalBlock.Number)
	return internalBlock, nil
}

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
