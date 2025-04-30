package decoder

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/ethereum/go-ethereum/accounts/abi"
)

// TemplateManager manages transaction decoding templates
type TemplateManager struct {
	redis RedisClient
}

// NewTemplateManager creates a new template manager
func NewTemplateManager(redis RedisClient) *TemplateManager {
	return &TemplateManager{
		redis: redis,
	}
}

// GetTemplate retrieves a template by name
func (tm *TemplateManager) GetTemplate(ctx context.Context, name string) (*Template, error) {
	key := getRedisKey("template", name)
	data, err := tm.redis.Get(ctx, key).Result()
	if err != nil {
		return nil, fmt.Errorf("redis get failed: %w", err)
	}

	var template Template
	if err := json.Unmarshal([]byte(data), &template); err != nil {
		return nil, fmt.Errorf("unmarshal failed: %w", err)
	}

	// Parse ABI for each method
	parsed, err := abi.JSON(strings.NewReader(template.ABI))
	if err != nil {
		return nil, fmt.Errorf("abi parse failed: %w", err)
	}

	// Store parsed methods
	template.Methods = make([]abi.Method, 0)
	for _, method := range parsed.Methods {
		template.Methods = append(template.Methods, method)
	}

	return &template, nil
}

// SaveTemplate saves a template to Redis
func (tm *TemplateManager) SaveTemplate(ctx context.Context, template *Template) error {
	key := getRedisKey("template", template.Name)
	data, err := json.Marshal(template)
	if err != nil {
		return fmt.Errorf("marshal failed: %w", err)
	}

	if err := tm.redis.Set(ctx, key, data, 24*time.Hour).Err(); err != nil {
		return fmt.Errorf("redis set failed: %w", err)
	}

	return nil
}

// ApplyTemplate applies a template's filters to a transaction
func (tm *TemplateManager) ApplyTemplate(tx map[string]interface{}, template *Template) bool {
	for _, filter := range template.Filters {
		if !applyFilter(tx, filter) {
			return false
		}
	}
	return true
}

func applyFilter(tx map[string]interface{}, filter FilterRule) bool {
	value, ok := tx[filter.Field]
	if !ok {
		// If field doesn't exist and we're checking for inequality, return true
		return filter.Operator == "neq"
	}

	switch filter.Operator {
	case "eq":
		return fmt.Sprint(value) == filter.Value
	case "neq":
		return fmt.Sprint(value) != filter.Value
	case "contains":
		return strings.Contains(fmt.Sprint(value), filter.Value)
	case "gt", "lt":
		// Handle numeric comparisons
		v1, ok1 := value.(float64)
		v2, ok2 := strconv.ParseFloat(filter.Value, 64)
		if !ok1 || ok2 != nil {
			return false
		}
		if filter.Operator == "gt" {
			return v1 > v2
		}
		return v1 < v2
	default:
		return false
	}
}
