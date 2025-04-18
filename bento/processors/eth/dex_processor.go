package eth

import (
	"context"
	"fmt"

	"github.com/benthosdev/benthos/v4/public/service"
	"github.com/web3ekko/ekko-ce/bento/processors/common"
)

// Known DEX protocols and their method signatures
var (
	uniswapV2Methods = map[string]string{
		"0x38ed1739": "swapExactTokensForTokens",
		"0x7ff36ab5": "swapExactETHForTokens",
		"0x18cbafe5": "swapExactTokensForETH",
	}

	uniswapV3Methods = map[string]string{
		"0x5ae401dc": "multicall",
		"0xac9650d8": "exactInputSingle",
		"0xc04b8d59": "exactInput",
	}

	sushiswapMethods = map[string]string{
		"0x38ed1739": "swapExactTokensForTokens",
		"0x7ff36ab5": "swapExactETHForTokens",
	}
)

func init() {
	err := service.RegisterProcessor(
		"eth_dex_swap",
		service.NewConfigSpec().
			Summary("Analyzes Ethereum DEX swaps (Uniswap, Sushiswap)."),
		func(conf *service.ParsedConfig) (service.Processor, error) {
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

	// Check Uniswap V2
	if _, ok := uniswapV2Methods[methodID]; ok {
		swapEvent = p.processUniswapV2Swap(tx, methodID)
	}

	// Check Uniswap V3
	if _, ok := uniswapV3Methods[methodID]; ok {
		swapEvent = p.processUniswapV3Swap(tx, methodID)
	}

	// Check Sushiswap
	if _, ok := sushiswapMethods[methodID]; ok {
		swapEvent = p.processSushiswapSwap(tx, methodID)
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

func (p *dexProcessor) processUniswapV2Swap(tx common.Transaction, methodID string) common.SwapEvent {
	data := tx.Data[10:] // Remove method ID
	if len(data) < 256 { // Minimum length for swap parameters
		return common.SwapEvent{Transaction: tx}
	}

	// Parse parameters based on method
	swap := common.SwapEvent{
		Transaction: tx,
		Protocol:   "Uniswap V2",
	}

	switch methodID {
	case "0x38ed1739": // swapExactTokensForTokens
		// Parse amountIn, amountOutMin, path, to, deadline
		swap.AmountIn = "0x" + data[:64]
		swap.TokenIn = "0x" + data[154:194]  // First token in path
		swap.TokenOut = "0x" + data[218:258] // Last token in path
	case "0x7ff36ab5": // swapExactETHForTokens
		// Parse amountOutMin, path, to, deadline
		swap.TokenIn = "ETH"
		swap.AmountIn = tx.Value
		swap.TokenOut = "0x" + data[154:194] // First token in path
	case "0x18cbafe5": // swapExactTokensForETH
		// Parse amountIn, amountOutMin, path, to, deadline
		swap.AmountIn = "0x" + data[:64]
		swap.TokenIn = "0x" + data[154:194]  // First token in path
		swap.TokenOut = "ETH"
	}

	return swap
}

func (p *dexProcessor) processUniswapV3Swap(tx common.Transaction, methodID string) common.SwapEvent {
	data := tx.Data[10:] // Remove method ID
	
	swap := common.SwapEvent{
		Transaction: tx,
		Protocol:   "Uniswap V3",
	}

	switch methodID {
	case "0xac9650d8": // exactInputSingle
		if len(data) < 384 {
			return common.SwapEvent{Transaction: tx}
		}
		// Parse parameters: tokenIn, tokenOut, fee, recipient, amountIn, amountOutMinimum
		swap.TokenIn = "0x" + data[24:64]
		swap.TokenOut = "0x" + data[88:128]
		swap.AmountIn = "0x" + data[192:256]
	}

	return swap
}

func (p *dexProcessor) processSushiswapSwap(tx common.Transaction, methodID string) common.SwapEvent {
	// Similar to Uniswap V2 but with Sushiswap-specific logic
	swap := p.processUniswapV2Swap(tx, methodID)
	swap.Protocol = "Sushiswap"
	return swap
}
