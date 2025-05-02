package decoder

import (
	"context"
	"testing"

	"github.com/web3ekko/ekko-ce/pipeline/internal/blockchain"
)

func TestDecode_WalletToWallet(t *testing.T) {
	d := NewDecoder(NewMemoryCache(), "testchain")
	tx := &blockchain.Transaction{
		Hash:  "0x1",
		From:  "0xfrom",
		To:    "0xto",
		Value: "123",
		Input: "0x",
	}
	err := d.DecodeTransaction(context.Background(), tx)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if tx.DecodedCall == nil {
		t.Fatal("Expected DecodedCall not nil for wallet-to-wallet transfer")
	}
	if tx.DecodedCall.Function != "transfer" {
		t.Errorf("expected Function 'transfer', got '%s'", tx.DecodedCall.Function)
	}
	params := tx.DecodedCall.Params
	if params["from"] != tx.From {
		t.Errorf("expected from '%s', got '%v'", tx.From, params["from"])
	}
	if params["to"] != tx.To {
		t.Errorf("expected to '%s', got '%v'", tx.To, params["to"])
	}
	if params["value"] != tx.Value {
		t.Errorf("expected value '%s', got '%v'", tx.Value, params["value"])
	}
}

func TestDecode_ContractCreation(t *testing.T) {
	d := NewDecoder(NewMemoryCache(), "testchain")
	initCode := "0x6001600101"
	tx := &blockchain.Transaction{
		Hash:  "0x2",
		From:  "0xfrom",
		To:    "",
		Value: "0",
		Input: initCode,
	}
	err := d.DecodeTransaction(context.Background(), tx)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if tx.DecodedCall == nil {
		t.Fatal("Expected DecodedCall not nil for contract creation")
	}
	if tx.DecodedCall.Function != "contract_creation" {
		t.Errorf("expected Function 'contract_creation', got '%s'", tx.DecodedCall.Function)
	}
	params := tx.DecodedCall.Params
	if params["from"] != tx.From {
		t.Errorf("expected from '%s', got '%v'", tx.From, params["from"])
	}
	if params["value"] != tx.Value {
		t.Errorf("expected value '%s', got '%v'", tx.Value, params["value"])
	}
	if params["init_code"] != tx.Input {
		t.Errorf("expected init_code '%s', got '%v'", tx.Input, params["init_code"])
	}
}
