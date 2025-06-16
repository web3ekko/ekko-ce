# DSPy Architecture for Ekko CE

## 🎯 **Correct DSPy Usage**

DSPy is used **ONLY** for converting natural language alert queries into structured job specifications with Polars code. It is **NOT** used for notification generation or delivery.

## 📋 **Alert Processing Flow**

```
1. User creates alert with natural language query
   ↓
2. DSPy converts query → Job Specification (Polars code)
   ↓
3. Job Specification stored with alert
   ↓
4. [FUTURE] External job runner executes job specs
   ↓
5. [FUTURE] If conditions met → Notification system sends alerts
```

## 🔧 **DSPy Components**

### **1. Job Specification Generator (`dspy_job_generator.py`)**

**Purpose:** Convert natural language → Polars code
**Input:** `"Alert when average swap value > 500 last 7d"`
**Output:** 
```json
{
  "job_name": "average_swap_alert",
  "schedule": "RRULE:FREQ=DAILY;INTERVAL=1",
  "time_window": "-7d..now",
  "sources": [
    {
      "type": "database",
      "handle": "swap_data", 
      "stream": "swaps",
      "subject": "values",
      "time_window": "-7d..now"
    }
  ],
  "polars_code": "import polars as pl\n\nresult = swap_data.filter(pl.col('value') > 500).select(pl.col('value').mean()).collect()"
}
```

### **2. DSPy Signatures**

#### **JobSpecGenerationSignature**
- **Input:** Natural language query
- **Output:** Complete JSON job specification
- **Validation:** Polars syntax checking

#### **PolarsSyntaxValidationSignature** 
- **Input:** Generated Polars code
- **Output:** Corrected code + issues found
- **Purpose:** Ensure valid Polars syntax

### **3. Background Task Integration**

**File:** `alert_job_utils.py`
**Function:** `generate_job_spec_from_alert()`
**Flow:**
1. Alert created with query
2. Background task calls DSPy generator
3. Job spec added to alert in KV store
4. Event published for job spec creation

## 🚫 **What DSPy Does NOT Handle**

- ❌ Notification message generation
- ❌ Notification delivery (email, Telegram, Discord)
- ❌ Notification routing logic
- ❌ Notification history tracking
- ❌ Apprise integration

## ✅ **Future Notification System**

**Status:** Alert processor removed - notifications will be handled by external job runner
**Future Responsibilities:**
1. Load notification destinations from settings
2. Create simple notification messages
3. Send to enabled destinations (via Apprise)
4. Store notification records for history
5. Publish NATS events

## 🔄 **Migration from OpenAI to DSPy**

### **Before (OpenAI Direct)**
```python
# akash_generator.py
response = client.chat.completions.create(
    model=model,
    messages=[{"role": "system", "content": SYSTEM_PROMPT}, 
              {"role": "user", "content": prompt}],
    temperature=0.1,
)
return response.choices[0].message.content
```

### **After (DSPy Structured)**
```python
# dspy_job_generator.py
class JobSpecGenerator(dspy.Module):
    def __init__(self):
        self.generate_spec = dspy.ChainOfThought(JobSpecGenerationSignature)
        self.validate_polars = dspy.ChainOfThought(PolarsSyntaxValidationSignature)
    
    def forward(self, query: str) -> dspy.Prediction:
        spec_result = self.generate_spec(query=enhanced_query)
        # Validation and error handling
        return validated_spec
```

## 🎯 **Benefits of DSPy Migration**

### **1. Structured Prompting**
- Clear input/output signatures
- Type-safe prompt engineering
- Modular prompt components

### **2. Better Error Handling**
- Automatic retry logic
- Structured validation
- Fallback mechanisms

### **3. Optimization Capabilities**
- Prompt optimization with DSPy
- Performance metrics
- A/B testing of prompts

### **4. Maintainability**
- Cleaner code organization
- Easier testing
- Better debugging

## 🧪 **Testing**

**File:** `test_dspy_generator.py`
**Purpose:** Validate DSPy job spec generation
**Tests:**
- Environment setup (API keys)
- Query conversion accuracy
- Polars syntax validation
- Backward compatibility

## 📝 **Configuration**

**Environment Variables:**
```bash
AKASH_API_KEY=your_api_key
AKASH_BASE_URL=https://chatapi.akash.network/api/v1
AKASH_MODEL=Meta-Llama-3-1-8B-Instruct-FP8
```

**DSPy Setup:**
```python
lm = dspy.OpenAI(
    api_key=AKASH_API_KEY,
    api_base=AKASH_BASE_URL,
    model=DEFAULT_MODEL,
    max_tokens=2048,
    temperature=0.1
)
dspy.settings.configure(lm=lm)
```

## 🚀 **Next Steps**

1. **Test DSPy generator** with various alert queries
2. **Optimize prompts** using DSPy's optimization features
3. **Add more validation** for generated Polars code
4. **Implement proper scheduling** for job spec execution
5. **Integrate Apprise** for actual notification delivery

## 📚 **Key Files**

- `dspy_job_generator.py` - Main DSPy implementation
- `alert_job_utils.py` - Integration with alert system
- `test_dspy_generator.py` - Testing suite
- `DSPy_Architecture.md` - This documentation

## 🗑️ **Removed Files**

- `alert_processor.py` - Removed background job processor

The DSPy system is now focused solely on its core strength: converting natural language into structured, executable Polars code for blockchain data analytics.
