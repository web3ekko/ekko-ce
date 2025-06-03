package blockchain



import (
	"bytes"
	"context" // Added import for context
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gorilla/websocket"
	"github.com/reugn/go-streams"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/common"
)

// WebSocketSource is a source that connects to an Avalanche node via WebSocket
type WebSocketSource struct {
	url     string
	httpURL string
	conn    *websocket.Conn
	outCh   chan any // Consider changing `any` to `*Block` once Block is defined
	ctx     context.Context
	cancel  context.CancelFunc
}

// NewWebSocketSource creates a new WebSocket source
func NewWebSocketSource(url, httpURL string) *WebSocketSource {
	ctx, cancel := context.WithCancel(context.Background())
	return &WebSocketSource{
		url:     url,
		httpURL: httpURL,
		outCh:   make(chan any), // Consider changing `any` to `*Block`
		ctx:     ctx,
		cancel:  cancel,
	}
}

// Out returns a channel that emits Block objects
func (s *WebSocketSource) Out() <-chan any {
	return s.outCh
}

// Via implements streams.Source
func (s *WebSocketSource) Via(flow streams.Flow) streams.Flow {
	return flow
}

// Close stops the WebSocket source
func (s *WebSocketSource) Close() error {
	s.cancel()
	if s.conn != nil {
		return s.conn.Close()
	}
	return nil
}

// getBlock fetches a full block by its hash
func (s *WebSocketSource) getBlock(hash string) (*Block, error) {
	req := &JSONRPCRequest{
		JSONRPC: "2.0",
		Method:  "eth_getBlockByHash",
		Params:  []interface{}{hash, true},
		ID:      1,
	}

	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("request marshal failed: %w", err)
	}

	httpReq, err := http.NewRequest("POST", s.httpURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("http request creation failed: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	// Log outgoing HTTP request for block data
	log.Printf("WebSocketSource: HTTP request for block %s to %s", hash, s.httpURL)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("http request failed: %w", err)
	}
	defer resp.Body.Close()

	var rpcResp JSONRPCResponse
	if err := json.NewDecoder(resp.Body).Decode(&rpcResp); err != nil {
		return nil, fmt.Errorf("response decode failed: %w", err)
	}

	if rpcResp.Error != nil {
		return nil, fmt.Errorf("rpc error: %s", rpcResp.Error.Message)
	}

	blockData, err := json.Marshal(rpcResp.Result)
	if err != nil {
		return nil, fmt.Errorf("block marshal failed: %w", err)
	}

	var block Block
	if err := json.Unmarshal(blockData, &block); err != nil {
		return nil, fmt.Errorf("block unmarshal failed: %w", err)
	}

	return &block, nil
}

// Start begins processing blocks
func (s *WebSocketSource) Start() error {
	// Connect to WebSocket
	conn, _, err := websocket.DefaultDialer.Dial(s.url, nil)
	if err != nil {
		return fmt.Errorf("websocket dial failed: %w", err)
	}
	s.conn = conn
	// Log successful connection
	log.Printf("WebSocketSource: connected to %s", s.url)

	// Subscribe to new blocks
	subscribeMsg := map[string]interface{}{
		"jsonrpc": "2.0",
		"id":      1,
		"method":  "eth_subscribe",
		"params":  []interface{}{"newHeads"},
	}
	if err := conn.WriteJSON(subscribeMsg); err != nil {
		return fmt.Errorf("subscription failed: %w", err)
	}
	log.Printf("WebSocketSource: subscribed to newHeads on %s", s.url)

	// Start processing in background
	go func() {
		defer close(s.outCh)
		defer conn.Close()

		// Process incoming messages
		for {
			select {
			case <-s.ctx.Done():
				return
			default:
				_, message, err := conn.ReadMessage()
				if err != nil {
					log.Printf("WebSocketSource: read message failed: %v", err)
					// Consider if this is a fatal error for the connection
					return // Exit goroutine on read failure
				}
				// Log raw WS message for debugging if needed, can be verbose
				// log.Printf("WebSocketSource: raw message: %s", string(message))

				var wsResponse struct {
					Params struct {
						SubscriptionID string `json:"subscription"`
						Result         struct {
							Hash       string `json:"hash"`
							ParentHash string `json:"parentHash"`
							Number     string `json:"number"`    // Hex string
							Timestamp  string `json:"timestamp"` // Hex string
						} `json:"result"`
					} `json:"params"`
					Method string `json:"method"` // To ensure it's a subscription event
				}

				if err := json.Unmarshal(message, &wsResponse); err != nil {
					log.Printf("WebSocketSource: unmarshal raw message failed: %v. Message: %s", err, string(message))
					continue
				}

				// Ensure it's a subscription event and not an error response or other message type
				if wsResponse.Method != "eth_subscription" || wsResponse.Params.Result.Hash == "" {
					// This might also catch the initial subscription confirmation which has a result that is the subscription ID, not a block head.
					// Proper handling would be to check if wsResponse.Params.Result is an object or a string.
					// For now, we assume newHeads events always have the Result object with a Hash.
					log.Printf("WebSocketSource: received non-subscription head event or initial confirmation: Method=%s, Params=%+v", wsResponse.Method, wsResponse.Params)
					continue
				}

				blockNumber, err := strconv.ParseUint(strings.TrimPrefix(wsResponse.Params.Result.Number, "0x"), 16, 64)
				if err != nil {
					log.Printf("WebSocketSource: failed to parse block number '%s': %v", wsResponse.Params.Result.Number, err)
					continue
				}

				timestamp, err := strconv.ParseUint(strings.TrimPrefix(wsResponse.Params.Result.Timestamp, "0x"), 16, 64)
				if err != nil {
					log.Printf("WebSocketSource: failed to parse timestamp '%s': %v", wsResponse.Params.Result.Timestamp, err)
					continue
				}

				headEvent := &common.NewHeadEvent{
					Hash:       wsResponse.Params.Result.Hash,
					ParentHash: wsResponse.Params.Result.ParentHash,
					Number:     blockNumber,
					Timestamp:  timestamp,
					NodeID:     "", // Will be populated by ManagedPipeline with its activeNodeConfig.ID
				}

				log.Printf("WebSocketSource: sending NewHeadEvent: Hash=%s, Number=%d", headEvent.Hash, headEvent.Number)
				
				// Send with select to handle context cancellation during potential block on outCh
				select {
				case s.outCh <- headEvent:
				case <-s.ctx.Done():
					log.Printf("WebSocketSource: context cancelled while sending NewHeadEvent to outCh.")
					return
				}
			}
		}
	}()

	return nil
}
