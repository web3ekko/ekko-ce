package decoder

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/redis/go-redis/v9"
)

// RedisClient is an interface for Redis operations
type RedisClient interface {
	Get(ctx context.Context, key string) *redis.StringCmd
	Set(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.StatusCmd
	SIsMember(ctx context.Context, key string, member interface{}) *redis.BoolCmd
	Close() error
}

// Template represents a transaction decoding template
type Template struct {
	Name      string       `json:"name"`
	ABI       string       `json:"abi"`
	Selectors []string     `json:"selectors"`
	Methods   []abi.Method `json:"methods"`
	Filters   []FilterRule `json:"filters"`
}

// FilterRule defines a rule for filtering transactions
type FilterRule struct {
	Field    string `json:"field"`    // Field to filter on (e.g., "to", "value", "method")
	Operator string `json:"operator"` // eq, neq, gt, lt, contains
	Value    string `json:"value"`    // Value to compare against
}

// SelectorEntry represents a cached ABI selector
type SelectorEntry struct {
	Name   string         `json:"name"`
	Inputs []abi.Argument `json:"inputs"`
	Method *abi.Method    `json:"-"`
}

// DecodedCall represents a decoded transaction call
type DecodedCall struct {
	Function string                 `json:"function"`
	Params   map[string]interface{} `json:"params"`
}


// getRedisKey constructs a Redis key for various types
func getRedisKey(keyType string, parts ...string) string {
	return fmt.Sprintf("%s:%s", keyType, strings.Join(parts, ":"))
}
