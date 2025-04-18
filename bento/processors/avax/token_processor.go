package avax

import (
	"context"
	"fmt"

	"github.com/benthosdev/benthos/v4/public/service"
	"github.com/web3ekko/ekko-ce/bento/processors/common"
)

func init() {
	err := service.RegisterProcessor(
		"avax_token_transfer",
		service.NewConfigSpec().
			Summary("Analyzes Avalanche token transfers (ERC20/ERC721).").
			Field(service.NewStringField("network").
				Description("Avalanche network (C-Chain, X-Chain)").
				Default("c-chain")),
		func(conf *service.ParsedConfig) (service.Processor, error) {
			network, err := conf.FieldString("network")
			if err != nil {
				return nil, err
			}
			return newTokenProcessor(network), nil
		})
	if err != nil {
		panic(err)
	}
}

type tokenProcessor struct {
	network string
}

func newTokenProcessor(network string) *tokenProcessor {
	return &tokenProcessor{
		network: network,
	}
}

// Process implements the Benthos service.Processor interface
func (p *tokenProcessor) Process(ctx context.Context, msg *service.Message) (service.MessageBatch, error) {
	var tx common.Transaction
	if err := msg.UnmarshalJSON(&tx); err != nil {
		return nil, fmt.Errorf("failed to parse transaction: %v", err)
	}

	switch p.network {
	case "c-chain":
		return p.processCChain(tx)
	case "x-chain":
		return p.processXChain(tx)
	default:
		return service.MessageBatch{msg}, nil
	}
}

func (p *tokenProcessor) processCChain(tx common.Transaction) (service.MessageBatch, error) {
	// C-Chain uses EVM, so token transfers are similar to Ethereum
	if len(tx.Data) < 10 {
		return service.MessageBatch{service.NewMessage(nil)}, nil
	}

	methodID := tx.Data[:10]
	var tokenTransfer common.TokenTransfer

	switch methodID {
	case "0xa9059cbb": // ERC20 transfer
		tokenTransfer = p.processERC20Transfer(tx)
	case "0x23b872dd": // ERC20/ERC721 transferFrom
		tokenTransfer = p.processTransferFrom(tx)
	case "0x42842e0e": // ERC721 safeTransferFrom
		tokenTransfer = p.processERC721Transfer(tx)
	default:
		return service.MessageBatch{service.NewMessage(nil)}, nil
	}

	newMsg := service.NewMessage(nil)
	if err := newMsg.SetJSON(tokenTransfer); err != nil {
		return nil, fmt.Errorf("failed to serialize token transfer: %v", err)
	}

	return service.MessageBatch{newMsg}, nil
}

func (p *tokenProcessor) processXChain(tx common.Transaction) (service.MessageBatch, error) {
	// X-Chain uses different format for asset transfers
	tokenTransfer := common.TokenTransfer{
		Transaction:  tx,
		TokenType:   "AVAX-Native",
		TokenAmount: tx.Value,
	}

	newMsg := service.NewMessage(nil)
	if err := newMsg.SetJSON(tokenTransfer); err != nil {
		return nil, fmt.Errorf("failed to serialize token transfer: %v", err)
	}

	return service.MessageBatch{newMsg}, nil
}

func (p *tokenProcessor) processERC20Transfer(tx common.Transaction) common.TokenTransfer {
	data := tx.Data[10:] // Remove method ID
	if len(data) < 128 {
		return common.TokenTransfer{Transaction: tx}
	}

	to := "0x" + data[24:64]    // First parameter is padded address
	amount := "0x" + data[64:] // Second parameter is amount

	return common.TokenTransfer{
		Transaction:  tx,
		TokenAddress: tx.To,
		TokenType:   "ERC20",
		TokenAmount: amount,
	}
}

func (p *tokenProcessor) processTransferFrom(tx common.Transaction) common.TokenTransfer {
	data := tx.Data[10:] // Remove method ID
	if len(data) < 192 {
		return common.TokenTransfer{Transaction: tx}
	}

	from := "0x" + data[24:64]     // First parameter is padded address
	to := "0x" + data[88:128]      // Second parameter is padded address
	amount := "0x" + data[128:192] // Third parameter is amount/tokenId

	return common.TokenTransfer{
		Transaction:  tx,
		TokenAddress: tx.To,
		TokenType:   "ERC20/ERC721",
		TokenAmount: amount,
	}
}

func (p *tokenProcessor) processERC721Transfer(tx common.Transaction) common.TokenTransfer {
	data := tx.Data[10:] // Remove method ID
	if len(data) < 192 {
		return common.TokenTransfer{Transaction: tx}
	}

	from := "0x" + data[24:64]     // First parameter is padded address
	to := "0x" + data[88:128]      // Second parameter is padded address
	tokenId := "0x" + data[128:192] // Third parameter is tokenId

	return common.TokenTransfer{
		Transaction:  tx,
		TokenAddress: tx.To,
		TokenType:   "ERC721",
		TokenAmount: tokenId,
	}
}
