package avax

import (
	"context"
	"fmt"

	"github.com/benthosdev/benthos/v4/public/service"
	"github.com/web3ekko/ekko-ce/bento/processors/common"
)

// Known Avalanche DEX protocols and their method signatures
var (
	traderJoeMethods = map[string]string{
		"0x38ed1739": "swapExactTokensForTokens",
		"0x7ff36ab5": "swapExactAVAXForTokens",
		"0x18cbafe5": "swapExactTokensForAVAX",
	}

	panglinMethods = map[string]string{
		"0x38ed1739": "swapExactTokensForTokens",
		"0x7ff36ab5": "swapExactAVAXForTokens",
	}

	// GMX method signatures
	gmxMethods = map[string]string{
		"0x6c65c8d1": "swap",
		"0x3c695d88": "increasePosition",
		"0x869d4921": "decreasePosition",
	}
)

func init() {
	err := service.RegisterProcessor(
		"avax_dex_swap",
		service.NewConfigSpec().
			Summary("Analyzes Avalanche DEX swaps (Trader Joe, Pangolin, GMX).").
			Field(service.NewStringField("network").
				Description("Avalanche network (C-Chain only)").
				Default("c-chain")),
		func(conf *service.ParsedConfig) (service.Processor, error) {
			network, err := conf.FieldString("network")
			if err != nil {
				return nil, err
			}
			if network != "c-chain" {
				return nil, fmt.Errorf("DEX swaps only supported on C-Chain")
			}
			return newDEXProcessor(), nil
		})
	if err != nil {
		panic(err)
	}
}

type dexProcessor struct{}

func newDEXProcessor() *dexProcessor {
	return &dexProcessor{}
}

// Process implements the Benthos service.Processor interface
func (p *dexProcessor) Process(ctx context.Context, msg *service.Message) (service.MessageBatch, error) {
	var tx common.Transaction
	if err := msg.UnmarshalJSON(&tx); err != nil {
		return nil, fmt.Errorf("failed to parse transaction: %v", err)
	}

	// Check if this is a DEX swap
	if len(tx.Data) < 10 {
		return service.MessageBatch{msg}, nil
	}

	methodID := tx.Data[:10]
	var swapEvent common.SwapEvent

	// Check Trader Joe
	if _, ok := traderJoeMethods[methodID]; ok {
		swapEvent = p.processTraderJoeSwap(tx, methodID)
	}

	// Check Pangolin
	if _, ok := panglinMethods[methodID]; ok {
		swapEvent = p.processPangolinSwap(tx, methodID)
	}

	// Check GMX
	if _, ok := gmxMethods[methodID]; ok {
		swapEvent = p.processGMXSwap(tx, methodID)
	}

	// If no swap was detected, return original message
	if swapEvent.Protocol == "" {
		return service.MessageBatch{msg}, nil
	}

	newMsg := service.NewMessage(nil)
	if err := newMsg.SetJSON(swapEvent); err != nil {
		return nil, fmt.Errorf("failed to serialize swap event: %v", err)
	}

	return service.MessageBatch{newMsg}, nil
}

func (p *dexProcessor) processTraderJoeSwap(tx common.Transaction, methodID string) common.SwapEvent {
	data := tx.Data[10:] // Remove method ID
	if len(data) < 256 { // Minimum length for swap parameters
		return common.SwapEvent{Transaction: tx}
	}

	swap := common.SwapEvent{
		Transaction: tx,
		Protocol:   "Trader Joe",
	}

	switch methodID {
	case "0x38ed1739": // swapExactTokensForTokens
		swap.AmountIn = "0x" + data[:64]
		swap.TokenIn = "0x" + data[154:194]  // First token in path
		swap.TokenOut = "0x" + data[218:258] // Last token in path
	case "0x7ff36ab5": // swapExactAVAXForTokens
		swap.TokenIn = "AVAX"
		swap.AmountIn = tx.Value
		swap.TokenOut = "0x" + data[154:194] // First token in path
	case "0x18cbafe5": // swapExactTokensForAVAX
		swap.AmountIn = "0x" + data[:64]
		swap.TokenIn = "0x" + data[154:194] // First token in path
		swap.TokenOut = "AVAX"
	}

	return swap
}

func (p *dexProcessor) processPangolinSwap(tx common.Transaction, methodID string) common.SwapEvent {
	// Pangolin uses same interface as Trader Joe
	swap := p.processTraderJoeSwap(tx, methodID)
	swap.Protocol = "Pangolin"
	return swap
}

func (p *dexProcessor) processGMXSwap(tx common.Transaction, methodID string) common.SwapEvent {
	data := tx.Data[10:] // Remove method ID

	swap := common.SwapEvent{
		Transaction: tx,
		Protocol:   "GMX",
	}

	switch methodID {
	case "0x6c65c8d1": // swap
		if len(data) < 320 {
			return common.SwapEvent{Transaction: tx}
		}
		// Parse parameters: tokenIn, tokenOut, amount
		swap.TokenIn = "0x" + data[24:64]
		swap.TokenOut = "0x" + data[88:128]
		swap.AmountIn = "0x" + data[128:192]
	case "0x3c695d88": // increasePosition
		swap.EventType = "IncreasePosition"
	case "0x869d4921": // decreasePosition
		swap.EventType = "DecreasePosition"
	}

	return swap
}
