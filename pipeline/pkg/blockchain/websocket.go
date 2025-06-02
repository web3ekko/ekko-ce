package blockchain



import (
	"bytes"
	"context" // Added import for context
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
	"github.com/reugn/go-streams"
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
					log.Printf("read failed: %v", err)
					return
				}
				// Log raw WS message
				log.Printf("WebSocketSource: raw message: %s", string(message))

				// Parse subscription response
				var response struct {
					Params struct {
						Result struct {
							Hash string `json:"hash"`
						} `json:"result"`
					} `json:"params"`
				}
				if err := json.Unmarshal(message, &response); err != nil {
					log.Printf("unmarshal failed: %v", err)
					continue
				}
				// Log parsed new head
				log.Printf("WebSocketSource: new head hash %s", response.Params.Result.Hash)

				// Get full block
				block, err := s.getBlock(response.Params.Result.Hash)
				if err != nil {
					log.Printf("get block failed: %v", err)
					continue
				}

				// Send block to channel
				s.outCh <- block
			}
		}
	}()

	return nil
}
