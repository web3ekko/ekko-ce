package main

import (
	"context"
	"encoding/json"
	"fmt"
	"testing"

	"github.com/benthosdev/benthos/v4/public/service"
	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/redis/go-redis/v9"
)

// fakeRedis simulates a Redis client by storing key/value pairs in memory.
type fakeRedis struct {
	data map[string]string
}

// Get returns a *redis.StringCmd using redis.NewStringResult from redis v9.
func (f *fakeRedis) Get(ctx context.Context, key string) *redis.StringCmd {
	if v, ok := f.data[key]; ok {
		return redis.NewStringResult(v, nil)
	}
	return redis.NewStringResult("", fmt.Errorf("key not found"))
}

func TestProcess_NoInput(t *testing.T) {
	// Test case: input field length < 10, so no processing should occur.
	testJSON := `{"input":"0x1", "to":"0xabc"}`
	msg := service.NewMessage([]byte(testJSON))
	var payload map[string]interface{}
	if err := json.Unmarshal([]byte(testJSON), &payload); err != nil {
		t.Fatal(err)
	}
	msg.SetStructured(payload)

	// Create a decoder with an empty fake Redis.
	d := &decoder{
		redis:   &fakeRedis{data: map[string]string{}},
		chainID: "1",
	}

	out, err := d.Process(context.Background(), msg)
	if err != nil {
		t.Fatal(err)
	}
	if len(out) != 1 {
		t.Fatalf("expected 1 message, got %d", len(out))
	}

	structured, err := out[0].AsStructured()
	if err != nil {
		t.Fatal(err)
	}
	result, ok := structured.(map[string]interface{})
	if !ok {
		t.Fatalf("expected payload to be map[string]interface{}, got %T", structured)
	}
	// Expect the payload to remain unchanged.
	if result["input"] != "0x1" {
		t.Errorf("expected input '0x1', got %v", result["input"])
	}
}

func TestProcess_WithValidSelector(t *testing.T) {
	// Test case: simulate a valid selector scenario.
	// Create a sigEntry with empty inputs for simplicity.
	sig := sigEntry{
		Name:   "transfer",
		Inputs: []abi.Argument{},
	}
	sigBytes, err := json.Marshal(sig)
	if err != nil {
		t.Fatal(err)
	}

	// Populate fake Redis with a key for the selector.
	fakeData := map[string]string{
		// For chainID "1", assume the selector is the first 10 characters of input (e.g., "0x12345678").
		"sel:1:0x12345678": string(sigBytes),
	}

	testJSON := `{"input":"0x1234567890abcdef", "to": "0xdeadbeef"}`
	msg := service.NewMessage([]byte(testJSON))
	var payload map[string]interface{}
	if err := json.Unmarshal([]byte(testJSON), &payload); err != nil {
		t.Fatal(err)
	}
	msg.SetStructured(payload)

	d := &decoder{
		redis:   &fakeRedis{data: fakeData},
		chainID: "1",
	}

	out, err := d.Process(context.Background(), msg)
	if err != nil {
		t.Fatal(err)
	}
	if len(out) != 1 {
		t.Fatalf("expected 1 message, got %d", len(out))
	}

	structured, err := out[0].AsStructured()
	if err != nil {
		t.Fatal(err)
	}
	result, ok := structured.(map[string]interface{})
	if !ok {
		t.Fatalf("expected payload to be map[string]interface{}, got %T", structured)
	}

	// For this test, decodeCalldata will return false because there are no inputs to decode,
	// so the "decoded_call" field should not exist.
	if _, exists := result["decoded_call"]; exists {
		t.Errorf("expected no decoded_call field, but found %v", result["decoded_call"])
	}
}
