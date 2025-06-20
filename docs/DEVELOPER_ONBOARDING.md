# 🚀 Ekko CE - Developer Onboarding Guide

## 👋 **WELCOME TO EKKO CE!**

This guide will get you up and running with the Ekko CE blockchain monitoring platform in under 30 minutes.

## 🎯 **WHAT IS EKKO CE?**

Ekko CE is a **Community Edition** blockchain monitoring and alerting platform that:
- 📊 **Monitors** wallet balances and transactions
- 🚨 **Alerts** on custom conditions using natural language
- 🔄 **Processes** real-time blockchain data
- 📈 **Analyzes** DeFi activities and price movements

## 🏗️ **ARCHITECTURE OVERVIEW**

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Dashboard  │───▶│ API Service │───▶│   DuckDB    │
│  (React)    │    │ (FastAPI)   │    │ (Analytics) │
└─────────────┘    └─────────────┘    └─────────────┘
                           │
                           ▼
                   ┌─────────────┐    ┌─────────────┐
                   │    NATS     │───▶│    MinIO    │
                   │ (Messaging) │    │ (Storage)   │
                   └─────────────┘    └─────────────┘
                           │
                           ▼
                   ┌─────────────┐    ┌─────────────┐
                   │  Pipeline   │    │Alert Executor│
                   │ (Data Fetch)│    │ (Background) │
                   └─────────────┘    └─────────────┘
```

---

## 🛠️ **QUICK START (5 MINUTES)**

### **1. Prerequisites**
```bash
# Required
- Docker & Docker Compose
- Git
- 8GB+ RAM
- 10GB+ disk space

# Optional (for local development)
- Python 3.11+
- Node.js 18+
- Rust 1.75+ (for future Rust services)
```

### **2. Clone & Start**
```bash
# Clone repository
git clone <repository-url>
cd ekko-ce

# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

### **3. Access Services**
```bash
# Dashboard (Frontend)
http://localhost:3000

# API Documentation
http://localhost:8000/docs

# MinIO Console
http://localhost:9001
# Login: minioadmin / minioadmin
```

### **4. Test the System**
```bash
# Health check
curl http://localhost:8000/

# Create a test wallet
curl -X POST "http://localhost:8000/wallets" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Wallet",
    "address": "0x1234567890abcdef1234567890abcdef12345678",
    "network": "avalanche"
  }'

# Test alert executor
curl -X POST "http://localhost:8000/alerts/test-execution"
```

---

## 📁 **PROJECT STRUCTURE**

```
ekko-ce/
├── api/                    # FastAPI backend service
│   ├── app/
│   │   ├── main.py        # Main application
│   │   ├── models.py      # Data models
│   │   ├── alert_executor.py  # Alert processing
│   │   └── ...
│   ├── requirements.txt   # Python dependencies
│   └── Dockerfile
├── dashboard/             # React frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   └── ...
│   ├── package.json       # Node dependencies
│   └── Dockerfile
├── pipeline/              # Data fetching service
│   ├── src/
│   │   ├── main.py       # Pipeline orchestrator
│   │   ├── fetchers/     # Blockchain fetchers
│   │   └── ...
│   └── requirements.txt
├── docs/                  # Documentation
│   ├── SERVICE_SPECIFICATIONS.md
│   ├── API_REFERENCE.md
│   └── ...
├── docker-compose.yml     # Service orchestration
└── README.md
```

---

## 🔧 **DEVELOPMENT WORKFLOW**

### **1. Making Changes**

#### **Backend (API) Changes:**
```bash
# Edit files in api/app/
vim api/app/main.py

# Rebuild and restart
docker-compose build api
docker-compose restart api

# View logs
docker-compose logs -f api
```

#### **Frontend (Dashboard) Changes:**
```bash
# Edit files in dashboard/src/
vim dashboard/src/components/WalletList.tsx

# Rebuild and restart (with hot reload)
docker-compose build dashboard
docker-compose restart dashboard
```

#### **Pipeline Changes:**
```bash
# Edit files in pipeline/src/
vim pipeline/src/fetchers/avalanche_fetcher.py

# Rebuild and restart
docker-compose build pipeline
docker-compose restart pipeline
```

### **2. Adding Dependencies**

#### **Python (API/Pipeline):**
```bash
# Add to requirements.txt
echo "new-package==1.0.0" >> api/requirements.txt

# Rebuild container
docker-compose build api
```

#### **Node.js (Dashboard):**
```bash
# Add to package.json or use yarn
cd dashboard
yarn add new-package

# Rebuild container
docker-compose build dashboard
```

### **3. Database Changes**
```bash
# Connect to DuckDB (via API container)
docker exec -it ekko-ce-api-1 python3 -c "
import duckdb
conn = duckdb.connect('/app/data/ekko.db')
conn.execute('SHOW TABLES').fetchall()
"

# Or use DuckDB CLI
docker exec -it ekko-ce-api-1 duckdb /app/data/ekko.db
```

---

## 🧪 **TESTING**

### **1. Unit Tests**
```bash
# API tests
docker exec -it ekko-ce-api-1 python3 -m pytest tests/

# Dashboard tests
docker exec -it ekko-ce-dashboard-1 yarn test
```

### **2. Integration Tests**
```bash
# Test API endpoints
curl -X GET "http://localhost:8000/wallets"
curl -X GET "http://localhost:8000/alerts/executor/stats"

# Test NATS messaging
docker exec -it nats nats pub test.subject "Hello World"
docker exec -it nats nats sub test.subject
```

### **3. Load Testing**
```bash
# Install hey (HTTP load testing)
go install github.com/rakyll/hey@latest

# Test API performance
hey -n 1000 -c 10 http://localhost:8000/wallets
```

---

## 🐛 **DEBUGGING**

### **1. View Logs**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f dashboard
docker-compose logs -f pipeline

# Last N lines
docker-compose logs --tail=50 api
```

### **2. Connect to Containers**
```bash
# API container
docker exec -it ekko-ce-api-1 bash

# Dashboard container
docker exec -it ekko-ce-dashboard-1 sh

# NATS container
docker exec -it nats sh
```

### **3. Check Service Health**
```bash
# API health
curl http://localhost:8000/

# Database status
curl http://localhost:8000/database/status

# NATS status
docker exec -it nats nats server info
```

### **4. Common Issues**

#### **Port Conflicts:**
```bash
# Check what's using ports
lsof -i :8000  # API
lsof -i :3000  # Dashboard
lsof -i :4222  # NATS

# Stop conflicting services
sudo kill -9 <PID>
```

#### **Database Issues:**
```bash
# Reset database
docker-compose down
docker volume rm ekko-ce_api_data
docker-compose up -d
```

#### **NATS Connection Issues:**
```bash
# Check NATS logs
docker-compose logs nats

# Test NATS connectivity
docker exec -it nats nats server ping
```

---

## 📚 **KEY CONCEPTS**

### **1. Data Flow**
1. **Pipeline** fetches blockchain data from RPC nodes
2. **NATS** routes messages between services
3. **Transactions Writer** stores data in MinIO (Delta Lake format)
4. **API** serves data from DuckDB to Dashboard
5. **Alert Executor** processes alert queries using Polars

### **2. Alert System**
1. User creates alert in **natural language**
2. **DSPy** infers parameters and generates **Polars DSL**
3. **Alert Executor** runs DSL against data sources
4. Results trigger **notifications** if conditions are met

### **3. Storage Architecture**
- **DuckDB**: Fast analytics queries, API responses
- **MinIO**: Long-term storage, Delta Lake tables
- **NATS KV**: Configuration, real-time state
- **Redis**: Caching, session storage

---

## 🎯 **COMMON TASKS**

### **1. Add New API Endpoint**
```python
# In api/app/main.py
@app.get("/my-new-endpoint")
async def my_new_endpoint():
    return {"message": "Hello World"}
```

### **2. Add New React Component**
```typescript
// In dashboard/src/components/MyComponent.tsx
import React from 'react';

export const MyComponent: React.FC = () => {
  return <div>My Component</div>;
};
```

### **3. Add New NATS Subject**
```python
# Publisher (in any service)
await nc.publish("my.new.subject", json.dumps(data).encode())

# Consumer (in any service)
async def handle_message(msg):
    data = json.loads(msg.data.decode())
    # Process data

await nc.subscribe("my.new.subject", cb=handle_message)
```

### **4. Add New Database Table**
```python
# In api/app/startup.py
conn.execute("""
    CREATE TABLE IF NOT EXISTS my_table (
        id UUID PRIMARY KEY,
        name VARCHAR NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
```

---

## 🚀 **NEXT STEPS**

### **📖 Read the Documentation:**
- [Service Specifications](./SERVICE_SPECIFICATIONS.md)
- [API Reference](./API_REFERENCE.md)
- [NATS Subjects Reference](./NATS_SUBJECTS_REFERENCE.md)

### **🛠️ Start Contributing:**
1. Pick an issue from the backlog
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### **💬 Get Help:**
- Check existing documentation
- Look at similar implementations in the codebase
- Ask questions in team chat
- Review code with senior developers

---

## 🎉 **WELCOME TO THE TEAM!**

You're now ready to contribute to Ekko CE! The platform is designed to be developer-friendly with clear separation of concerns, comprehensive documentation, and modern tooling.

**Happy coding!** 🚀
