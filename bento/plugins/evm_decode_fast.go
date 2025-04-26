// Package main implements a Benthos batch processor plugin called
// `evm_decode_fast`. It translates an EVM transaction’s calldata
// to a `{function, params}` map using a selector->signature JSON blob that sits in Valkey.
//
// The plugin chooses the fastest path first:
//
//   1. Try selector-level cache:  sel:<chain>:<selector>
//   2. Fallback to address-scoped key for overloaded functions.
//   3. If still no luck, we return the message untouched – the upstream ABI resolver
//      processor will eventually fill the cache and the next retry will succeed.
//
// Compile:
//   go build -buildmode=plugin -o evm_decode_fast.so evm_decode_fast.go

package main

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"syscall"

	"github.com/benthosdev/benthos/v4/public/service"
	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/redis/go-redis/v9"
)

// hexToBytes safely strips the "0x" prefix (if any).
func hexToBytes(h string) ([]byte, error) {
	return hex.DecodeString(strings.TrimPrefix(h, "0x"))
}

// RedisGetter interface
type RedisGetter interface {
	Get(ctx context.Context, key string) *redis.StringCmd
}

// decoder implements the BatchProcessor interface
// It holds a Redis client (as RedisGetter) and a chain ID for lookup keys.
type decoder struct {
	redis   RedisGetter
	chainID string
}

// Process implements the batch processing method.
// It converts the incoming message to a structured map, extracts the input,
// and uses cached function signature data to decode the calldata if possible.
func (d *decoder) Process(ctx context.Context, msg *service.Message) ([]*service.Message, error) {
	structured, err := msg.AsStructured()
	if err != nil {
		return nil, err
	}

	tx, ok := structured.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("expected map[string]any but got %T", structured)
	}

	inputHex, _ := tx["input"].(string)
	if len(inputHex) < 10 {
		return []*service.Message{msg}, nil
	}
	selector := strings.ToLower(inputHex[:10])
	toAddr, _ := tx["to"].(string)

	var sig sigEntry
	if err := d.getSelector(ctx, "sel:"+d.chainID+":"+selector, &sig); err == nil {
		if d.decodeCalldata(tx, sig, inputHex[10:]) {
			return wrap(msg, tx), nil
		}
	}

	addrKey := "sel:" + d.chainID + ":" + strings.ToLower(toAddr) + ":" + selector
	if err := d.getSelector(ctx, addrKey, &sig); err == nil {
		if d.decodeCalldata(tx, sig, inputHex[10:]) {
			return wrap(msg, tx), nil
		}
	}

	return []*service.Message{msg}, nil
}

// ProcessBatch processes a batch of messages by applying Process to each message.
// It has been updated to match the expected signature: ProcessBatch(context.Context, service.MessageBatch) ([]service.MessageBatch, error)
func (d *decoder) ProcessBatch(ctx context.Context, batch service.MessageBatch) ([]service.MessageBatch, error) {
	var out service.MessageBatch
	for _, msg := range batch {
		processed, err := d.Process(ctx, msg)
		if err != nil {
			return nil, err
		}
		out = append(out, processed...)
	}
	// Return the processed messages as a single batch within a slice
	return []service.MessageBatch{out}, nil
}

// getSelector pulls and unmarshals a selector JSON entry from Valkey.
func (d *decoder) getSelector(ctx context.Context, key string, out *sigEntry) error {
	s, err := d.redis.Get(ctx, key).Result()
	if err != nil {
		return err
	}
	return json.Unmarshal([]byte(s), out)
}

// decodeCalldata decodes the calldata (hex string) using the provided signature entry.
// On success, it populates tx["decoded_call"] with a map containing the function name and parameters.
func (d *decoder) decodeCalldata(tx map[string]any, s sigEntry, calldataHex string) bool {
	if len(calldataHex) == 0 && len(s.Inputs) > 0 {
		return false
	}
	data, err := hexToBytes(calldataHex)
	if err != nil {
		return false
	}

	m := abi.NewMethod(s.Name, s.Name, abi.Function, "", false, false, s.Inputs, nil)
	decoded, err := m.Inputs.Unpack(data)
	if err != nil {
		return false
	}

	// Skip adding decoded_call if there are no inputs
	if len(s.Inputs) == 0 {
		return false
	}

	params := map[string]any{}
	for i, arg := range s.Inputs {
		params[arg.Name] = decoded[i]
	}
	tx["decoded_call"] = map[string]any{
		"function": s.Name,
		"params":   params,
	}
	return true
}

// wrap creates a new message with the modified structured body.
func wrap(orig *service.Message, body any) []*service.Message {
	out := orig.Copy()
	out.SetStructured(body)
	return []*service.Message{out}
}

// Close is a no-op for this processor and satisfies the BatchProcessor interface.
func (d *decoder) Close(ctx context.Context) error {
	return nil
}

// sigEntry represents the JSON object stored in Valkey
// containing the function signature and its inputs.
type sigEntry struct {
	Name   string         `json:"name"`
	Inputs []abi.Argument `json:"inputs"`
}

// getenvDefault retrieves the environment variable for the specified key or returns the default value.
func getenvDefault(key, def string) string {
	v := def
	if s, ok := syscall.Getenv(key); ok {
		v = s
	}
	return v
}

func init() {
	spec := service.NewConfigSpec().
		Summary("Fast EVM calldata decoder using selector cache")

	ctor := func(conf *service.ParsedConfig, res *service.Resources) (service.BatchProcessor, error) {
		addr := getenvDefault("VALKEY_ADDR", "valkey:6379")
		rds := redis.NewClient(&redis.Options{
			Addr: addr,
		})
		return &decoder{
			redis:   rds,
			chainID: res.Label(),
		}, nil
	}

	service.RegisterBatchProcessor("evm_decode_fast", spec, ctor)
}
